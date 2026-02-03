"""LLM Chat workflow - direct LLM interaction."""

from src.core.registry import BaseWorkflow
from src.core.config import load_config


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
    
    @property
    def allowed_tools(self) -> list[str]:
        """Load allowed tools from config.yaml."""
        config = load_config()
        return config.get("workflows", {}).get("llm_chat", {}).get("allowed_tools", [])
    
    @property
    def allowed_workflows(self) -> list[str]:
        """Load allowed workflows from config.yaml."""
        config = load_config()
        return config.get("workflows", {}).get("llm_chat", {}).get("allowed_workflows", [])
    
    async def execute(self, input_data: dict) -> dict:
        from src.main import get_llm_client
        from src.models import Message
        from src.core.registry import registry
        
        message = input_data.get("message", "")
        system_prompt = input_data.get("system_prompt", "You are a helpful assistant.")
        
        client = get_llm_client()
        
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=message),
        ]
        
        # Get allowed tools specs (combine tools and workflows)
        allowed_items = self.allowed_tools + getattr(self, "allowed_workflows", [])
        tools = registry.get_tool_specs(allowed_items)
        
        response = await client.chat(messages, tools=tools)
        
        return {
            "response": response.content,
            "model": response.model,
            "usage": response.usage,
            "tool_calls": response.tool_calls or [],
        }
