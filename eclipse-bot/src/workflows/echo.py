"""Echo workflow - simple test workflow."""

from src.core.registry import BaseWorkflow


class EchoWorkflow(BaseWorkflow):
    """Simple echo workflow for testing."""
    
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
