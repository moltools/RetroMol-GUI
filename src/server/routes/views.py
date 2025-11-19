"""Module for handling view requests."""

import time

import numpy as np
from flask import Blueprint, current_app, request, jsonify
import umap

from routes.helpers import hex_to_bits


blp_get_embedding_space = Blueprint("get_embedding_space", __name__)


@blp_get_embedding_space.post("/api/getEmbeddingSpace")
def get_embedding_space() -> tuple[dict[str, str], int]:
    """
    Handle POST requests to retrieve embedding space information.

    :return: a tuple containing an empty dictionary and HTTP status code 200
    """
    payload = request.get_json(force=True) or {}

    session_id = payload.get("sessionId")
    items = payload.get("items", [])
    jitter = True

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
