"""Workflows package."""

from src.core.registry import (
    BaseWorkflow,
    WorkflowRegistry,
    WorkflowRun,
    WorkflowStatus,
    registry,
    get_registry,
)
from .llm_chat import LLMChatWorkflow


def register_all_workflows():
    """Register all workflows to the global registry."""
    registry.register(LLMChatWorkflow())


__all__ = [
    "BaseWorkflow",
    "WorkflowRegistry",
    "WorkflowRun",
    "WorkflowStatus",
    "registry",
    "get_registry",
    "LLMChatWorkflow",
    "register_all_workflows",
]
