"""LLM Chat workflow - direct LLM interaction."""

from src.core.registry import BaseWorkflow


class LLMChatWorkflow(BaseWorkflow):
    """LLM-powered chat workflow."""
    
    name = "llm_chat"
    description = "Send a message to the LLM and get a response"
    parameters = {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "The user message to send to the LLM"},
            "system_prompt": {"type": "string", "description": "Optional system prompt"},
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
