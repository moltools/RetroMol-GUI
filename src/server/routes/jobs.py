"""Module for defining job endpoints."""

import re
import tempfile
import time

import numpy as np
from flask import Blueprint, current_app, request, jsonify
from retromol.api import run_retromol
from retromol.fingerprint import (
    FingerprintGenerator,
    NameSimilarityConfig,
    polyketide_family_of,
    polyketide_ancestors_of,
)
from retromol.io import Input as RetroMolInput
from retromol.rules import get_path_default_matching_rules
from retromol.readout import linear_readout as retromol_linear_readout
from biocracker.antismash import parse_region_gbk_file
from biocracker.readout import NRPSModuleReadout, PKSModuleReadout, linear_readouts as biocracker_linear_readouts
from biocracker.text_mining import get_default_tokenspecs, mine_virtual_tokens

from routes.helpers import bits_to_hex, get_unique_identifier, kmerize_sequence
from routes.models_registry import get_cache_dir, get_paras_model
from routes.session_store import load_session_with_items, update_item

blp_submit_compound = Blueprint("submit_compound", __name__)
blp_submit_gene_cluster = Blueprint("submit_gene_cluster", __name__)


COLLAPSE_BY_NAME = {
    "glycosylation": ["glycosyltransferase"],
    "methylation": ["methyltransferase"],
}


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
    collapse_by_name: list[str] = list(COLLAPSE_BY_NAME.keys())
    cfg = NameSimilarityConfig(
        # family_of=polyketide_family_of,
        # family_repeat_scale=1,
        ancestors_of=polyketide_ancestors_of,
        ancestor_repeat_scale=1,
        symmetric=True,
    )
    generator = FingerprintGenerator(
        matching_rules_yaml=path_default_matching_rules,
        collapse_by_name=collapse_by_name,
        name_similarity=cfg
    )
    return generator


def _compute_compound(generator: FingerprintGenerator, smiles: str) -> tuple[list[float], list[str], list[dict]]:
    """
    Compute 512-bit fingerprint for a compound given its SMILES.

    :param generator: the fingerprint generator instance
    :param smiles: the SMILES string of the compound
    :return: tuple of (list of coverage values, list of fingerprint hex strings, list of linear readouts)
    """
    # Parse compound with RetroMol
    input_data = RetroMolInput(cid="compound", repr=smiles)
    result = run_retromol(input_data)

    # Calculate coverage
    cov = result.best_total_coverage()

    # Calculate linear readouts
    readout = retromol_linear_readout(result, require_identified=False)
    linear_readouts = []
    for level_idx, level in enumerate(readout["levels"]):
        for path_idx, path in enumerate(level["strict_paths"]):
            ms = path["ordered_monomers"]
            if len(ms) <= 2: continue  # skip too short
            ms_fwd = [
                {
                    "id": get_unique_identifier(),
                    "name": m.get("identity", "unknown"),
                    "displayName": None,
                    "smiles": m.get("smiles", None),
                }
                for m in ms
            ]
            ms_rev = list(reversed(ms_fwd))
            linear_readouts.append({
                "id": get_unique_identifier(),
                "name": f"level{level_idx}_path{path_idx}_fwd",
                "sequence": ms_fwd,
            })
            linear_readouts.append({
                "id": get_unique_identifier(),
                "name": f"level{level_idx}_path{path_idx}_rev",
                "sequence": ms_rev,
            })

    # Generate fingerprints
    fps: np.ndarray = generator.fingerprint_from_result(result, num_bits=512, counted=False) # shape [N, 512] where N>=1

    # Convert fingerprints to hex strings
    fp_hex_strings = [bits_to_hex(fp) for fp in fps] if len(fps) > 0 else [np.zeros((512,), dtype=bool)]

    return [cov for _ in range(len(fp_hex_strings))], fp_hex_strings, linear_readouts


