"""Slack planning tools for Deep Agents.

Tools for managing plans and progress updates in Slack threads.
Separates execution logic from Tool wrappers for internal reuse.
"""

from langchain_core.tools import tool
from typing import Optional

# --- Implementation Logic (Plain Async Functions) ---

async def execute_post_checklist(channel: str, thread_ts: str, items: list[str]) -> dict:
    """Internal logic for posting checklist."""
    from src.core.context import get_context
    slack = get_context().slack
    
    checklist = "\n".join([f"- [ ] {item}" for item in items])
    resp = await slack.send_message(channel, f"📋 **Plan**\n{checklist}", thread_ts=thread_ts)
    return {"ts": resp.get("ts")}

async def execute_update_checklist(channel: str, ts: str, items: list[dict]) -> str:
    """Internal logic for updating checklist."""
    from src.core.context import get_context
    slack = get_context().slack
    
    checklist = "\n".join([
        f"- [{'x' if item['done'] else ' '}] {item['text']}" 
        for item in items
    ])
    await slack.update_message(channel, ts, f"📋 **Plan**\n{checklist}")
    return "Checklist updated"

async def execute_upload_plan_file(channel: str, thread_ts: str, content: str, filename: str = "plan.md") -> dict:
    """Internal logic for file upload."""
    from src.core.context import get_context
    slack = get_context().slack
    
    result = await slack.app.client.files_upload_v2(
        channel=channel,
        thread_ts=thread_ts,
        content=content,
        filename=filename,
        title="📄 Detailed Plan"
    )
    return {"file_id": result.get("file", {}).get("id")}

async def execute_post_progress(channel: str, thread_ts: str, message: str) -> dict:
    """Internal logic for progress update."""
    from src.core.context import get_context
    slack = get_context().slack
    
    resp = await slack.send_message(channel, message, thread_ts=thread_ts)
    return {"ts": resp.get("ts")}


# --- Tool Wrappers (Exposed to Agents) ---

@tool
async def post_checklist(channel: str, thread_ts: str, items: list[str]) -> dict:
    """Post a checklist to Slack thread for planning.
    
    Args:
        channel: Slack channel ID
        thread_ts: Thread timestamp
        items: List of checklist items
    
    Returns:
        Message timestamp for updates
    """
    return await execute_post_checklist(channel, thread_ts, items)

@tool
async def update_checklist(channel: str, ts: str, items: list[dict]) -> str:
    """Update checklist with progress.
    
    Args:
        channel: Slack channel ID
        ts: Message timestamp to update
        items: List of dicts with 'text' and 'done' keys
    
    Returns:
        Confirmation message
    """
    return await execute_update_checklist(channel, ts, items)

@tool
async def upload_plan_file(channel: str, thread_ts: str, content: str, filename: str = "plan.md") -> dict:
    """Upload complex plan as .md file to Slack thread.
    
    Args:
        channel: Slack channel ID
        thread_ts: Thread timestamp
        content: Markdown content
        filename: Filename (default: plan.md)
    """
    return await execute_upload_plan_file(channel, thread_ts, content, filename)

@tool
async def post_progress(channel: str, thread_ts: str, message: str) -> dict:
    """Post progress update as thread reply.
    
    Args:
        channel: Slack channel ID
        thread_ts: Thread timestamp
        message: Progress message
    """
    return await execute_post_progress(channel, thread_ts, message)


# Export all Slack tools
ALL_SLACK_TOOLS = [
    post_checklist,
    update_checklist,
    upload_plan_file,
    post_progress,
]
