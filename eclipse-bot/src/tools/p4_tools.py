"""Perforce (P4) tools for Eclipse Bot."""

import asyncio
from src.core.registry import BaseWorkflow
from src.core import PerforceClient


class P4SyncTool(BaseWorkflow):
    """Sync files from Perforce depot."""
    
    name = "p4_sync"
    description = "Sync files from Perforce depot to the workspace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Depot path to sync (e.g., //Eclipse_Studio/Main/...)"},
        },
    }
    
    async def execute(self, input_data: dict) -> dict:
        path = input_data.get("path", "//...")
        
        try:
            p4 = PerforceClient()
            output = await asyncio.to_thread(p4.sync, path)
            
            lines = [l for l in output.strip().split("\n") if l]
            
            return {
                "output": output[:2000] if len(output) > 2000 else output,
                "files_count": len(lines),
                "path": path,
            }
        except Exception as e:
            return {"error": str(e)}


class P4DiffTool(BaseWorkflow):
    """Show diff of opened files in Perforce."""
    
    name = "p4_diff"
    description = "Show diff of opened (modified) files in Perforce."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to diff (default: all opened files)"},
        },
    }
    
    async def execute(self, input_data: dict) -> dict:
        path = input_data.get("path", "//...")
        
        try:
            p4 = PerforceClient()
            output = await asyncio.to_thread(p4.diff, path)
            
            # Truncate large diffs
            if len(output) > 10000:
                output = output[:10000] + "\n... [truncated, diff too large]"
            
            return {
                "diff": output,
                "path": path,
            }
        except Exception as e:
            return {"error": str(e)}


class P4GrepTool(BaseWorkflow):
    """Search for pattern in Perforce depot files."""
    
    name = "p4_grep"
    description = "Search for a pattern in Perforce depot files using p4 grep."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Search pattern (regex)"},
            "path": {"type": "string", "description": "Depot path to search in"},
            "case_insensitive": {"type": "boolean", "description": "Case insensitive search"},
        },
        "required": ["pattern", "path"],
    }
    
    async def execute(self, input_data: dict) -> dict:
        pattern = input_data.get("pattern", "")
        path = input_data.get("path", "//...")
        case_insensitive = input_data.get("case_insensitive", False)
        
        try:
            p4 = PerforceClient()
            
            # Build grep command args
            args = ["grep"]
            if case_insensitive:
                args.append("-i")
            args.extend(["-e", pattern, path])
            
            output = await asyncio.to_thread(p4._run, *args, check=False)
            
            lines = output.strip().split("\n")[:30]  # Limit results
            
            return {
                "matches": lines,
                "count": len(lines),
                "pattern": pattern,
            }
        except Exception as e:
            return {"error": str(e)}


class P4RevertTool(BaseWorkflow):
    """Revert changes in Perforce."""
    
    name = "p4_revert"
    description = "Revert opened files in Perforce (discard local changes)."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to revert (default: all opened files)"},
            "unchanged_only": {"type": "boolean", "description": "Only revert unchanged files (-a flag)"},
        },
    }
    
    async def execute(self, input_data: dict) -> dict:
        path = input_data.get("path", "//...")
        unchanged_only = input_data.get("unchanged_only", False)
        
        try:
            p4 = PerforceClient()
            
            if unchanged_only:
                output = await asyncio.to_thread(p4._run, "revert", "-a", path)
            else:
                output = await asyncio.to_thread(p4.revert, path)
            
            return {
                "output": output,
                "path": path,
                "unchanged_only": unchanged_only,
            }
        except Exception as e:
            return {"error": str(e)}


class P4EditTool(BaseWorkflow):
    """Open file for edit in Perforce (checkout)."""
    
    name = "p4_edit"
    description = "Open a file for edit (checkout) in Perforce."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to open for edit"},
        },
        "required": ["path"],
    }
    
    async def execute(self, input_data: dict) -> dict:
        path = input_data.get("path", "")
        
        if not path:
            return {"error": "Path is required"}
        
        try:
            p4 = PerforceClient()
            output = await asyncio.to_thread(p4.edit, path)
            
            return {
                "output": output,
                "path": path,
                "status": "opened for edit",
            }
        except Exception as e:
            return {"error": str(e)}


class P4StatusTool(BaseWorkflow):
    """Show currently opened files in Perforce."""
    
    name = "p4_status"
    description = "Show currently opened (checked out) files in Perforce."
    parameters = {
        "type": "object",
        "properties": {},
    }
    
    async def execute(self, input_data: dict) -> dict:
        try:
            p4 = PerforceClient()
            output = await asyncio.to_thread(p4.status)
            
            lines = [l for l in output.strip().split("\n") if l]
            
            return {
                "opened_files": lines,
                "count": len(lines),
            }
        except Exception as e:
            return {"error": str(e)}
