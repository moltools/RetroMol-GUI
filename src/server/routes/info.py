"""Endpoint to get detailed information about compounds and clusters."""

from flask import Blueprint, jsonify, request
from routes.database import SessionLocal
from bionexus.db.models import Compound, CandidateCluster


blp_item_info = Blueprint("item_info", __name__)


@blp_item_info.get("/api/itemInfo")
def get_item_info():
    kind = (request.args.get("kind") or "").strip()
    db_id_raw = (request.args.get("db_id") or "").strip()

    if not kind or not db_id_raw:
        return jsonify({"ok": False, "error": "Missing kind or db_id"}), 400

    try:
        db_id = int(db_id_raw)
    except ValueError:
        return jsonify({"ok": False, "error": "db_id must be an integer"}), 400

    with SessionLocal() as session:
        if kind == "compound":
            obj = session.get(Compound, db_id)
        elif kind == "cluster":
            obj = session.get(CandidateCluster, db_id)
        else:
            return jsonify({"ok": False, "error": "Invalid kind"}), 400

        if obj is None:
            return jsonify({"ok": False, "error": "Not found"}), 404
        
        refs = obj.references
        anns = obj.annotations

        references = [
            {
                "name": r.name,
                "database_name": r.database_name,
                "database_identifier": r.database_identifier,
            }
            for r in refs
        ]

        annotations = [
            {"scheme": a.scheme, "key": a.key, "value": a.value}
            for a in anns
        ]

    return jsonify({"ok": True, "references": references, "annotations": annotations}), 200
