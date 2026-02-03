"""Base workflow class and state definitions."""

from abc import ABC, abstractmethod
from typing import TypedDict, Optional, Any
from dataclasses import dataclass

from ..core.workflow_engine import WorkflowEngine, WorkflowResult


class WorkflowState(TypedDict, total=False):
    """Base state schema for workflows.

    Extend this for custom workflow states:

        class MyState(WorkflowState):
            custom_field: str
            results: list[str]
    """

    # Common fields
    input: str
    output: str
    error: Optional[str]
    metadata: dict[str, Any]


class BaseWorkflow(ABC):
    """Abstract base class for AI workflows.

    Subclass this to create custom workflows:

        class MyWorkflow(BaseWorkflow):
            name = "my_workflow"

            def build(self):
                @self.engine.node("process")
                async def process(state):
                    return {"output": state["input"].upper()}

                self.engine.set_entry_point("process")
                self.engine.add_edge("process", END)

            def get_state_schema(self):
                return MyState
    """

    name: str = "base_workflow"

    def __init__(self):
        self.engine: WorkflowEngine = WorkflowEngine()
        self.build()
        self.engine.compile(self.get_state_schema())

    @abstractmethod
    def build(self):
        """Build the workflow graph.

        Override this to define nodes and edges:
            - Use @self.engine.node("name") to define nodes
            - Use self.engine.add_edge() to connect nodes
            - Use self.engine.set_entry_point() to set start node
        """
        pass

    @abstractmethod
    def get_state_schema(self) -> type:
        """Return the state schema TypedDict or dataclass."""
        pass

    async def run(self, initial_state: dict) -> WorkflowResult:
        """Execute the workflow asynchronously."""
        return await self.engine.run(initial_state)

    def run_sync(self, initial_state: dict) -> WorkflowResult:
        """Execute the workflow synchronously."""
        return self.engine.run_sync(initial_state)
