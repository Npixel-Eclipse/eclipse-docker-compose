import logging
from typing import List, Optional, Callable
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)

import asyncio
from src.core.context import get_context

class AutoCompactor:
    """Smart Context Compactor inspired by Claude Code strategies."""

    def __init__(
        self, 
        model: BaseChatModel, 
        max_tokens: int, 
        summary_ratio: float = 0.5,
        recent_messages_buffer: int = 10
    ):
        """
        Args:
            model: LLM to use for summarization.
            max_tokens: Threshold to trigger compaction.
            summary_ratio: Target size ratio for the summary (not strictly enforced, but guides logic).
            recent_messages_buffer: Number of recent messages to ALWAYS keep intact.
        """
        self.model = model
        self.max_tokens = max_tokens
        self.recent_buffer = recent_messages_buffer

    def invoke(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """Apply compaction if token count exceeds limit."""
        try:
            # 1. Calculate current tokens (Approximate or use model's counter)
            # We use a simple approximation here if token_counter lacks, 
            # but ideally should use self.model.get_num_tokens_from_messages(messages)
            try:
                current_tokens = self.model.get_num_tokens_from_messages(messages)
            except Exception:
                # Fallback: strict char count / 4
                current_tokens = sum(len(m.content) for m in messages) // 4
            
            if current_tokens < self.max_tokens:
                return messages

            logger.info(f"AutoCompact Triggered: {current_tokens} > {self.max_tokens}")
            
            # --- NOTIFICATION: Send Slack Message ---
            try:
                # We attempt to send a notification, but since this runs in a Checkpointer thread,
                # there might be no event loop. We proceed carefully.
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                
                if loop:
                    ctx = get_context()
                    if ctx and ctx.channel:
                        msg = "🧹 *Auto Compact Triggered*\n대화 내용이 너무 길어져서 자동 요약 정리했습니다. (주요 파일 경로 및 맥락은 보존됩니다)"
                        reply_ts = ctx.thread_ts or ctx.msg_ts
                        loop.create_task(ctx.slack.send_message(ctx.channel, msg, thread_ts=reply_ts))
            except Exception as notify_err:
                # Logging only, do not crash the compaction process
                logger.warning(f"AutoCompact notification skipped: {notify_err}")
            # ----------------------------------------

            # 2. Identify segments
            # [System] --- [To Summarize] --- [Recent Buffer]
            system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
            non_system = [m for m in messages if not isinstance(m, SystemMessage)]

            if len(non_system) <= self.recent_buffer:
                # Nothing to compact if we only have recent messages
                return messages

            to_summarize = non_system[:-self.recent_buffer]
            recent = non_system[-self.recent_buffer:]

            # 3. Generate Summary
            summary_text = self._generate_summary(to_summarize)
            
            # 4. Construct new history
            # We wrap summary in a SystemMessage or specialized message to inform the agent
            summary_message = SystemMessage(
                content=f" [PREVIOUS CONVERSATION SUMMARY]\nThe following is a condensed summary of the earlier conversation. Use this context to understand past decisions:\n\n{summary_text}"
            )

            new_history = system_msgs + [summary_message] + recent
            
            # Log reduction
            try:
                new_tokens = self.model.get_num_tokens_from_messages(new_history)
                logger.info(f"Context Compacted: {current_tokens} -> {new_tokens}")
            except:
                pass

            return new_history

        except Exception as e:
            import traceback
            logger.error(f"AutoCompact Failed: {e}\n{traceback.format_exc()}")
            return messages

    def _generate_summary(self, messages: List[BaseMessage]) -> str:
        """Call LLM to summarize the message list."""
        conversation_text = ""
        for m in messages:
            role = m.type.upper()
            conversation_text += f"{role}: {m.content}\n"

        prompt = (
            "Summarize the following technical conversation concisely.\n"
            "Key Requirements:\n"
            "1. **Preserve file paths and directories**: Explicitly list all visited directories and modified files.\n"
            "2. Preserve function names and specific technical decisions.\n"
            "3. Note any finished tasks and pending TODOs.\n"
            "4. Ignore casual chitchat.\n\n"
            f"Conversation:\n{conversation_text}"
        )

        response = self.model.invoke([HumanMessage(content=prompt)])
        return response.content
