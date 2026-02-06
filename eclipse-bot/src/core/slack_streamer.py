"""Slack Streaming Handler.

Handles the complexity of:
1. Buffering token streams from the LLM.
2. Filtering out "thought" blocks and internal monologue.
3. Throttling updates to Slack to avoid rate limits.
"""

import time
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

class SlackStreamer:
    """Manages streaming responses to Slack."""
    
    def __init__(self, ctx, channel: str, thread_ts: str, throttle_interval: float = 1.0):
        self.ctx = ctx
        self.channel = channel
        self.thread_ts = thread_ts
        self.throttle_interval = throttle_interval
        
        self.streamer = None
        self.buffer = ""
        self.last_update_time = 0.0
        self.response_started = False
        
        # UI State
        self.last_status_update_time = 0.0

    async def start(self, event: dict):
        """Initialize the underlying Slack stream."""
        self.streamer = await self.ctx.slack.get_streamer(
            channel=self.channel,
            recipient_team_id=event.get("team", ""),
            recipient_user_id=event.get("user", ""),
            thread_ts=self.thread_ts
        )

    async def update_status(self, messages: list[str] = None, status_text: str = None):
        """Update the Assistant Status UI (throttled for text updates)."""
        current_time = time.time()
        
        # Always allow "Loading" messages (list) as they are major state changes
        if messages:
            await self.ctx.slack.set_assistant_status(
                self.channel, self.thread_ts, loading_messages=messages
            )
            return

        # Throttle "Thinking..." text updates
        if status_text and (current_time - self.last_status_update_time > 0.5):
            await self.ctx.slack.set_assistant_status(
                self.channel, self.thread_ts, status=status_text
            )
            self.last_status_update_time = current_time

    async def handle_token(self, content: str):
        """Process a single content token from the LLM."""
        if not content:
            return

        # 1. Check for "First Token" of actual response (to clear status)
        if not self.response_started and content.strip():
            # If it doesn't look like a thought block start
            if not (self.buffer + content).lower().strip().startswith("thought:"):
                await self.ctx.slack.set_assistant_status(self.channel, self.thread_ts, "")
                self.response_started = True

        self.buffer += content
        
        # 2. Throttle & Filter
        current_time = time.time()
        if current_time - self.last_update_time > self.throttle_interval:
            await self._flush_buffer()

    async def _flush_buffer(self):
        """Clean buffer and send to Slack."""
        if not self.buffer:
            return

        # Check for partial "thought:" at the END of buffer
        # We don't want to flush "thou" if the next token is "ght:"
        target = "thought:"
        lower_buf = self.buffer.lower()
        
        # Check if the buffer *ends* with a partial prefix of "thought:"
        # e.g. "Answer... tho", "Answer... thoug"
        # We only hold back if the match is at the very end
        for i in range(1, len(target)):
            partial = target[:i]
            if lower_buf.endswith(partial):
                # Found partial match at end, hold back this flush
                # BUT, if buffer is huge, we might be holding back false positives.
                # Heuristic: Only hold back if the partial match is recent (short buffer logic usually handles this)
                return 
            
        try:
            # Clean "thought:" blocks
            clean_text = re.sub(r'(?im)^(\s*thought:\s*)+', '', self.buffer)
            
            if clean_text:
                if self.streamer:
                    await self.streamer.append(markdown_text=clean_text)
                self.buffer = "" # Clear buffer only if sent
                self.last_update_time = time.time()
        except Exception as e:
            logger.warning(f"Error flushing stream: {e}")

    async def stop(self):
        """Finalize the stream."""
        # Flush remaining
        if self.buffer:
            clean_text = re.sub(r'(?im)^(\s*thought:\s*)+', '', self.buffer).strip()
            if clean_text and self.streamer:
                await self.streamer.append(markdown_text=clean_text)
        
        # Clear status
        await self.ctx.slack.set_assistant_status(self.channel, self.thread_ts, "")
        
        if self.streamer:
            await self.streamer.stop()
