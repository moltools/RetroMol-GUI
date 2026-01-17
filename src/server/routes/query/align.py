"""Module for aligning sequence items and creating MSA."""

from dataclasses import dataclass, field, asdict
from typing import Any, Callable

from retromol.chem.fingerprint import calculate_tanimoto_similarity

from versalign.aligner import Aligner, setup_aligner
from versalign.scoring import create_substitution_matrix_dynamically
from versalign.docking import DockingResult, dock_against_target

from bionexus.db.models import CandidateCluster, Compound, Reference

from routes.database import SessionLocal
from routes.query.retrieve import get_references
from routes.query.seq import (
    DISPLAY_NAME_UNIDENTIFIED,
    SequenceItem,
    Gap,
    NonGap,
    SequenceItemReadout,
)
from helpers.guid import generate_guid


@dataclass(frozen=True)
class MSAItemToken:
    """
    A single aligned position rendered for the frontend.

    :var isGap: whether this token represents a gap
    :var name: display name of the item
    :var smiles: optional SMILES representation
    :var id: unique identifier
    """

    isGap: bool
    name: str
    smiles: str | None = None
    id: str = field(default_factory=generate_guid)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the MSAItemToken to a dictionary.

        :return: a dictionary representation of the MSAItemToken
        """
        return asdict(self)


@dataclass(frozen=True)
class MSASequenceBlock:
    """
    A contiguous block (owned by one block_idx) shown as a subsequence in the UI.

    :var name: name of the block
    :var sequence: list of MSAItemTokens in this block
    :var id: unique identifier
    """

    name: str
    sequence: list[MSAItemToken]
    id: str = field(default_factory=generate_guid)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the MSASequenceBlock to a dictionary.

        :return: a dictionary representation of the MSASequenceBlock
        """
        return {
            "name": self.name,
            "sequence": [token.to_dict() for token in self.sequence],
            "id": self.id,
        }


@dataclass(frozen=True)
class RowReference:
    """
    Reference to the original database entry for a given MSA row.

    :var name: name of the entry
    :var database_name: name of the database
    :var database_identifier: unique identifier in the database
    """

    name: str
    database_name: str
    database_identifier: str

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the RowReference to a dictionary.

        :return: a dictionary representation of the RowReference
        """
        return asdict(self)
    
    @classmethod
    def from_reference(cls, reference: Reference) -> "RowReference":
        """
        Create a RowReference from a Reference object.

        :param reference: Reference object
        :return: constructed RowReference
        """
        return cls(
            name=reference.name,
            database_name=reference.database_name,
            database_identifier=reference.database_identifier,
        )


@dataclass(frozen=True)
class MSARow:
    """
    One row in the MSA: Query or a retrieved result.

    :var name: name of the row
    :var sequence: list of MSASequenceBlocks in the row
    :var references: list of RowReferences for this row
    :var alignment_score: optional alignment score
    :var cosine_score: optional cosine similarity score
    :var id: unique identifier
    """

    name: str
    sequence: list[MSASequenceBlock] = field(default_factory=list)
    references: list[RowReference] = field(default_factory=list)

    alignment_score: float | None = None
    cosine_score: float | None = None
    id: str = field(default_factory=generate_guid)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the MSARow to a dictionary.

        :return: a dictionary representation of the MSARow
        """
        return {
            "name": self.name,
            "sequence": [block.to_dict() for block in self.sequence],
            "references": [ref.to_dict() for ref in self.references],
            "alignment_score": self.alignment_score,
            "cosine_score": self.cosine_score,
            "id": self.id,
        }


