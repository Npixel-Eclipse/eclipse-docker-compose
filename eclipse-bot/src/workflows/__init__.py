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
from .reset_session import ResetSessionWorkflow


def register_all_workflows():
    """Register all workflows to the global registry."""
    registry.register(EchoWorkflow())
    registry.register(LLMChatWorkflow())
    registry.register(ResetSessionWorkflow())


__all__ = [
    "BaseWorkflow",
    "WorkflowRegistry",
    "WorkflowRun",
    "WorkflowStatus",
    "registry",
    "get_registry",
    "EchoWorkflow",
    "LLMChatWorkflow",
    "ResetSessionWorkflow",
    "register_all_workflows",
]
