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

# Global checkpointer for conversation state persistence
try:
    os.makedirs("/data4/db", exist_ok=True)
    db_path = "/data4/db/eclipse_bot.db"
    _conn = sqlite3.connect(db_path, check_same_thread=False)
except PermissionError:
    import logging
    logging.getLogger(__name__).error("Permission denied for /data4/db. Falling back to /tmp/db.")
    os.makedirs("/tmp/db", exist_ok=True)
    db_path = "/tmp/db/eclipse_bot.db"
    _conn = sqlite3.connect(db_path, check_same_thread=False)

logging.getLogger(__name__).info(f"Using persistence DB at: {db_path}")
_checkpointer = CustomSqliteSaver(_conn)

from src.config import get_settings
from src.agents.subagents import get_subagents
from src.agents.prompts import PERSONA_CONFIGS
from src.agents.utils import get_chat_model
from src.tools.p4_tools import ALL_P4_TOOLS
from src.tools.slack_tools import ALL_SLACK_TOOLS
from src.skills.code_review import code_review


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
    import logging
    
    # Dynamic Context Management
    # 1. Fetch actual limit from OpenRouter
    limit = get_context_window(model_name, default=128000)
    
    # 2. Safety Buffer (System prompt + Output generation needs space)
    # Reserve ~5k tokens for output and system instructions
    safe_limit = max(limit - 5000, 4000) 
    
    logging.getLogger(__name__).info(f"Dynamic Context: Model={model_name}, Limit={limit}, Trimming_At={safe_limit}")

    # Context Management: Keep last ~safe_limit tokens
    trimmer = trim_messages(
        max_tokens=safe_limit,
        strategy="last",
        token_counter=model_instance,
        include_system=True,
        allow_partial=False,
        start_on="human",
    )

    return create_deep_agent(
        model=model_instance,
        system_prompt=cfg["prompt"],
        subagents=get_subagents(),
        tools=ALL_P4_TOOLS + ALL_SLACK_TOOLS + [code_review],
        backend=StateBackend,
        checkpointer=_checkpointer,
        state_modifier=trimmer, 
    )