@dataclass(frozen=True)
class MSAResult:
    """
    Top-level payload that API returns {"msa": [...]}.
    """

    msa: list[MSARow] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the MSAResult to a dictionary.
        
        :return: a dictionary representation of the MSAResult
        """
        return {"msa": [row.to_dict() for row in self.msa]}
    
    @classmethod
    def from_alignment(
        cls,
        # Aligned token rows; row[0] is target/query
        rows: list[list[str]],
        # Per-row ownership of each global col -> block_idx or None
        block_maps: list[list[int | None]],
        # Readouts for each row in the SAME ORDER as rows
        # rows[0] is query_readout, rows[1:] correspond to retrieved_readouts
        query_readout: SequenceItemReadout,
        retrieved_readouts: list[SequenceItemReadout],
        retrieved_items: list[Compound | CandidateCluster],
        retrieved_alignment_scores: list[float],
        retrieved_cosine_scores: list[float],
        # How to label items consistently with the tokens used in rows
        label_fn: Callable[[Any], str],
        gap_repr: str,
        display_name_unidentified: str,
        gap_display_name: str,
    ) -> "MSAResult":
        """
        Create an MSAResult from alignment data.

        :param rows: aligned token rows; row[0] is target/query
        :param block_maps: per-row ownership of each global col -> block_idx or None
        :param query_readout: SequenceItemReadout for the query row
        :param retrieved_readouts: list of SequenceItemReadouts for retrieved rows
        :param retrieved_items: list of retrieved Compound or CandidateCluster items
        :param retrieved_alignment_scores: list of alignment scores for retrieved rows
        :param retrieved_cosine_scores: list of cosine similarity scores for retrieved rows
        :param label_fn: function to label items consistently with the tokens used in rows
        :param gap_repr: string representation used for gaps in the alignment
        :param display_name_unidentified: display name for unidentified items
        :param gap_display_name: display name for gaps
        :return: constructed MSAResult
        """
        if not rows:
            return cls()

        result = cls()

        # Query row: split into original blocks for display
        q_map = {label_fn(it): it for it in query_readout.flatten_items()}

        block_order = sorted(
            range(len(query_readout.blocks)),
            key=lambda i: len(query_readout.blocks[i]),
            reverse=True,
        )
        target_block_indices = [
            bidx for bidx in block_order for _ in query_readout.blocks[bidx]
        ]

        query_blocks: list[MSASequenceBlock] = []
        current_bidx: int | None = None
        current_tokens: list[MSAItemToken] = []
        current_name: str | None = None

        target_pos = -1
        last_block_idx: int | None = None
        first_block_idx: int | None = target_block_indices[0] if target_block_indices else None

        for tok in rows[0]:
            if tok != gap_repr:
                target_pos += 1
                bidx = target_block_indices[target_pos]
                last_block_idx = bidx
            else:
                bidx = last_block_idx if last_block_idx is not None else first_block_idx

            if bidx != current_bidx:
                if current_tokens:
                    query_blocks.append(MSASequenceBlock(
                        name=current_name or "alignment gap",
                        sequence=current_tokens,
                    ))
                current_bidx = bidx
                current_name = query_readout.block_ids[bidx] if bidx is not None else "alignment gap"
                current_tokens = []

            if tok == gap_repr:
                current_tokens.append(MSAItemToken(isGap=True, name=gap_display_name))
            else:
                obj = q_map.get(tok)
                current_tokens.append(MSAItemToken(
                    isGap=False,
                    name=(obj.display_name if obj is not None else display_name_unidentified),
                ))

        if current_tokens:
            query_blocks.append(MSASequenceBlock(
                name=current_name or "alignment gap",
                sequence=current_tokens,
            ))

        query_row = MSARow(
            name="Query",
            alignment_score=None,
            cosine_score=None,
            sequence=query_blocks,
            references=[],
        )
        result.msa.append(query_row)

        # Retrieved rows
        if len(rows) != len(block_maps):
            raise ValueError("rows/block_maps length mismatch")
        
        if len(retrieved_readouts) != len(rows) - 1:
            raise ValueError("retrieved_readouts/rows length mismatch")
        
        if len(retrieved_items) != len(rows) - 1:
            raise ValueError("retrieved_items/rows length mismatch")
        
        if len(retrieved_alignment_scores) != len(rows) - 1:
            raise ValueError("retrieved_alignment_scores/rows length mismatch")
        
        if len(retrieved_cosine_scores) != len(rows) - 1:
            raise ValueError("retrieved_cosine_scores/rows length mismatch")
        
        for ridx in range(1, len(rows)):
            row_tokens = rows[ridx]
            block_map = block_maps[ridx]
            readout = retrieved_readouts[ridx - 1]
            item = retrieved_items[ridx - 1]

            mapping = {label_fn(it): it for it in readout.flatten_items()}

            # Build blocks in column order, including gap-only runs
            blocks: list[MSASequenceBlock] = []
            current_bidx: int | None = None
            current_tokens: list[MSAItemToken] = []
            current_name: str | None = None

            for col_idx, tok in enumerate(row_tokens):
                bidx = block_map[col_idx]
                if bidx != current_bidx:
                    if current_tokens:
                        blocks.append(MSASequenceBlock(
                            name=current_name or "alignment gap",
                            sequence=current_tokens,
                        ))
                    current_bidx = bidx
                    current_name = readout.block_ids[bidx] if bidx is not None else "alignment gap"
                    current_tokens = []

                if bidx is None:
                    current_tokens.append(MSAItemToken(isGap=True, name=gap_display_name))
                elif tok == gap_repr:
                    current_tokens.append(MSAItemToken(isGap=True, name=gap_display_name))
                else:
                    obj = mapping.get(tok)
                    current_tokens.append(MSAItemToken(
                        isGap=False,
                        name=(obj.display_name if obj is not None else display_name_unidentified),
                    ))

            if current_tokens:
                blocks.append(MSASequenceBlock(
                    name=current_name or "alignment gap",
                    sequence=current_tokens,
                ))

            # Retrieve references
            with SessionLocal() as session:
                item_type = Compound if isinstance(item, Compound) else CandidateCluster
                refs = get_references(session, item_type, item.id)
                refs = [RowReference.from_reference(r) for r in refs]

            if refs:
                name = refs[0].name
            else:
                if isinstance(item, Compound):
                    name = f"Compound {item.id}"
                else:
                    name = f"Cluster {item.file_name}"
            
            result.msa.append(MSARow(
                name=name,
                alignment_score=retrieved_alignment_scores[ridx - 1],
                cosine_score=retrieved_cosine_scores[ridx - 1],
                sequence=blocks,
                references=refs,
            ))

        return result
    

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
        query_internal_open_gap_score=-5.0,
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
