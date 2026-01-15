"""Query service API endpoint."""

from flask import Blueprint, current_app, request, jsonify

from routes.session_store import load_item
from routes.query.pipeline import cross_modal_retrieval


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
    item = load_item(session_id, item_id)
    if item is None:
        return jsonify({"error": "Item not found"}), 404
    
    payload_type = item.get("kind", None)
    payload_blob = item.get("payload", None)
    if not payload_type or payload_type not in ["cluster", "compound"]:
        return jsonify({"error": "Invalid item kind"}), 400
    if not payload_blob:
        return jsonify({"error": "Missing item payload"}), 400
    
    try:
        msa_result = cross_modal_retrieval(
            payload_type=payload_type,
            payload_blob=payload_blob,
            query_against_clusters=query_against_clusters,
            query_against_compounds=query_against_compounds,
        )
    except ValueError as e:
        current_app.logger.error(f"error during cross-modal retrieval: {e}")
        return jsonify({"error": str(e)}), 500
    
    return jsonify(msa_result), 200
