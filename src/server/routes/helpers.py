"""Module contains helper functions for various endpoints."""

from flask import current_app

from routes.config import SESSIONS_KEY


def _get_session_store() -> dict:
    """
    Retrieve the session store from the application configuration.

    :return: dictionary representing the session store
    """
    store = current_app.config.get(SESSIONS_KEY)
    if store is None:
        store = {}
        current_app.config[SESSIONS_KEY] = store
    return store
