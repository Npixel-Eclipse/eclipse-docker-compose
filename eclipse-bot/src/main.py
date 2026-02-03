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
        if channel.startswith("D"):
            await handle_message_with_context(event, say, is_mention=False)
        # 2. 채널 내 메시지 (스레드 포함)
        else:
            # 봇이 명시적으로 멘션된 경우 app_mention 핸들러에서 처리하므로 
            # 일반 message 핸들러에서는 중복 응답 방지를 위해 무시합니다.
            bot_id = await slack_integration.get_bot_user_id()
            if f"<@{bot_id}>" in event.get("text", ""):
                return 

            # 멘션 이벤트가 아닌 일반 메시지 이벤트이므로 is_mention=False로 시작
            # (나중에 스레드/이력 분석을 통해 응답 여부 결정)
            await handle_message_with_context(event, say, is_mention=False)

    async def handle_message_with_context(event: dict, say, is_mention: bool):
        """Handle message with conversation context from database."""
        user = event.get("user", "unknown")
        text = event.get("text", "")
        channel = event.get("channel", "")
        
        # Determine thread_ts based on context
        if channel.startswith("D"):
            # DMs should (usually) be treated as flat conversations, so no thread_ts
            thread_ts = None
        else:
            # In channels: use existing thread_ts (reply) or current ts (top-level)
            # This allows top-level mentions to start threads, and replies to stay in threads
            thread_ts = event.get("thread_ts") or event.get("ts")
        
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
        history = await conversation_store.get_conversation(
            channel_id=channel,
            thread_ts=thread_ts if (is_mention or thread_ts) else None,
            limit=20,
        )

        # Automatic Session Start for DMs (if history is empty of assistant messages)
        # Note: 'history' might contain the user's current message, so we check for prior assistant responses.
        if channel.startswith("D") and not any(m.role == "assistant" for m in history):
             import uuid
             new_session_id = str(uuid.uuid4())
             start_msg = f"🔄 [SESSION_START] ID: {new_session_id}\n새로운 세션이 시작되었습니다."
             await say(start_msg)
             # Add to history so LLM sees it immediately (context consistency)
             history.append(Message(role="assistant", content=start_msg))
             logger.info(f"Auto-started new session {new_session_id} for DM {channel}")

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
            
            # 대화 이력을 텍스트로 구성하여 의도 분석에 활용 (최대 20개)
            history_text = "\n".join([f"{m.role}: {m.content[:150]}" for m in history[-20:]])
            intent_prompt = f"이전 대화 맥락:\n{history_text}\n\n판단할 메시지: {clean_text}\n\n{intent_prompt_template}"
            
            intent_response = await llm_client.chat([
                Message(role="user", content=intent_prompt)
            ])
            intent_decision = intent_response.content.strip().upper()
            logger.info(f"AI Intent Analysis Decision: [{intent_decision}] for text: '{clean_text[:50]}'")
            
            if "YES" in intent_decision:
                should_respond = True
                is_mention = True
            else:
                # 봇에게 한 말이 아니더라도 문맥 보존을 위해 DB에는 저장
                await conversation_store.add_message(
                    channel_id=channel,
                    thread_ts=thread_ts,
                    user_id=user,
                    role="user",
                    content=clean_text,
                )
                return

        if not should_respond:
            return

        # Save the current user message to database for future context
        await conversation_store.add_message(
            channel_id=channel,
            thread_ts=thread_ts if (is_mention or channel.startswith("C")) else None, # DM은 thread_ts 없이 저장
            user_id=user,
            role="user",
            content=clean_text,
        )

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
                    if is_mention:
                        # Mentions/Threads: Real-time streaming
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
                        # DMs: Standard text output
                        response_text = response.content or ""
                        await say(text=response_text)
                        response_sent = True
                    
                    # Add completed assistant response to history
                    assistant_msg = Message(role="assistant", content=response_text)
                    messages.append(assistant_msg)
                    
                    # Save to database
                    await conversation_store.add_message(
                        channel_id=channel,
                        thread_ts=thread_ts if is_mention else None,
                        user_id="assistant",
                        role="assistant",
                        content=response_text,
                    )
                    break
                
                # If there ARE tool calls, save the assistant's tool_call message and continue
                assistant_msg = Message(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls
                )
                messages.append(assistant_msg)
                
                # Save assistant response/tool_call to database
                await conversation_store.add_message(
                    channel_id=channel,
                    thread_ts=thread_ts if is_mention else None,
                    user_id="assistant",
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
                    
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
                    
                    # Add tool result to history
                    tool_msg = Message(
                        role="tool",
                        tool_call_id=tool_call["id"],
                        content=json.dumps(tool_result, ensure_ascii=False)
                    )
                    messages.append(tool_msg)
                    
                    # Save tool result to database
                        tool_call_id=tool_call["id"],
                    )
                    
                    # Special Handling: If reset_session was called, suppress LLM's follow-up text
                    # The tool itself posts markers ([SESSION_START]), which is sufficient.
                    if tool_name == "reset_session":
                        response_sent = True
                        break
            
            if not response_text and not response_sent:
                response_text = "워크플로우 실행을 완료했습니다."
                
        except Exception as e:
            logger.error(f"Agentic loop error: {e}")
            response_text = f"죄송합니다, 에이전트 실행 중 오류가 발생했습니다: {str(e)}"

        # Send response (only if not already sent via streaming)
        if not response_sent and response_text:
            if is_mention:
                await say(text=response_text, thread_ts=thread_ts)
            else:
                await say(text=response_text)  # DM은 스레드 없이 응답

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
