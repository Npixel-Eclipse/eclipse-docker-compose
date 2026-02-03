"""Slack integration using Bolt framework with Socket Mode."""

import asyncio
import logging
from typing import Callable, Optional, Any
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

import re
logger = logging.getLogger(__name__)


class SlackIntegration:
    """Slack Bot integration with Socket Mode support."""

    def __init__(
        self,
        bot_token: str,
        app_token: str,
    ):
        self.app = AsyncApp(token=bot_token)
        self.app_token = app_token
        self._handler: Optional[AsyncSocketModeHandler] = None
        self._message_handlers: list[Callable] = []
        self._mention_handlers: list[Callable] = []
        self.bot_user_id: Optional[str] = None

        # Register internal event handlers
        self._setup_handlers()
        
        # Add global middleware to log ALL incoming events for debugging (DEBUG level)
        @self.app.middleware
        async def log_all_events(body, next):
            try:
                import json
                logger.debug(f"RAW PAYLOAD RECEIVED: {json.dumps(body, ensure_ascii=False)}")
            except Exception as e:
                logger.debug(f"RAW PAYLOAD RECEIVED (not JSON): {body}")
            return await next()

    async def get_bot_user_id(self) -> str:
        """Fetch and cache the bot's user ID."""
        if not self.bot_user_id:
            auth_response = await self.app.client.auth_test()
            self.bot_user_id = auth_response["user_id"]
        return self.bot_user_id

    def _setup_handlers(self):
        """Setup Slack event handlers."""

        @self.app.event("app_mention")
        async def handle_mention(event: dict, say: Callable):
            """Handle app mentions and ensure the bot is in the channel."""
            channel = event.get("channel")
            logger.info(f"DEBUG: [app_mention] event received - user={event.get('user')}, channel={channel}, ts={event.get('ts')}")
            
            # Ensure bot is in the channel to receive future message events
            try:
                await self.app.client.conversations_join(channel=channel)
            except Exception as e:
                logger.warning(f"Failed to join channel {channel}: {e} (might already be in it)")

            for handler in self._mention_handlers:
                try:
                    await handler(event, say)
                except Exception as e:
                    logger.error(f"Mention handler error: {e}")

        @self.app.event("message")
        async def handle_message(event: dict, say: Callable):
            """Handle all message events (unified handler to prevent duplicates)."""
            await self._internal_handle_message(event, say)

    async def _internal_handle_message(self, event: dict, say: Callable):
        user_id = event.get("user")
        bot_id = event.get("bot_id")
        subtype = event.get("subtype")
        channel = event.get("channel")
        text = event.get("text", "")[:50]
        
        logger.info(f"DEBUG: [message_callback] received - user={user_id}, bot_id={bot_id}, subtype={subtype}, channel={channel}, text='{text}'")
        
        bot_user_id = await self.get_bot_user_id()
        if user_id == bot_user_id or bot_id == bot_user_id:
            return
            
        if subtype in ["message_deleted", "bot_message", "message_changed"]:
            return
            
        for handler in self._message_handlers:
            try:
                await handler(event, say)
            except Exception as e:
                logger.error(f"Message handler error: {e}")

    def on_mention(self, handler: Callable):
        """Register a handler for app mentions.

        Args:
            handler: Async function(event, say) to handle mentions

        Example:
            @slack.on_mention
            async def handle(event, say):
                await say(f"Hello <@{event['user']}>!")
        """
        self._mention_handlers.append(handler)
        return handler

    def on_message(self, handler: Callable):
        """Register a handler for direct messages.

        Args:
            handler: Async function(event, say) to handle messages

        Example:
            @slack.on_message
            async def handle(event, say):
                await say("I received your message!")
        """
        self._message_handlers.append(handler)
        return handler

    async def send_message(
        self,
        channel: str,
        text: str,
        thread_ts: Optional[str] = None,
        blocks: Optional[list[dict]] = None,
    ) -> dict:
        """Send a message to a channel.

        Args:
            channel: Channel ID
            text: Message text
            thread_ts: Thread timestamp for replies
            blocks: Block Kit blocks

        Returns:
            Slack API response
        """
        kwargs: dict[str, Any] = {"channel": channel, "text": text}
        if thread_ts:
            kwargs["thread_ts"] = thread_ts
        if blocks:
            kwargs["blocks"] = blocks

        return await self.app.client.chat_postMessage(**kwargs)

        kwargs: dict[str, Any] = {"channel": channel, "ts": ts, "text": text}
        if blocks:
            kwargs["blocks"] = blocks
        return await self.app.client.chat_update(**kwargs)

    async def add_reaction(self, channel: str, timestamp: str, name: str):
        """Add a reaction to a message."""
        try:
            logger.info(f"SlaskIntegration.add_reaction called: ch={channel}, ts={timestamp}, name={name}")
            await self.app.client.reactions_add(
                channel=channel,
                timestamp=timestamp,
                name=name
            )
            logger.info(f"SlaskIntegration.add_reaction success: {name}")
        except Exception as e:
            logger.warning(f"Failed to add reaction {name}: {e}")
            # Raising exception to let workflow know (or log error there too)
            # CodeReviewWorkflow catches it now, so exposing it is better for debug
            # But let's keep warning to not crash critical path if not essential.

    async def remove_reaction(self, channel: str, timestamp: str, name: str):
        """Remove a reaction from a message."""
        try:
            logger.info(f"SlaskIntegration.remove_reaction called: ch={channel}, ts={timestamp}, name={name}")
            await self.app.client.reactions_remove(
                channel=channel,
                timestamp=timestamp,
                name=name
            )
        except Exception as e:
            logger.warning(f"Failed to remove reaction {name}: {e}")

    async def get_file_info(self, file_id: str) -> dict:
        """Get information about a Slack file."""
        try:
            return await self.app.client.files_info(file=file_id)
        except Exception as e:
            logger.error(f"Failed to get file info: {e}")
            return {"ok": False, "error": str(e)}

    async def download_file(self, file_id: str) -> Optional[str]:
        """Download file content from Slack."""
        try:
            file_info = await self.get_file_info(file_id)
            if not file_info.get("ok"):
                return None
                
            file_data = file_info.get("file", {})
            url_private = file_data.get("url_private_download") or file_data.get("url_private")
            
            if not url_private:
                return None
            
            # Download using bot token for auth
            import httpx
            headers = {"Authorization": f"Bearer {self.bot_token}"}
            async with httpx.AsyncClient() as client:
                response = await client.get(url_private, headers=headers)
                response.raise_for_status()
                return response.text
                
        except Exception as e:
            logger.error(f"Failed to download file: {e}")
            return None

    async def add_reminder(self, text: str, time: str, user: Optional[str] = None) -> dict:
        """Create a Slack reminder."""
        try:
            return await self.app.client.reminders_add(
                text=text,
                time=time,
                user=user
            )
        except Exception as e:
            logger.error(f"Failed to add reminder: {e}")
            return {"ok": False, "error": str(e)}

    async def list_reminders(self) -> dict:
        """List active reminders."""
        try:
            return await self.app.client.reminders_list()
        except Exception as e:
            logger.error(f"Failed to list reminders: {e}")
            return {"ok": False, "error": str(e)}

    async def create_canvas(self, title: str, content: str, channel_id: Optional[str] = None) -> dict:
        """Create a new Slack Canvas."""
        try:
            # Note: Canvas API might use canvases.create or similar
            # This is a placeholder - actual API endpoint may vary
            return await self.app.client.canvases_create(
                title=title,
                document_content={
                    "type": "markdown",
                    "markdown": content
                },
                channel_id=channel_id
            )
        except Exception as e:
            logger.error(f"Failed to create canvas: {e}")
            return {"ok": False, "error": str(e)}

    async def get_canvas(self, canvas_id: str) -> dict:
        """Read a Slack Canvas."""
        try:
            return await self.app.client.canvases_access(canvas_id=canvas_id)
        except Exception as e:
            logger.error(f"Failed to get canvas: {e}")
            return {"ok": False, "error": str(e)}

    async def update_canvas(self, canvas_id: str, content: str) -> dict:
        """Update an existing Slack Canvas."""
        try:
            return await self.app.client.canvases_edit(
                canvas_id=canvas_id,
                changes=[{
                    "operation": "replace",
                    "document_content": {
                        "type": "markdown",
                        "markdown": content
                    }
                }]
            )
        except Exception as e:
            logger.error(f"Failed to update canvas: {e}")
            return {"ok": False, "error": str(e)}

    async def get_streamer(
        self,
        channel: str,
        recipient_team_id: str,
        recipient_user_id: str,
        thread_ts: str,
    ):
        """Get an official Slack SDK chat_stream helper."""
        return SlackStreamer(
            self.app.client, 
            channel, 
            recipient_team_id, 
            recipient_user_id, 
            thread_ts
        )

    async def start(self):
        """Start the Socket Mode handler (non-blocking)."""
        self._handler = AsyncSocketModeHandler(self.app, self.app_token)
        # Use connect_async() instead of start_async() to avoid blocking
        await self._handler.connect_async()
        logger.info("Slack Socket Mode handler started")

    async def stop(self):
        """Stop the Socket Mode handler."""
        if self._handler:
            await self._handler.close_async()
            logger.info("Slack Socket Mode handler stopped")

class SlackStreamer:
    """Helper to stream responses to Slack using the official SDK chat_stream utility."""
    
    def __init__(
        self, 
        client, 
        channel: str, 
        recipient_team_id: str,
        recipient_user_id: str,
        thread_ts: str
    ):
        self.client = client
        self.channel = channel
        self.recipient_team_id = recipient_team_id
        self.recipient_user_id = recipient_user_id
        self.thread_ts = thread_ts
        self._streamer = None

    async def _init_streamer(self):
        """Initialize the official SDK streamer."""
        if not self._streamer:
            self._streamer = await self.client.chat_stream(
                channel=self.channel,
                thread_ts=self.thread_ts,
                recipient_team_id=self.recipient_team_id,
                recipient_user_id=self.recipient_user_id,
            )

    async def append(self, markdown_text: str):
        """Add text to the ongoing stream using the official SDK."""
        await self._init_streamer()
        await self._streamer.append(markdown_text=markdown_text)

    async def stop(self, blocks: Optional[list[dict]] = None):
        """Finalize the stream using the official SDK, optionally adding interactive blocks."""
        if self._streamer:
            await self._streamer.stop(blocks=blocks)

