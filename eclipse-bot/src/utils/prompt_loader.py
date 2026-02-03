"""Prompt loader utility."""

import logging
from pathlib import Path
from functools import lru_cache

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


@lru_cache(maxsize=32)
def load_prompt(name: str = "default") -> str:
    """Load a prompt from the prompts directory.
    
    Args:
        name: Prompt name (without .md extension)
        
    Returns:
        Prompt content as string
        
    Example:
        prompt = load_prompt("default")
        prompt = load_prompt("code_assistant")
    """
    prompt_path = PROMPTS_DIR / f"{name}.md"
    
    if not prompt_path.exists():
        logger.warning(f"Prompt '{name}' not found, using default")
        prompt_path = PROMPTS_DIR / "default.md"
    
    if not prompt_path.exists():
        logger.error("Default prompt not found!")
        return "You are a helpful assistant. Respond in Korean."
    
    return prompt_path.read_text(encoding="utf-8").strip()


def reload_prompt(name: str = "default") -> str:
    """Reload a prompt (bypasses cache).
    
    Use this when you've updated a prompt file and want to reload it.
    """
    load_prompt.cache_clear()
    return load_prompt(name)


def list_prompts() -> list[str]:
    """List all available prompts."""
    if not PROMPTS_DIR.exists():
        return []
    return [p.stem for p in PROMPTS_DIR.glob("*.md")]
