"""Dynamic Agent Factory for the Eclipse Orchestration Platform.

Generates Main Orchestrators with context-aware personas.
Supports per-agent model and API key overrides.
"""

from deepagents import create_deep_agent
from deepagents.backends import StateBackend
from langgraph.checkpoint.memory import MemorySaver

from src.config import get_settings
from src.agents.subagents import get_subagents
from src.agents.prompts import PERSONA_CONFIGS
from src.agents.utils import get_chat_model
from src.tools.p4_tools import ALL_P4_TOOLS
from src.tools.slack_tools import ALL_SLACK_TOOLS
from src.skills.code_review import code_review

# Global checkpointer for conversation state persistence
_checkpointer = MemorySaver()


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
    
    return create_deep_agent(
        model=model_instance,
        system_prompt=cfg["prompt"],
        subagents=get_subagents(),
        tools=ALL_P4_TOOLS + ALL_SLACK_TOOLS + [code_review],
        backend=StateBackend,
        checkpointer=_checkpointer,
    )
