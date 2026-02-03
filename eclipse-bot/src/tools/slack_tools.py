"""Slack-specific tools for reading files, managing reminders, and working with canvases."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from src.core.registry import BaseTool

logger = logging.getLogger(__name__)


class ReadSlackFileTool(BaseTool):
    """Read contents of a file uploaded to Slack."""
    
    name = "read_slack_file"
    description = "Read the contents of a file that was uploaded to Slack. Provide the file URL or ID."
    parameters = {
        "type": "object",
        "properties": {
            "file_url": {
                "type": "string",
                "description": "The Slack file URL (e.g., from a message containing a file)"
            }
        },
        "required": ["file_url"]
    }
    
    async def execute(self, input_data: dict) -> dict:
        """Download and read file contents."""
        from src.main import get_slack_integration
        
        file_url = input_data.get("file_url", "")
        slack = get_slack_integration()
        
        try:
            # Extract file ID from URL if needed
            # URLs typically look like: https://files.slack.com/files-pri/...
            # or just a file ID directly
            file_id = self._extract_file_id(file_url)
            
            # Get file info
            file_info = await slack.get_file_info(file_id)
            
            if not file_info or not file_info.get("ok"):
                return {"status": "error", "error": "File not found or inaccessible"}
            
            file_data = file_info.get("file", {})
            file_name = file_data.get("name", "unknown")
            file_type = file_data.get("mimetype", "unknown")
            
            # Download file content
            content = await slack.download_file(file_id)
            
            return {
                "status": "success",
                "file_name": file_name,
                "file_type": file_type,
                "content": content,
                "size": len(content) if content else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to read Slack file: {e}")
            return {"status": "error", "error": str(e)}
    
    def _extract_file_id(self, file_url: str) -> str:
        """Extract file ID from Slack file URL."""
        # If it's already just an ID, return it
        if not file_url.startswith("http"):
            return file_url
            
        # Extract from URL pattern
        # Example: https://files.slack.com/files-pri/T123/F456/file.txt
        parts = file_url.split("/")
        for i, part in enumerate(parts):
            if part.startswith("F") and len(part) > 1:
                return part
                
        return file_url


class SetReminderTool(BaseTool):
    """Set a reminder in Slack."""
    
    name = "set_reminder"
    description = "Create a Slack reminder to notify a user at a specific time"
    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "What to remind about"
            },
            "time": {
                "type": "string",
                "description": "When to send the reminder (e.g., 'in 30 minutes', 'tomorrow at 9am', 'in 2 hours')"
            },
            "user_id": {
                "type": "string",
                "description": "User ID to remind (optional, defaults to the requesting user)"
            }
        },
        "required": ["text", "time"]
    }
    
    async def execute(self, input_data: dict) -> dict:
        """Create a reminder."""
        from src.main import get_slack_integration
        
        text = input_data.get("text", "")
        time_str = input_data.get("time", "")
        user_id = input_data.get("user_id")
        
        slack = get_slack_integration()
        
        try:
            result = await slack.add_reminder(text, time_str, user_id)
            
            if result.get("ok"):
                reminder = result.get("reminder", {})
                return {
                    "status": "success",
                    "reminder_id": reminder.get("id"),
                    "time": reminder.get("time"),
                    "message": f"Reminder set: '{text}' {time_str}"
                }
            else:
                return {
                    "status": "error",
                    "error": result.get("error", "Failed to create reminder")
                }
                
        except Exception as e:
            logger.error(f"Failed to set reminder: {e}")
            return {"status": "error", "error": str(e)}


class ListRemindersTool(BaseTool):
    """List active reminders."""
    
    name = "list_reminders"
    description = "List all active reminders for the current user"
    parameters = {
        "type": "object",
        "properties": {}
    }
    
    async def execute(self, input_data: dict) -> dict:
        """List reminders."""
        from src.main import get_slack_integration
        
        slack = get_slack_integration()
        
        try:
            result = await slack.list_reminders()
            
            if result.get("ok"):
                reminders = result.get("reminders", [])
                return {
                    "status": "success",
                    "count": len(reminders),
                    "reminders": [
                        {
                            "id": r.get("id"),
                            "text": r.get("text"),
                            "time": r.get("time"),
                            "user": r.get("user")
                        }
                        for r in reminders
                    ]
                }
            else:
                return {
                    "status": "error",
                    "error": result.get("error", "Failed to list reminders")
                }
                
        except Exception as e:
            logger.error(f"Failed to list reminders: {e}")
            return {"status": "error", "error": str(e)}


class CreateCanvasTool(BaseTool):
    """Create a new Slack Canvas."""
    
    name = "create_canvas"
    description = "Create a new Slack Canvas document with the given content"
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Title of the canvas"
            },
            "content": {
                "type": "string",
                "description": "Markdown content for the canvas"
            },
            "channel_id": {
                "type": "string",
                "description": "Channel ID to share the canvas in (optional)"
            }
        },
        "required": ["title", "content"]
    }
    
    async def execute(self, input_data: dict) -> dict:
        """Create a canvas."""
        from src.main import get_slack_integration
        
        title = input_data.get("title", "")
        content = input_data.get("content", "")
        channel_id = input_data.get("channel_id")
        
        slack = get_slack_integration()
        
        try:
            result = await slack.create_canvas(title, content, channel_id)
            
            if result.get("ok"):
                canvas = result.get("canvas", {})
                return {
                    "status": "success",
                    "canvas_id": canvas.get("id"),
                    "url": canvas.get("url"),
                    "message": f"Canvas '{title}' created successfully"
                }
            else:
                return {
                    "status": "error",
                    "error": result.get("error", "Failed to create canvas")
                }
                
        except Exception as e:
            logger.error(f"Failed to create canvas: {e}")
            return {"status": "error", "error": str(e)}


class ReadCanvasTool(BaseTool):
    """Read contents of a Slack Canvas."""
    
    name = "read_canvas"
    description = "Read the contents of an existing Slack Canvas"
    parameters = {
        "type": "object",
        "properties": {
            "canvas_id": {
                "type": "string",
                "description": "ID of the canvas to read"
            }
        },
        "required": ["canvas_id"]
    }
    
    async def execute(self, input_data: dict) -> dict:
        """Read a canvas."""
        from src.main import get_slack_integration
        
        canvas_id = input_data.get("canvas_id", "")
        slack = get_slack_integration()
        
        try:
            result = await slack.get_canvas(canvas_id)
            
            if result.get("ok"):
                canvas = result.get("canvas", {})
                return {
                    "status": "success",
                    "title": canvas.get("title"),
                    "content": canvas.get("content"),
                    "url": canvas.get("url")
                }
            else:
                return {
                    "status": "error",
                    "error": result.get("error", "Failed to read canvas")
                }
                
        except Exception as e:
            logger.error(f"Failed to read canvas: {e}")
            return {"status": "error", "error": str(e)}


class UpdateCanvasTool(BaseTool):
    """Update an existing Slack Canvas."""
    
    name = "update_canvas"
    description = "Update or append content to an existing Slack Canvas"
    parameters = {
        "type": "object",
        "properties": {
            "canvas_id": {
                "type": "string",
                "description": "ID of the canvas to update"
            },
            "content": {
                "type": "string",
                "description": "New markdown content (will replace existing content)"
            }
        },
        "required": ["canvas_id", "content"]
    }
    
    async def execute(self, input_data: dict) -> dict:
        """Update a canvas."""
        from src.main import get_slack_integration
        
        canvas_id = input_data.get("canvas_id", "")
        content = input_data.get("content", "")
        
        slack = get_slack_integration()
        
        try:
            result = await slack.update_canvas(canvas_id, content)
            
            if result.get("ok"):
                return {
                    "status": "success",
                    "canvas_id": canvas_id,
                    "message": "Canvas updated successfully"
                }
            else:
                return {
                    "status": "error",
                    "error": result.get("error", "Failed to update canvas")
                }
                
        except Exception as e:
            logger.error(f"Failed to update canvas: {e}")
            return {"status": "error", "error": str(e)}

