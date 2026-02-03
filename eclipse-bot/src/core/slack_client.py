"""Slack integration using Bolt framework with Socket Mode."""

import asyncio
import logging
import time
from typing import Callable, Optional, Any
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

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

        # Register internal event handlers
        self._setup_handlers()

    def _setup_handlers(self):
        """Setup Slack event handlers."""

        @self.app.event("app_mention")
        async def handle_mention(event: dict, say: Callable):
            """Handle app mentions."""
            for handler in self._mention_handlers:
                try:
                    await handler(event, say)
                except Exception as e:
                    logger.error(f"Mention handler error: {e}")

        @self.app.event("message")
        async def handle_message(event: dict, say: Callable):
            """Handle direct messages."""
            # Ignore bot messages and app mentions (handled separately)
            if event.get("bot_id") or event.get("subtype"):
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

    async def update_message(
        self,
        channel: str,
        ts: str,
        text: str,
        blocks: Optional[list[dict]] = None,
    ) -> dict:
        """Update an existing message."""
        kwargs: dict[str, Any] = {"channel": channel, "ts": ts, "text": text}
        if blocks:
            kwargs["blocks"] = blocks
        return await self.app.client.chat_update(**kwargs)

    async def get_streamer(
        self,
        channel: str,
        recipient_team_id: str,
        recipient_user_id: str,
        thread_ts: Optional[str] = None,
    ):
        """Get an official Slack chat_stream helper."""
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
    """Helper to stream responses to Slack using official chat.startStream API."""
    
    def __init__(
        self, 
        client, 
        channel: str, 
        recipient_team_id: str,
        recipient_user_id: str,
        thread_ts: Optional[str] = None
    ):
        self.client = client
        self.channel = channel
        self.recipient_team_id = recipient_team_id
        self.recipient_user_id = recipient_user_id
        self.thread_ts = thread_ts
        self.stream_id = None

    async def append(self, markdown_text: str):
        """Add text to the ongoing stream."""
        if not self.stream_id:
            # Initialize the stream
            response = await self.client.chat_startStream(
                channel=self.channel,
                thread_ts=self.thread_ts,
                recipient_team_id=self.recipient_team_id,
                recipient_user_id=self.recipient_user_id,
            )
            self.stream_id = response["stream_id"]

        # Append to the stream
        await self.client.chat_appendStream(
            channel=self.channel,
            stream_id=self.stream_id,
            markdown_text=markdown_text
        )

    async def stop(self):
        """Finalize the stream."""
        if self.stream_id:
            await self.client.chat_stopStream(
                channel=self.channel,
                stream_id=self.stream_id
            )
