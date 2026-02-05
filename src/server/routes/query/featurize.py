"""Featurization utilities for query items."""

from typing import Any, Literal

from retromol.model.result import Result
from retromol.model.reaction_graph import MolNode
from retromol.model.rules import RuleSet
from retromol.fingerprint.fingerprint import FingerprintGenerator

from biocracker.query.modules import LinearReadout

from routes.query.seq import NonGap, SequenceItemReadout


RULESET = RuleSet.load_default()
GENERATOR = FingerprintGenerator(RULESET.matching_rules)

FP_COUNTED = True
FP_SIZE = 1024


def calculate_payload_fingerprint(
    payload_type: Literal["cluster", "compound"],
    payload: Result | LinearReadout,
) -> list[float]:
    """
    Calculate the fingerprint for the given payload based on its type.

    :param payload_type: the type of the payload ("cluster" or "compound")
    :param payload: the payload object (Result or LinearReadout)
    :return: the calculated fingerprint as a sequence of floats
    :raises ValueError: if the payload_type is unsupported
    :raises AssertionError: if the payload type does not match the expected class
    """
    match payload_type:
        case "cluster":
            assert isinstance(payload, LinearReadout), f"expected LinearReadout payload, got {type(payload)}"
            fp = GENERATOR.fingerprint_from_biocracker_readout(payload, by_orf=False, num_bits=FP_SIZE, counted=FP_COUNTED)
        case "compound":
            assert isinstance(payload, Result), f"expected Result payload, got {type(payload)}"
            fp = GENERATOR.fingerprint_from_result(payload, num_bits=FP_SIZE, counted=FP_COUNTED)
        case _:
            raise ValueError(f"unsupported payload_type: {payload_type}")

    return fp


def _format_readout_compound(
    payload: Result,
    fragment: bool = False,
    payload_db_id: int | None = None,
) -> SequenceItemReadout:
    """
    Format the readout for a compound payload.

    :param payload: the compound payload object (Result)
    :param fragment: whether to treat each node as a separate fragment
    :param payload_db_id: optional database identifier for the payload
    :return: the formatted readout as a sequence of sequences of SequenceItem
    """
    linear_readouts: list[list[MolNode]] = payload.linear_readout.paths

    if fragment:
        # Flatten linear_readouts
        linear_readouts = [[node] for path in linear_readouts for node in path]

    formatted_blocks = []
    for path in linear_readouts:
        formatted_block = [NonGap.from_retromol_molnode(n) for n in path]
        formatted_blocks.append(formatted_block)

    return SequenceItemReadout(
        kind="compound",
        db_id=payload_db_id,
        block_ids=[f"structural readout {i+1}" for i in range(len(formatted_blocks))],
        blocks=formatted_blocks,
    )


def _format_readout_cluster(
    payload: LinearReadout,
    payload_db_id: int | None = None,
) -> SequenceItemReadout:
    """
    Format the readout for a cluster payload.

    :param payload: the cluster payload object (LinearReadout)
    :param payload_db_id: optional database identifier for the payload
    :return: the formatted readout as a sequence of sequences of SequenceItem
    """
    block_ids = []
    formatted_blocks = []
    for orf_name, orf in payload.biosynthetic_order(by_orf=True):
        formatted_block = [NonGap.from_biocracker_module(m) for m in orf]
        block_ids.append(f"ORF {orf_name}")
        formatted_blocks.append(formatted_block)

    # Process found modifiers into individual blocks
    for modifier in payload.modifiers:  
        block_ids.append(modifier)
        formatted_block = [NonGap.from_biocracker_modifier(modifier)]
        formatted_blocks.append(formatted_block)

    return SequenceItemReadout(
        kind="cluster",
        db_id=payload_db_id,
        block_ids=block_ids,
        blocks=formatted_blocks,
    )


def format_payload_readout(
    payload_type: Literal["cluster", "compound"],
    payload: Result | LinearReadout,
    payload_db_id: int | None = None,
) -> SequenceItemReadout:
    """
    Format the readout for the given payload based on its type.

    :param payload_type: the type of the payload ("cluster" or "compound")
    :param payload: the payload object (Result or LinearReadout)
    :param payload_db_id: optional database identifier for the payload
    :return: the formatted readout as a sequence of sequences of SequenceItem
    :raises ValueError: if the payload_type is unsupported
    :raises AssertionError: if the payload type does not match the expected class
    """
    match payload_type:
        case "cluster":
            assert isinstance(payload, LinearReadout), f"expected LinearReadout payload, got {type(payload)}"
            query_seq = _format_readout_cluster(payload, payload_db_id)
        case "compound":
            assert isinstance(payload, Result), f"expected Result payload, got {type(payload)}"
            query_seq = _format_readout_compound(payload, fragment=False, payload_db_id=payload_db_id)
        case _:
            raise ValueError(f"unsupported payload_type: {payload_type}")

    return query_seq


def load_payload(
    payload_type: Literal["cluster", "compound"],
    payload_blob: dict[str, Any],
) -> Result | LinearReadout:
    """
    Load the payload object from its blob representation based on its type.

    :param payload_type: the type of the payload ("cluster" or "compound")
    :param payload_blob: the payload data as a dictionary
    :return: the loaded payload object (Result or LinearReadout)
    :raises ValueError: if the payload_type is unsupported
    """
    match payload_type:
        case "cluster":
            payload = LinearReadout.from_dict(payload_blob)
        case "compound":
            payload = Result.from_dict(payload_blob)
        case _:
            raise ValueError(f"unsupported payload_type: {payload_type}")

    return payload


def featurize_item(
    payload_type: Literal["cluster", "compound"],
    payload_blob: dict[str, Any],
) -> tuple[list[float], SequenceItemReadout]:
    """
    Featurize the given payload based on its type.

    :param payload_type: the type of the payload ("cluster" or "compound")
    :param payload_blob: the payload data as a dictionary
    :return: a tuple containing the feature vector and query blocks
    :raises ValueError: if the payload_type is unsupported
    """
    payload = load_payload(payload_type, payload_blob)
    query_vec = calculate_payload_fingerprint(payload_type, payload)
    query_seq = format_payload_readout(payload_type, payload)

    return query_vec, query_seq
