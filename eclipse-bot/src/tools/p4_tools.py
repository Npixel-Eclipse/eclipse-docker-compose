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


class P4FilelogTool(BaseWorkflow):
    """Get file revision history."""
    
    name = "p4_filelog"
    description = "Get revision history of a file (who changed it, when, why)."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to get history for"},
            "max_revisions": {"type": "integer", "description": "Max revisions to show (default: 20)"},
        },
        "required": ["path"],
    }
    
    async def execute(self, input_data: dict) -> dict:
        path = input_data.get("path", "")
        max_revisions = input_data.get("max_revisions", 20)
        
        try:
            p4 = PerforceClient()
            output = await asyncio.to_thread(p4._run, "filelog", "-m", str(max_revisions), path, check=False)
            
            if len(output) > 5000:
                output = output[:5000] + "\n... [truncated]"
            
            return {
                "history": output,
                "path": path,
            }
        except Exception as e:
            return {"error": str(e)}


class P4DescribeTool(BaseWorkflow):
    """Get changelist details."""
    
    name = "p4_describe"
    description = "Get detailed information about a changelist (files, description, diff)."
    parameters = {
        "type": "object",
        "properties": {
            "changelist": {"type": "string", "description": "Changelist number"},
            "show_diff": {"type": "boolean", "description": "Include file diffs (default: false)"},
        },
        "required": ["changelist"],
    }
    
    async def execute(self, input_data: dict) -> dict:
        changelist = input_data.get("changelist", "")
        show_diff = input_data.get("show_diff", False)
        
        try:
            p4 = PerforceClient()
            
            args = ["describe"]
            if not show_diff:
                args.append("-s")  # Summary only
            args.append(changelist)
            
            output = await asyncio.to_thread(p4._run, *args, check=False)
            
            if len(output) > 10000:
                output = output[:10000] + "\n... [truncated]"
            
            return {
                "description": output,
                "changelist": changelist,
            }
        except Exception as e:
            return {"error": str(e)}


class P4ChangesTool(BaseWorkflow):
    """List changelists."""
    
    name = "p4_changes"
    description = "List changelists for a path or user."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Depot path to filter by"},
            "user": {"type": "string", "description": "User to filter by"},
            "max_results": {"type": "integer", "description": "Max results (default: 20)"},
            "status": {"type": "string", "description": "Status filter: pending, submitted, shelved"},
        },
    }
    
    async def execute(self, input_data: dict) -> dict:
        path = input_data.get("path", "//...")
        user = input_data.get("user")
        max_results = input_data.get("max_results", 20)
        status = input_data.get("status", "submitted")
        
        try:
            p4 = PerforceClient()
            
            args = ["changes", "-m", str(max_results), "-s", status]
            if user:
                args.extend(["-u", user])
            args.append(path)
            
            output = await asyncio.to_thread(p4._run, *args, check=False)
            
            lines = [l for l in output.strip().split("\n") if l][:max_results]
            
            return {
                "changelists": lines,
                "count": len(lines),
            }
        except Exception as e:
            return {"error": str(e)}


class P4PrintTool(BaseWorkflow):
    """Get file content from depot."""
    
    name = "p4_print"
    description = "Get file content from Perforce depot (any revision)."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Depot file path (can include #rev or @change)"},
        },
        "required": ["path"],
    }
    
    async def execute(self, input_data: dict) -> dict:
        path = input_data.get("path", "")
        
        try:
            p4 = PerforceClient()
            output = await asyncio.to_thread(p4._run, "print", "-q", path, check=False)
            
            lines = output.splitlines()
            total_lines = len(lines)
            
            # Limit to 500 lines
            if total_lines > 500:
                output = "\n".join(lines[:500]) + f"\n... [truncated, showing 500/{total_lines} lines]"
            
            return {
                "content": output,
                "total_lines": total_lines,
                "path": path,
            }
        except Exception as e:
            return {"error": str(e)}


class P4AnnotateTool(BaseWorkflow):
    """Get file blame/annotate info."""
    
    name = "p4_annotate"
    description = "Show who changed each line of a file (blame)."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to annotate"},
            "show_changes": {"type": "boolean", "description": "Show changelist numbers instead of dates"},
        },
        "required": ["path"],
    }
    
    async def execute(self, input_data: dict) -> dict:
        path = input_data.get("path", "")
        show_changes = input_data.get("show_changes", True)
        
        try:
            p4 = PerforceClient()
            
            args = ["annotate"]
            if show_changes:
                args.append("-c")  # Show changelist numbers
            args.append(path)
            
            output = await asyncio.to_thread(p4._run, *args, check=False)
            
            lines = output.splitlines()
            if len(lines) > 200:
                output = "\n".join(lines[:200]) + f"\n... [truncated, showing 200/{len(lines)} lines]"
            
            return {
                "annotate": output,
                "path": path,
            }
        except Exception as e:
            return {"error": str(e)}


class P4FstatTool(BaseWorkflow):
    """Get file status information."""
    
    name = "p4_fstat"
    description = "Get detailed file status (revision, action, lock status, etc.)."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to check"},
        },
        "required": ["path"],
    }
    
    async def execute(self, input_data: dict) -> dict:
        path = input_data.get("path", "")
        
        try:
            p4 = PerforceClient()
            output = await asyncio.to_thread(p4._run, "fstat", path, check=False)
            
            # Parse fstat output into dict
            info = {}
            for line in output.strip().split("\n"):
                if line.startswith("..."):
                    parts = line[3:].strip().split(" ", 1)
                    if len(parts) == 2:
                        info[parts[0]] = parts[1]
            
            return {
                "info": info,
                "path": path,
            }
        except Exception as e:
            return {"error": str(e)}
