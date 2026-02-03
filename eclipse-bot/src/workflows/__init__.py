"""Workflows package."""

from src.core.registry import (
    BaseWorkflow,
    WorkflowRegistry,
    WorkflowRun,
    WorkflowStatus,
    registry,
    get_registry,
)
from .echo import EchoWorkflow
from .llm_chat import LLMChatWorkflow


def register_all_workflows():
    """Register all workflows to the global registry."""
    registry.register(EchoWorkflow())
    registry.register(LLMChatWorkflow())


__all__ = [
    "BaseWorkflow",
    "WorkflowRegistry",
    "WorkflowRun",
    "WorkflowStatus",
    "registry",
    "get_registry",
    "EchoWorkflow",
    "LLMChatWorkflow",
    "register_all_workflows",
]
