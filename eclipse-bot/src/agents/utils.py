"""Utility functions for Eclipse Bot agents."""

import logging
from langchain.chat_models import init_chat_model
from src.config import get_settings

logger = logging.getLogger(__name__)

def get_chat_model(model_name: str = None, api_key: str = None):
    """Instantiate a Chat model with proper provider and API key.
    
    Handles OpenRouter (via openai provider + base_url) and other providers.
    """
    settings = get_settings()
    
    # Fallback to defaults if not provided
    model_name = model_name or settings.main_agent_model or settings.default_model
    effective_api_key = api_key or settings.openrouter_api_key
    
    # Common kwargs for all models
    common_kwargs = {"streaming": True}
    if effective_api_key:
        common_kwargs["api_key"] = effective_api_key
    
    logger.info(f"Initializing model: {model_name} (using key ending in ...{effective_api_key[-4:] if effective_api_key else 'None'})")

    # Arguments for OpenRouter
    openrouter_kwargs = {
        "model_provider": "openai",
        "base_url": settings.openrouter_base_url,
        **common_kwargs # Merge common kwargs
    }

    # Case 1: OpenRouter format (org/model)
    if "/" in model_name and ":" not in model_name:
        return init_chat_model(model=model_name, **openrouter_kwargs)
    
    # Case 2: DeepAgents/LangChain format (provider:model)
    if ":" in model_name:
        provider, name = model_name.split(":", 1)
        
        # If provider is 'openai' or 'openrouter', route to settings.openrouter_base_url
        if provider in ["openai", "openrouter"]:
            return init_chat_model(model=name, **openrouter_kwargs)
            
        # Standardize 'google' to 'google_genai' for native access
        if provider == "google":
            provider = "google_genai"
            
        return init_chat_model(model=name, model_provider=provider, api_key=effective_api_key)
        
    # Case 3: Just a model name (fallback to OpenRouter if slash in default model or if it looks like one)
    # For this project, we assume single names are OpenRouter models if it's the primary provider
    return init_chat_model(model=model_name, **openrouter_kwargs)
