"""Reset session workflow - clear conversation history."""

from src.core.registry import BaseWorkflow


class ResetSessionWorkflow(BaseWorkflow):
    """Reset the current session by clearing conversation history."""
    
    name = "reset_session"
    description = "Reset the current session by clearing conversation history"
    parameters = {
        "type": "object",
        "properties": {
            "channel_id": {"type": "string", "description": "The Slack channel ID"},
            "thread_ts": {"type": "string", "description": "The thread timestamp (optional)"},
        },
        "required": ["channel_id"],
    }
    
    async def execute(self, input_data: dict) -> dict:
        from src.main import get_conversation_store
        
        channel_id = input_data.get("channel_id")
        thread_ts = input_data.get("thread_ts")
        
        store = get_conversation_store()
        await store.clear_conversation(channel_id, thread_ts)
        
        return {
            "status": "success",
            "message": f"Conversation history for channel {channel_id} cleared.",
        }
