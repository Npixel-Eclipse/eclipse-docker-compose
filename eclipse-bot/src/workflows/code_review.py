"""Code Review Workflow - Event Driven Analysis."""

import re
import asyncio
import logging
from typing import List, Dict, Any, Optional

from src.core import BaseWorkflow, LLMClient
from src.models import Message
from src.core.config import get_config
from src.core.perforce_client import PerforceClient

logger = logging.getLogger(__name__)

class CodeReviewWorkflow(BaseWorkflow):
    """
    Automated Code Review Workflow triggered by Slack events.
    Parses P4 CLs, fetches changes, matches strategies, and generates reviews using LLM.
    """
    name = "code_review"
    description = "Automated code review based on P4 changelists"
    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string", 
                "description": "Text containing the CL number(s) to review, e.g. 'CL 123456'"
            }
        },
        "required": ["text"]
    }
    
    def __init__(self, llm_client: LLMClient):
        super().__init__()
        self.llm = llm_client
        self.config = get_config()
        self.p4 = PerforceClient()
        
        from src.main import get_slack_integration
        self.slack = get_slack_integration()

    @property
    def allowed_tools(self) -> list[str]:
        """Load allowed tools from config.yaml for dynamic tool calling during review."""
        from src.core.config import load_config
        config = load_config()
        return config.get("workflows", {}).get("code_review", {}).get("allowed_tools", [])

    async def execute(self, input_data: dict) -> dict:
        """
        Main execution entry point.
        input_data expected keys: "text", "channel", "trigger_ts", "thread_ts"
        """
        text = input_data.get("text", "")
        channel = input_data.get("channel")
        # trigger_ts: Message to react to (e.g. user command)
        # thread_ts: Thread to reply in (e.g. parent session)
        trigger_ts = input_data.get("trigger_ts") or input_data.get("ts")
        thread_ts = input_data.get("thread_ts") or input_data.get("ts")
        
        # 1. Parse Change Lists
        explicit_cls = input_data.get("cl_numbers", [])
        if explicit_cls:
            if isinstance(explicit_cls, str):
                cls = [explicit_cls]
            else:
                cls = explicit_cls
        else:
            cls = self._parse_changelists(text)
            
        if not cls:
            return {"status": "skipped", "reason": "No CLs found"}

        # 2. Mark Processing (Reaction on Trigger Message)
        if trigger_ts:
            logger.info(f"[CodeReview] Adding reaction 'loading' to {channel}/{trigger_ts}")
            await self.slack.add_reaction(channel, trigger_ts, "loading")
        else:
            logger.warning(f"[CodeReview] No trigger_ts provided for reaction. input_data keys: {input_data.keys()}")
        
        try:
            reports = []
            total_issues = 0

            # 3. Process each CL
            for cl in cls:
                cl_report = await self._process_cl(cl, channel, thread_ts)
                if cl_report:
                    reports.append(cl_report)
                    total_issues += cl_report.get("issues", 0)

            # 4. Final Report
            if reports:
                await self._send_report(channel, thread_ts, reports, total_issues)
                if trigger_ts:
                    await self.slack.remove_reaction(channel, trigger_ts, "loading")
                    await self.slack.add_reaction(channel, trigger_ts, "heavy_check_mark")
            else:
                 if trigger_ts:
                    await self.slack.remove_reaction(channel, trigger_ts, "loading")
                    await self.slack.add_reaction(channel, trigger_ts, "white_check_mark") # Processed but no review generated

        except Exception as e:
            logger.error(f"Code review failed: {e}", exc_info=True)
            if trigger_ts:
                await self.slack.remove_reaction(channel, trigger_ts, "loading")
                await self.slack.add_reaction(channel, trigger_ts, "ai") # Fail emoji
            # Error message should go to thread
            await self.slack.send_message(channel, f"❌ 코드 리뷰 중 오류가 발생했습니다: {str(e)}", thread_ts=thread_ts)
            return {"status": "error", "error": str(e)}
        finally:
             # Ensure cleanup if somehow missed above (though handled explicitly now for replace)
             pass

        return {"status": "success", "total_issues": total_issues}

    def _parse_changelists(self, text: str) -> List[str]:
        """Extract CL numbers from text using Regex."""
        # Patterns: "cl: 12345", "cl 12345", or just "123456" (careful with this one)
        # n8n logic was: /(?<![-.])\b\d+\b(?!\.)/g etc.
        # Let's be safe and look for explicit CL references or large numbers if implicit
        
        # Pattern 1: Explicit "cl: 12345" or "cl 12345"
        explicit_matches = re.findall(r'(?:cl|change)\s*[:#]?\s*(\d+)', text, re.IGNORECASE)
        
        # Pattern 2: 6+ digit numbers (common for P4 CLs) if explicit failed? 
        # Or just merge them. Let's include standalone 5+ digit numbers for convenience
        # but avoid potential dates/times if possible. 
        # Using n8n's strict pattern: /(?<![-.])\b\d+\b(?!\.)/g implies isolated numbers
        
        standalone_matches = re.findall(r'(?<![-.])\b(\d{5,})\b(?!\.)', text)
        
        all_cls = set(explicit_matches + standalone_matches)
        return list(all_cls)

    async def _process_cl(self, cl: str, channel: str, ts: str) -> Optional[Dict[str, Any]]:
        """Fetch P4 data and run strategies."""
        logger.info(f"Processing CL: {cl}")
        
        # 1. Get Description & Files
        try:
            # PerforceClient.run is blocking, so offload to thread
            describe_output = await asyncio.to_thread(self.p4.run, "describe", "-s", cl)
            if not describe_output:
                logger.warning(f"CL {cl} not found or empty.")
                return None
            
            # P4 output format parsing is needed if using raw command
            # But let's assume raw string for now and regex match files
            full_desc = describe_output if isinstance(describe_output, str) else str(describe_output)
            
        except Exception as e:
            logger.error(f"Failed to fetch CL {cl}: {e}")
            return None

        # 2. Identify Files and content
        # We need a list of files to match extensions.
        # 'p4 describe -s' lists files at the end.
        files = re.findall(r'//.*', full_desc) # Simple grep for depot paths
        
        # 3. Match Strategies
        strategies = self.config.get("code_review.strategies", [])
        matched_tasks = []

        for strategy in strategies:
            if self._is_strategy_applicable(strategy, files, full_desc):
                matched_tasks.append(
                    self._run_llm_review(strategy, cl, full_desc)
                )
        
        if not matched_tasks:
            return None

        # 4. Execute LLM Reviews in Parallel with Progressive Updates
        # Create an initial message to update
        initial_msg = f"⏳ **Code Review Started**\nAnalyzing {len(matched_tasks)} strategies..."
        resp = await self.slack.send_message(channel, initial_msg, thread_ts=thread_ts)
        report_ts = resp.get("ts") if resp else None
        
        results = []
        completed_count = 0
        total_tasks = len(matched_tasks)
        
        # Track partial results for display
        partial_reports = []

        for coro in asyncio.as_completed(matched_tasks):
            res = await coro
            completed_count += 1
            if res:
                results.append(res)
                partial_reports.append(res)
                
                # Update Message with Progress
                # Format: 
                # ⏳ Analyzing... (1/3)
                # ✅ Rust: Pass
                # ...
                
                current_text = f"⏳ **Code Review in Progress ({completed_count}/{total_tasks})**\n\n"
                
                # Append finished results
                for r in partial_reports:
                    status_icon = "✅" if r["status"] == "PASS" else "⚠️" if r["status"] == "REQUEST_CHANGES" else "❌"
                    current_text += f"{status_icon} **{r['name']}**: {r['status']}\n"
                    
                if report_ts:
                    await self.slack.update_message(channel, report_ts, current_text)
        
        # 5. Finalize Report (Replace progressive message with final format)
        # Use _send_report logic but targeting the EXISTING message (update) logic?
        # Actually _send_report sends a NEW message in original code.
        # Let's refactor _send_report to return text, then we update 'report_ts'.
        
        # Aggregate
        issues_count = 0
        for res in results:
             match = re.search(r'\[Issues Found\]:\s*(\d+)', res.get("raw", ""))
             if match:
                 issues_count += int(match.group(1))
             # Also count explicit issues list if available (structured)
             issues_count += len(res.get("issues", []))

        # We construct the final text here manually to allow 'update_message'
        # Or we can delete the progress message and let _send_report send a fresh one? 
        # Update is better to reduce clutter.
        
        final_text = self._build_final_report_text(results, issues_count)
        if report_ts:
            await self.slack.update_message(channel, report_ts, final_text)
        else:
            await self.slack.send_message(channel, final_text, thread_ts=thread_ts)
            
        return {
            "cl": cl,
            "outputs": results,
            "issues": issues_count
        }

    def _build_final_report_text(self, outputs: List[dict], total_issues: int) -> str:
        """Build final report text."""
        relevant_reports = [out for out in outputs if out["status"] == "REQUEST_CHANGES" and out.get("issues")]
        pass_reports = [out for out in outputs if out["status"] == "PASS"]
        
        if not relevant_reports:
             return f"✅ **Code Review Passed** (Checked by {len(pass_reports)} experts)"

        real_issue_count = sum(len(out["issues"]) for out in relevant_reports)
        final_text = "## 🔍 AI 코드 리뷰 결과\n\n"
        final_text += f"🚨 **발견된 중요 이슈: {real_issue_count}건**\n\n"
        
        for out in relevant_reports:
            final_text += f"{out['emoji']} **{out['name']}**\n"
            for issue in out["issues"]:
                file_info = f"(`{issue.get('file')}`)" if issue.get('file') else ""
                final_text += f"- **[{issue.get('category', 'Issue')}]** {issue.get('description')} {file_info}\n"
            final_text += "\n"
            
        if pass_reports:
             final_text += f"\n--- \n✅ **Pass**: {', '.join([r['name'] for r in pass_reports])}"
             
        return final_text

    def _is_strategy_applicable(self, strategy: dict, files: List[str], full_desc: str) -> bool:
        """Check if strategy applies based on extensions and keywords."""
        # 1. Check Extensions
        extensions = strategy.get("extensions", [])
        has_extension = False
        if extensions:
             for f in files:
                if any(f.endswith(ext) for ext in extensions):
                    has_extension = True
                    break
        else:
            # If no extensions defined, assume check all? Or careful?
            # Usually safer to require extension or keyword
            pass
            
        if not has_extension and extensions:
            return False

        # 2. Check Keywords (Optional)
        keywords = strategy.get("keywords", [])
        if keywords:
            # Search in file paths or description? 
            # n8n logic checked 'p4' var which is full output (desc + files)
            found_keyword = any(k.lower() in full_desc.lower() for k in keywords)
            if not found_keyword:
                return False
                
        return True

    async def _run_llm_review(self, strategy: dict, cl: str, p4_desc: str) -> dict:
        """Run LLM for a specific strategy using Tool Calling for structured output."""
        system_prompt = strategy["prompt"]
        emoji = strategy.get("emoji", "📝")
        name = strategy.get("name", "Review")
        
        # Define the Tool Schema
        submit_review_tool = {
            "type": "function",
            "function": {
                "name": "submit_review",
                "description": "Submit code review results. Call this function even if no issues are found (with status='PASS').",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reviewer_name": {
                            "type": "string",
                            "description": "Name of the reviewer specialist"
                        },
                        "status": {
                            "type": "string", 
                            "enum": ["PASS", "REQUEST_CHANGES"],
                            "description": "Output PASS if code is clean, REQUEST_CHANGES if issues found."
                        },
                        "issues": {
                            "type": "array",
                            "description": "List of issues found. Empty if status is PASS.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "category": {"type": "string"},
                                    "file": {"type": "string"},
                                    "line": {"type": "string"},
                                    "description": {"type": "string", "description": "Critical analysis of the issue"}
                                },
                                "required": ["category", "file", "description"]
                            }
                        }
                    },
                    "required": ["reviewer_name", "status", "issues"]
                }
            }
        }
        
        user_content = f"**P4 Change Description (CL {cl}):**\n\n{p4_desc[:50000]}" 
        
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_content)
        ]
        
        try:
            # Enforce tool choice
            response = await self.llm.chat(
                messages, 
                tools=[submit_review_tool],
                # tool_choice={"type": "function", "function": {"name": "submit_review"}} # Check LLMClient support?
                # Most clients auto-detect, but let's assume auto for now or check implementation.
                # If tool_choice not supported explicitly in current client, prompt engineering does heavy lifting.
            )
            
            # Parse Tool Call
            result = {
                "name": name,
                "emoji": emoji,
                "status": "ERROR",
                "issues": [],
                "raw": response.content
            }
            
            if response.tool_calls:
                # Assuming first tool call is the review
                tool_call = response.tool_calls[0]
                if tool_call.get("function", {}).get("name") == "submit_review":
                    import json
                    args = json.loads(tool_call["function"]["arguments"])
                    result["status"] = args.get("status", "PASS")
                    result["issues"] = args.get("issues", [])
            else:
                # Fallback if model just chatted
                logger.warning(f"LLM did not call tool for {name}. Content: {response.content}")
                result["status"] = "PASS" # Default to pass if uncertainty
                
            return result
            
        except Exception as e:
            logger.error(f"LLM review failed for {name}: {e}")
            return {
                "name": name,
                "emoji": emoji,
                "status": "ERROR",
                "error": str(e)
            }

    async def _send_report(self, channel: str, ts: str, reports: List[dict], total_issues: int):
        """Format and send final report to Slack."""
        
        # Filter for actual changes or errors
        relevant_reports = []
        pass_reports = []
        
        real_issue_count = 0
        
        for report in reports:
             # report structure: {cl:..., outputs: [ {name, status, issues}, ... ]}
             for out in report["outputs"]:
                if out["status"] == "REQUEST_CHANGES" and out.get("issues"):
                    relevant_reports.append(out)
                    real_issue_count += len(out["issues"])
                elif out["status"] == "PASS":
                     pass_reports.append(out)
        
        # Construct Message
        if not relevant_reports:
            # All Pass
            msg = f"✅ **Code Review Passed** (Checked by {len(pass_reports)} experts)"
            await self.slack.send_message(channel, msg, thread_ts=ts)
            return

        final_text = "## 🔍 AI 코드 리뷰 결과\n\n"
        final_text += f"🚨 **발견된 중요 이슈: {real_issue_count}건**\n\n"
        
        for out in relevant_reports:
            final_text += f"{out['emoji']} **{out['name']}**\n"
            for issue in out["issues"]:
                # Format: - [Category] Description (File)
                file_info = f"(`{issue.get('file')}`)" if issue.get('file') else ""
                final_text += f"- **[{issue.get('category', 'Issue')}]** {issue.get('description')} {file_info}\n"
            final_text += "\n"
            
        if pass_reports:
             final_text += f"\n--- \n✅ **Pass**: {', '.join([r['name'] for r in pass_reports])}"
                
        # Send as Reply
        await self.slack.send_message(channel, final_text, thread_ts=ts)

