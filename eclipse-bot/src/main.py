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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
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

    # Initialize Conversation Store
    conversation_store = ConversationStore(settings.database_url)
    await conversation_store.initialize()
    logger.info("Conversation store initialized")

    # Register example workflows
    from .workflows.examples import register_examples
    register_examples()
    logger.info("Example workflows registered")

    # Initialize Slack Integration
    slack_integration = SlackIntegration(
        bot_token=settings.slack_bot_token,
        app_token=settings.slack_app_token,
    )

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
        
        # 1. DM 처리
        if channel.startswith("D"):
            await handle_message_with_context(event, say, is_mention=False)
        # 2. 채널 내 메시지 (스레드 포함)
        else:
            # 멘션 이벤트가 아닌 일반 메시지 이벤트이므로 is_mention=False로 시작
            # (나중에 스레드/이력 분석을 통해 응답 여부 결정)
            await handle_message_with_context(event, say, is_mention=False)

    async def handle_message_with_context(event: dict, say, is_mention: bool):
        """Handle message with conversation context from database."""
        user = event.get("user", "unknown")
        text = event.get("text", "")
        channel = event.get("channel", "")
        thread_ts = event.get("thread_ts") or event.get("ts")
        
        # Clean text (remove bot mention if present)
        if is_mention:
            clean_text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
        else:
            clean_text = text.strip()

        if not clean_text:
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
            logger.info(f"Analyzing intent for threaded message: {clean_text[:50]}...")
            intent_prompt_template = load_prompt("intent_check")
            intent_prompt = intent_prompt_template.replace("{{text}}", clean_text)
            
            intent_response = await llm_client.chat([
                Message(role="user", content=intent_prompt)
            ])
            
            if "YES" in intent_response.content.upper():
                logger.info("AI Intent Analysis: YES (Bot-directed)")
                should_respond = True
                # 스레드 내 대화이므로 스트리밍 모드 활성화를 위해 is_mention을 True로 설정
                is_mention = True
            else:
                logger.info("AI Intent Analysis: NO (User-to-user conversation)")
                return

        # 4. 그 외(일반 채널 메시지 등)는 무시
        if not should_respond:
            return

        # Build messages for LLM
        system_prompt = load_prompt("default")
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

        # Save user message to database
        await conversation_store.add_message(
            channel_id=channel,
            thread_ts=thread_ts if is_mention else None,
            user_id=user,
            role="user",
            content=clean_text,
        )

        # Agentic Loop (Function Calling)
        import json
        from .workflows import get_registry
        registry = get_registry()
        
        max_iterations = 5
        iteration = 0
        response_sent = False
        
        try:
            while iteration < max_iterations:
                iteration += 1
                
                # Get registered tools
                tools = registry.get_all_tool_specs()
                
                # Get LLM response with tool support
                response = await llm_client.chat(messages, tools=tools)
                
                if not response.tool_calls:
                    # Final response logic
                    if is_mention:
                        # Mentions/Threads: Real-time streaming using new API
                        response_text = ""
                        try:
                            streamer = await slack_integration.get_streamer(
                                channel=channel,
                                thread_ts=thread_ts
                            )
                            async for chunk in llm_client.chat_stream(messages):
                                response_text += chunk
                                await streamer.append(markdown_text=chunk)
                            await streamer.stop()
                            response_sent = True
                        except Exception as stream_err:
                            logger.error(f"Streaming error: {stream_err}")
                            response_text = response.content or ""
                    else:
                        # DMs: Standard text output without streaming or threading
                        response_text = response.content or ""
                    
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
                    await conversation_store.add_message(
                        channel_id=channel,
                        thread_ts=thread_ts if is_mention else None,
                        user_id="system",
                        role="tool",
                        content=json.dumps(tool_result, ensure_ascii=False),
                        tool_call_id=tool_call["id"],
                    )
            
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
