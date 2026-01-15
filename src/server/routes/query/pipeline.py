"""Pipeline for cross-modal retrieval."""

import uuid
from dataclasses import dataclass
from typing import Any

from flask import current_app

from routes.query.align import MSAResult, score_by_alignment, item_label_fn
from routes.query.featurize import featurize_item
from routes.query.retrieve import ann_search
from routes.query.seq import DISPLAY_NAME_UNIDENTIFIED, Gap, SequenceItemReadout
from routes.query.featurize import load_payload, format_payload_readout

from versalign.docking import DockingResult, DockPlacement

from bionexus.db.models import CandidateCluster, Compound


@dataclass(frozen=True)
class _InsKey:
    """
    Key to uniquely identify an insertion column in docking results.

    :var result_idx: index of the docking result
    :var placement_idx: index of the placement within the docking result
    :var col_in_region: column index within the insertion region
    :var anchor: target position anchor for the insertion
    """

    result_idx: int
    placement_idx: int
    col_in_region: int
    anchor: int  # insertion occurs AFTER this target position; -1 means before target[0]


def _slice_alignment_to_target_region(
    center_aln: list[str],
    block_aln: list[str],
    start: int,
    end: int,
    gap_repr: str,
) -> tuple[list[str], list[str]]:
    """
    Slice (center_aln, block_aln) down to the columns that map to target coordinates
    [start, end] inclusive, while keeping insertion columns (center token == gap_repr)
    that occur while inside the region.

    :param center_aln: list of hashes representing the center alignment SequenceItems
    :param block_aln: list of hashes representing the block alignment SequenceItems
    :param start: start target position (inclusive)
    :param end: end target position (inclusive)
    :param gap_repr: hash string representing of a gap
    """
    if len(center_aln) != len(block_aln):
        raise ValueError("alignment lenght mismatch")
    
    out_c: list[str] = []
    out_b: list[str] = []

    target_pos = -1
    in_region = False

    for c_tok, b_tok in zip(center_aln, block_aln):
        if c_tok != gap_repr:
            target_pos += 1
            in_region = (start <= target_pos <= end)

            if start <= target_pos <= end:
                out_c.append(c_tok)
                out_b.append(b_tok)

            if target_pos > end:
                break

        else:
            if in_region:
                out_c.append(c_tok)
                out_b.append(b_tok)

    return out_c, out_b


