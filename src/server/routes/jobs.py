"""Module for defining job endpoints."""

import hashlib
import time
from random import random

from flask import Blueprint, request, jsonify

from routes.helpers import _get_session_store

blp_submit_compound = Blueprint("submit_compound", __name__)
blp_submit_gene_cluster = Blueprint("submit_gene_cluster", __name__)


def _find_session(session_id: str) -> dict | None:
    """
    Find and return a session by its ID.

    :param session_id: the ID of the session to find
    :return: the session dictionary if found, else None
    """
    sessions = _get_session_store()
    return sessions.get(session_id)


def _find_item(session: dict, item_id: str) -> dict | None:
    """
    Find and return an item by its ID within a given session.

    :param session: the session dictionary containing items
    :param item_id: the ID of the item to find
    :return: the item dictionary if found, else None
    """
    items = session.get("items", [])
    for item in items:
        if item.get("id") == item_id:
            return item
    return None


def _set_item_status(item: dict, status: str, error_message: str | None = None) -> None:
    """
    Update the status and error message of a given item.

    :param item: the item dictionary to update
    :param status: the new status to set
    :param error_message: optional error message to set
    .. note:: this function modifies the item in place.
    """
    item["status"] = status

    # Store ms since epoch; matches frontend convention
    item["updatedAt"] = int(time.time() * 1000)

    if error_message is not None:
        item["errorMessage"] = error_message
    else:
        # Clear old errors if any
        if "errorMessage" in item:
            item["errorMessage"] = None


def _compute_fingerprint_512() -> str:
    """
    Dummy function to compute a 512-bit fingerprint as a hex string (128 chars).

    :return: a dummy fingerprint string
    """
    random_string = str(time.time())
    h = hashlib.sha512(random_string.encode("utf-8")).hexdigest()
    assert len(h) == 128, "Fingerprint length mismatch"
    return h


@blp_submit_compound.post("/api/submitCompound")
def submit_compound():
    """
    Endpoint to submit a compound for processing.

    Expected JSON body:
      - sessionId: str
      - itemId: str
      - name: str
      - smiles: str

    :return: JSON response
    """
    payload = request.get_json(force=True) or {}

    session_id = payload.get("sessionId")
    item_id = payload.get("itemId")
    name = payload.get("name")
    smiles = payload.get("smiles")

    if not session_id or not item_id:
        return jsonify({"error": "Missing sessionId or itemId"}), 400
    
    sess = _find_session(session_id)
    if sess is None:
        return jsonify({"error": "Session not found"}), 404
    
    item = _find_item(sess, item_id)
    if item is None:
        return jsonify({"error": "Item not found"}), 404
    
    if item.get("kind") != "compound":
        return jsonify({"error": "Item is not a compound"}), 400

    t0 = time.time()

    # TODO: update item details; include more processing in future
    item["name"] = name or item.get("name")
    item["smiles"] = smiles or item.get("smiles")

    # Mark as processing before doing any work
    _set_item_status(item, "processing")
    
    try:
        # Calculate fingerprint
        fp_hex = _compute_fingerprint_512()
        item["fingerprint512"] = fp_hex
        item["coverage"] = round(random(), 2)  # dummy coverage value between 0 and 1

        # Finished successfully
        _set_item_status(item, "done")
    except Exception as e:
        _set_item_status(item, "error", error_message=str(e))
        elapsed = int((time.time() - t0) * 1000)
        return jsonify({
            "ok": False,
            "status": "error",
            "elapsed_ms": elapsed,
            "error": str(e),
        }), 500
    
    elapsed = int((time.time() - t0) * 1000)
    return jsonify({
        "ok": True,
        "status": "done",
        "elapsed_ms": elapsed,
    }), 200


@blp_submit_gene_cluster.post("/api/submitGeneCluster")
def submit_gene_cluster():
    """
    Endpoint to submit a gene cluster for processing.

    Expected JSON body:
      - sessionId: str
      - itemId: str
      - name: str
      - fileContent: str

    :return: JSON response
    """
    payload = request.get_json(force=True) or {}

    session_id = payload.get("sessionId")
    item_id = payload.get("itemId")
    name = payload.get("name")
    file_content = payload.get("fileContent")

    if not session_id or not item_id:
        return jsonify({"error": "Missing sessionId or itemId"}), 400
    
    sess = _find_session(session_id)
    if sess is None:
        return jsonify({"error": "Session not found"}), 404
    
    item = _find_item(sess, item_id)
    if item is None:
        return jsonify({"error": "Item not found"}), 404
    
    if item.get("kind") != "gene_cluster":
        return jsonify({"error": "Item is not a gene cluster"}), 400

    t0 = time.time()

    # TODO: update item details; include more processing in future
    item["name"] = name or item.get("name")
    item["fileContent"] = file_content or item.get("fileContent")

    # Mark as processing before doing any work
    _set_item_status(item, "processing")
    
    try:
        # Calculate fingerprint
        fp_hex = _compute_fingerprint_512()
        item["fingerprint512"] = fp_hex
        
        # Finished successfully
        _set_item_status(item, "done")
    except Exception as e:
        _set_item_status(item, "error", error_message=str(e))
        elapsed = int((time.time() - t0) * 1000)
        return jsonify({
            "ok": False,
            "status": "error",
            "elapsed_ms": elapsed,
            "error": str(e),
        }), 500
    
    elapsed = int((time.time() - t0) * 1000)
    return jsonify({
        "ok": True,
        "status": "done",
        "elapsed_ms": elapsed,
    }), 200
