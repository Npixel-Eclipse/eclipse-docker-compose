"""Perforce (P4) tools for Deep Agents.

All P4 tools converted to LangChain @tool format for use with create_deep_agent.
Uses AppContext for client management.
"""

import asyncio
import logging
from langchain_core.tools import tool
from src.core.context import get_context

logger = logging.getLogger(__name__)

@tool
async def p4_describe(changelist: str, show_diff: bool = False, mode: str = "snippet") -> str:
    """Get detailed information about a changelist (p4d 2022.1).
    
    Args:
        changelist: The numerical ID of the changelist.
        show_diff: If True, returns unified diffs (-du).
        mode: 'snippet' (default) - truncates very large outputs.
              'full' - returns complete output (caution: token heavy).
    """
    logger.info(f"Tool invoked: p4_describe(changelist={changelist}, show_diff={show_diff}, mode={mode})")
    try:
        p4 = get_context().p4
        args = ["describe"]
        if show_diff:
            args.append("-du")
        else:
            args.append("-s")
        args.append(changelist)
        
        output = await asyncio.to_thread(p4._run, *args, check=False)
        
        if mode == "snippet" and len(output) > 10000:
            output = output[:10000] + "\n... [truncated snippet, use mode='full' for detail]"
        
        return output
    except Exception as e:
        return f"Error: {e}"

@tool
async def p4_annotate(path: str, show_changes: bool = True, mode: str = "snippet") -> str:
    """Display file content with revision info for each line (blame).
    
    Args:
        path: Depot or local path to the file.
        show_changes: If True, uses -c to show changelist numbers.
        mode: 'snippet' (default) - shows first 200 lines.
              'full' - shows all content.
    """
    logger.info(f"Tool invoked: p4_annotate(path={path}, show_changes={show_changes}, mode={mode})")
    try:
        p4 = get_context().p4
        args = ["annotate"]
        if show_changes:
            args.append("-c")
        args.append(path)
        
        output = await asyncio.to_thread(p4._run, *args, check=False)
        
        if mode == "full":
            return output
            
        lines = output.splitlines()
        if len(lines) > 200:
            output = "\n".join(lines[:200]) + f"\n... [truncated snippet, use mode='full' to see all {len(lines)} lines]"
        
        return output
    except Exception as e:
        return f"Error: {e}"

@tool
async def p4_filelog(path: str, max_revisions: int = 20, mode: str = "snippet") -> str:
    """List revision history of a file, including integrations.
    
    Args:
        path: Depot or local path to the file.
        max_revisions: Limits output count (default 20).
        mode: 'snippet' (default) - truncates long descriptions.
              'full' - returns complete output.
    """
    logger.info(f"Tool invoked: p4_filelog(path={path}, max_revisions={max_revisions}, mode={mode})")
    try:
        p4 = get_context().p4
        output = await asyncio.to_thread(p4._run, "filelog", "-m", str(max_revisions), path, check=False)
        
        if mode == "snippet" and len(output) > 5000:
            output = output[:5000] + "\n... [truncated snippet, use mode='full' for detail]"
        
        return output
    except Exception as e:
        return f"Error: {e}"

@tool
async def p4_print(path: str, mode: str = "snippet") -> str:
    """Retrieve file contents from the Perforce depot.
    
    Args:
        path: Depot path, optionally with revision/changelist.
        mode: 'snippet' (default) - shows first 500 lines.
              'full' - shows all content.

    ⚠️ WARNING: Do NOT use this to fetch entire source files (1GB+). Use p4_annotate or grep instead.
    """
    logger.info(f"Tool invoked: p4_print(path={path}, mode={mode})")
    try:
        p4 = get_context().p4
        output = await asyncio.to_thread(p4._run, "print", "-q", path, check=False)
        
        if mode == "full":
            return output
            
        lines = output.splitlines()
        total_lines = len(lines)
        if total_lines > 500:
            output = "\n".join(lines[:500]) + f"\n... [truncated snippet, use mode='full' to see all {total_lines} lines]"
        
        return output
    except Exception as e:
        return f"Error: {e}"

