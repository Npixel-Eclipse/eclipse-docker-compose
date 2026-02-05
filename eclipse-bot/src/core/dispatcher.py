import time
import logging
from src.config import get_settings
from src.core.context import get_context
from src.agents.factory import create_agent

logger = logging.getLogger(__name__)

async def detect_persona(event: dict, trigger_type: str) -> str:
    """Detect agent persona based on context. Default to 'general'."""
    # Simple logic for now, can be expanded
    if trigger_type == "api":
        return "automation"
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
    ctx.set_request_context(channel, status_anchor, user_id=event.get("user"), team_id=event.get("team"))
    
    # 0. Set Initial Assistant Status IMMEDIATELY for UX
    await ctx.slack.set_assistant_status(
        channel, status_anchor, 
        loading_messages=["요청하신 내용을 내용 분석 중입니다...", "최적의 답변을 생성하고 있습니다...", "컨텍스트를 파악하는 중입니다..."]
    )

    try:
        # 1. Detect Persona & Create Agent
        persona = await detect_persona(event, trigger_type)
        agent = create_agent(persona_type=persona)
        
        logger.info(f"Triggered workflow: {persona} (channel: {channel}, session: {session_id})")

        # 2. Dynamic Agent Token Streaming (SlackStreamer)
        # Assuming manual message management is handled inside agent or here? 
        # The main agent usually streams to a single block.
        # But earlier we moved code_review to manual. 
        # For general chat, we still need a streamer.
        
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
                if kind == "on_tool_start" and not response_started:
                    tool_name = event_chunk["name"]
                    await ctx.slack.set_assistant_status(
                        channel, status_anchor, 
                        loading_messages=[f"도구 실행 중: {tool_name}", "필요한 정보를 가져오고 있습니다...", "잠시만 기다려 주세요."]
                    )
                elif kind == "on_chain_start" and not response_started:
                    name = event_chunk.get("name", "")
                    # Only show status for actual Specialist Agents (which all end in '-expert')
                    if name and "-expert" in name:
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
                    if content:
                        buffer += content
                        
                        # Only mark response started (and clear status) if we have meaningful content
                        # And ensure that content is NOT just a thought block
                        if not response_started and content.strip():
                             # Quick check: if the very first thing is "thought:", don't start yet
                             if not buffer.lower().strip().startswith("thought:"):
                                await ctx.slack.set_assistant_status(channel, status_anchor, "")
                                response_started = True
                        
                        # Throttle Slack updates
                        current_time = time.time()
                        if current_time - last_update_time > settings.streaming_throttle_interval:
                            try:
                                # Code-Level Suppression: Regex filter
                                import re
                                
                                # Only strip the "thought:" prefix (one or more times), NOT the whole line.
                                # Reason: Sometimes the model puts the actual answer immediately after "thought:".
                                # Also handles stuttering "thought:thought:"
                                clean_text = re.sub(r'(?im)^(\s*thought:\s*)+', '', buffer)
                                
                                if clean_text:
                                    await streamer.append(markdown_text=clean_text)
                                    buffer = "" # Clear buffer only if we sent something
                                    last_update_time = current_time
                                else:
                                    # If cleaning made it empty, it was purely "thought:" with no content.
                                    # Keep buffer to wait for more content (or more thought stutters)
                                    pass

                            except Exception as e:
                                logger.warning(f"Error appending stream: {e}")
            
            # Final append
            if buffer:
                import re
                clean_text = re.sub(r'(?im)^(\s*thought:\s*)+', '', buffer).strip()
                if clean_text:
                    await streamer.append(markdown_text=clean_text)
                
            await ctx.slack.set_assistant_status(channel, status_anchor, "")
                
        finally:
            await streamer.stop()
            await ctx.slack.set_assistant_status(channel, status_anchor, "")
            
    except Exception as e:
        logger.error(f"Error during agent trigger: {e}")
        error_text = f"❌ 에이전트 실행 중 오류가 발생했습니다: {str(e)}"
        
        if msg_ts:
            await ctx.slack.update_message(channel, msg_ts, error_text)
        else:
            await ctx.slack.send_message(channel, error_text, thread_ts=thread_ts)
