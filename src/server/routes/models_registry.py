"""Module for loading and caching machine learning models used in the application."""

from pathlib import Path
import os

from flask import current_app

from biocracker.inference.model_paras import ParasModel
from biocracker.inference.model_pfam import PfamModel


CACHE_DIR = os.environ.get("CACHE_DIR", "/app/cache")
_model_cache: dict[str, object | None] = {}

PARAS_MODEL_PATH = os.environ.get("PARAS_MODEL_PATH", None)
PFAM_HMM_DIR_PATH = os.environ.get("PFAM_HMM_DIR_PATH", None)


# Make sure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)


def get_cache_dir() -> str:
    """
    Get the cache directory path.
    
    :return: the cache directory path
    """
    return CACHE_DIR


def get_paras_model() -> ParasModel | None:
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
            _model_cache["paras"] = ParasModel(threshold=0.1, keep_top=3, cache_dir=get_cache_dir(), model_path=path)
        else:
            current_app.logger.warning(f"PARAS model not found at {path}; letting BioCracker download into {CACHE_DIR}")
            _model_cache["paras"] = None
        return _model_cache["paras"]
    else:
        # Model path is not defined
        current_app.logger.warning("PARAS_MODEL_PATH not set; letting BioCracker download into CACHE_DIR")
        return None
    

def get_pfam_models() -> list[PfamModel] | None:
    """
    Load and return Pfam models from disk, caching them in memory.

    :return: the loaded Pfam models, or None if not found
    """
    # Check if model is already cached
    if "pfam" in _model_cache:
        return _model_cache["pfam"]
    
    # Check if HMM directory path is defined
    if PFAM_HMM_DIR_PATH:
        path = Path(PFAM_HMM_DIR_PATH)
        if path.is_dir():
            current_app.logger.info(f"Loading Pfam models from {path}")
            hmm_paths = [f for f in path.glob("*.hmm") if f.is_file()]
            pfam_models = []
            for hmm_path in hmm_paths:
                current_app.logger.info(f"Loading Pfam model from {hmm_path}")
                pfam_model = PfamModel(hmm_path=hmm_path, label=hmm_path.stem)
                pfam_models.append(pfam_model)
            _model_cache["pfam"] = pfam_models
        else:
            current_app.logger.warning(f"Pfam HMM directory not found at {path}; letting BioCracker download into {CACHE_DIR}")
            _model_cache["pfam"] = None
        return _model_cache["pfam"]
    else:
        # HMM directory path is not defined
        current_app.logger.warning("PFAM_HMM_DIR_PATH not set")
        return None
