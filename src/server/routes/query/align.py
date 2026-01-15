"""Module for aligning sequence items and creating MSA."""

from dataclasses import dataclass
from typing import Any

from retromol.chem.fingerprint import calculate_tanimoto_similarity

from versalign.aligner import Aligner, setup_aligner
from versalign.scoring import create_substitution_matrix_dynamically
from versalign.docking import DockingResult, dock_against_target

from routes.query.seq import (
    DISPLAY_NAME_UNIDENTIFIED,
    SequenceItem,
    Gap,
    NonGap,
    SequenceItemReadout,
)


@dataclass(frozen=True)
class MSAResult:
    """
    Data structure representing the MSA result of a query.
    """
    def to_dict(self) -> dict[str, Any]:
        """
        Convert the MSAResult to a dictionary.
        
        :return: a dictionary representation of the MSAResult
        """
        return {
            "msa": [],
        }
    

def item_compare_fn(a: SequenceItem, b:  SequenceItem) -> float:
    """
    Compare two SequenceItems or Gaps for sorting.
    """
    # Deal with gaps first
    if isinstance(a, Gap) or isinstance(b, Gap):
        return 0.0
    
    # Both items are non-gaps at this point
    if isinstance(a, NonGap) and isinstance(b, NonGap):
        if a.morgan_fp is not None and b.morgan_fp is not None:
            return calculate_tanimoto_similarity(a.morgan_fp, b.morgan_fp)
        
        if a.display_name == DISPLAY_NAME_UNIDENTIFIED or b.display_name == DISPLAY_NAME_UNIDENTIFIED:
            return 0.0  # could be correct, but we don't know
        
        if a.display_name == b.display_name:  # NOTE: this is a display name, not unique
            return 1.0

    return -2.0


def item_label_fn(item: SequenceItem) -> str:
    """
    Generate a label for a SequenceItem or Gap.

    :param item: SequenceItem or Gap
    :return: label string
    """
    return str(hash(item))


def _setup_aligner(
    readout1: SequenceItemReadout,
    readout2: SequenceItemReadout,
) -> Aligner:
    """
    Setup an Aligner for two SequenceItemReadouts.

    :param readout1: first SequenceItemReadout
    :param readout2: second SequenceItemReadout
    :return: configured Aligner
    """
    readout1_items = readout1.flatten_items()
    readout2_items = readout2.flatten_items()
    unique_items = list(set(readout1_items + readout2_items + [Gap()]))
    sm, _ = create_substitution_matrix_dynamically(
        unique_items,
        compare=item_compare_fn,
        label_fn=item_label_fn
    )

    aligner = setup_aligner(
        sm,
        "global",
        target_internal_open_gap_score=-5.0,
        target_left_open_gap_score=-2.5,
        target_right_open_gap_score=-2.5,
        query_internal_open_gap_score=-5.0,
        query_left_open_gap_score=-2.5,
        query_right_open_gap_score=-2.5,
        label_fn=item_label_fn,
    )

    return aligner


def score_by_alignment(
    query: SequenceItemReadout,
    items: list[SequenceItemReadout]
) -> tuple[list[DockingResult], list[float]]:
    """
    Rerank nearest neighbors based on more accurate scoring.

    :param query: SequenceItemReadout of the query item
    :param items: list of SequenceItemReadouts to be scored against the query
    :return: tuple of list of DockingResults and their corresponding scores
    """
    aln_results = []
    aln_scores: list[float] = []

    for item in items:
        aligner = _setup_aligner(query, item)
        
        aln: DockingResult = dock_against_target(
            aligner=aligner,
            target=query.flatten_items(),
            candidates=item.blocks,
            gap_repr=Gap.alignment_representation(),
            allow_block_reverse=True,
            strategy="nonoverlap",
        )

        aln_results.append(aln)
        aln_scores.append(aln.total_score)

    return aln_results, aln_scores
