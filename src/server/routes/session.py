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

        - for existing items (same id): update fields IN PLACE, but do NOT override
          status/errorMessage/updatedAt (these are owned by the job backend)
        - for new items: accept them as-is
        - items that are missing in the payload are treated as deleted
    
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

    old_items_list = old_session.get("items", []) or []
    new_items_list = new_session.get("items", []) or []

    # Index existing items by id
    old_by_id: dict[str, dict] = {item.get("id"): item for item in old_items_list if item.get("id")}
    merged_items: list[dict] = []

    for new_item in new_items_list:
        item_id = new_item.get("id")
        if not item_id:
            # No id? Just accept as-is (or skip, your choice)
            merged_items.append(new_item)
            continue

        old_item = old_by_id.get(item_id)

        if old_item is None:
            # Truly new item: accept the client version
            merged_items.append(new_item)
        else:
            # Update existing item IN PLACE, BUT keep status fields from server
            # If we don't update in place, references held elsewhere may break 
            # and UI will show stale date/endless 'processing' state for an import
            for key, value in new_item.items():
                if key in ("status", "errorMessage", "updatedAt"):
                    # Do not overwrite job-owned fields
                    continue
                old_item[key] = value

            merged_items.append(old_item)

    # Items omitted by client are considered deleted: we do NOT re-add leftovers
    # from old_by_id here.

    old_session["items"] = merged_items
    store[session_id] = old_session

    return jsonify({"sessionId": session_id}), 200
