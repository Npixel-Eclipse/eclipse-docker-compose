"""Code search tools for Eclipse Bot."""

import asyncio
import subprocess
from src.core.registry import BaseWorkflow


class SearchCodeTool(BaseWorkflow):
    """Search for patterns in code files using ripgrep."""
    
    name = "search_code"
    description = "Search for a pattern in files using ripgrep. Returns matching lines with file paths and line numbers. Max 30 results."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Search pattern (supports regex)"},
            "directory": {"type": "string", "description": "Directory to search in"},
            "file_pattern": {"type": "string", "description": "File glob pattern (e.g., '*.py')"},
            "case_insensitive": {"type": "boolean", "description": "Case insensitive search"},
            "max_results": {"type": "integer", "description": "Maximum results (default: 30)"},
        },
        "required": ["pattern", "directory"],
    }
    
    async def execute(self, input_data: dict) -> dict:
        pattern = input_data.get("pattern", "")
        directory = input_data.get("directory", ".")
        file_pattern = input_data.get("file_pattern")
        case_insensitive = input_data.get("case_insensitive", False)
        max_results = input_data.get("max_results", 30)
        
        cmd = ["rg", "--line-number", "--no-heading", f"--max-count={max_results}"]
        
        if case_insensitive:
            cmd.append("-i")
        
        if file_pattern:
            cmd.extend(["-g", file_pattern])
        
        cmd.extend([pattern, directory])
        
        try:
            result = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, text=True, timeout=30
            )
            
            output = result.stdout.strip()
            matches = []
            
            for line in output.split("\n")[:max_results]:
                if line and ":" in line:
                    parts = line.split(":", 2)
                    if len(parts) >= 3:
                        matches.append({
                            "file": parts[0],
                            "line": int(parts[1]) if parts[1].isdigit() else parts[1],
                            "content": parts[2][:200],
                        })
            
            return {
                "matches": matches,
                "count": len(matches),
                "pattern": pattern,
            }
        except FileNotFoundError:
            # Fallback to grep
            cmd = ["grep", "-rn"]
            if case_insensitive:
                cmd.append("-i")
            cmd.extend([pattern, directory])
            
            try:
                result = await asyncio.to_thread(
                    subprocess.run, cmd, capture_output=True, text=True, timeout=30
                )
                lines = result.stdout.strip().split("\n")[:max_results]
                return {"matches": lines, "count": len(lines), "pattern": pattern}
            except Exception as e:
                return {"error": str(e)}
        except Exception as e:
            return {"error": str(e)}
