"""File system tools for Eclipse Bot."""

from pathlib import Path
from src.core.registry import BaseWorkflow


class ReadFileTool(BaseWorkflow):
    """Read file contents with line range support."""
    
    name = "read_file"
    description = "Read the contents of a file. Returns max 500 lines at a time. Use start_line/end_line for pagination."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to the file to read"},
            "start_line": {"type": "integer", "description": "Start line number (1-indexed, default: 1)"},
            "end_line": {"type": "integer", "description": "End line number (inclusive, default: start_line + 500)"},
        },
        "required": ["path"],
    }
    
    async def execute(self, input_data: dict) -> dict:
        path = Path(input_data.get("path", ""))
        start_line = input_data.get("start_line")
        end_line = input_data.get("end_line")
        
        if not path.exists():
            return {"error": f"File not found: {path}"}
        
        if not path.is_file():
            return {"error": f"Not a file: {path}"}
        
        try:
            content = path.read_text(encoding="utf-8")
            lines = content.splitlines()
            total_lines = len(lines)
            
            # Apply line range with max 500 lines limit
            start_idx = (start_line - 1) if start_line else 0
            max_lines = 500
            default_end = min(start_idx + max_lines, total_lines)
            end_idx = min(end_line, start_idx + max_lines) if end_line else default_end
            
            lines = lines[start_idx:end_idx]
            content = "\n".join(lines)
            
            has_more = end_idx < total_lines
            
            # Truncate if still too large
            if len(content) > 50000:
                content = content[:50000] + "\n... [truncated]"
            
            return {
                "content": content,
                "total_lines": total_lines,
                "showing_lines": f"{start_idx + 1}-{end_idx}",
                "has_more": has_more,
                "size_bytes": path.stat().st_size,
            }
        except Exception as e:
            return {"error": str(e)}


class WriteFileTool(BaseWorkflow):
    """Write or create a file."""
    
    name = "write_file"
    description = "Write content to a file. Creates the file if it doesn't exist."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to the file to write"},
            "content": {"type": "string", "description": "Content to write to the file"},
            "append": {"type": "boolean", "description": "If true, append instead of overwriting"},
        },
        "required": ["path", "content"],
    }
    
    async def execute(self, input_data: dict) -> dict:
        path = Path(input_data.get("path", ""))
        content = input_data.get("content", "")
        append = input_data.get("append", False)
        
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            
            mode = "a" if append else "w"
            with open(path, mode, encoding="utf-8") as f:
                f.write(content)
            
            return {
                "status": "success",
                "path": str(path),
                "bytes_written": len(content.encode("utf-8")),
                "action": "appended" if append else "written",
            }
        except Exception as e:
            return {"error": str(e)}


class ListDirectoryTool(BaseWorkflow):
    """List directory contents."""
    
    name = "list_directory"
    description = "List files and directories in a given path. Max 200 entries, depth 3 for recursive."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path to list"},
            "recursive": {"type": "boolean", "description": "List recursively (max depth 3)"},
            "show_hidden": {"type": "boolean", "description": "Include hidden files"},
        },
        "required": ["path"],
    }
    
    async def execute(self, input_data: dict) -> dict:
        path = Path(input_data.get("path", "."))
        recursive = input_data.get("recursive", False)
        show_hidden = input_data.get("show_hidden", False)
        
        if not path.exists():
            return {"error": f"Path not found: {path}"}
        
        if not path.is_dir():
            return {"error": f"Not a directory: {path}"}
        
        try:
            entries = []
            
            if recursive:
                for item in path.rglob("*"):
                    if len(item.relative_to(path).parts) > 3:
                        continue
                    if not show_hidden and any(p.startswith(".") for p in item.parts):
                        continue
                    entries.append({
                        "path": str(item.relative_to(path)),
                        "type": "dir" if item.is_dir() else "file",
                        "size": item.stat().st_size if item.is_file() else None,
                    })
            else:
                for item in path.iterdir():
                    if not show_hidden and item.name.startswith("."):
                        continue
                    entries.append({
                        "name": item.name,
                        "type": "dir" if item.is_dir() else "file",
                        "size": item.stat().st_size if item.is_file() else None,
                    })
            
            entries.sort(key=lambda x: (x["type"] != "dir", x.get("name", x.get("path", ""))))
            
            if len(entries) > 200:
                entries = entries[:200]
                entries.append({"note": "... truncated"})
            
            return {
                "entries": entries,
                "count": len(entries),
                "path": str(path),
            }
        except Exception as e:
            return {"error": str(e)}
