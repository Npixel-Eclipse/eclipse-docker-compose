from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

from src.core.context import get_context
from src.core.dispatcher import handle_event_trigger

router = APIRouter()

class TriggerRequest(BaseModel):
    summary: str
    description: Optional[str] = None
    context: Optional[Dict[str, Any]] = {}
    channel: str # Required for notification

@router.post("/trigger")
async def trigger_workflow(req: TriggerRequest, background_tasks: BackgroundTasks):
    """
    Async Trigger Endpoint.
    Returns 202 Accepted immediately, processes in background.
    """
    ctx = get_context()
    
    # Construct a mock event object compatible with handle_event_trigger
    from src.core.dispatcher import create_event_payload
    
    mock_event = create_event_payload(
        channel=req.channel,
        text=f"{req.summary}\n{req.description or ''}",
        user=req.context.get("user_id", "API_TRIGGER"),
        ts=req.context.get("ts"),
        thread_ts=req.context.get("thread_ts"),
        team=req.context.get("team_id")
    )
    
    # Wrapper to inject context before running
    # Note: handle_event_trigger sets context internally, so we just call it.
    # We need a dummy 'say' function since it expects one
    async def mock_say(text: str = "", **kwargs):
        # In API context, 'say' might post to Slack if channel is valid
        if req.channel:
            await ctx.slack.send_message(req.channel, text, **kwargs)

    # Schedule task
    background_tasks.add_task(
        handle_event_trigger, 
        event=mock_event, 
        say=mock_say, 
        trigger_type="api"
    )

    return {"status": "accepted", "message": "Workflow queued in background"}
