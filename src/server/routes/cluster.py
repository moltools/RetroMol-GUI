"""Blueprints for cluster-related API endpoints."""

import time
import tempfile
import os

from flask import Blueprint, current_app, jsonify, request

from biocracker.io.readers import load_regions
from biocracker.io.options import AntiSmashOptions
from biocracker.inference.registry import register_domain_model, register_gene_model
from biocracker.pipelines.annotate_region import annotate_region
from biocracker.query.modules import NRPSModule, PKSModule, linear_readout as biocracker_linear_readout

from routes.session_store import load_session_with_items, update_item
from routes.models_registry import get_paras_model, get_pfam_models

blp_submit_cluster = Blueprint("submit_cluster", __name__)


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


@blp_submit_cluster.post("/api/submitCluster")
def submit_cluster():
    """
    Submit a cluster for processing.
    """
    payload = request.get_json(force=True) or {}
    session_id = payload.get("sessionId")
    item_id = payload.get("itemId")
    name = payload.get("name")
    file_content = payload.get("fileContent")

    current_app.logger.info(f"submit_cluster called: session_id={session_id} item_id={item_id}")

    if not session_id or not item_id:
        current_app.logger.warning("submit_cluster: missing sessionId or itemId")
        return jsonify({"error": "Missing sessionId or itemId"}), 400
    
    # Validate session + item exists and kind is correct
    full_sess = load_session_with_items(session_id)
    if full_sess is None:
        current_app.logger.warning(f"submit_cluster: session not found: {session_id}")
        return jsonify({"error": "Session not found"}), 404
    
    item = next((it for it in full_sess.get("items", []) if it.get("id") == item_id), None)
    if item is None:
        current_app.logger.warning(f"submit_cluster: item not found: {item_id}")
        return jsonify({"error": "Item not found"}), 404
    
    if item.get("kind") != "cluster":
        current_app.logger.warning(f"submit_cluster: wrong kind={item.get('kind')}")
        return jsonify({"error": "Item is not a cluster"}), 400

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
        current_app.logger.warning(f"submit_cluster: failed to mark item as processing: {item_id}")
        return jsonify({"error": "Item not found during update"}), 404
    
    tmp_path = None
    try:
        options = AntiSmashOptions(readout_level="cand_cluster")

        paras_model = get_paras_model()
        if paras_model:
            register_domain_model(paras_model)
        
        pfam_models = get_pfam_models()
        print(f"PFAM models loaded: {pfam_models}")
        for pfam_model in pfam_models or []:
            register_gene_model(pfam_model)

        # Heavy work
        # Write file content to a temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gbk", delete=True) as tmp:
            tmp.write(file_content or "")
            tmp.flush()
            tmp_path = tmp.name
            regions = load_regions(tmp_path, options=options)

        # TODO: only saving readout of last candidate cluster found... need to keep all of them and create individual items for each
        for region in regions:
            annotate_region(region)
            readout = biocracker_linear_readout(region)

            module_scores: list[float] = []
            for m in readout.modules:
                if isinstance(m, NRPSModule):
                    if s := m.substrate:
                        module_scores.append(s.score)
                    else:
                        module_scores.append(0.0)
                elif isinstance(m, PKSModule):
                    # Readout from antiSMASH GBK is always confident
                    module_scores.append(1.0)
                else:
                    current_app.logger.warning(f"submit_cluster: unknown module type: {type(m)}")
                    module_scores.append(0.0)
        
            score: float = sum(module_scores) / len(module_scores) if module_scores else 0.0
            result_as_dict: dict = readout.to_dict()

        # Set final status=done and store results on this item only
        def mark_done(it: dict) -> None:
            it["name"] = name or it.get("name")
            it["fileContent"] = file_content or it.get("fileContent")
            it["score"] = score
            it["payload"] = result_as_dict
            _set_item_status_inplace(it, "done")

        update_item(session_id, item_id, mark_done)

    except Exception as e:
        current_app.logger.exception(f"submit_cluster: error for item_id={item_id}")

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
    current_app.logger.info(f"submit_cluster: finished item_id={item_id} elapsed_ms={elapsed}")

    return jsonify({
        "ok": True,
        "status": "done",
        "elapsed_ms": elapsed,
    }), 200