def _compute_gene_cluster(generator: FingerprintGenerator, itemId: str, gbk_str: str) -> tuple[list[float], list[str], list[dict]]:
    """
    Dummy function to compute a 512-bit fingerprint as a hex string (128 chars).

    :param generator: the fingerprint generator instance
    :param itemId: the ID of the gene cluster item
    :param gbk_str: the GenBank file content as a string
    :return: tuple of (list of average prediction values, list of fingerprint hex strings, list of linear readouts)
    """
    # Write gbk_str to a temporary file
    with tempfile.NamedTemporaryFile(delete=True, suffix=".gbk") as temp_gbk_file:
        temp_gbk_file.write(gbk_str.encode("utf-8"))
        temp_gbk_file.flush()
        gbk_path = temp_gbk_file.name

        # Configure tokenspecs
        tokenspecs = get_default_tokenspecs()

        # Parse gene cluster file
        targets = parse_region_gbk_file(gbk_path, top_level="cand_cluster")  # 'region' or 'cand_cluster' top level

    # Generate readouts
    level = "gene"  # 'rec' or 'gene' level
    avg_pred_vals, fps, linear_readouts = [], [], []
    for target in targets:
        pred_vals = []
        raw_kmers = []

        # Mine for tokenspecs (i.e., family tokens)
        for mined_tokenspec in mine_virtual_tokens(target, tokenspecs):
            if token_spec := mined_tokenspec.get("token"):
                for token_name, values in COLLAPSE_BY_NAME.items():
                    if token_spec in values:
                        raw_kmers.append([(token_name, None)])

        # Optionally load PARAS model
        paras_model = get_paras_model()

        # Extract module kmers
        for readout in biocracker_linear_readouts(
            target,
            model=paras_model,
            cache_dir_override=get_cache_dir(),
            level=level,
            pred_threshold=0.1
        ):
            kmer, linear_readout = [], []
            for module in readout["readout"]:
                match module:
                    case PKSModuleReadout(module_type="PKS_A") as m:
                        kmer.append(("A", None))
                        pred_vals.append(1.0)
                        linear_readout.append({
                            "id": get_unique_identifier(),
                            "name": "A",
                            "displayName": None,
                            "smiles": None,
                        })
                    case PKSModuleReadout(module_type="PKS_B") as m:
                        kmer.append(("B", None))
                        pred_vals.append(1.0)
                        linear_readout.append({
                            "id": get_unique_identifier(),
                            "name": "B",
                            "displayName": None,
                            "smiles": None,
                        })
                    case PKSModuleReadout(module_type="PKS_C") as m:
                        kmer.append(("C", None))
                        pred_vals.append(1.0)
                        linear_readout.append({
                            "id": get_unique_identifier(),
                            "name": "C",
                            "displayName": None,
                            "smiles": None,
                        })
                    case PKSModuleReadout(module_type="PKS_D") as m:
                        kmer.append(("D", None))
                        pred_vals.append(1.0)
                        linear_readout.append({
                            "id": get_unique_identifier(),
                            "name": "D",
                            "displayName": None,
                            "smiles": None,
                        })
                    case NRPSModuleReadout() as m:
                        substrate_name = m.get("substrate_name", None)
                        substrate_smiles = m.get("substrate_smiles", None)
                        substrate_score = m.get("score", 0.0)
                        kmer.append((substrate_name, substrate_smiles))
                        pred_vals.append(substrate_score)
                        linear_readout.append({
                            "id": get_unique_identifier(),
                            "name": substrate_name or "unknown",
                            "displayName": None,
                            "smiles": substrate_smiles,
                        })
                    case _: raise ValueError("Unknown module readout type")

            if len(kmer) > 0:
                raw_kmers.append(kmer)

            if len(linear_readout) >= 2:  # skip too short
                linear_readouts.append({
                    "id": get_unique_identifier(),
                    "name": f"{itemId}_readout_{len(linear_readouts)+1}",
                    "sequence": linear_readout,
                })

        # Mine for kmers of lengths 1 to 3
        kmers = []
        kmer_lengths = [1, 2, 3]
        for k in kmer_lengths:
            for raw_kmer in raw_kmers:
                kmers.extend(kmerize_sequence(raw_kmer, k))

        # Generate fingerprint
        fp: np.ndarray = generator.fingerprint_from_kmers(kmers, num_bits=512, counted=False)

        # Convert to hex string
        fp_hex_string = bits_to_hex(fp)

        # Calculate average prediction value
        avg_pred_val = float(np.mean(pred_vals)) if len(pred_vals) > 0 else 0.0
        
        avg_pred_vals.append(avg_pred_val)
        fps.append(fp_hex_string)

    return avg_pred_vals, fps, linear_readouts


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
        coverages, fp_hex_strings, linear_readout = _compute_compound(generator, smiles)

        # Set final status=done and store results on this item only
        def mark_done(it: dict) -> None:
            it["name"] = name or it.get("name")
            it["smiles"] = smiles or it.get("smiles")
            it["fingerprints"] = [
                {
                    "id": get_unique_identifier(),
                    "fingerprint512": fp_hex,
                    "score": cov,
                }
                for cov, fp_hex in zip(coverages, fp_hex_strings, strict=True)
            ]
            it["primarySequences"] = linear_readout
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
        generator = _setup_fingerprint_generator()
        scores, fp_hex_strings, readout = _compute_gene_cluster(generator, item_id, file_content)
        
        # Set final status=done and store results on this item only
        def mark_done(it: dict) -> None:
            it["name"] = name or it.get("name")
            it["fileContent"] = file_content or it.get("fileContent")
            it["fingerprints"] = [
                {
                    "id": get_unique_identifier(),
                    "fingerprint512": fp_hex,
                    "score": score,
                }
                for idx, (score, fp_hex) in enumerate(zip(scores, fp_hex_strings, strict=True), start=1)
            ]
            it["primarySequences"] = readout
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
