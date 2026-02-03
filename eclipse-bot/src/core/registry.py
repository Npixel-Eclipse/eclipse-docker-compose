"""Workflow registry for managing and executing workflows."""

import uuid
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class WorkflowStatus(str, Enum):
    """Workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class WorkflowRun:
    """Represents a single workflow execution."""
    run_id: str
    workflow_name: str
    status: WorkflowStatus
    input_data: dict[str, Any]
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class BaseWorkflow(ABC):
    """Base class for all workflows.
    
    Usage:
        class MyWorkflow(BaseWorkflow):
            name = "my_workflow"
            description = "Does something useful"
            
            async def execute(self, input_data: dict) -> dict:
                # Your workflow logic here
                result = input_data["value"] * 2
                return {"result": result}
        
        # Register
        registry.register(MyWorkflow())
        
        # Execute
        run = await registry.execute("my_workflow", {"value": 21})
        print(run.result)  # {"result": 42}
    """
    
    name: str = "base_workflow"
    description: str = "Base workflow"
    parameters: dict[str, Any] = {"type": "object", "properties": {}}
    
    def get_tool_spec(self) -> dict[str, Any]:
        """Generate OpenAI/OpenRouter tool specification for this workflow.
        
        Returns:
            Dictionary following the tool specification format
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
    
    @abstractmethod
    async def execute(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute the workflow.
        
        Args:
            input_data: Input data for the workflow
            
        Returns:
            Workflow result as dictionary
        """
        pass


class WorkflowRegistry:
    """Registry for managing workflows.
    
    Usage:
        registry = WorkflowRegistry()
        
        # Register a workflow
        registry.register(MyWorkflow())
        
        # List available workflows
        workflows = registry.list_workflows()
        
        # Get tool specs for LLM
        tools = registry.get_all_tool_specs()
        
        # Execute a workflow
        run = await registry.execute("my_workflow", {"key": "value"})
        
        # Get run status
        run = registry.get_run(run.run_id)
    """
    
    def __init__(self):
        self._workflows: dict[str, BaseWorkflow] = {}
        self._runs: dict[str, WorkflowRun] = {}
    
    def register(self, workflow: BaseWorkflow) -> None:
        """Register a workflow.
        
        Args:
            workflow: Workflow instance to register
        """
        self._workflows[workflow.name] = workflow
        logger.info(f"Registered workflow: {workflow.name}")
    
    def unregister(self, name: str) -> bool:
        """Unregister a workflow.
        
        Args:
            name: Workflow name
            
        Returns:
            True if unregistered, False if not found
        """
        if name in self._workflows:
            del self._workflows[name]
            logger.info(f"Unregistered workflow: {name}")
            return True
        return False
    
    def get_workflow(self, name: str) -> Optional[BaseWorkflow]:
        """Get a workflow by name.
        
        Args:
            name: Workflow name
            
        Returns:
            Workflow instance or None
        """
        return self._workflows.get(name)
    
    def list_workflows(self) -> list[dict[str, str]]:
        """List all registered workflows.
        
        Returns:
            List of workflow info dicts with name and description
        """
        return [
            {"name": w.name, "description": w.description}
            for w in self._workflows.values()
        ]
    
    def get_all_tool_specs(self) -> list[dict[str, Any]]:
        """Get tool specifications for all registered workflows.
        
        Returns:
            List of tool specs for use with LLM
        """
        return [w.get_tool_spec() for w in self._workflows.values()]
    
    async def execute(
        self,
        workflow_name: str,
        input_data: dict[str, Any],
    ) -> WorkflowRun:
        """Execute a workflow.
        
        Args:
            workflow_name: Name of the workflow to execute
            input_data: Input data for the workflow
            
        Returns:
            WorkflowRun with execution results
            
        Raises:
            ValueError: If workflow not found
        """
        workflow = self._workflows.get(workflow_name)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_name}")
        
        # Create run record
        run = WorkflowRun(
            run_id=str(uuid.uuid4()),
            workflow_name=workflow_name,
            status=WorkflowStatus.RUNNING,
            input_data=input_data,
        )
        self._runs[run.run_id] = run
        
        try:
            logger.info(f"Executing workflow: {workflow_name} (run_id: {run.run_id})")
            result = await workflow.execute(input_data)
            run.result = result
            run.status = WorkflowStatus.COMPLETED
            run.completed_at = datetime.utcnow()
            logger.info(f"Workflow completed: {workflow_name} (run_id: {run.run_id})")
        except Exception as e:
            run.error = str(e)
            run.status = WorkflowStatus.FAILED
            run.completed_at = datetime.utcnow()
            logger.error(f"Workflow failed: {workflow_name} - {e}")
        
        return run
    
    def get_run(self, run_id: str) -> Optional[WorkflowRun]:
        """Get a workflow run by ID.
        
        Args:
            run_id: Run identifier
            
        Returns:
            WorkflowRun or None
        """
        return self._runs.get(run_id)
    
    def list_runs(
        self,
        workflow_name: Optional[str] = None,
        limit: int = 100,
    ) -> list[WorkflowRun]:
        """List workflow runs.
        
        Args:
            workflow_name: Filter by workflow name (optional)
            limit: Maximum number of runs to return
            
        Returns:
            List of WorkflowRun objects
        """
        runs = list(self._runs.values())
        if workflow_name:
            runs = [r for r in runs if r.workflow_name == workflow_name]
        runs.sort(key=lambda x: x.created_at, reverse=True)
        return runs[:limit]


# Global registry instance
registry = WorkflowRegistry()


def get_registry() -> WorkflowRegistry:
    """Get the global workflow registry."""
    return registry
