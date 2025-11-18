"""Module for loading and caching machine learning models used in the application."""

from pathlib import Path
import os

from flask import current_app
import joblib


CACHE_DIR = os.environ.get("CACHE_DIR", "/app/cache")
PARAS_MODEL_PATH = os.environ.get("PARAS_MODEL_PATH", None)
_model_cache: dict[str, object | None] = {}


# Make sure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)


def get_cache_dir() -> str:
    """
    Get the cache directory path.
    
    :return: the cache directory path
    """
    return CACHE_DIR


def get_paras_model() -> object | None:
    """
    Load and return the PARAS model from disk, caching it in memory.
    
    :return: the loaded PARAS model, or None if not found
    """
    # Check if model is already cached
    if "paras" in _model_cache:
        return _model_cache["paras"]

    # Check if model path is defined
    if PARAS_MODEL_PATH:
        # Model path is defined; attempt to load the model
        path = Path(PARAS_MODEL_PATH)
        if path.is_file():
            current_app.logger.info(f"Loading PARAS model from {path}")
            _model_cache["paras"] = joblib.load(path)
        else:
            current_app.logger.warning(f"PARAS model not found at {path}; letting BioCracker download into {CACHE_DIR}")
            _model_cache["paras"] = None
        return _model_cache["paras"]
    else:
        # Model path is not defined
        current_app.logger.warning("PARAS_MODEL_PATH not set; letting BioCracker download into CACHE_DIR")
        return None
