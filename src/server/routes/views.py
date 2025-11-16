"""Module for handling view requests."""

import time

import numpy as np
from flask import Blueprint, current_app, request, jsonify
from sklearn.decomposition import PCA

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

    current_app.logger.info(f"get_embedding_space called: session_id={session_id} items_count={len(items)}")

    if not session_id or not items:
        current_app.logger.warning("get_embedding_space: missing sessionId or items")
        return jsonify({"error": "Missing sessionId or items"}), 400
    
    # Make sure every item has an ID
    item = next((it for it in items if "id" not in it), None)
    if item is not None:
        current_app.logger.warning("get_embedding_space: one or more items missing 'id'")
        return jsonify({"error": "One or more items missing 'id'"}), 400
    
    # Make sure every item has a fingerprint512
    item = next((it for it in items if "fingerprint512" not in it), None)
    if item is not None:
        current_app.logger.warning("get_embedding_space: one or more items missing 'fingerprint512'")
        return jsonify({"error": "One or more items missing 'fingerprint512'"}), 400
    
    t0 = time.time()

    try:
        # Decode fingerprints
        fps = np.array([hex_to_bits(item["fingerprint512"]) for item in items])

        # Perform PCA to reduce to 2D
        pca = PCA(n_components=2)
        reduced = pca.fit_transform(fps)

        points = [
            {
                "id": item.get("id"),
                "x": reduced[i, 0],
                "y": reduced[i, 1]
            } for i, item in enumerate(items)
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
