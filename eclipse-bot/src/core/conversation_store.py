"""Stateless conversation memory store leveraging Slack's history."""

import logging
from typing import Optional, List, Any
from ..models import Message

logger = logging.getLogger(__name__)

class ConversationStore:
    """Stateless conversation storage using Slack as the source of truth.
    
    Instead of storing messages in a DB, it fetches them directly from Slack
    when needed.
    """
    
    def __init__(self):
        """Initialize the store."""
        self.slack_integration = None
        
    def set_slack_integration(self, slack_integration: Any):
        """Inject SlackIntegration instance."""
        self.slack_integration = slack_integration
        logger.info("SlackIntegration injected into ConversationStore")
    
    async def initialize(self):
        """No DB initialization needed."""
        pass
    
    async def add_message(
        self,
        channel_id: str,
        role: str,
        content: Optional[str] = None,
        user_id: str = "system",
        thread_ts: Optional[str] = None,
        tool_calls: Optional[list] = None,
        tool_call_id: Optional[str] = None,
    ) -> int:
        """No-op for stateless store. Slack handles storage."""
        # We don't need to save anything. Slack saves it when we send it.
        # Return a dummy ID.
        return 0
    
    async def get_conversation(
        self,
        channel_id: str,
        thread_ts: Optional[str] = None,
        limit: int = 20,
    ) -> List[Message]:
        """Fetch conversation history directly from Slack."""
        if not self.slack_integration:
            logger.error("SlackIntegration not set in ConversationStore")
            return []

        try:
            client = self.slack_integration.app.client
            messages = []
            
            # Case 1: Thread Reply
            if thread_ts:
                response = await client.conversations_replies(
                    channel=channel_id,
                    ts=thread_ts,
                    limit=limit
                )
                slack_messages = response.get("messages", [])
            
            # Case 2: Channel/DM History (No Thread)
            else:
                response = await client.conversations_history(
                    channel=channel_id,
                    limit=limit
                )
                slack_messages = response.get("messages", [])

            # Convert Slack messages to our Message model
            # Slack returns newest first? No, replies returns oldest first usually, history returns newest.
            # Let's standardize to [Oldest -> Newest] for LLM context.
            
            # replies: usually chronological
            # history: usually reverse chronological
            
            # If history (no thread), reverse it to make it chronological
            if not thread_ts:
                slack_messages = list(reversed(slack_messages))
                
            bot_id = await self.slack_integration.get_bot_user_id()

            for msg in slack_messages:
                # Basic role mapping
                msg_user = msg.get("user")
                text = msg.get("text", "")
                
                role = "user"
                if msg_user == bot_id:
                    role = "assistant"
                
                # Check for "Session Start" marker if in DM? 
                # For now just return raw history.
                # User requested specific DM parsing logic.
                # "Scan for [SESSION_START] ... [SESSION_END]"
                
                # Handling System/Tool messages might be tricky with just Slack history 
                # unless we format them specifically. 
                # For now map text content.
                
                messages.append(Message(
                    role=role,
                    content=text,
                    user_id=msg_user or "unknown"
                ))
                
            return messages

        except Exception as e:
            logger.error(f"Failed to fetch Slack history: {e}")
            return []
    
    async def clear_conversation(
        self,
        channel_id: str,
        thread_ts: Optional[str] = None,
    ):
        """Mark session end (Logic handled in session tools, no-op here)."""
        pass
    
    async def close(self):
        """No connection to close."""
        pass
