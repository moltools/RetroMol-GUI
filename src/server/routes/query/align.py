"""Module for aligning sequence items and creating MSA."""

from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Literal

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
    Mask,
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
class MSARow:
    """
    One row in the MSA: Query or a retrieved result.

    :var name: name of the row
    :var kind: "compound" or "cluster"
    :var db_id: database ID of the item
    :var sequence: list of MSASequenceBlocks in the row
    :var alignment_score: optional alignment score
    :var cosine_score: optional cosine similarity score
    :var match_score: ratio of item tokens visible in the alignment
    :var id: unique identifier
    """

    name: str
    sequence: list[MSASequenceBlock] = field(default_factory=list)

    kind: Literal["compound", "cluster"] | None = None
    db_id: int | None = None
    alignment_score: float | None = None
    cosine_score: float | None = None
    match_score: float | None = None
    id: str = field(default_factory=generate_guid)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the MSARow to a dictionary.

        :return: a dictionary representation of the MSARow
        """
        return {
            "name": self.name,
            "kind": self.kind,
            "db_id": self.db_id,
            "sequence": [block.to_dict() for block in self.sequence],
            "alignment_score": self.alignment_score,
            "cosine_score": self.cosine_score,
            "match_score": self.match_score,
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
        retrieved_items: list[Compound | CandidateCluster | None],
        retrieved_alignment_scores: list[float],
        retrieved_cosine_scores: list[float],
        retrieved_match_scores: list[float],
        # How to label items consistently with the tokens used in rows
        label_fn: Callable[[Any], str],
        gap_repr: str,
        display_name_unidentified: str,
        gap_display_name: str,
        retrieved_row_names: list[str | None] | None = None,
        query_name: str | None = None,
    ) -> "MSAResult":
        """
        Create an MSAResult from alignment data.

        :param rows: aligned token rows; row[0] is target/query
        :param block_maps: per-row ownership of each global col -> block_idx or None
        :param query_readout: SequenceItemReadout for the query row
        :param retrieved_readouts: list of SequenceItemReadouts for retrieved rows
        :param retrieved_items: list of retrieved items (db models or None for uploads)
        :param retrieved_alignment_scores: list of alignment scores for retrieved rows
        :param retrieved_cosine_scores: list of cosine similarity scores for retrieved rows
        :param retrieved_match_scores: list of match scores for retrieved rows
        :param label_fn: function to label items consistently with the tokens used in rows
        :param gap_repr: string representation used for gaps in the alignment
        :param display_name_unidentified: display name for unidentified items
        :param gap_display_name: display name for gaps
        :param retrieved_row_names: optional list of display names for retrieved rows
        :param query_name: optional display name for the query row
        :return: constructed MSAResult
        """
        if not rows:
            return cls()

        result = cls()

        # Query row: split into original blocks for display
        q_map = {label_fn(it): it for it in query_readout.flatten_items()}
        
        if query_readout.kind == "compound":
            # We sort on length descending for compounds
            block_order = sorted(
                range(len(query_readout.blocks)),
                key=lambda i: len(query_readout.blocks[i]),
                reverse=True,
            )
        else:
            # Keep original order for clusters
            block_order = list(range(len(query_readout.blocks)))

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

        display_query_name = (query_name or "").strip()
        query_row = MSARow(
            name=f"Query: {display_query_name}" if display_query_name else "Query",
            kind=None,
            db_id=None,
            alignment_score=None,
            cosine_score=None,
            match_score=None,
            sequence=query_blocks,
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
        
        if len(retrieved_match_scores) != len(rows) - 1:
            raise ValueError("retrieved_match_scores/rows length mismatch")

        if retrieved_row_names is not None and len(retrieved_row_names) != len(rows) - 1:
            raise ValueError("retrieved_row_names/rows length mismatch")
        
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

            row_name = None
            if retrieved_row_names is not None:
                row_name = retrieved_row_names[ridx - 1]

            if row_name is None and item is not None:
                # Retrieve references
                with SessionLocal() as session:
                    item_type = Compound if isinstance(item, Compound) else CandidateCluster
                    refs = get_references(session, item_type, item.id)

                if refs:
                    row_name = refs[0].name
                else:
                    if isinstance(item, Compound):
                        row_name = f"Compound {item.id}"
                    else:
                        row_name = f"Cluster {item.file_name}"

            if row_name is None:
                row_name = "Uploaded item"
            
            result.msa.append(MSARow(
                name=row_name,
                kind=readout.kind,
                db_id=readout.db_id,
                alignment_score=retrieved_alignment_scores[ridx - 1],
                cosine_score=retrieved_cosine_scores[ridx - 1],
                match_score=retrieved_match_scores[ridx - 1],
                sequence=blocks,
            ))

        return result
    

def item_compare_fn(a: SequenceItem, b:  SequenceItem) -> float:
    """
    Compare two SequenceItems or Gaps for sorting.
    """
    score = 0.0
    mask_penalty = -1e6

    # Deal with masks
    if isinstance(a, Mask) and isinstance(b, Mask):
        return 0.0  # identical masks
    elif (isinstance(a, Mask) and isinstance(b, NonGap)) or (isinstance(b, Mask) and isinstance(a, NonGap)):
        return mask_penalty
    elif (isinstance(a, Mask) and isinstance(b, Gap)) or (isinstance(b, Mask) and isinstance(a, Gap)):
        return score  # same as gap vs gap/non-gap

    # Deal with gaps first
    if isinstance(a, Gap) or isinstance(b, Gap):
        return score
    
    # Both items are non-gaps at this point
    if isinstance(a, NonGap) and isinstance(b, NonGap):
        
        # Compare family tokens
        a_fam_toks = set(a.family_tokens)
        b_fam_toks = set(b.family_tokens)
        fam_tok_overlap = a_fam_toks.intersection(b_fam_toks)
        fam_tok_differs = a_fam_toks.symmetric_difference(b_fam_toks)

        # Compare ancestor tokens
        a_anc_toks = set(a.ancestor_tokens)
        b_anc_toks = set(b.ancestor_tokens)
        anc_tok_overlap = a_anc_toks.intersection(b_anc_toks)
        anc_tok_differs = a_anc_toks.symmetric_difference(b_anc_toks)

        tok_overlap = fam_tok_overlap.union(anc_tok_overlap)
        score += 0.5 * len(tok_overlap)

        tok_differs = fam_tok_differs.union(anc_tok_differs)
        score -= 0.5 * len(tok_differs)

        if a.morgan_fp is not None and b.morgan_fp is not None:
            score += calculate_tanimoto_similarity(a.morgan_fp, b.morgan_fp)
            return score
        
        elif a.display_name == DISPLAY_NAME_UNIDENTIFIED or b.display_name == DISPLAY_NAME_UNIDENTIFIED:
            return 0.0  # could be correct, but we don't know
        
        else:
            return score

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
    unique_items = list(set(readout1_items + readout2_items + [Gap(), Mask()]))
    sm, _ = create_substitution_matrix_dynamically(
        unique_items,
        compare=item_compare_fn,
        label_fn=item_label_fn
    )

    aligner = setup_aligner(
        sm,
        "global",
        # Gap penalties
        target_internal_open_gap_score=-5.0,
        query_internal_open_gap_score=-5.0,
        # We don't care about gaps at the ends for docking
        target_left_open_gap_score=0.0,
        target_right_open_gap_score=0.0,
        target_left_extend_gap_score=0.0,
        target_right_extend_gap_score=0.0,
        query_left_open_gap_score=0.0,
        query_right_open_gap_score=0.0,
        query_left_extend_gap_score=0.0,
        query_right_extend_gap_score=0.0,
        # Label function
        label_fn=item_label_fn,
    )

    return aligner


def score_by_alignment(
    query: SequenceItemReadout,
    items: list[SequenceItemReadout],
    unaligned_item_penalty: float = 0.5,
) -> tuple[list[DockingResult], list[float], list[float]]:
    """
    Rerank nearest neighbors based on more accurate scoring.

    :param query: SequenceItemReadout of the query item
    :param items: list of SequenceItemReadouts to be scored against the query
    :param unaligned_item_penalty: penalty per item per unaligned block
    :return: tuple of list of DockingResults and their corresponding scores
    """
    aln_results = []
    aln_scores: list[float] = []
    match_scores: list[float] = []

    gap_repr = Gap.alignment_representation()

    for item in items:
        aligner = _setup_aligner(query, item)
        
        aln: DockingResult = dock_against_target(
            aligner=aligner,
            target=query.flatten_items(),
            candidates=item.blocks,
            gap_repr=gap_repr,
            mask_repr=Mask.alignment_representation(),
            allow_block_reverse=True,
        )

        # Get full length of item
        cum_len = len(item.flatten_items())
        visible_items = _count_visible_tokens_in_docking(aln, gap_repr)
        match_score = visible_items / cum_len if cum_len > 0 else 0.0
    
        # Penalize unaligned regions
        unaligned_items = 0
        for block_idx in aln.unused_blocks:
            # Get length of unaligned block and calculate penalty
            len_unused_block = len(item.blocks[block_idx])
            unaligned_items += len_unused_block

        unaligned_penalty = unaligned_items * unaligned_item_penalty
        aln_score = aln.total_score - unaligned_penalty

        aln_results.append(aln)
        aln_scores.append(aln_score)
        match_scores.append(match_score)

    return aln_results, aln_scores, match_scores


def _count_visible_tokens_in_docking(docking: DockingResult, gap_repr: str) -> int:
    """
    Count item tokens that will be visible in the alignment for a docking result.

    This mirrors the region slicing logic used in the MSA merge and respects
    collision resolution within a single row (max score wins on target columns).
    """
    visible = 0
    placements = sorted(docking.placements, key=lambda p: (p.start, p.end))

    # Count insertion tokens (unique columns, so no collision handling needed).
    for placement in placements:
        target_pos = -1
        in_region = False
        prefix_anchor = placement.start - 1

        for c_tok, b_tok in zip(placement.center_aln, placement.block_aln):
            if c_tok != gap_repr:
                target_pos += 1
                if target_pos > placement.end:
                    break
                in_region = placement.start <= target_pos <= placement.end
            else:
                if (in_region or target_pos == prefix_anchor) and b_tok != gap_repr:
                    visible += 1

    # Count target-column tokens with collision handling (max score wins).
    score_by_pos: dict[int, float] = {}
    has_token_by_pos: dict[int, bool] = {}

    for placement in placements:
        target_pos = -1
        in_region = False
        score = float(placement.score)

        for c_tok, b_tok in zip(placement.center_aln, placement.block_aln):
            if c_tok != gap_repr:
                target_pos += 1
                if target_pos > placement.end:
                    break
                in_region = placement.start <= target_pos <= placement.end
                if not in_region:
                    continue

                current_score = score_by_pos.get(target_pos, float("-inf"))
                if score > current_score:
                    score_by_pos[target_pos] = score
                    has_token_by_pos[target_pos] = (b_tok != gap_repr)
            else:
                continue

    for has_token in has_token_by_pos.values():
        if has_token:
            visible += 1

    return visible
