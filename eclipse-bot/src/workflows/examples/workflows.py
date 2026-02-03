"""Example workflows for Eclipse Bot."""

from ..registry import BaseWorkflow


class EchoWorkflow(BaseWorkflow):
    """Simple echo workflow for testing.
    
    Usage:
        Input: {"message": "Hello"}
        Output: {"echo": "Hello", "length": 5}
    """
    
    name = "echo"
    description = "Echoes back the input message with its length"
    parameters = {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "The message to echo back"},
        },
        "required": ["message"],
    }
    
    async def execute(self, input_data: dict) -> dict:
        message = input_data.get("message", "")
        return {
            "echo": message,
            "length": len(message),
        }


class LLMChatWorkflow(BaseWorkflow):
    """LLM-powered chat workflow.
    
    Usage:
        Input: {"message": "What is Python?", "system_prompt": "You are helpful."}
        Output: {"response": "Python is...", "model": "..."}
    """
    
    name = "llm_chat"
    description = "Send a message to the LLM and get a response"
    parameters = {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "The user message to send to the LLM"},
            "system_prompt": {"type": "string", "description": "Optional system prompt for the context"},
        },
        "required": ["message"],
    }
    
    async def execute(self, input_data: dict) -> dict:
        from src.main import get_llm_client
        from src.models import Message
        
        message = input_data.get("message", "")
        system_prompt = input_data.get("system_prompt", "You are a helpful assistant.")
        
        client = get_llm_client()
        
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=message),
        ]
        
        response = await client.chat(messages)
        
        return {
            "response": response.content,
            "model": response.model,
            "usage": response.usage,
        }


class P4SyncWorkflow(BaseWorkflow):
    """Perforce sync workflow.
    
    Usage:
        Input: {"path": "//Eclipse_Studio/Main/..."}
        Output: {"synced": "...", "files_count": 100}
    """
    
    name = "p4_sync"
    description = "Sync files from Perforce depot to the agent workspace"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Depot path to sync (e.g. //Eclipse_Studio/Main/...)"},
        },
    }
    
    async def execute(self, input_data: dict) -> dict:
        import asyncio
        from src.core import PerforceClient
        
        path = input_data.get("path", "//...")
        
        p4 = PerforceClient()
        # Use asyncio.to_thread to run the synchronous p4.sync without blocking
        output = await asyncio.to_thread(p4.sync, path)
        
        # Count synced files
        lines = [l for l in output.strip().split("\n") if l]
        
        return {
            "synced": output[:1000] if len(output) > 1000 else output,
            "files_count": len(lines),
        }


class ResetSessionWorkflow(BaseWorkflow):
    """Workflow to clear conversation history.
    
    Usage:
        Input: {"channel_id": "C123", "thread_ts": "123.456"}
        Output: {"status": "success", "message": "Conversation history cleared"}
    """
    
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


# Register all example workflows
def register_examples():
    """Register all example workflows to the global registry."""
    from ..registry import registry
    
    registry.register(EchoWorkflow())
    registry.register(LLMChatWorkflow())
    registry.register(P4SyncWorkflow())
    registry.register(ResetSessionWorkflow())
