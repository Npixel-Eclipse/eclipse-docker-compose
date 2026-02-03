"""Bash/shell command tools for Eclipse Bot."""

import asyncio
import subprocess
from src.core.registry import BaseWorkflow


class RunCommandTool(BaseWorkflow):
    """Execute a shell command."""
    
    name = "run_command"
    description = "Execute a shell command and return the output. Dangerous commands are blocked. Timeout: 60s."
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to execute"},
            "cwd": {"type": "string", "description": "Working directory for the command"},
            "timeout": {"type": "integer", "description": "Timeout in seconds (default: 60)"},
        },
        "required": ["command"],
    }
    
    async def execute(self, input_data: dict) -> dict:
        command = input_data.get("command", "")
        cwd = input_data.get("cwd")
        timeout = input_data.get("timeout", 60)
        
        # Safety check - block dangerous commands
        dangerous_patterns = [
            "rm -rf /", "rm -rf /*", "mkfs", "> /dev/", "dd if=",
            ":(){ :|:& };:", "chmod -R 777 /", "chown -R"
        ]
        for pattern in dangerous_patterns:
            if pattern in command:
                return {"error": f"Blocked dangerous command: {pattern}"}
        
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=timeout,
            )
            
            stdout = result.stdout
            stderr = result.stderr
            
            # Truncate large outputs
            if len(stdout) > 20000:
                stdout = stdout[:20000] + "\n... [truncated]"
            if len(stderr) > 5000:
                stderr = stderr[:5000] + "\n... [truncated]"
            
            return {
                "stdout": stdout,
                "stderr": stderr,
                "return_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Command timed out after {timeout} seconds"}
        except Exception as e:
            return {"error": str(e)}