def merge_dockings_into_global_alignment(
    target: list[str],
    dockings: list[DockingResult],
    gap_repr: str,
) -> tuple[list[list[str]], list[list[int | None]]]:
    """
    Merge multiple docking results into a global MSAResult.

    :param target: the tokenized target SequenceItemReadout
    :param dockings: list of DockingResult to merge
    :param gap_repr: string representation for gaps
    :return: tuple of (aligned rows, block maps)
    :raises ValueError: if target blocks are empty
    """
    if not target:
        raise ValueError("target blocks are empty")
    
    n = len(target)

    # Collect ALL insertion columns across all dockings, anchored to a target boundary
    # anchor = j means "insertion column occurs after target position j"
    # anchor = -1 means "before target[0]"
    insertions_by_anchor: dict[int, list[_InsKey]] = {a: [] for a in range(-1, n)}
    # We also need to later map each insertion column identity -> global column index
    inskey_to_global_col: dict[_InsKey, int] = {}

    # Also precompute mapping of target positions -> global columns (once built)
    targetpos_to_global_col: dict[int, int] = {}

    # To place insertions deterministically, we'll sort them by:
    # (result_idx, placement start, placement_idx, col_in_region)
    # We need placement start; capture it in a side map
    placement_start: dict[tuple[int, int], int] = {}

    for ri, dr in enumerate(dockings):
        placements = sorted(dr.placements, key=lambda p: (p.start, p.end))
        for pi, p in enumerate(placements):
            placement_start[(ri, pi)] = p.start

            reg_center, reg_block = _slice_alignment_to_target_region(
                center_aln=p.center_aln,
                block_aln=p.block_aln,
                start=p.start,
                end=p.end,
                gap_repr=gap_repr,
            )

            # Walk region columns and anchor insertions.
            # We anchor insertion columns to "after the last consumed target position"
            # Initialize target_pos to p.start - 1 so that the first consumed target sets it to p.start
            tpos = p.start - 1
            for ci, c_tok in enumerate(reg_center):
                if c_tok != gap_repr:
                    tpos += 1
                else:
                    # Insertion after tpos (which is in [p.start-1, .. p.end-1])
                    # If tpos == p.start-1, that's an insertion before the first consumed symbol in the region
                    anchor = tpos
                    if anchor < -1: anchor = -1
                    if anchor > n - 1: anchor = n - 1
                    insertions_by_anchor[anchor].append(_InsKey(ri, pi, ci, anchor=anchor))

    # Sort insertions at each anchor deterministically
    for anchor, keys in insertions_by_anchor.items():
        keys.sort(
            key=lambda k: (
                k.result_idx,
                placement_start.get((k.result_idx, k.placement_idx), 10**9),
                k.placement_idx,
                k.col_in_region,
            )
        )

    # Build the global aligned center, assigning global column indices
    aligned_center: list[str] = []

    # Insertions before target[0] (anchor -1)
    for k in insertions_by_anchor[-1]:
        inskey_to_global_col[k] = len(aligned_center)
        aligned_center.append(gap_repr)

    # For each target pos j: emit target[j], then insertion anchored at j
    for j in range(n):
        targetpos_to_global_col[j] = len(aligned_center)
        aligned_center.append(target[j])

        for k in insertions_by_anchor[j]:
            inskey_to_global_col[k] = len(aligned_center)
            aligned_center.append(gap_repr)

    aligned_target = aligned_center[:]  # same content; separate name for readability
    L = len(aligned_center)

    # Helper to write a placement into a row, with "max score wins" on collisions
    def _project_one_placement_into_row(
        row: list[str],
        score_row: list[float],
        block_map: list[int | None],
        ri: int,
        pi: int,
        p: DockPlacement,
    ) -> None:
        """
        Project one placement into the given row, updating in-place.

        :param row: list of strings representing the row to update
        :param score_row: list of floats representing the scores for each column in the row
        :param block_map: mapping from block indices to global column indices
        :param ri: index of the docking result
        :param pi: index of the placement within the docking result
        :param p: DockPlacement to project
        """
        reg_center, reg_block = _slice_alignment_to_target_region(
            center_aln=p.center_aln,
            block_aln=p.block_aln,
            start=p.start,
            end=p.end,
            gap_repr=gap_repr,
        )

        tpos = p.start - 1
        for ci, (c_tok, b_tok) in enumerate(zip(reg_center, reg_block)):
            if c_tok != gap_repr:
                tpos += 1
                gcol = targetpos_to_global_col[tpos]
            else:
                # tpos should naturally be in [p.start-1, .. p.end-1], so we don't need clamping here
                if not (-1 <= tpos <= n - 1):
                    raise ValueError("unexpected target position for insertion column")
                key = _InsKey(ri, pi, ci, anchor=tpos)
                # Because we sorted+assigned by identity, this must exist
                gcol = inskey_to_global_col.get(key, None)
                if gcol is None:
                    # Extremely defensive fallback: skip if we somehow didn't register it
                    continue

            if b_tok == gap_repr:
                continue

            # Resolve collisions within the same row
            if score_row[gcol] < float(p.score):
                row[gcol] = b_tok
                score_row[gcol] = float(p.score)
                # Mark block owernship
                block_map[gcol] = p.block_idx

    # Build rows\
    row_ids = list(range(len(dockings)))
    rows: list[list[str]] = []
    block_maps: list[list[int | None]] = []

    for ri, dr in enumerate(dockings):
        placements = sorted(dr.placements, key=lambda p: (p.start, p.end))
        row = [gap_repr] * L
        score_row = [float("-inf")] * L
        block_map = [None] * L
        for pi, p in enumerate(placements):
            _project_one_placement_into_row(
                row=row,
                score_row=score_row,
                block_map=block_map,
                ri=ri,
                pi=pi,
                p=p,
            )

        rows.append(row)
        block_maps.append(block_map)

    # First row should be the target
    rows = [aligned_target] + rows
    block_maps = [[None] * L] + block_maps

    return rows, block_maps


