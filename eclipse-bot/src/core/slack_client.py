"""Slack integration using Bolt framework with Socket Mode."""

import logging
from typing import Callable, Optional
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

logger = logging.getLogger(__name__)


class SlackIntegration:
    """Slack Bot integration for Eclipse Bot."""

    def __init__(self, bot_token: str, app_token: str):
        self.app = AsyncApp(token=bot_token)
        self.app_token = app_token
        self.handler: Optional[AsyncSocketModeHandler] = None
        self._bot_user_id: Optional[str] = None
        self._setup_handlers()

    def _setup_handlers(self):
        """Internal bolt handlers (placeholder)."""
        pass

    async def get_bot_user_id(self) -> str:
        """Fetch and cache the bot's user ID."""
        if not self._bot_user_id:
            auth_test = await self.app.client.auth_test()
            self._bot_user_id = auth_test["user_id"]
        return self._bot_user_id

    def on_mention(self, handler: Callable):
        """Register a handler for app mentions."""
        @self.app.event("app_mention")
        async def internal_handler(event, say):
            await handler(event, say)

    def on_message(self, handler: Callable):
        """Register a handler for direct messages."""
        @self.app.event("message")
        async def internal_handler(event, say):
            # Bolt handles filtering (e.g. only DMs) if needed via matchers
            await handler(event, say)

    async def send_message(
        self,
        channel: str,
        text: str,
        thread_ts: Optional[str] = None,
        blocks: Optional[list[dict]] = None,
    ) -> dict:
        """Send a message to a channel."""
        params = {
            "channel": channel,
            "text": text,
            "thread_ts": thread_ts,
            "blocks": blocks
        }
        return await self.app.client.chat_postMessage(**params)

    async def update_message(
        self,
        channel: str,
        ts: str,
        text: str,
        blocks: Optional[list[dict]] = None
    ) -> dict:
        """Update an existing message."""
        return await self.app.client.chat_update(
            channel=channel,
            ts=ts,
            text=text,
            blocks=blocks
        )

    async def add_reaction(self, channel: str, timestamp: str, name: str):
        """Add a reaction to a message."""
        return await self.app.client.reactions_add(
            channel=channel,
            timestamp=timestamp,
            name=name
        )

    async def set_assistant_status(self, channel: str, thread_ts: str, status: str = "Thinking...", loading_messages: Optional[list[str]] = None):
        """Set the assistant status (shimmering effect + text) in a thread.

        Requires assistant:write scope.
        """
        try:
            params = {
                "channel_id": channel,
                "thread_ts": thread_ts,
                "status": status
            }
            if loading_messages:
                params["loading_messages"] = loading_messages
                
            resp = await self.app.client.assistant_threads_setStatus(**params)
            if not resp.get("ok"):
                logger.warning(f"Slack API error setting assistant status: {resp.get('error')}")
            return resp
        except Exception as e:
            logger.warning(f"Failed to set assistant status Exception: {e}")
            return None

    async def get_streamer(
        self,
        channel: str,
        recipient_team_id: str,
        recipient_user_id: str,
        thread_ts: Optional[str] = None,
    ):
        """Get an official Slack chat_stream helper."""
        # Use the built-in helper from slack_sdk
        # This internally uses chat.startStream / appendStream / stopStream
        try:
            return await self.app.client.chat_stream(
                channel=channel,
                thread_ts=thread_ts,
                recipient_team_id=recipient_team_id,
                recipient_user_id=recipient_user_id,
                buffer_size=1
            )
        except AttributeError:
            # Fallback for older SDK versions that might not have the helper
            logger.warning("chat_stream helper not found, using legacy update logic is NOT recommended for Assistant UI")
            raise

    async def start(self):
        """Start the Socket Mode handler."""
        self.handler = AsyncSocketModeHandler(self.app, self.app_token)
        await self.handler.connect_async()

    async def stop(self):
        """Stop the Socket Mode handler."""
        if self.handler:
            await self.handler.close_async()
