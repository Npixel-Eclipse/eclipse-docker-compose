"""Dynamic Agent Factory for the Eclipse Orchestration Platform.

Generates Main Orchestrators with context-aware personas.
Supports per-agent model and API key overrides.
"""

from deepagents import create_deep_agent
from deepagents.backends import StateBackend
# Use custom checkpointer to avoid version issues
from src.core.checkpointer import CustomSqliteSaver
import sqlite3
import os
import logging
from src.core.model_registry import get_context_window
from src.config import get_settings
from src.agents.subagents import get_subagents
from src.agents.prompts import PERSONA_CONFIGS
from src.agents.utils import get_chat_model
from src.tools.p4_tools import ALL_P4_TOOLS
from src.tools.slack_tools import ALL_SLACK_TOOLS
from src.tools.opensearch_tools import ALL_OPENSEARCH_TOOLS
from src.skills.code_review import code_review

# Global checkpointer for conversation state persistence
try:
    settings = get_settings()
    db_dir = os.path.dirname(settings.persistence_db_path)
    os.makedirs(db_dir, exist_ok=True)
    db_path = settings.persistence_db_path
    _conn = sqlite3.connect(db_path, check_same_thread=False)
except PermissionError:
    settings = get_settings() # Re-fetch to be safe
    logging.getLogger(__name__).error(f"Permission denied for {settings.persistence_db_path}. Falling back to {settings.persistence_fallback_path}.")
    
    db_dir = os.path.dirname(settings.persistence_fallback_path)
    os.makedirs(db_dir, exist_ok=True)
    db_path = settings.persistence_fallback_path
    _conn = sqlite3.connect(db_path, check_same_thread=False)

logging.getLogger(__name__).info(f"Using persistence DB at: {db_path}")
_checkpointer = CustomSqliteSaver(_conn)


def create_agent(persona_type: str = "general"):
    """Create a dynamic Deep Agent orchestrator.
    
    Args:
        persona_type: 'general', 'code_review' (deprecated), 'automation', etc.
    """
    settings = get_settings()
    # Fallback to general if persona not found (e.g. code_review which is now a skill)
    cfg = PERSONA_CONFIGS.get(persona_type, PERSONA_CONFIGS["general"])
    
    model_name = cfg.get("model") or settings.main_agent_model
    api_key = cfg.get("api_key") or settings.openrouter_api_key
    
    # Pre-instantiate model instance to handle API keys and providers safely
    model_instance = get_chat_model(model_name, api_key)
    
    from langchain_core.messages import trim_messages
    from src.core.model_registry import get_context_window
    
    # Dynamic Context Management
    # 1. Fetch actual limit from OpenRouter
    limit = get_context_window(model_name, default=128000)
    
    # 2. Safety Buffer (System prompt + Output generation needs space)
    # Reserve ~5k tokens for output and system instructions
    safe_limit = max(limit - 5000, 4000) 
    
    logging.getLogger(__name__).info(f"Dynamic Context: Model={model_name}, Limit={limit}, Trimming_At={safe_limit}")

    # Context Management Strategy
    # User Request: "Auto Compact" instead of simple Trimming
    from src.core.compactor import AutoCompactor
    
    # We use a secondary model instance (or the same one) for summarization
    # Ideally, use a cheaper/faster model for summary if possible, but reusing main model is fine for consistency.
    compactor = AutoCompactor(
        model=model_instance,
        max_tokens=safe_limit,
        recent_messages_buffer=20  # Keep last 20 messages intact
    )

    # Pass compactor to checkpointer for load-time optimization
    checkpointer_instance = CustomSqliteSaver(_conn, context_manager=compactor)

    return create_deep_agent(
        model=model_instance,
        system_prompt=cfg["prompt"],
        subagents=get_subagents(),
        tools=ALL_P4_TOOLS + ALL_SLACK_TOOLS + ALL_OPENSEARCH_TOOLS + [code_review],
        backend=StateBackend,
        checkpointer=checkpointer_instance,
    )
