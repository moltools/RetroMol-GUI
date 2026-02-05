"""Helpers for generating GUIDs."""

import uuid


def generate_guid() -> str:
    """
    Generate a new GUID.
    
    :return: a string representation of a new GUID
    """
    return str(uuid.uuid4())
