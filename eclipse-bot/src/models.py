"""Shared data models for the Eclipse Bot."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any


@dataclass
class Message:
    """Chat message for LLM interactions and conversation storage.
    
    Attributes:
        role: Message role - "system", "user", "assistant", or "tool"
        content: Message text content
        user_id: Optional Slack user ID (for conversation storage)
        created_at: Optional timestamp (for conversation storage)
        tool_calls: Optional list of tool calls from the assistant
        tool_call_id: Required for "tool" role messages
    """
    role: str
    content: Optional[str] = None
    user_id: Optional[str] = None
    created_at: Optional[datetime] = None
    tool_calls: Optional[list[dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


@dataclass
class LLMResponse:
    """LLM response container.
    
    Attributes:
        content: Response text from the LLM (may be empty if tool_calls present)
        model: Model name used for the response
        usage: Token usage statistics
        tool_calls: Optional list of tool calls to execute
    """
    content: Optional[str]
    model: str
    usage: dict = field(default_factory=dict)
    tool_calls: Optional[list[dict[str, Any]]] = None
