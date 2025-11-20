"""Module for handling view requests."""

import math
import time

import numpy as np
import umap
from flask import Blueprint, current_app, request, jsonify

from routes.helpers import hex_to_bits
from routes.query import execute_named_query


blp_get_embedding_space = Blueprint("get_embedding_space", __name__)
blp_enrich = Blueprint("enrich", __name__)


def _log_hypergeom_probability(a: int, b: int, c: int, d: int) -> float:
    """
    Compute log probability of a 2x2 table under the hypergeometric model.
    
    :param a: count in cell (1,1)
    :param b: count in cell (1,2)
    :param c: count in cell (2,1)
    :param d: count in cell (2,2)
    :return: log probability
    """
    total = a + b + c + d
    return (
        math.lgamma(a + b + 1)
        - math.lgamma(a + 1)
        - math.lgamma(b + 1)
        + math.lgamma(c + d + 1)
        - math.lgamma(c + 1)
        - math.lgamma(d + 1)
        - math.lgamma(total + 1)
        + math.lgamma(a + c + 1)
        + math.lgamma(b + d + 1)
    )


def _fisher_exact_two_sided(a: int, b: int, c: int, d: int) -> float:
    """
    Return two-sided Fisher's exact test p-value for a 2x2 table.
    
    :param a: count in cell (1,1)
    :param b: count in cell (1,2)
    :param c: count in cell (2,1)
    :param d: count in cell (2,2)
    :return: two-sided p-value
    """
    if min(a, b, c, d) < 0:
        raise ValueError("Fisher's exact test counts must be non-negative")

    r1 = a + b
    r2 = c + d
    c1 = a + c

    min_a = max(0, c1 - r2)
    max_a = min(r1, c1)

    obs_log_prob = _log_hypergeom_probability(a, b, c, d)
    p_sum = 0.0
    for x in range(min_a, max_a + 1):
        y = r1 - x
        z = c1 - x
        w = r2 - z
        if y < 0 or z < 0 or w < 0:
            continue
        log_prob = _log_hypergeom_probability(x, y, z, w)
        if log_prob <= obs_log_prob + 1e-12:
            p_sum += math.exp(log_prob)

    return min(p_sum, 1.0)


@blp_get_embedding_space.post("/api/getEmbeddingSpace")
def get_embedding_space() -> tuple[dict[str, str], int]:
    """
    Handle POST requests to retrieve embedding space information.

    :return: a tuple containing an empty dictionary and HTTP status code 200
    """
    payload = request.get_json(force=True) or {}

    session_id = payload.get("sessionId")
    items = payload.get("items", [])

    current_app.logger.info(f"get_embedding_space called: session_id={session_id} items_count={len(items)}")

    if not session_id or not items:
        current_app.logger.warning("get_embedding_space: missing sessionId or items")
        return jsonify({"error": "Missing sessionId or items"}), 400
    
    # Filter out any item that does not have required fields for item
    required_fields_item = {"id", "kind", "fingerprints"}
    items = [item for item in items if required_fields_item.issubset(item.keys())]

    # Filter out any item that does not have required fields for fingerprint item
    required_fields_fp = {"id", "fingerprint512", "score"}
    for item in items:
        item["fingerprints"] = [fp_item for fp_item in item["fingerprints"] if required_fields_fp.issubset(fp_item.keys())]
    
    t0 = time.time()

    # Gather all "kind" types; if both "compound" and "gene_cluster" are present, set reduce_fp to True
    reduce_fp = False
    kinds = set(item["kind"] for item in items)
    if "compound" in kinds and "gene_cluster" in kinds:
        reduce_fp = True

    try:
        # Decode fingerprints
        kinds, parent_ids, child_ids, fps = [], [], [], []
        for item in items:
            for fp_item in item["fingerprints"]:
                kinds.append(item["kind"])
                parent_ids.append(item["id"])
                child_ids.append(fp_item["id"])
                fps.append(hex_to_bits(fp_item["fingerprint512"]))

        # Handle case with no fingerprints
        if len(fps) == 0:
            # Return empty points
            points = []

        else:
            # Convert to numpy array
            fps = np.array(fps)

            # Reduce dimensionality if needed
            if reduce_fp:
                # Remove every bit that is not set in "gene_cluster" fingerprints
                gene_cluster_fps = fps[[i for i, kind in enumerate(kinds) if kind == "gene_cluster"]]
                bits_to_keep = np.any(gene_cluster_fps, axis=0)
                fps = fps[:, bits_to_keep]

            # Reduce dimensionality using UMAP
            n_samples = fps.shape[0]
            if n_samples == 1:
                # Single point: put it at the origin (jitter will be applied later so might not be exactly at origin)
                reduced = np.zeros((1, 2))
            elif n_samples <= 3:
                # UMAP's spectral step is fragile for very small N
                # Put points on unit circle evenly spaced
                angles = np.linspace(0, 2 * np.pi, n_samples, endpoint=False)
                reduced = np.stack([np.cos(angles), np.sin(angles)], axis=1)
            else:
                # UMAP requires num_neighbors < num_samples
                n_neighbors = min(15, n_samples - 1)
                reducer = umap.UMAP(
                    n_components=2,
                    n_neighbors=n_neighbors,
                    random_state=42,
                    metric="cosine"
                )
                reduced = reducer.fit_transform(fps)

            points = [
                {
                    "parent_id": parent_id,
                    "child_id": child_id,
                    "kind": kind,
                    "x": float(reduced[i, 0]),
                    "y": float(reduced[i, 1]),
                } for i, (kind, parent_id, child_id) in enumerate(zip(kinds, parent_ids, child_ids))
            ]
    except Exception as e:
        current_app.logger.error(f"get_embedding_space: error processing items: {e}")
        return jsonify({"error": "Error processing items"}), 500

    elapsed = int((time.time() - t0) * 1000)
    current_app.logger.info(f"get_embedding_space: finished session_id={session_id} elapsed_ms={elapsed}")
    
    return jsonify({
        "ok": True,
        "status": "done",
        "elapsed_ms": elapsed,
        "points": points
    }), 200


