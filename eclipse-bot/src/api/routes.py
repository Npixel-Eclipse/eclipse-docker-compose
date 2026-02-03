"""API route definitions."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Any

from ..workflows import get_registry, WorkflowStatus

router = APIRouter()


class WorkflowRunRequest(BaseModel):
    """Request model for workflow execution.
    
    Example:
        {
            "workflow_name": "echo",
            "input_data": {"message": "Hello World"}
        }
    """
    workflow_name: str
    input_data: dict[str, Any]


class WorkflowRunResponse(BaseModel):
    """Response model for workflow execution."""
    run_id: str
    status: str
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class WorkflowInfo(BaseModel):
    """Workflow information."""
    name: str
    description: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="0.1.0")


@router.get("/workflows", response_model=list[WorkflowInfo])
async def list_workflows():
    """List all available workflows.
    
    Returns:
        List of registered workflows with name and description
    """
    registry = get_registry()
    workflows = registry.list_workflows()
    return [WorkflowInfo(**w) for w in workflows]


@router.post("/workflow/run", response_model=WorkflowRunResponse)
async def run_workflow(request: WorkflowRunRequest):
    """Execute a registered workflow.
    
    Args:
        request: Workflow name and input data
        
    Returns:
        Execution result with run_id and status
        
    Example:
        POST /workflow/run
        {
            "workflow_name": "echo",
            "input_data": {"message": "Hello"}
        }
    """
    registry = get_registry()
    
    # Check if workflow exists
    workflow = registry.get_workflow(request.workflow_name)
    if not workflow:
        available = [w["name"] for w in registry.list_workflows()]
        raise HTTPException(
            status_code=404,
            detail=f"Workflow '{request.workflow_name}' not found. Available: {available}",
        )
    
    # Execute workflow
    try:
        run = await registry.execute(request.workflow_name, request.input_data)
        return WorkflowRunResponse(
            run_id=run.run_id,
            status=run.status.value,
            result=run.result,
            error=run.error,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflow/status/{run_id}", response_model=WorkflowRunResponse)
async def get_workflow_status(run_id: str):
    """Get workflow execution status.
    
    Args:
        run_id: Workflow run identifier
        
    Returns:
        Workflow run status and result
    """
    registry = get_registry()
    run = registry.get_run(run_id)
    
    if not run:
        raise HTTPException(
            status_code=404,
            detail=f"Run not found: {run_id}",
        )
    
    return WorkflowRunResponse(
        run_id=run.run_id,
        status=run.status.value,
        result=run.result,
        error=run.error,
    )


@router.get("/workflow/runs")
async def list_runs(workflow_name: Optional[str] = None, limit: int = 100):
    """List workflow runs.
    
    Args:
        workflow_name: Filter by workflow name (optional)
        limit: Maximum number of runs to return
        
    Returns:
        List of workflow runs
    """
    registry = get_registry()
    runs = registry.list_runs(workflow_name=workflow_name, limit=limit)
    
    return [
        {
            "run_id": r.run_id,
            "workflow_name": r.workflow_name,
            "status": r.status.value,
            "created_at": r.created_at.isoformat(),
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in runs
    ]
