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
from .code_review import CodeReviewWorkflow


def register_all_workflows(llm_client=None):
    """Register all workflows to the global registry."""
    registry.register(LLMChatWorkflow())
    if llm_client:
        registry.register(CodeReviewWorkflow(llm_client))


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