@blp_enrich.post("/api/enrich")
def run_enrichment() -> tuple[dict[str, str], int]:
    """
    Handle POST requests to run enrichment analysis.

    :return: a tuple containing an empty dictionary and HTTP status code 200
    """
    payload = request.get_json(force=True) or {}

    fp_hex_string = payload.get("fingerprint512")
    query_settings = payload.get("querySettings", {})

    # Guard against missing fingerprint
    if not fp_hex_string:
        return jsonify({"error": "Missing fingerprint512"}), 400

    t0 = time.time()

    result = execute_named_query(
        name="cross_modal_retrieval",
        params={
            "fingerprint512": fp_hex_string,
            "querySettings": query_settings,
        },
        paging={},
        order={},
    )

    # If num_rows is equal to max_limit_in_group, we know there are more results
    # Throw error and ask user to up the score threshold
    max_limit_in_group = 1000
    num_rows = len(result["rows"])
    if num_rows >= max_limit_in_group:
        return jsonify({
            "error": f"Too many items in in-group (>={max_limit_in_group}). Please increase the score threshold in query settings and try again."
        }), 400

    # Get unique IDs
    readout_ids = set([item["identifier"] for item in result["rows"]])

    # Map those to compounds and genbank regions
    item_ids = execute_named_query(
        name="retrieve_items_by_fingerprint_ids",
        params={"rf_ids": list(readout_ids)},
        paging={ "limit": 1_000_000_000 },  # use high limit otherwise default limit of 1000 applies
        order={},
    )
    compound_ids: set[int] = set()
    genbank_region_ids: set[int] = set()
    for row in item_ids["rows"]:
        compound_id = row["compound_id"]
        genbank_region_id = row["genbank_region_id"]
        if compound_id and not genbank_region_id: compound_ids.add(compound_id)
        elif genbank_region_id and not compound_id: genbank_region_ids.add(genbank_region_id)
        # Ignore rows that have both or neither

    # If somehow no targets, return empty result
    if not compound_ids and not genbank_region_ids:
        return jsonify({
            "ok": True,
            "status": "done",
            "elapsed_ms": int((time.time() - t0) * 1000),
            "result": {
                "querySettings": query_settings,
                "items": [],
            }
        }), 200
    
    subset_total_targets = len(compound_ids) + len(genbank_region_ids)

    # Get all annotation counts
    ann_full = execute_named_query(
        name="annotation_counts_full",
        params={},
        paging={ "limit": 1_000_000_000 },  # use high limit otherwise default limit of 1000 applies
        order={},
    )

    # Get annotation counts for subset
    ann_subset = execute_named_query(
        name="annotation_counts_subset",
        params={
            "compound_ids": list(compound_ids),
            "genbank_region_ids": list(genbank_region_ids),
        },
        paging={ "limit":  1_000_000_000 },  # use high limit otherwise default limit of 1000 applies
        order={},
    )

    # Total number of targets in universe (all compounds + all genbank regions)
    bg_counts = execute_named_query(
        name="target_counts",
        params={},
        paging={},
        order={},
    )
    bg_row = bg_counts["rows"][0]
    background_total_targets = int(bg_row["n_compounds"]) + int(bg_row["n_genbank_regions"])

    # Do statistical enrichment analysis (Fisher's exact test)
    full_rows = ann_full.get("rows", [])
    subset_rows = ann_subset.get("rows", [])
    enrichment_candidates: list[dict] = []

    if (
        subset_rows
        and full_rows
        and subset_total_targets > 0
        and background_total_targets > subset_total_targets
    ):
        def _ann_key(row: dict) -> tuple:
            return (row.get("scheme"), row.get("key"), row.get("value"))

        full_lookup = {_ann_key(row): row for row in full_rows}
    
        for row in subset_rows:
            key = _ann_key(row)
            base_row = full_lookup.get(key)
            if not base_row:
                continue

            subset_with = int(row.get("n_compounds", 0)) + int(row.get("n_genbank_regions", 0))
            if subset_with <= 0:
                continue

            background_with = int(base_row.get("n_compounds", 0)) + int(base_row.get("n_genbank_regions", 0))
            if background_with <= 0 or background_with < subset_with:
                continue
            
            # 2x2 per target:
            # a = subset tarets WITH this annotation
            # b = subset targets WITHOUT this annotation
            # c = background-only targets WITH this annotation
            # d = background-only targets WITHOUT this annotation
            a = subset_with
            b = subset_total_targets - a

            background_only_total = background_total_targets - subset_total_targets
            c = background_with - a
            d = background_only_total - c

            if min(a, b, c, d) < 0:
                continue

            p_value = _fisher_exact_two_sided(a, b, c, d)
    
            enrichment_candidates.append({
                "id": f"{row['scheme']}::{row['key']}::{row['value']}",
                "schema": row["scheme"],
                "key": row["key"],
                "value": row["value"],
                "subset_count": a,
                "background_count": background_with,
                "p_value": p_value,
            })

    # Multiple hypothesis correction (Benjamini-Hochberg)
    # Need to do this to take into account the number of tests performed)
    candidate_count = len(enrichment_candidates)
    if candidate_count > 0:
        # Sort by raw p-value
        sorted_indices = sorted(
            range(candidate_count),
            key=lambda idx: enrichment_candidates[idx]["p_value"]
        )

        # Calculate adjusted p-values using Benjamini-Hochberg procedure
        cumulative_min = 1.0
        adjusted_values = [1.0] * candidate_count
        for order_idx in range(candidate_count - 1, -1, -1):
            candidate_idx = sorted_indices[order_idx]
            rank = order_idx + 1
            raw_p = enrichment_candidates[candidate_idx]["p_value"]
            adjusted = (raw_p * candidate_count) / rank
            if adjusted < cumulative_min:
                cumulative_min = adjusted
            adjusted_values[candidate_idx] = cumulative_min if cumulative_min < 1.0 else 1.0
        for idx, adj_p in enumerate(adjusted_values):
            enrichment_candidates[idx]["adjusted_p_value"] = adj_p

    elapsed = int((time.time() - t0) * 1000)

    # Sort results by adjusted p-value and p-value
    items = []
    if enrichment_candidates:
        items = sorted(
            (
                {
                    "id": candidate["id"],
                    "schema": candidate["schema"],
                    "key": candidate["key"],
                    "value": candidate["value"],
                    "p_value": candidate["p_value"],
                    "adjusted_p_value": candidate.get("adjusted_p_value", candidate["p_value"]),
                }
                for candidate in enrichment_candidates
            ),
            key=lambda entry: (entry["adjusted_p_value"], entry["p_value"]),
        )

    return jsonify({
        "ok": True,
        "status": "done",
        "elapsed_ms": elapsed,
        "result": {
            "querySettings": query_settings,
            "items": items,
        }
    }), 200
