"""Session management tools."""

import uuid
from src.core.registry import BaseWorkflow


class ResetSessionTool(BaseWorkflow):
    """Reset the current session by clearing conversation history."""
    
    name = "reset_session"
    description = "Reset the current session by clearing conversation history"
    parameters = {
        "type": "object",
        "properties": {
            "channel_id": {"type": "string", "description": "The Slack channel ID (optional if called in context)"},
            "thread_ts": {"type": "string", "description": "The thread timestamp (optional)"},
        },
        "required": [],
    }
    
    async def execute(self, input_data: dict) -> dict:
        from src.main import get_slack_integration
        
        channel_id = input_data.get("channel_id")
        thread_ts = input_data.get("thread_ts")
        slack = get_slack_integration()
        
        new_session_id = str(uuid.uuid4())
        
        # 1. Send Session End Marker for previous session (if exists - conceptual)
        # Actually just sending New Session Start marker acts as a delimiter.
        # But explicit END is clearer.
        await slack.send_message(
            channel_id,
            f"🚫 [SESSION_END] Previous Session Closed.",
            thread_ts=thread_ts
        )
        
        # 2. Send Session Start Marker
        await slack.send_message(
            channel_id,
            f"🔄 [SESSION_START] ID: {new_session_id}\n새로운 세션이 시작되었습니다.",
            thread_ts=thread_ts
        )
        
        return {
            "status": "success",
            "message": f"Session reset. New Session ID: {new_session_id}",
        }
