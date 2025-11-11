"""Module for defining session endpoints."""

from flask import Blueprint, request, current_app


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
    new_session = request.json.get("session")
    session_id = new_session.get("sessionId")
    if session_id in current_app.config["SESSIONS"]:
        return {"error": "Session ID already exists"}, 400
    current_app.config["SESSIONS"][session_id] = new_session
    return {"sessionId": session_id}, 200


@blp_delete_session.route("/api/deleteSession", methods=["POST"])
def delete_session() -> tuple[dict[str, str], int]:
    """
    Delete a session.
    
    :return: A tuple containing a dictionary with the session ID and an HTTP status code.
    """
    session_id = request.json.get("sessionId")
    session = current_app.config["SESSIONS"].get(session_id)
    if not session:
        return {"error": "Session not found"}, 404
    del current_app.config["SESSIONS"][session_id]
    return {"sessionId": session_id}, 200


@blp_get_session.route("/api/getSession", methods=["POST"])
def get_session() -> tuple[dict[str, str], int]:
    """
    Get a session.
    
    :return: A tuple containing a dictionary with the session data and an HTTP status code.
    """
    session_id = request.json.get("sessionId")
    session = current_app.config["SESSIONS"].get(session_id)
    if not session:
        return {"error": "Session not found"}, 404
    return {"sessionId": session["sessionId"], "session": session}, 200


@blp_save_session.route("/api/saveSession", methods=["POST"])
def save_session() -> tuple[dict[str, str], int]:
    """
    Save a session.
    
    :return: A tuple containing a dictionary with the session ID and an HTTP status code.
    """
    new_session = request.json.get("session")
    session_id = new_session.get("sessionId")
    old_session = current_app.config["SESSIONS"].get(session_id)
    if not old_session:
        return {"error": "Session not found"}, 404
    current_app.config["SESSIONS"][session_id] = new_session
    return {"sessionId": session_id}, 200
