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
    
    def __init__(self, llm_client: LLMClient):
        super().__init__()
        self.llm = llm_client
        self.config = get_config()
        self.p4 = PerforceClient()
        
        from src.main import get_slack_integration
        self.slack = get_slack_integration()

    async def execute(self, input_data: dict) -> dict:
        """
        Main execution entry point.
        input_data expected keys: "text", "channel", "ts"
        """
        text = input_data.get("text", "")
        channel = input_data.get("channel")
        ts = input_data.get("ts")
        
        # 1. Parse Change Lists
        cls = self._parse_changelists(text)
        if not cls:
            return {"status": "skipped", "reason": "No CLs found"}

        # 2. Mark Processing
        await self.slack.add_reaction(channel, ts, "loading")
        
        try:
            reports = []
            total_issues = 0

            # 3. Process each CL
            for cl in cls:
                cl_report = await self._process_cl(cl, channel, ts)
                if cl_report:
                    reports.append(cl_report)
                    total_issues += cl_report.get("issues", 0)

            # 4. Final Report
            if reports:
                await self._send_report(channel, ts, reports, total_issues)
                await self.slack.add_reaction(channel, ts, "heavy_check_mark")
            else:
                 await self.slack.add_reaction(channel, ts, "white_check_mark") # Processed but no review generated (e.g. no strategy matched)

        except Exception as e:
            logger.error(f"Code review failed: {e}", exc_info=True)
            await self.slack.add_reaction(channel, ts, "ai") # Fail emoji
            await self.slack.send_message(channel, f"❌ 코드 리뷰 중 오류가 발생했습니다: {str(e)}", thread_ts=ts)
            return {"status": "error", "error": str(e)}
        finally:
            await self.slack.remove_reaction(channel, ts, "loading")

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
            describe_output = await self.p4.run("describe", "-s", cl)
            if not describe_output:
                logger.warning(f"CL {cl} not found or empty.")
                return None
            
            # P4 output format parsing is needed if using raw command
            # But let's assume raw string for now and regex match files
            full_desc = describe_output[0] if isinstance(describe_output, list) else str(describe_output)
            
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

        # 4. Execute LLM Reviews in Parallel
        results = await asyncio.gather(*matched_tasks)
        
        # 5. Aggregate
        issues_count = 0
        outputs = []
        
        for res in results:
            if res:
                outputs.append(res)
                # Parse issue count from LLM output: "[Issues Found]: N issues"
                match = re.search(r'\[Issues Found\]:\s*(\d+)', res)
                if match:
                    issues_count += int(match.group(1))

        return {
            "cl": cl,
            "outputs": outputs,
            "issues": issues_count
        }

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

    async def _run_llm_review(self, strategy: dict, cl: str, p4_desc: str) -> str:
        """Run LLM for a specific strategy."""
        system_prompt = strategy["prompt"]
        emoji = strategy.get("emoji", "📝")
        name = strategy.get("name", "Review")
        
        # Construct User Prompt
        # Limit p4_desc size to avoid context overflow? 
        # Gemini 1.5/2.0 has huge context, but let's be reasonable.
        user_content = f"**P4 Change Description (CL {cl}):**\n\n{p4_desc[:50000]}" 
        
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_content)
        ]
        
        try:
            response = await self.llm.chat(messages)
            content = response.content
            # Add Header
            return f"{emoji} **{name} Review**\n{content}"
        except Exception as e:
            logger.error(f"LLM review failed for {name}: {e}")
            return f"{emoji} **{name} Review**\n❌ LLM execution failed."

    async def _send_report(self, channel: str, ts: str, reports: List[dict], total_issues: int):
        """Format and send final report to Slack."""
        
        final_text = "## 🔍 AI 코드 리뷰 결과\n\n"
        final_text += f"📊 **총 이슈: {total_issues}건 | 리뷰 대상 CL: {len(reports)}개**\n\n"
        
        for report in reports:
            cl = report["cl"]
            # final_text += f"### CL {cl}\n" # Single CL usually
            for out in report["outputs"]:
                final_text += out + "\n\n---\n\n"
                
        # Send as Reply
        await self.slack.send_message(channel, final_text, thread_ts=ts)