def cross_modal_retrieval(
    payload_type: str,
    payload_blob: dict[str, Any],
    query_against_clusters: bool,
    query_against_compounds: bool,
    top_k: int = 20,
) -> MSAResult:
    """
    Perform cross-modal retrieval given an item payload.
    
    :param payload_type: type of the payload ("cluster" or "compound")
    :param payload_blob: the actual payload data
    :param query_against_clusters: whether to query against clusters
    :param query_against_compounds: whether to query against compounds
    :param top_k: number of top results to return
    :return: MSAResult containing the retrieval results
    :raises ValueError: if no nearest neighbors found or alignment fails
    """
    # Featurize query
    featurized_item: tuple[list[float], SequenceItemReadout] = featurize_item(payload_type, payload_blob)
    query_vec, query_blocks = featurized_item

    # ANN with query_vec; return nearest neighbors with cosine DISTANCE
    nns: list[tuple[CandidateCluster | Compound, float]] = ann_search(
        query_vec,
        query_against_clusters=query_against_clusters,
        query_against_compounds=query_against_compounds,
    )
    current_app.logger.debug(f"found {len(nns)} nearest neighbors")

    # Featurize nearest neighbors as SequenceItemReadout with cosine SCORE (1 - distance)
    nns_featurized: list[SequenceItemReadout] = []
    nns_cosine_scores: list[float] = []
    for item, distance in nns:
        assert isinstance(item, (CandidateCluster, Compound)), "expected item to be CandidateCluster or Compound"
        item_type = "cluster" if isinstance(item, CandidateCluster) else "compound"
        item_blob = item.biocracker if item_type == "cluster" else item.retromol
        item_payload = load_payload(item_type, item_blob)
        item_readout = format_payload_readout(item_type, item_payload)
        nns_featurized.append(item_readout)
        nns_cosine_scores.append(1.0 - distance)

    if not nns_featurized or not query_blocks:
        raise ValueError("no nearest neighbors found or query blocks are empty")

    # Rerank nearest neighbors by alignment
    alignment_results: tuple[list[DockingResult], list[float]] = score_by_alignment(query_blocks, nns_featurized)
    aln_results, aln_scores = alignment_results

    if not aln_results or not aln_scores:
        raise ValueError("alignment scoring failed; no results or scores obtained")

    # Get top K nns_featurized and aln_results; first sorted on aln_scores, then on nns_cosine_scores
    top_k_indices = sorted(range(len(aln_scores)), key=lambda i: (aln_scores[i], nns_cosine_scores[i]), reverse=True)[:top_k]
    current_app.logger.debug(f"top k indices: {top_k_indices}")

    top_k_nns_featurized    = [nns_featurized[i] for i in top_k_indices]
    top_k_aln_results       = [aln_results[i] for i in top_k_indices]
    top_k_aln_scores        = [aln_scores[i] for i in top_k_indices]
    top_k_cosine_scores     = [nns_cosine_scores[i] for i in top_k_indices]

    current_app.logger.debug(f"found {len(top_k_nns_featurized)} top-k nearest neighbors after reranking")
    current_app.logger.debug(f"top scores for first nearest neighbor: aln {top_k_aln_scores[0]}, cosine {top_k_cosine_scores[0]}")

    # Merge top K dockings into global alignment
    rows, block_maps = merge_dockings_into_global_alignment(
        target=[item_label_fn(item) for item in query_blocks.flatten_items()],
        dockings=top_k_aln_results,
        gap_repr=Gap.alignment_representation(),
    )

    msa_result = {"msa": []}

    # Format row[0] as target
    mapping = {item_label_fn(item): item for item in query_blocks.flatten_items()}
    msa_item = {
        "id": str(uuid.uuid4()),
        "name": "Query",
        "alignment_score": None,
        "cosine_score": None,
        "sequence": [
            {
                "id": str(uuid.uuid4()),
                "name": "query primary sequence",
                "sequence": [
                    {
                        "id": str(uuid.uuid4()),
                        "isGap": (tok == Gap.alignment_representation()),
                        "name": mapping.get(tok).display_name if tok in mapping else "unknown",
                        "smiles": None,
                    }
                    for tok in rows[0]
                ]
            }
        ],
        "references": []
    }
    msa_result["msa"].append(msa_item)

    max_len = len(rows[0])

    # We now need to translate the tokenized SequenceItems back to their original SequenceItems
    for i in range(1, len(rows[1:])):  # skip target row at index 0
        row = rows[i]
        block_map = block_maps[i]

        # Create map
        readout = nns_featurized[top_k_indices[i]]
        mapping = {item_label_fn(item): item for item in readout.flatten_items()}

        msa_item = {
            "id": str(uuid.uuid4()),
            "name": f"Result {i+1}",
            "alignment_score": top_k_aln_scores[i],
            "cosine_score": top_k_cosine_scores[i],
            "sequence": [],
            "references": [],
        }
        # Create subseq per block idx, in order of appearance in block_map
        block_idx_to_subseq: dict[int, list[dict[str, Any]]] = {}
        block_order: list[int] = []

        for col_idx, tok in enumerate(row):
            block_idx = block_map[col_idx]
            if block_idx is None:
                continue  # skip columns not owned by a block

            if block_idx not in block_idx_to_subseq:
                block_idx_to_subseq[block_idx] = []
                block_order.append(block_idx)

            if tok == Gap.alignment_representation():
                seq_item = {
                    "id": str(uuid.uuid4()),
                    "isGap": True,
                    "name": Gap().display_name,
                    "smiles": None,
                }
            else:
                obj = mapping.get(tok)
                seq_item = {
                    "id": str(uuid.uuid4()),
                    "isGap": False,
                    "name": obj.display_name if obj is not None else DISPLAY_NAME_UNIDENTIFIED,
                    "smiles": None,
                }

            block_idx_to_subseq[block_idx].append(seq_item)

        msa_item["sequence"] = [
            {
                "id": str(uuid.uuid4()),
                "name": f"retrieved primary sequence block {block_idx}",
                "sequence": block_idx_to_subseq[block_idx],
            }
            for block_idx in block_order
        ]

        # Pad with gaps if needed
        cum_len = 0
        for subseq in msa_item["sequence"]:
            cum_len += len(subseq["sequence"])
        if cum_len < max_len:
            len_diff = max_len - cum_len
            msa_item["sequence"].append(
                {
                    "id": str(uuid.uuid4()),
                    "name": "padding gap",
                    "sequence": [
                        {
                            "id": str(uuid.uuid4()),
                            "isGap": True,
                            "name": Gap().display_name,
                            "smiles": None,
                        }
                        for _ in range(len_diff)
                    ]
                }
            )

        msa_result["msa"].append(msa_item)

    return msa_result