@tool
async def p4_grep(pattern: str, path: str = "//...", case_insensitive: bool = False) -> str:
    """Search for a regular expression pattern within depot files.
    
    Args:
        pattern: The regex pattern to search for.
        path: Depot path to search in (e.g., '//Eclipse_Studio/Main/...').
        case_insensitive: If True, uses -i for case-insensitive matching.

    ⚠️ WARNING: Avoid running on root //... if possible. Use specific paths to prevent timeouts.
    """
    logger.info(f"Tool invoked: p4_grep(pattern={pattern}, path={path}, case_insensitive={case_insensitive})")
    try:
        p4 = get_context().p4
        args = ["grep", "-n"]
        if case_insensitive:
            args.append("-i")
        args.extend(["-e", pattern, path])
        
        output = await asyncio.to_thread(p4._run, *args, check=False)
        
        lines = output.strip().split("\n")[:30]
        return "\n".join(lines) + f"\n[{len(lines)} matches shown]"
    except Exception as e:
        return f"Error: {e}"

@tool
async def p4_sync(path: str = "//...") -> str:
    """Synchronize the client workspace with the depot.
    
    Args:
        path: Depot path to sync.
    """
    try:
        p4 = get_context().p4
        output = await asyncio.to_thread(p4.sync, path)
        lines = [l for l in output.strip().split("\n") if l]
        return f"{output[:2000]}\n... [truncated]" if len(output) > 2000 else output
    except Exception as e:
        return f"Error: {e}"

@tool
async def p4_diff(path: str = "//...", mode: str = "snippet") -> str:
    """Compare workspace files with their depot counterparts.
    
    Args:
        path: Depot or local path to diff.
        mode: 'snippet' (default) - truncates large diffs.
        'full' - returns complete diff.
    """
    try:
        p4 = get_context().p4
        output = await asyncio.to_thread(p4._run, "diff", "-du", path, check=False)
        
        if mode == "snippet" and len(output) > 10000:
            output = output[:10000] + "\n... [truncated snippet, use mode='full' for detail]"
        
        return output
    except Exception as e:
        return f"Error: {e}"

@tool
async def p4_revert(path: str = "//...", unchanged_only: bool = False) -> str:
    """Undo changes to opened files in the workspace.
    
    Args:
        path: Path to revert.
        unchanged_only: If True, only revert files that haven't been modified locally.
    """
    try:
        p4 = get_context().p4
        if unchanged_only:
            output = await asyncio.to_thread(p4._run, "revert", "-a", path)
        else:
            output = await asyncio.to_thread(p4.revert, path)
        return output
    except Exception as e:
        return f"Error: {e}"

@tool
async def p4_edit(path: str) -> str:
    """Mark files in the workspace as open for modification.
    
    Args:
        path: Local or depot path to the file(s) to be checked out.
    """
    try:
        p4 = get_context().p4
        output = await asyncio.to_thread(p4.edit, path)
        return f"{output}\nStatus: opened for edit"
    except Exception as e:
        return f"Error: {e}"

@tool
async def p4_status() -> str:
    """Report workspace changes requiring reconciliation."""
    try:
        p4 = get_context().p4
        output = await asyncio.to_thread(p4.status)
        return output
    except Exception as e:
        return f"Error: {e}"

@tool
async def p4_changes(path: str = "//...", user: str = None, max_results: int = 20, status: str = "submitted") -> str:
    """List changelists matching specified criteria.
    
    Args:
        path: Limit to changelists affecting files in this path.
        user: Limit to changelists created by this user.
        status: 'pending', 'submitted', or 'shelved'.

    ⚠️ WARNING: Do NOT search by time/date (e.g. @2024/01/01). Use CL numbers or Revisions (#head) only.
    """
    try:
        p4 = get_context().p4
        args = ["changes", "-m", str(max_results), "-s", status]
        if user: args.extend(["-u", user])
        args.append(path)
        output = await asyncio.to_thread(p4._run, *args, check=False)
        return output
    except Exception as e:
        return f"Error: {e}"

@tool
async def p4_fstat(path: str) -> str:
    """Display status information and metadata for files."""
    try:
        p4 = get_context().p4
        output = await asyncio.to_thread(p4._run, "fstat", path, check=False)
        return output
    except Exception as e:
        return f"Error: {e}"

# Export all P4 tools
ALL_P4_TOOLS = [
    p4_describe, p4_annotate, p4_filelog, p4_print, 
    p4_grep, p4_sync, p4_diff, p4_revert, 
    p4_edit, p4_status, p4_changes, p4_fstat,
]
