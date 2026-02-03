"""Tools package - atomic tools for LLM function calling."""

from .file_tools import ReadFileTool, WriteFileTool, ListDirectoryTool
from .code_tools import SearchCodeTool
from .bash_tools import RunCommandTool
from .p4_tools import (
    P4SyncTool, P4DiffTool, P4GrepTool, 
    P4RevertTool, P4EditTool, P4StatusTool
)


def register_all_tools():
    """Register all tools to the global registry."""
    from src.core.registry import registry
    
    # File tools
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(ListDirectoryTool())
    
    # Code tools
    registry.register(SearchCodeTool())
    
    # Bash tools
    registry.register(RunCommandTool())
    
    # Perforce tools
    registry.register(P4SyncTool())
    registry.register(P4DiffTool())
    registry.register(P4GrepTool())
    registry.register(P4RevertTool())
    registry.register(P4EditTool())
    registry.register(P4StatusTool())


__all__ = [
    "ReadFileTool", "WriteFileTool", "ListDirectoryTool",
    "SearchCodeTool", "RunCommandTool",
    "P4SyncTool", "P4DiffTool", "P4GrepTool", 
    "P4RevertTool", "P4EditTool", "P4StatusTool",
    "register_all_tools",
]
