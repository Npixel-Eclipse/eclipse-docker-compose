import logging
import time
from src.config import get_settings
from src.core.context import get_context
from src.agents.factory import create_agent
from src.core.slack_streamer import SlackStreamer
from src.common.enums import TriggerType, PersonaType

logger = logging.getLogger(__name__)

async def detect_persona(trigger_type: TriggerType) -> PersonaType:
    """Detect agent persona based on context."""
    if trigger_type == TriggerType.API:
        return PersonaType.AUTOMATION
    return PersonaType.GENERAL

def create_event_payload(channel: str, text: str, user: str = None, ts: str = None, thread_ts: str = None, team: str = None) -> dict:
    """Standardize event payload creation for API/Test triggers."""
    return {
        "channel": channel,
        "text": text,
        "user": user,
        "ts": ts,
        "thread_ts": thread_ts,
        "team": team
    }

async def handle_event_trigger(event: dict, say, trigger_type: TriggerType = TriggerType.MENTION):
    """Unified handler that instantiates a dynamic agent based on context."""
    settings = get_settings()
    ctx = get_context()
    
    channel = event["channel"]
    msg_ts = event.get("ts")
    thread_ts = event.get("thread_ts")
    text = event.get("text", "")
    
    # Session Anchor: Thread TS if usually in thread, else Channel ID
    session_anchor = thread_ts or channel
    session_id = f"slack_{session_anchor}"
    
    # UI Anchor: Where to show typing status (Thread or Message)
    status_anchor = thread_ts or msg_ts
    
    # Set Request Context
    ctx.set_request_context(channel, status_anchor, user_id=event.get("user"), team_id=event.get("team"))
    
    # Initialize Streamer
    streamer = SlackStreamer(ctx, channel, status_anchor, throttle_interval=settings.streaming_throttle_interval)
    
    # Initial UI Status
    await streamer.update_status(messages=[
        "요청하신 내용을 분석 중입니다...", 
        "컨텍스트를 파악하는 중입니다..."
    ])

    try:
        # 1. Detect Persona & Create Agent
        persona = await detect_persona(trigger_type)
        agent = create_agent(persona_type=persona)
        
        logger.info(f"Triggered workflow: {persona} (channel: {channel}, session: {session_id})")

        # 2. Start Stream
        await streamer.start(event)
        
        # 3. Execution Loop
        try:
            async for event_chunk in agent.astream_events(
                {"messages": [{"role": "user", "content": text}]},
                config={
                    "configurable": {"thread_id": session_id},
                    "recursion_limit": 100,
                },
                version="v2"
            ):
                kind = event_chunk["event"]
                
                # A. Tool Execution Status
                if kind == "on_tool_start" and not streamer.response_started:
                    tool_name = event_chunk["name"]
                    await streamer.update_status(messages=[f"도구 실행 중: {tool_name}"])
                
                # B. Sub-Agent Status
                elif kind == "on_chain_start" and not streamer.response_started:
                    name = event_chunk.get("name", "")
                    if name and "-expert" in name:
                        await streamer.update_status(messages=[f"Agent 협업 중: {name}"])

                # C. Token Streaming
                if kind == "on_chat_model_stream":
                    chunk = event_chunk["data"]["chunk"]
                    
                    # C-1. Handle Internal Monologue (Thought) Status
                    if hasattr(chunk, "additional_kwargs") and "thought" in chunk.additional_kwargs:
                         await streamer.update_status(status_text=f"추론 중: {chunk.additional_kwargs['thought'][:30]}...")
                         continue
                    
                    content = chunk.content
                    if content and "thought:" in content.lower():
                        await streamer.update_status(status_text="핵심 로직 분석 중...")
                        # We still pass content to handler to filter/buffer it
                    
                    # C-2. Pass to Streamer
                    if content:
                        await streamer.handle_token(content)
            
        finally:
            await streamer.stop()
            
    except Exception as e:
        logger.error(f"Error during agent trigger: {e}")
        error_text = f"❌ 에이전트 실행 중 오류가 발생했습니다: {str(e)}"
        # Determine where to reply
        # Use status_anchor (thread_ts or msg_ts) to reply in thread
        reply_ts = status_anchor or msg_ts
        
        try:
            await ctx.slack.send_message(channel, error_text, thread_ts=reply_ts)
        except Exception as send_err:
            logger.error(f"Failed to send error message to Slack: {send_err}")
