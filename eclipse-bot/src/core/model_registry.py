"""Model Registry for Dynamic Configuration.

Fetches and caches model metadata (like context window size) from OpenRouter.
"""

import logging
import requests
from functools import lru_cache
from typing import Optional, Dict, Any

from src.config import get_settings

logger = logging.getLogger(__name__)

# In-memory cache for model info to avoid repeated API calls
_MODEL_CACHE: Dict[str, Any] = {}

def fetch_openrouter_models() -> Dict[str, Any]:
    """Fetch all available models from OpenRouter API."""
    settings = get_settings()
    if not settings.openrouter_api_key:
        logger.warning("No OpenRouter API key found. Skipping model fetch.")
        return {}

    try:
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "HTTP-Referer": "https://eclipse-bot.internal", # Optional but polite
        }
        resp = requests.get("https://openrouter.ai/api/v1/models", headers=headers, timeout=10)
        resp.raise_for_status()
        
        data = resp.json().get("data", [])
        # Index by ID for easier lookup
        return {item["id"]: item for item in data}
        
    except Exception as e:
        logger.error(f"Failed to fetch OpenRouter models: {e}")
        return {}

def get_model_info(model_id: str) -> Optional[Dict[str, Any]]:
    """Get metadata for a specific model ID."""
    global _MODEL_CACHE
    
    # Lazy load cache
    if not _MODEL_CACHE:
        logger.info("Initializing Model Registry Cache...")
        _MODEL_CACHE = fetch_openrouter_models()
        logger.info(f"Cached {_MODEL_CACHE.__len__()} models from OpenRouter.")
        
    return _MODEL_CACHE.get(model_id)

def get_context_window(model_id: str, default: int = 4096) -> int:
    """Get context window size for a model, with safe fallback."""
    info = get_model_info(model_id)
    if info:
        # OpenRouter returns 'context_length'
        ctx_len = info.get("context_length") or info.get("context_window")
        if ctx_len:
            return int(ctx_len)
            
    # Hardcoded fallbacks for known common models if API fails
    if "kimi" in model_id.lower():
        return 128000
    if "gpt-4" in model_id.lower():
        return 128000
    if "claude-3" in model_id.lower():
        return 200000
        
    logger.warning(f"Could not determine context window for {model_id}. Using default {default}.")
    return default
