"""Module for defining session endpoints."""

import time

from flask import Blueprint, request, jsonify

from routes.helpers import _get_session_store


blp_create_session = Blueprint("create_session", __name__)
blp_delete_session = Blueprint("delete_session", __name__)
blp_get_session = Blueprint("get_session", __name__)
blp_save_session = Blueprint("save_session", __name__)


@blp_create_session.route("/api/createSession", methods=["POST"])
def create_session() -> tuple[dict[str, str], int]:
    """
    Create a new session.
    
    :return: A tuple containing a dictionary with the session ID and an HTTP status code.
    """
    payload = request.get_json(force=True) or {}
    new_session = payload.get("session")

    if not isinstance(new_session, dict):
        return {"error": "Missing or invalid session"}, 400
    
    session_id = new_session.get("sessionId")
    if not isinstance(session_id, str) or not session_id:
        return {"error": "Missing or invalid sessionId"}, 400
    
    store = _get_session_store()
    if session_id in store:
        return {"error": "Session already exists"}, 400
    
    # Basic normalization for safety
    created = new_session.get("created")
    if not isinstance(created, (int, float)):
        created = int(time.time() * 1000)
    else:
        created = int(created)

    items = new_session.get("items", [])
    if not isinstance(items, list):
        items = []

    new_session["created"] = created
    new_session["items"] = items

    store[session_id] = new_session

    return jsonify({"sessionId": session_id}), 200


@blp_delete_session.route("/api/deleteSession", methods=["POST"])
def delete_session() -> tuple[dict[str, str], int]:
    """
    Delete a session.
    
    :return: A tuple containing a dictionary with the session ID and an HTTP status code.
    """
    payload = request.get_json(force=True) or {}
    session_id = payload.get("sessionId")

    if not isinstance(session_id, str) or not session_id:
        return {"error": "Missing or invalid sessionId"}, 400

    store = _get_session_store()
    if session_id not in store:
        return {"error": "Session not found"}, 404
    
    del store[session_id]
    return jsonify({"sessionId": session_id}), 200


@blp_get_session.route("/api/getSession", methods=["POST"])
def get_session() -> tuple[dict[str, str], int]:
    """
    Get a session.
    
    :return: A tuple containing a dictionary with the session data and an HTTP status code.
    """
    payload = request.get_json(force=True) or {}
    session_id = payload.get("sessionId")

    if not isinstance(session_id, str) or not session_id:
        return {"error": "Missing or invalid sessionId"}, 400

    store = _get_session_store()
    session = store.get(session_id)
    if session is None:
        return {"error": "Session not found"}, 404
    
    # Ensure items is always a list so the frontend + Zod don't complain
    items = session.get("items", [])
    if not isinstance(items, list):
        items = []
        session["items"] = items

    return jsonify({"sessionId": session["sessionId"], "session": session}), 200


@blp_save_session.route("/api/saveSession", methods=["POST"])
def save_session() -> tuple[dict[str, str], int]:
    """
    Save/merge a session from the client.

    Client owns: which items exist and their user-editable fields
    Server owns: what state those items are in (status, timestamps, errors)
    
    :return: A tuple containing a dictionary with the session ID and an HTTP status code.
    """
    payload = request.get_json(force=True) or {}
    new_session = payload.get("session")

    if not isinstance(new_session, dict):
        return {"error": "Missing or invalid session"}, 400
    
    session_id = new_session.get("sessionId")
    if not session_id:
        return {"error": "Missing sessionId"}, 400
    
    # Make sure SESSIONS exists
    store = _get_session_store()

    old_session = store.get(session_id)
    if not old_session:
        return {"error": "Session not found"}, 404
    
    # Merge top-level fields
    old_session["sessionId"] = new_session["sessionId"]
    old_session["created"] = new_session.get("created", old_session.get("created"))

    # Merge items
    incoming_items = new_session.get("items", []) or []
    existing_items = old_session.get("items", []) or []

    # Index existing items by id
    existing_by_id: dict[str, dict] = {}
    for item in existing_items:
        item_id = item.get("id")
        if item_id:
            existing_by_id[item_id] = item

    merged_items: list[dict] = []

    for inc in incoming_items:
        item_id = inc.get("id")
        if not item_id:
            continue

        srv = existing_by_id.get(item_id)

        if srv is None:
            # Brand new item from the client -> accept it as-is
            merged_items.append(inc)
            continue

        # Start from server version so we keep status/updatedAt/errorMessage
        merged = dict(srv)

        # Client-owned fields
        merged["kind"] = inc.get("kind", merged.get("kind"))

        if merged["kind"] == "compound":
            merged["name"] = inc.get("name", merged.get("name"))
            merged["smiles"] = inc.get("smiles", merged.get("smiles"))
        elif merged["kind"] == "gene_cluster":
            merged["fileName"] = inc.get("fileName", merged.get("fileName"))
            merged["fileContent"] = inc.get("fileContent", merged.get("fileContent"))

        # Server-owned fields (status, updatedAt, errorMessage) are preserved
        # even if the client sent different values, we ignore them

        merged_items.append(merged)

    old_session["items"] = merged_items
    store[session_id] = old_session

    return jsonify({"sessionId": session_id}), 200
