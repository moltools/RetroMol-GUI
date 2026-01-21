"""Query service API endpoint."""

from flask import Blueprint, current_app, request, jsonify

from routes.session_store import load_item
from routes.query.pipeline import cross_modal_retrieval
from routes.query.enrichment import enrichment_study
from routes.query.align import MSAResult


blp_query_item = Blueprint("query_item", __name__)


@blp_query_item.get("/api/queryItem")
def query_item():
    """
    Endpoint to query a specific item (cluster or compound).
    """
    session_id = request.args.get("sessionId", "").strip()
    item_id = request.args.get("itemId", "").strip()
    if not session_id:
        return jsonify({"error": "Missing sessionId"}), 400
    if not item_id:
        return jsonify({"error": "Missing itemId"}), 400
    
    query_against_clusters = request.args.get("queryAgainstClusters", "true").lower() == "true"
    query_against_compounds = request.args.get("queryAgainstCompounds", "true").lower() == "true"
    current_app.logger.debug(f"query_against_compounds: {query_against_compounds}")
    current_app.logger.debug(f"query_against_clusters: {query_against_clusters}")
    if not query_against_clusters and not query_against_compounds:
        return jsonify({"error": "At least one of queryAgainstClusters or queryAgainstCompounds must be true"}), 400
    
    # Retrieve item from session store
    current_app.logger.info(f"Retrieving query item: session_id={session_id} item_id={item_id}")
    item = load_item(session_id, item_id)
    if item is None:
        return jsonify({"error": "Item not found"}), 404
    current_app.logger.info(f"Loaded item for querying: session_id={session_id} item_id={item_id} kind={item.get('kind')}")
    
    payload_type = item.get("kind", None)
    payload_blob = item.get("payload", None)
    if not payload_type or payload_type not in ["cluster", "compound"]:
        current_app.logger.error(f"Invalid item kind for querying: {payload_type}")
        return jsonify({"error": "Invalid item kind"}), 400
    if not payload_blob:
        current_app.logger.error("Missing item payload for querying")
        return jsonify({"error": "Missing item payload"}), 400
    
    try:
        current_app.logger.info(f"Starting cross-modal retrieval for item_id={item_id}")
        msa_result: MSAResult = cross_modal_retrieval(
            payload_type=payload_type,
            payload_blob=payload_blob,
            query_against_clusters=query_against_clusters,
            query_against_compounds=query_against_compounds,
        )
    except ValueError as e:
        current_app.logger.error(f"Error during cross-modal retrieval: {e}")
        return jsonify({"error": str(e)}), 500
    
    return jsonify(msa_result.to_dict()), 200


@blp_query_item.get("/api/enrichment")
def enrichment():
    """
    Endpoint to run annotation enrichment on nearest neighbors.
    """
    session_id = request.args.get("sessionId", "").strip()
    item_id = request.args.get("itemId", "").strip()
    if not session_id:
        return jsonify({"error": "Missing sessionId"}), 400
    if not item_id:
        return jsonify({"error": "Missing itemId"}), 400

    threshold_raw = request.args.get("thresholdPct", "80").strip()
    try:
        threshold_pct = float(threshold_raw)
    except ValueError:
        return jsonify({"error": "thresholdPct must be a number"}), 400
    if threshold_pct < 0 or threshold_pct > 100:
        return jsonify({"error": "thresholdPct must be between 0 and 100"}), 400

    query_against_clusters = request.args.get("queryAgainstClusters", "true").lower() == "true"
    query_against_compounds = request.args.get("queryAgainstCompounds", "true").lower() == "true"
    if not query_against_clusters and not query_against_compounds:
        return jsonify({"error": "At least one of queryAgainstClusters or queryAgainstCompounds must be true"}), 400

    # Retrieve item from session store
    current_app.logger.info(f"Retrieving enrichment item: session_id={session_id} item_id={item_id}")
    item = load_item(session_id, item_id)
    if item is None:
        return jsonify({"error": "Item not found"}), 404
    current_app.logger.info(
        f"Loaded item for enrichment: session_id={session_id} item_id={item_id} kind={item.get('kind')}"
    )

    payload_type = item.get("kind", None)
    payload_blob = item.get("payload", None)
    if not payload_type or payload_type not in ["cluster", "compound"]:
        current_app.logger.error(f"Invalid item kind for enrichment: {payload_type}")
        return jsonify({"error": "Invalid item kind"}), 400
    if not payload_blob:
        current_app.logger.error("Missing item payload for enrichment")
        return jsonify({"error": "Missing item payload"}), 400

    try:
        current_app.logger.info(f"Starting enrichment study for item_id={item_id}")
        result = enrichment_study(
            payload_type=payload_type,
            payload_blob=payload_blob,
            query_against_clusters=query_against_clusters,
            query_against_compounds=query_against_compounds,
            threshold_pct=threshold_pct,
        )
    except ValueError as e:
        current_app.logger.error(f"Error during enrichment study: {e}")
        return jsonify({"error": str(e)}), 500

    return jsonify(result), 200
