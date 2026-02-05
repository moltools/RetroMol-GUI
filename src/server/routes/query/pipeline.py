"""Pipeline for cross-modal retrieval."""

import uuid
import math
from typing import Any, Sequence

from flask import current_app

from routes.query.align import MSAResult, score_by_alignment, item_label_fn
from routes.query.featurize import featurize_item
from routes.query.retrieve import ann_search
from routes.query.seq import DISPLAY_NAME_UNIDENTIFIED, Gap, SequenceItemReadout
from routes.query.featurize import load_payload, format_payload_readout

from versalign.docking import DockingResult, DockPlacement

from bionexus.db.models import CandidateCluster, Compound


# Turn off BiopythonDeprecationWarning warnings
import warnings
from Bio import BiopythonDeprecationWarning
warnings.simplefilter("ignore", BiopythonDeprecationWarning)


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
    that occur while inside the region and immediately before the region start.

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
    prefix_anchor = start - 1

    for c_tok, b_tok in zip(center_aln, block_aln):
        if c_tok != gap_repr:
            target_pos += 1
            if target_pos > end:
                break

            in_region = (start <= target_pos <= end)
            if in_region:
                out_c.append(c_tok)
                out_b.append(b_tok)

        else:
            if in_region or target_pos == prefix_anchor:
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

    # Collect insertion lengths across all dockings, anchored to a target boundary
    # anchor = j means "insertion occurs after target position j"
    # anchor = -1 means "before target[0]"
    insertion_lengths: dict[int, int] = {a: 0 for a in range(-1, n)}

    # Precompute mapping of target positions -> global columns (once built)
    targetpos_to_global_col: dict[int, int] = {}

    for dr in dockings:
        placements = sorted(dr.placements, key=lambda p: (p.start, p.end))
        for p in placements:
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
            insertion_offset = 0
            for c_tok in reg_center:
                if c_tok != gap_repr:
                    tpos += 1
                    insertion_offset = 0
                else:
                    # Insertion after tpos (which is in [p.start-1, .. p.end-1])
                    # If tpos == p.start-1, that's an insertion before the first consumed symbol in the region
                    anchor = tpos
                    if anchor < -1: anchor = -1
                    if anchor > n - 1: anchor = n - 1
                    insertion_lengths[anchor] = max(insertion_lengths[anchor], insertion_offset + 1)
                    insertion_offset += 1

    # Build the global aligned center, assigning global column indices
    aligned_center: list[str] = []
    insertion_cols_by_anchor: dict[int, list[int]] = {a: [] for a in range(-1, n)}

    # Insertions before target[0] (anchor -1)
    for _ in range(insertion_lengths[-1]):
        insertion_cols_by_anchor[-1].append(len(aligned_center))
        aligned_center.append(gap_repr)

    # For each target pos j: emit target[j], then insertion anchored at j
    for j in range(n):
        targetpos_to_global_col[j] = len(aligned_center)
        aligned_center.append(target[j])

        for _ in range(insertion_lengths[j]):
            insertion_cols_by_anchor[j].append(len(aligned_center))
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
        insertion_offset = 0
        for c_tok, b_tok in zip(reg_center, reg_block):
            if c_tok != gap_repr:
                tpos += 1
                gcol = targetpos_to_global_col[tpos]
                insertion_offset = 0
            else:
                # tpos should naturally be in [p.start-1, .. p.end-1], so we don't need clamping here
                if not (-1 <= tpos <= n - 1):
                    raise ValueError("unexpected target position for insertion column")
                anchor = tpos
                if anchor < -1: anchor = -1
                if anchor > n - 1: anchor = n - 1
                cols = insertion_cols_by_anchor[anchor]
                if insertion_offset >= len(cols):
                    insertion_offset += 1
                    continue
                gcol = cols[insertion_offset]
                insertion_offset += 1

            if b_tok == gap_repr:
                # Keep block ownership for gap columns, but never override a real token
                if row[gcol] == gap_repr and score_row[gcol] < float(p.score):
                    score_row[gcol] = float(p.score)
                    block_map[gcol] = p.block_idx
                continue

            # Resolve collisions within the same row
            if score_row[gcol] < float(p.score):
                row[gcol] = b_tok
                score_row[gcol] = float(p.score)
                # Mark block ownership
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


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    :param a: first vector
    :param b: second vector
    :return: cosine similarity in [-1, 1]
    """
    if a is None or b is None:
        return 0.0
    try:
        if len(a) == 0 or len(b) == 0:
            return 0.0
    except TypeError:
        return 0.0
    if len(a) != len(b):
        current_app.logger.warning("cosine similarity length mismatch: %s vs %s", len(a), len(b))
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def cross_modal_retrieval(
    payload_type: str,
    payload_blob: dict[str, Any],
    query_against_clusters: bool,
    query_against_compounds: bool,
    user_uploads: list[dict[str, Any]] | None = None,
    query_name: str | None = None,
    top_k: int = 18,
    ann_search_limit: int | None = None,
    cluster_where: Sequence[Any] | None = None,
    compound_where: Sequence[Any] | None = None,
) -> MSAResult:
    """
    Perform cross-modal retrieval given an item payload.
    
    :param payload_type: type of the payload ("cluster" or "compound")
    :param payload_blob: the actual payload data
    :param query_against_clusters: whether to query against clusters
    :param query_against_compounds: whether to query against compounds
    :param user_uploads: optional list of session items to include in retrieval
    :param query_name: optional display name for the query row
    :param top_k: number of top results to return
    :param ann_search_limit: optional override for ANN search radius
    :param cluster_where: optional extra filters for cluster ANN query
    :param compound_where: optional extra filters for compound ANN query
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
        limit=ann_search_limit,
        cluster_where=cluster_where,
        compound_where=compound_where,
    )
    current_app.logger.debug(f"found {len(nns)} nearest neighbors")

    # Featurize nearest neighbors as SequenceItemReadout with cosine SCORE (1 - distance)
    nns_featurized: list[SequenceItemReadout] = []
    nns_cosine_scores: list[float] = []
    retrieved_items: list[CandidateCluster | Compound | None] = []
    retrieved_names: list[str | None] = []
    for item, distance in nns:
        assert isinstance(item, (CandidateCluster, Compound)), "expected item to be CandidateCluster or Compound"
        item_type = "cluster" if isinstance(item, CandidateCluster) else "compound"
        item_blob = item.biocracker if item_type == "cluster" else item.retromol
        item_payload = load_payload(item_type, item_blob)

        # Get item database ID if available
        try:
            item_db_id = item.id
        except AttributeError:
            item_db_id = None

        item_readout = format_payload_readout(item_type, item_payload, item_db_id)
        nns_featurized.append(item_readout)
        nns_cosine_scores.append(1.0 - distance)
        retrieved_items.append(item)
        retrieved_names.append(None)

    # Include user uploads (session items) if provided
    for upload in user_uploads or []:
        if not isinstance(upload, dict):
            continue
        upload_kind = upload.get("kind")
        upload_payload = upload.get("payload")
        if upload_kind not in ("cluster", "compound"):
            continue
        if not upload_payload:
            continue
        try:
            upload_vec, upload_readout = featurize_item(upload_kind, upload_payload)
        except Exception as exc:
            current_app.logger.warning("failed to featurize user upload: %s", exc)
            continue
        cosine_score = _cosine_similarity(query_vec, upload_vec)
        nns_featurized.append(upload_readout)
        nns_cosine_scores.append(cosine_score)
        retrieved_items.append(None)
        retrieved_names.append(upload.get("name") or "Uploaded item")
    
    if not nns_featurized or not query_blocks:
        raise ValueError("no nearest neighbors found or query blocks are empty")

    # Rerank nearest neighbors by alignment
    alignment_results: tuple[list[DockingResult], list[float], list[float]] = score_by_alignment(query_blocks, nns_featurized)
    aln_results, aln_scores, aln_match_scores = alignment_results

    if not aln_results or not aln_scores:
        raise ValueError("alignment scoring failed; no results or scores obtained")

    # Get top K nns_featurized and aln_results; first sorted on aln_scores, then on nns_cosine_scores, and then on aln_match_scores
    top_k_indices = sorted(range(len(aln_scores)), key=lambda i: (aln_scores[i], nns_cosine_scores[i], aln_match_scores[i]), reverse=True)[:top_k]
    current_app.logger.debug(f"top k indices: {top_k_indices}")

    top_k_nns_featurized    = [nns_featurized[i] for i in top_k_indices]
    top_k_retrieved_items   = [retrieved_items[i] for i in top_k_indices]
    top_k_retrieved_names   = [retrieved_names[i] for i in top_k_indices]
    top_k_aln_results       = [aln_results[i] for i in top_k_indices]
    top_k_aln_scores        = [aln_scores[i] for i in top_k_indices]
    top_k_cosine_scores     = [nns_cosine_scores[i] for i in top_k_indices]
    top_k_match_scores      = [aln_match_scores[i] for i in top_k_indices]

    current_app.logger.debug(f"found {len(top_k_nns_featurized)} top-k nearest neighbors after reranking")
    current_app.logger.debug(f"top scores for first nearest neighbor: aln {top_k_aln_scores[0]}, cosine {top_k_cosine_scores[0]}, match {top_k_match_scores[0]}")

    # Merge top K dockings into global alignment
    rows, block_maps = merge_dockings_into_global_alignment(
        target=[item_label_fn(item) for item in query_blocks.flatten_items()],
        dockings=top_k_aln_results,
        gap_repr=Gap.alignment_representation(),
    )

    msa_result: MSAResult = MSAResult.from_alignment(
        rows=rows,
        block_maps=block_maps,
        query_readout=query_blocks,
        retrieved_readouts=top_k_nns_featurized,
        retrieved_items=top_k_retrieved_items,
        retrieved_alignment_scores=top_k_aln_scores,
        retrieved_cosine_scores=top_k_cosine_scores,
        retrieved_match_scores=top_k_match_scores,
        retrieved_row_names=top_k_retrieved_names,
        label_fn=item_label_fn,
        gap_repr=Gap.alignment_representation(),
        display_name_unidentified=DISPLAY_NAME_UNIDENTIFIED,
        gap_display_name=Gap().display_name,
        query_name=query_name,
    )

    return msa_result
