"""Module for defining job endpoints."""

import hashlib
import time

import numpy as np
from flask import Blueprint, current_app, request, jsonify
from retromol.api import run_retromol
from retromol.fingerprint import (
    FingerprintGenerator,
    NameSimilarityConfig,
    polyketide_family_of
)
from retromol.io import Input as RetroMolInput
from retromol.rules import get_path_default_matching_rules

from routes.helpers import bits_to_hex
from routes.session_store import load_session_with_items, update_item


blp_submit_compound = Blueprint("submit_compound", __name__)
blp_submit_gene_cluster = Blueprint("submit_gene_cluster", __name__)


def _set_item_status_inplace(item: dict, status: str, error_message: str | None = None) -> None:
    """
    Update the status and error message of an item in place.

    :param item: the item dictionary to update
    :param status: the new status string
    :param error_message: optional error message string
    """
    item["status"] = status
    item["updatedAt"] = int(time.time() * 1000)

    if error_message is not None:
        item["errorMessage"] = error_message
    else:
        if "errorMessage" in item:
            item["errorMessage"] = None


def _setup_fingerprint_generator() -> FingerprintGenerator:
    """
    Setup and return a FingerprintGenerator instance.

    :return: FingerprintGenerator instance
    """
    path_default_matching_rules = get_path_default_matching_rules()
    collapse_by_name = ["glycosylation", "methylation"]
    cfg = NameSimilarityConfig(family_of=polyketide_family_of, symmetric=True, family_repeat_scale=1)
    generator = FingerprintGenerator(
        matching_rules_yaml=path_default_matching_rules,
        collapse_by_name=collapse_by_name,
        name_similarity=cfg
    )
    return generator


def _compute_fingerprint_512_compound(generator: FingerprintGenerator, smiles: str) -> tuple[float, str]:
    """
    Compute 512-bit fingerprint for a compound given its SMILES.

    :param generator: the fingerprint generator instance
    :param smiles: the SMILES string of the compound
    :return: tuple of (coverage, list of fingerprint hex strings)
    """
    input_data = RetroMolInput(cid="compound", repr=smiles)
    result = run_retromol(input_data)
    cov = result.best_total_coverage()
    fps: np.ndarray = generator.fingerprint_from_result(result, num_bits=512, counted=False) # shape [N, 512] where N>=1
    fp: np.ndarray = fps[0] if len(fps) > 0 else np.zeros((512,), dtype=bool)
    fp_hex_string = bits_to_hex(fp)
    return cov, fp_hex_string


def _compute_fingerprint_512_gene_cluster() -> str:
    """
    Dummy function to compute a 512-bit fingerprint as a hex string (128 chars).

    :return: a dummy fingerprint string
    """
    random_string = str(time.time())
    h = hashlib.sha512(random_string.encode("utf-8")).hexdigest()
    assert len(h) == 128, "Fingerprint length mismatch"
    return h


@blp_submit_compound.post("/api/submitCompound")
def submit_compound() -> tuple[dict[str, str], int]:
    """
    Endpoint to submit a compound for processing.

    Expected JSON body:
      - sessionId: str
      - itemId: str
      - name: str
      - smiles: str

    :return: a tuple containing a JSON response and HTTP status code
    """
    payload = request.get_json(force=True) or {}

    session_id = payload.get("sessionId")
    item_id = payload.get("itemId")
    name = payload.get("name")
    smiles = payload.get("smiles")

    current_app.logger.info(f"submit_compound called: session_id={session_id} item_id={item_id}")

    if not session_id or not item_id:
        current_app.logger.warning("submit_compound: missing sessionId or itemId")
        return jsonify({"error": "Missing sessionId or itemId"}), 400
    
    # Validate session + item exists and kind is correct
    full_sess = load_session_with_items(session_id)
    if full_sess is None:
        current_app.logger.warning(f"submit_compound: session not found: {session_id}")
        return jsonify({"error": "Session not found"}), 404
    
    item = next((it for it in full_sess.get("items", []) if it.get("id") == item_id), None)
    if item is None:
        current_app.logger.warning(f"submit_compound: item not found: {item_id}")
        return jsonify({"error": "Item not found"}), 404
    
    if item.get("kind") != "compound":
        current_app.logger.warning(f"submit_compound: wrong kind={item.get('kind')}")
        return jsonify({"error": "Item is not a compound"}), 400

    t0 = time.time()

    # Set status=processing early on this item only
    def mark_processing(it: dict) -> None:
        """
        Update item details and mark as processing.

        :param it: the item dictionary to update
        """
        it["name"] = name or it.get("name")
        it["smiles"] = smiles or it.get("smiles")
        _set_item_status_inplace(it, "processing")

    ok = update_item(session_id, item_id, mark_processing)
    if not ok:
        current_app.logger.warning(f"submit_compound: failed to mark item as processing: {item_id}")
        return jsonify({"error": "Item not found during update"}), 404
    
    try:
        # Heavy work
        generator = _setup_fingerprint_generator()
        coverage, fp_hex_string = _compute_fingerprint_512_compound(generator, smiles)

        # Set final status=done and store results on this item only
        def mark_done(it: dict) -> None:
            it["name"] = name or it.get("name")
            it["smiles"] = smiles or it.get("smiles")
            it["fingerprint512"] = fp_hex_string
            it["coverage"] = coverage
            _set_item_status_inplace(it, "done")

        update_item(session_id, item_id, mark_done)

    except Exception as e:
        current_app.logger.exception(f"submit_compound: error for item_id={item_id}")

        def mark_error(it: dict) -> None:
            _set_item_status_inplace(it, "error", error_message=str(e))

        update_item(session_id, item_id, mark_error)

        elapsed = int((time.time() - t0) * 1000)
        return jsonify({
            "ok": False,
            "status": "error",
            "elapsed_ms": elapsed,
            "error": str(e),
        }), 500
    
    elapsed = int((time.time() - t0) * 1000)
    current_app.logger.info(f"submit_compound: finished item_id={item_id} elapsed_ms={elapsed}")

    return jsonify({
        "ok": True,
        "status": "done",
        "elapsed_ms": elapsed,
    }), 200


