"""FastAPI application entrypoint."""

import re
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from .config import get_settings
from .api import router
from .core import LLMClient, SlackIntegration, ConversationStore
from .models import Message
from .utils import load_prompt
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True, # Ensure this config overrides any existing settings
)
logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)

# Global instances (initialized in lifespan)
llm_client: LLMClient | None = None
slack_integration: SlackIntegration | None = None
conversation_store: ConversationStore | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    global llm_client, slack_integration, conversation_store

    settings = get_settings()
    logger.info("Starting AI Workflow Framework...")

    # Initialize LLM Client
    llm_client = LLMClient(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        default_model=settings.default_model,
    )
    logger.info(f"LLM Client initialized with model: {settings.default_model}")

    # Initialize Slack Integration (First, as Store depends on it)
    slack_integration = SlackIntegration(
        bot_token=settings.slack_bot_token,
        app_token=settings.slack_app_token,
    )
    
    # Fetch bot user ID to avoid duplicate processing in on_message
    bot_user_id = await slack_integration.get_bot_user_id()
    logger.info(f"Slack Bot User ID: {bot_user_id}")
    
    # Initialize Conversation Store (Stateless)
    conversation_store = ConversationStore()
    conversation_store.set_slack_integration(slack_integration)
    await conversation_store.initialize()
    logger.info("Conversation store initialized (Stateless)")

    # Register workflows and tools
    from .workflows import register_all_workflows
    from .tools import register_all_tools
    register_all_workflows(llm_client)
    register_all_tools()
    logger.info("Workflows and tools registered")

    # --- Register AI Interaction Handlers ---
    
    @slack_integration.app.action("feedback_buttons_action")
    async def handle_feedback(ack, body, say):
        await ack()
        user_id = body["user"]["id"]
        action_value = body["actions"][0]["value"]
        logger.info(f"Feedback received from {user_id}: {action_value}")
        # Optionally update the message or send a temporary response
        # await say(f"<@{user_id}>님, 소중한 피드백 감사합니다! ({action_value})", thread_ts=body["message"]["ts"])

    @slack_integration.app.action("delete_ai_response")
    async def handle_delete(ack, body):
        await ack()
        channel_id = body["channel"]["id"]
        message_ts = body["message"]["ts"]
        try:
            await slack_integration.app.client.chat_delete(
                channel=channel_id,
                ts=message_ts
            )
            logger.info(f"AI response deleted in {channel_id} (ts: {message_ts})")
        except Exception as e:
            logger.error(f"Failed to delete message: {e}")

    # ----------------------------------------

    # Setup Slack handlers with conversation memory
    @slack_integration.on_mention
    async def handle_mention_with_memory(event: dict, say):
        """Handler for app mentions with conversation memory."""
        await handle_message_with_context(event, say, is_mention=True)

    @slack_integration.on_message
    async def handle_any_message(event: dict, say):
        """Handler for messages (DMs and channel messages)."""
        channel = event.get("channel", "")
        thread_ts = event.get("thread_ts")
        text = event.get("text", "")
        ts = event.get("ts")
        
        # --- Code Review Trigger Check ---
        from .core.config import get_config
        from .workflows import get_registry
        
        config = get_config()
        target_channel = config.get("code_review.target_channel_id")
        
        # If in target channel and NOT a thread reply (or handle threads too? Usually top-level)
        if channel == target_channel and not thread_ts:
            registry = get_registry()
            # Run Code Review Workflow asynchronously
            # We don't await it to block other processing, or we can await?
            # Better to spawn task.
            import asyncio
            asyncio.create_task(registry.execute("code_review", {
                "text": text,
                "channel": channel,
                "ts": ts
            }))
            # We rely on CodeReviewWorkflow to validate CLs. 
            # If no CLs, it finishes quickly.
        # ---------------------------------
        
        # 1. DM 처리
        # -> DM도 일반 메시지처럼 처리 (스레드 강제화는 handle_message_with_context 내에서 수행)
        if channel.startswith("D"):
            await handle_message_with_context(event, say, is_mention=False)
        # 2. 채널 내 메시지
        else:
             # 봇이 명시적으로 멘션된 경우 app_mention 핸들러에서 처리하므로 중복 응답 방지
             bot_id = await slack_integration.get_bot_user_id()
             if f"<@{bot_id}>" in event.get("text", ""):
                 return
             
             await handle_message_with_context(event, say, is_mention=False)

    async def handle_message_with_context(event: dict, say, is_mention: bool):
        """Handle message with conversation context from database."""
        user = event.get("user", "unknown")
        text = event.get("text", "")
        channel = event.get("channel", "")
        
        # Determine thread_ts based on context
        # Enforce Threading for ALL channels (including DMs)
        # If it's a reply, use thread_ts. If top-level, treat it as parent of new thread (use ts).
        thread_ts = event.get("thread_ts") or event.get("ts")
        logger.info(f"DEBUG: Context for {channel} - user_ts={event.get('ts')}, thread_ts(in)={event.get('thread_ts')} => Using thread_ts={thread_ts}")
        
        # Clean text (remove bot mention if present)
        if is_mention:
            clean_text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
        else:
            clean_text = text.strip()

        if not clean_text:
            if is_mention:
                await say(
                    text=f"안녕하세요 <@{user}>! 무엇을 도와드릴까요?",
                    thread_ts=thread_ts,
                )
            return

        # Get conversation history from database
        # User requested "almost no context limit". Increasing to 100 (Slack API default max per page).
        history = await conversation_store.get_conversation(
            channel_id=channel,
            thread_ts=thread_ts,
            limit=100,
        )

        # [REMOVED] Automatic Session Start for DMs (User requested removal)

        # 응답 여부 판단 (Decision Logic)
        should_respond = False
        
        # 1. 멘션이 있으면 무조건 응답
        if is_mention:
            should_respond = True
        # 2. DM이면 무조건 응답
        elif channel.startswith("D"):
            should_respond = True
        # 3. 멘션 없는 스레드 답글인 경우 (AI 의도 분석 수행)
        elif thread_ts and history:
            logger.info(f"Analyzing intent for threaded message in {channel}. History: {len(history)} messages.")
            
            intent_prompt_template = load_prompt("intent_check")
            
            # 대화 이력을 텍스트로 구성하여 의도 분석에 활용
            # User requested to remove truncation ([:150]) and limits
            history_text = "\n".join([f"{m.role}: {m.content}" for m in history])
            intent_prompt = f"이전 대화 맥락:\n{history_text}\n\n판단할 메시지: {clean_text}\n\n{intent_prompt_template}"
            
            intent_response = await llm_client.chat([
                Message(role="user", content=intent_prompt)
            ])
            intent_decision = intent_response.content.strip().upper()
            logger.info(f"AI Intent Analysis Decision: [{intent_decision}] for text: '{clean_text[:50]}'")
            
            if "YES" in intent_decision:
                should_respond = True
                is_mention = True # Treat as mention for streaming purposes
            else:
                # 봇에게 한 말이 아니면 무시 (Slack에 이미 저장되어 있음)
                return

        if not should_respond:
            return

        # (User message is already in Slack, no need to 'save' to DB explicitly)

        # Build messages for LLM
        system_prompt = load_prompt("llm_chat")
        messages = [
            Message(role="system", content=system_prompt)
        ]
        
        # Add conversation history
        for msg in history:
            messages.append(Message(
                role=msg.role, 
                content=msg.content,
                tool_calls=msg.tool_calls,
                tool_call_id=msg.tool_call_id
            ))
        
        # Add current message
        messages.append(Message(role="user", content=clean_text))


        # Agentic Loop (Function Calling)
        import json
        from .workflows import get_registry
        from .workflows.llm_chat import LLMChatWorkflow
        
        registry = get_registry()
        
        # [FORCED TRIGGER] Check for explicit Code Review request pattern
        # User requested unconditional code enforcement for reviews
        import re
        review_pattern = r"(?:code\s*review|리뷰).*(?:cl|change)?\s*(\d+)|(?:cl|change)\s*(\d+).*(?:code\s*review|리뷰)"
        if re.search(review_pattern, clean_text, re.IGNORECASE):
            logger.info(f"Forced Code Review Trigger detected for text: {clean_text}")
            
            # Execute Code Review Workflow directly
            try:
                # Notify user that review is starting (since it might take a moment)
                await say(text=f"🔍 CL 분석 및 리뷰를 시작합니다...", thread_ts=thread_ts)
                
                review_args = {
                    "text": clean_text,
                    "channel_id": channel,
                    "thread_ts": thread_ts
                }
                
                run = await registry.execute("code_review", review_args)
                result_content = run.result if run.status == "completed" else f"리뷰 실패: {run.error}"
                
                # Send Result
                if is_mention or channel.startswith("D"):
                    await say(text=result_content, thread_ts=thread_ts)
                else:
                    await say(text=result_content)
                return  # Exit function after forced review
            except Exception as e:
                logger.error(f"Forced review execution failed: {e}")
                await say(text=f"죄송합니다. 리뷰 실행 중 오류가 발생했습니다: {e}", thread_ts=thread_ts)
                return

        
        max_iterations = 5
        iteration = 0
        response_sent = False
        
        try:
            while iteration < max_iterations:
                iteration += 1
                
                # Get registered tools (RESTRICTED to LLMChatWorkflow allowed tools)
                tools = registry.get_tool_specs(LLMChatWorkflow.allowed_tools)
                
                # Get LLM response with tool support
                response = await llm_client.chat(messages, tools=tools)
                
                if not response.tool_calls:
                    # Final response logic
                    # Use Streaming for BOTH Mentions and DMs (Universal Streaming as requested)
                    if is_mention or channel.startswith("D"):
                        # Mentions/Threads/DMs: Real-time streaming
                        response_text = ""
                        # 공식 SDK chat_stream은 thread_ts를 필수(required)로 요구합니다.
                        # DM 등에서 thread_ts가 None인 경우, 현재 메시지의 ts를 사용합니다.
                        stream_thread_ts = thread_ts or event.get("ts")
                        
                        try:
                            streamer = await slack_integration.get_streamer(
                                channel=channel,
                                recipient_team_id=event.get("team"),
                                recipient_user_id=event.get("user"),
                                thread_ts=stream_thread_ts
                            )
                            # Append debug prefix first -> Removed
                            
                            async for chunk in llm_client.chat_stream(messages):
                                response_text += chunk
                                await streamer.append(markdown_text=chunk)
                            
                            # Create AI interactive blocks (Feedback + Delete)
                            interactive_blocks = [
                                {
                                    "type": "context_actions",
                                    "elements": [
                                        {
                                            "type": "feedback_buttons",
                                            "action_id": "feedback_buttons_action",
                                            "positive_button": {
                                                "text": {"type": "plain_text", "text": "👍"},
                                                "value": "positive"
                                            },
                                            "negative_button": {
                                                "text": {"type": "plain_text", "text": "👎"},
                                                "value": "negative"
                                            }
                                        },
                                        {
                                            "type": "icon_button",
                                            "icon": "trash",
                                            "text": {"type": "plain_text", "text": "삭제"},
                                            "action_id": "delete_ai_response",
                                            "value": "delete"
                                        }
                                    ]
                                }
                            ]
                            await streamer.stop(blocks=interactive_blocks)
                            response_sent = True
                        except Exception as stream_err:
                            logger.error(f"Streaming failed, falling back to standard post: {stream_err}")
                            # Fallback: Get response via non-streaming API
                            fallback_response = await llm_client.chat(messages)
                            response_text = fallback_response.content or "죄송합니다. 응답 생성 중 오류가 발생했습니다."
                            await slack_integration.send_message(
                                channel=channel,
                                text=response_text,
                                thread_ts=thread_ts 
                            )
                            response_sent = True
                    else:
                        # Should rarely be reached if logic covers all cases
                        response_text = response.content or ""
                        await say(text=response_text)
                        response_sent = True
                    
                    # Add completed assistant response to history (for current session context only)
                    assistant_msg = Message(role="assistant", content=response_text)
                    messages.append(assistant_msg)
                    break
                
                # If there ARE tool calls, save the assistant's tool_call message and continue
                assistant_msg = Message(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls
                )
                messages.append(assistant_msg)
                    
                # Execute tool calls
                for tool_call in response.tool_calls:
                    tool_name = tool_call["function"]["name"]
                    tool_args = json.loads(tool_call["function"]["arguments"])
                    
                    # Context Injection: Automatically add channel_id/thread_ts if missing or empty
                    if not tool_args.get("channel_id"):
                         tool_args["channel_id"] = channel
                    if not tool_args.get("thread_ts") and thread_ts:
                         tool_args["thread_ts"] = thread_ts
                    
                    logger.info(f"Agent calling tool: {tool_name} with args: {tool_args}")
                    
                    try:
                        run = await registry.execute(tool_name, tool_args)
                        tool_result = run.result if run.status == "completed" else {"error": run.error}
                    except Exception as e:
                        tool_result = {"error": str(e)}
                    
                    # Add tool result to history (local loop context)
                    tool_msg = Message(
                        role="tool",
                        tool_call_id=tool_call["id"],
                        content=json.dumps(tool_result, ensure_ascii=False)
                    )
                    messages.append(tool_msg)
                    
                    # Special Handling: If reset_session was called, suppress LLM's follow-up text
                    # Only if the tool succeeded (which means it posted markers).
                    # If it failed, let the LLM explain the error.
                    if tool_name == "reset_session":
                        if "error" not in tool_result:
                            response_sent = True
                            break
                        else:
                            # Let LLM see the error and respond
                            response_sent = False
            
            if not response_text and not response_sent:
                response_text = "워크플로우 실행을 완료했습니다."
                
        except Exception as e:
            logger.error(f"Agentic loop error: {e}")
            response_text = f"죄송합니다, 에이전트 실행 중 오류가 발생했습니다: {str(e)}"

        # Send response (only if not already sent via streaming)
        if not response_sent and response_text:
            if is_mention or channel.startswith("D"):
                await say(text=response_text, thread_ts=thread_ts)
            else:
                 # Fallback
                await say(text=response_text)

    # Start Slack Socket Mode
    await slack_integration.start()
    logger.info("Starting AI Workflow Framework...")

    yield

    # Shutdown
    logger.info("Shutting down AI Workflow Framework...")
    if slack_integration:
        await slack_integration.stop()
    if llm_client:
        await llm_client.close()
    if conversation_store:
        await conversation_store.close()


# Create FastAPI app
app = FastAPI(
    title="AI Workflow Framework",
    description="Reusable AI agent for workflow automation",
    version="0.1.0",
    lifespan=lifespan,
)

# Include API routes
app.include_router(router)


def get_llm_client() -> LLMClient:
    """Get the global LLM client instance."""
    if llm_client is None:
        raise RuntimeError("LLM client not initialized")
    return llm_client


def get_slack_integration() -> SlackIntegration:
    """Get the global Slack integration instance."""
    if slack_integration is None:
        raise RuntimeError("Slack integration not initialized")
    return slack_integration


def get_conversation_store() -> ConversationStore:
    """Get the global conversation store instance."""
    if conversation_store is None:
        raise RuntimeError("Conversation store not initialized")
    return conversation_store


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
