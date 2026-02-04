"""Eclipse Bot - Orchestration Platform Entrypoint."""

import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI

from src.config import get_settings
from src.core import SlackIntegration, PerforceClient
from src.core.context import get_context
from src.agents.factory import create_agent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    settings = get_settings()
    ctx = get_context()

    logger.info("Starting Eclipse Orchestration Platform...")

    # Initialize Singleton Clients
    ctx.slack = SlackIntegration(
        bot_token=settings.slack_bot_token,
        app_token=settings.slack_app_token,
    )
    ctx.p4 = PerforceClient()
    
    # Slack Event Registration
    @ctx.slack.on_mention
    async def handle_mention(event: dict, say):
        await handle_event_trigger(event, say, trigger_type="mention")

    @ctx.slack.on_message
    async def handle_any_message(event: dict, say):
        channel = event.get("channel", "")
        if channel.startswith("D"): # Handle DMs
            await handle_event_trigger(event, say, trigger_type="dm")

    await ctx.slack.start()
    yield
    await ctx.slack.stop()


app = FastAPI(lifespan=lifespan)


async def detect_persona(event: dict, trigger_type: str) -> str:
    """Detect agent persona based on context. Default to 'general'."""
    return "general"


async def handle_event_trigger(event: dict, say, trigger_type: str):
    """Unified handler that instantiates a dynamic agent based on context."""
    settings = get_settings()
    ctx = get_context()
    
    channel = event["channel"]
    msg_ts = event.get("ts")
    thread_ts = event.get("thread_ts")
    text = event.get("text", "")
    
    # Session ID choice (History Persistence):
    # 1. Use thread_ts if in a thread
    # 2. Use channel ID if top-level DM/Message
    session_anchor = thread_ts or channel
    session_id = f"slack_{session_anchor}"
    
    # UI Anchor for Assistant Status (Visuals):
    # This must be a TIMESTAMP (ts) for Slack API
    status_anchor = thread_ts or msg_ts
    
    # Global request context for tools (e.g. code_review)
    ctx.set_request_context(channel, status_anchor, user_id=event.get("user"))
    
    # 0. Set Initial Assistant Status IMMEDIATELY for UX
    await ctx.slack.set_assistant_status(
        channel, status_anchor, 
        loading_messages=["요청을 확인하고 있습니다...", "잠시만 기다려 주세요.", "생각 중..."]
    )

    try:
        # 1. Detect Persona & Create Agent
        persona = await detect_persona(event, trigger_type)
        agent = create_agent(persona_type=persona)
        
        logger.info(f"Triggered workflow: {persona} (channel: {channel}, session: {session_id})")

        # 2. Dynamic Agent Token Streaming (SlackStreamer)
        streamer = await ctx.slack.get_streamer(
            channel=channel,
            recipient_team_id=event.get("team", ""),
            recipient_user_id=event.get("user", ""),
            thread_ts=status_anchor
        )
        
        buffer = ""
        last_update_time = 0
        last_status_update_time = 0
        response_started = False
        
        try:
            async for event_chunk in agent.astream_events(
                {
                    "messages": [{"role": "user", "content": text}],
                },
                config={
                    "configurable": {"thread_id": session_id},
                    "recursion_limit": 50,
                },
                version="v2"
            ):
                kind = event_chunk["event"]
                
                # Assistant Status Updates
                # Assistant Status Updates
                if kind == "on_tool_start" and not response_started:
                    # Tool calls - Only show if not yet typing
                    tool_name = event_chunk["name"]
                    await ctx.slack.set_assistant_status(
                        channel, status_anchor, 
                        loading_messages=[f"도구 실행 중: {tool_name}", "필요한 정보를 가져오고 있습니다...", "잠시만 기다려 주세요."]
                    )
                elif kind == "on_chain_start" and not response_started:
                    name = event_chunk.get("name", "")
                    if name and name not in ["LangGraph", "agent"]:
                            # Expert calls - Only show if not yet typing
                             await ctx.slack.set_assistant_status(
                                 channel, status_anchor, 
                                 loading_messages=[f"Agent 협업 중: {name}", "기술 검토를 요청했습니다.", "분석 결과를 기다리는 중..."]
                             )

                # Capture individual tokens from the chat model
                if kind == "on_chat_model_stream":
                    chunk = event_chunk["data"]["chunk"]
                    content = chunk.content
                    current_time = time.time()
                    
                    # 1. Thought Redirection (Throttled)
                    # Redirect detailed thoughts to status bar, but max once per 0.5s to avoid API limits
                    should_update_status = (current_time - last_status_update_time > 0.5)

                    if hasattr(chunk, "additional_kwargs") and "thought" in chunk.additional_kwargs:
                        if should_update_status:
                            thought_val = chunk.additional_kwargs["thought"]
                            await ctx.slack.set_assistant_status(channel, status_anchor, f"추론 중: {thought_val[:30]}...")
                            last_status_update_time = current_time
                        continue
                    
                    if content and "thought:" in content.lower():
                         if should_update_status:
                             await ctx.slack.set_assistant_status(channel, status_anchor, "핵심 로직 분석 중...")
                             last_status_update_time = current_time
                         continue

                    # 2. Main Response Streaming
                    if not response_started:
                        # Clear status immediately when real text starts
                        await ctx.slack.set_assistant_status(channel, status_anchor, "")
                        response_started = True
                        
                    if content:
                        buffer += content
                        
                        # Throttle Slack updates
                        current_time = time.time()
                        if current_time - last_update_time > settings.streaming_throttle_interval:
                            try:
                                await streamer.append(markdown_text=buffer)
                                buffer = "" # Clear buffer after appending
                                last_update_time = current_time
                            except Exception as e:
                                logger.warning(f"Error appending stream: {e}")
            
            # Final append to ensure everything is captured
            if buffer:
                await streamer.append(markdown_text=buffer)
                
            # Clear status effect
            await ctx.slack.set_assistant_status(channel, status_anchor, "")
                
        finally:
            await streamer.stop()
            # Ensure status is cleared even on error inside the loop
            await ctx.slack.set_assistant_status(channel, status_anchor, "")
            
    except Exception as e:
        logger.error(f"Error during agent trigger: {e}")
        error_text = f"❌ 에이전트 실행 중 오류가 발생했습니다: {str(e)}"
        
        if msg_ts:
            await ctx.slack.update_message(channel, msg_ts, error_text)
        else:
            await ctx.slack.send_message(channel, error_text, thread_ts=thread_ts)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "platform": "eclipse-orchestrator"}
