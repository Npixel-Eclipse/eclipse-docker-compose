"""Ralph-Skill for Code Review Orchestration.

This skill implements the "Ralph Loop" pattern for autonomous code reviews.
It acts as a supervisor that:
1. Analyzes the P4 Changelist.
2. Selects relevant specialist sub-agents.
3. Posts a dynamic checklist to Slack.
4. Iteratively invokes each sub-agent and updates the checklist.
5. Synthesizes a final report.
"""

import logging
import asyncio
from langchain_core.tools import tool
from deepagents import create_deep_agent
from deepagents.backends import StateBackend
from langgraph.checkpoint.memory import MemorySaver

from src.core.context import get_context
from src.agents.subagents import get_subagents
from src.tools.slack_tools import (
    execute_post_checklist, 
    execute_update_checklist, 
    execute_post_progress
)

logger = logging.getLogger(__name__)

@tool
async def code_review(cl: str) -> str:
    """Perform a comprehensive code review using specialist agents (Ralph Loop).
    
    Args:
        cl: The P4 Changelist number to review.
    """
    ctx = get_context()
    if not ctx.current_request:
         return "Error: No active request context found."
         
    channel = ctx.current_request.channel
    thread_ts = ctx.current_request.thread_ts
    
    # 1. Analyze CL to identify file types
    logger.info(f"Starting Ralph Loop for CL {cl}")
    try:
        # Get file list using P4 (lightweight describe)
        describe_output = await asyncio.to_thread(ctx.p4.run, "describe", "-s", cl, check=False)
        files = []
        for line in describe_output.splitlines():
            if "..." in line and "//" in line:
                # Parse depot path
                path = line.split(" ")[1].split("#")[0]
                files.append(path)
    except Exception as e:
        return f"failed to analyze CL {cl}: {e}"

    # 2. Select Agents based on file extensions
    selected_agents = []
    all_subagents = get_subagents()
    
    # Mapping extensions to agent names
    ext_map = {
        ".kt": ["kotlin-expert"],
        ".rs": ["rust-expert", "ecs-expert"], # ECS is Rust-based
        ".java": ["jpa-expert"],
        ".yaml": ["yaml-expert"],
        ".yml": ["yaml-expert"],
        ".proto": ["proto-expert"],
    }
    
    detected_specialists = set()
    for f in files:
        for ext, agents in ext_map.items():
            if f.endswith(ext):
                for agent in agents:
                    detected_specialists.add(agent)
                    
    # Always include core agents
    required_agents = {"architecture-expert", "security-expert", "game-logic-expert"}
    # game-logic-expert checks math/state, ecs-expert checks storage/views. Both are useful.
    
    final_agents_set = detected_specialists.union(required_agents)
    
    # Filter subagent definitions
    agents_to_run = [a for a in all_subagents if a["name"] in final_agents_set]
    
    if not agents_to_run:
        return f"No suitable agents found for CL {cl}. (Files: {files})"

    # 3. Post Checklist to Slack
    checklist_items = [
        "변경 사항 분석 (CL Analysis)",
        *[f"Agent 리뷰: {agent['name']}" for agent in agents_to_run]
    ]
    checklist_resp = await execute_post_checklist(channel, thread_ts, checklist_items)
    checklist_ts = checklist_resp["ts"]
    
    # Mark first step as done
    await execute_update_checklist(
        channel, checklist_ts,
        [{"text": checklist_items[0], "done": True}] + 
        [{"text": item, "done": False} for item in checklist_items[1:]]
    )
    
    # 4. Ralph Loop: Parallel Aggregation (Centralized)
    # We collect results from all agents and return a single report.
    logger.info(f"Starting parallel execution for: {[a['name'] for a in agents_to_run]}")
    await __send_status(context, channel, thread_ts, "⏳ 전문가들의 분석을 취합하고 있습니다...")

    import asyncio
    
    async def run_single_agent(idx, agent_spec):
        agent_name = agent_spec["name"]
        try:
            # Create dedicated agent instance
            sub_agent = create_deep_agent(
                model=agent_spec["model"],
                system_prompt=agent_spec["system_prompt"],
                tools=agent_spec["tools"],
                backend=StateBackend,
                checkpointer=MemorySaver(),
            )
            
            # Invoke Agent
            config = {"configurable": {"thread_id": f"review_{cl}_{agent_name}"}}
            inputs = {"messages": [{"role": "user", "content": f"Review CL {cl} in Korean. Focus on your specialty. If you see specific issues like blocking calls or security flaws, point them out with examples."}]}
            
            # Capture output
            result_text = ""
            async for event in sub_agent.astream_events(inputs, config=config, version="v2"):
                if event["event"] == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if chunk.content:
                        result_text += chunk.content
            
            # Filter 'thought:'
            import re
            # Simple strip of leading 'thought:' blocks if any remain
            clean_text = re.sub(r'(?im)^(\s*thought:\s*)+', '', result_text).strip()
            
            # Update checklist
            await execute_update_checklist(
                channel, checklist_ts, 
                [{"text": checklist_items[idx+1], "done": True}]
            )
            
            return f"*🤖 {agent_name}*\n{clean_text}"

        except Exception as e:
            logger.error(f"Agent {agent_name} failed: {e}")
            return f"*🤖 {agent_name}*\n❌ Error: {str(e)}"

    # Run all agents
    tasks = [run_single_agent(i, a) for i, a in enumerate(agents_to_run)]
    results = await asyncio.gather(*tasks)
    
    # 5. Final Consolidation
    consolidated_report = "\n\n".join(results)
    
    await execute_update_checklist(
        channel, checklist_ts, 
        [{"text": item, "done": True} for item in checklist_items]
    )
    
    return consolidated_report