@blp_submit_gene_cluster.post("/api/submitGeneCluster")
def submit_gene_cluster()  -> tuple[dict[str, str], int]:
    """
    Endpoint to submit a gene cluster for processing.

    Expected JSON body:
      - sessionId: str
      - itemId: str
      - name: str
      - fileContent: str

    :return: a tuple containing a JSON response and HTTP status code
    """
    payload = request.get_json(force=True) or {}

    session_id = payload.get("sessionId")
    item_id = payload.get("itemId")
    name = payload.get("name")
    file_content = payload.get("fileContent")

    current_app.logger.info(f"submit_gene_cluster called: session_id={session_id} item_id={item_id}")

    if not session_id or not item_id:
        current_app.logger.warning("submit_gene_cluster: missing sessionId or itemId")
        return jsonify({"error": "Missing sessionId or itemId"}), 400
    
    # Validate session + item exists and kind is correct
    full_sess = load_session_with_items(session_id)
    if full_sess is None:
        current_app.logger.warning(f"submit_gene_cluster: session not found: {session_id}")
        return jsonify({"error": "Session not found"}), 404
    
    item = next((it for it in full_sess.get("items", []) if it.get("id") == item_id), None)
    if item is None:
        current_app.logger.warning(f"submit_gene_cluster: item not found: {item_id}")
        return jsonify({"error": "Item not found"}), 404
    
    if item.get("kind") != "gene_cluster":
        current_app.logger.warning(f"submit_gene_cluster: wrong kind={item.get('kind')}")
        return jsonify({"error": "Item is not a gene cluster"}), 400

    t0 = time.time()

    # Set status=processing early on this item only
    def mark_processing(it: dict) -> None:
        """
        Update item details and mark as processing.

        :param it: the item dictionary to update
        """
        it["name"] = name or it.get("name")
        it["fileContent"] = file_content or it.get("fileContent")
        _set_item_status_inplace(it, "processing")
    
    ok = update_item(session_id, item_id, mark_processing)
    if not ok:
        current_app.logger.warning(f"submit_gene_cluster: failed to mark item as processing: {item_id}")
        return jsonify({"error": "Item not found during update"}), 404

    try:
        # Heavy work
        fp_hex_string = _compute_fingerprint_512_gene_cluster()
        
        # Set final status=done and store results on this item only
        def mark_done(it: dict) -> None:
            it["name"] = name or it.get("name")
            it["fileContent"] = file_content or it.get("fileContent")
            it["fingerprint512"] = fp_hex_string
            _set_item_status_inplace(it, "done")

        update_item(session_id, item_id, mark_done)

    except Exception as e:
        current_app.logger.exception(f"submit_gene_cluster: error for item_id={item_id}")

        def mark_error(it: dict) -> None:
            _set_item_status_inplace(it, "error", error_message=str(e))
        
        update_item(session_id, item_id, mark_error)
        
        elapsed = int((time.time() - t0) * 1000)
        return jsonify({
            "ok": False,
            "status": "error",
            "elapsed_ms": elapsed,
            "error": str(e),
        }), 500
    
    elapsed = int((time.time() - t0) * 1000)
    current_app.logger.info(f"submit_gene_cluster: finished item_id={item_id} elapsed_ms={elapsed}")

    return jsonify({
        "ok": True,
        "status": "done",
        "elapsed_ms": elapsed,
    }), 200
