#!/usr/bin/env python3
"""Concurrent reviewer agent for Phase 4 implementation validation."""

import asyncio
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from claude_agent_sdk import ClaudeSDKClient
    from .logger import SupervisorLogger

from .templates import (
    REVIEWER_PROMPT_TEMPLATE,
    REVIEWER_FEEDBACK_ACTION,
    REVIEWER_FEEDBACK_TEMPLATE,
)


class ReviewerState(Enum):
    INITIALIZING = "initializing"
    READY = "ready"
    REVIEWING = "reviewing"
    DEGRADED = "degraded"


@dataclass
class ReviewResult:
    """Result of a review cycle."""
    issues: List[str] = field(default_factory=list)
    files_reviewed: Set[str] = field(default_factory=set)
    is_repeat_issue: bool = False
    cycle_count: int = 0


@dataclass
class ReviewerContext:
    """Context for reviewer: requirements, interfaces, and changed files."""
    requirements_summary: str
    changed_files: dict  # Dict[str, str]: path -> content
    interfaces_summary: str = ""


class ReviewerAgent:
    """Runs a Sonnet reviewer that validates code changes against Phase 1 requirements."""

    def __init__(
        self,
        logger: "SupervisorLogger",
        requirements_summary: str,
        working_dir: str
    ) -> None:
        self._logger = logger
        self._requirements_summary = requirements_summary
        self._working_dir = working_dir
        self._state = ReviewerState.INITIALIZING
        self._client: Optional["ClaudeSDKClient"] = None
        self._options = None
        self._session_id: Optional[str] = None
        self._issue_history: Dict[str, int] = {}

    @property
    def state(self) -> ReviewerState:
        return self._state

    async def start(self) -> None:
        """Start the reviewer agent session. Transitions to READY or DEGRADED."""
        try:
            self._logger.log_event("REVIEWER", "Starting reviewer agent (Sonnet)")

            from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

            self._options = ClaudeAgentOptions(
                cwd=self._working_dir,
                model="sonnet",
                max_budget_usd=1.0,
                permission_mode="bypassPermissions",
            )

            self._client = ClaudeSDKClient(self._options)
            self._state = ReviewerState.READY
            self._logger.log_event("REVIEWER", "Reviewer agent ready")

        except Exception as e:
            self._state = ReviewerState.DEGRADED
            self._logger.log_event("REVIEWER", f"Reviewer initialization failed: {e}")

    async def review(self, context: ReviewerContext) -> ReviewResult:
        """Review changed files against requirements. Returns empty result if degraded or no changes."""
        if self._state == ReviewerState.DEGRADED:
            return ReviewResult()

        if not context.changed_files:
            return ReviewResult()

        try:
            self._state = ReviewerState.REVIEWING

            prompt = self._build_review_prompt(context)
            response_text = await self._query_reviewer(prompt)
            issues = self._parse_issues(response_text)

            self._logger.log_event(
                "REVIEWER",
                f"Review complete: {len(issues)} issue(s) in {len(context.changed_files)} file(s)"
            )

            issue_info = self._track_issues(issues)

            result = ReviewResult(
                issues=issues,
                files_reviewed=set(context.changed_files.keys()),
                is_repeat_issue=issue_info.get("is_repeat", False),
                cycle_count=issue_info.get("max_cycle", 0)
            )

            self._state = ReviewerState.READY
            return result

        except Exception as e:
            self._logger.log_event("REVIEWER", f"Review failed: {e}")
            self._state = ReviewerState.READY
            return ReviewResult()

    def _build_review_prompt(self, context: ReviewerContext) -> str:
        files_section = ""
        for path, content in context.changed_files.items():
            files_section += f"\n### {path}\n```\n{content}\n```\n"

        interfaces_section = ""
        if context.interfaces_summary:
            interfaces_section = f"\n## Interfaces from Phase 2\n{context.interfaces_summary}\n"

        return REVIEWER_PROMPT_TEMPLATE.format(
            requirements_summary=context.requirements_summary,
            interfaces_section=interfaces_section,
            files_section=files_section
        )

    async def _query_reviewer(self, prompt: str) -> str:
        """Send review prompt to Sonnet and collect response."""
        from claude_agent_sdk import ClaudeSDKClient

        async def _run():
            text = ""
            async with ClaudeSDKClient(self._options) as client:
                await client.query(prompt)
                async for message in client.receive_response():
                    if hasattr(message, 'content') and message.content:
                        for block in message.content:
                            if hasattr(block, 'text'):
                                text += block.text
            return text

        return await asyncio.wait_for(_run(), timeout=120.0)

    def _parse_issues(self, response_text: str) -> List[str]:
        """Parse reviewer response into a list of issues."""
        if not response_text or not response_text.strip():
            return []

        text = response_text.strip()

        if "no issues found" in text.lower():
            return []

        issues = self._extract_issue_items(text)

        if not issues and len(text) > 30:
            issues = [text]

        return issues

    def _extract_issue_items(self, text: str) -> List[str]:
        """Extract individual issue strings from bulleted/numbered text.

        This parsing is optional — the raw reviewer response could be forwarded
        directly to the implementer. We parse primarily to enable per-issue
        repeat detection and accurate issue counts in logs.
        """
        issues = []
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
            if line.startswith(('- ', '* ', '• ')):
                issue = line.lstrip('-*• ').strip()
                if issue:
                    issues.append(issue)
            elif len(line) > 2 and line[0].isdigit() and '. ' in line[:5]:
                parts = line.split('. ', 1)
                if len(parts) == 2 and parts[1].strip():
                    issues.append(parts[1].strip())
        return issues

    def format_feedback(self, result: ReviewResult) -> str:
        """Format review result as feedback text for implementer injection."""
        if not result.issues:
            return ""

        issues_text = "\n".join(f"- {issue}" for issue in result.issues)
        files_text = ", ".join(result.files_reviewed) if result.files_reviewed else "no files"

        return REVIEWER_FEEDBACK_TEMPLATE.format(
            files_text=files_text,
            cycle_count=result.cycle_count,
            issues_text=issues_text,
            action_instruction=REVIEWER_FEEDBACK_ACTION,
        )

    async def stop(self) -> None:
        """Stop the reviewer agent and clean up resources."""
        self._logger.log_event("REVIEWER", "Stopping reviewer agent")
        self._client = None
        self._options = None
        self._session_id = None
        self._state = ReviewerState.DEGRADED

    def should_escalate(self, result: ReviewResult) -> bool:
        """Returns True if same issue persists after 2 feedback cycles."""
        return result.is_repeat_issue and result.cycle_count >= 2

    def _track_issues(self, issues: List[str]) -> dict:
        """Track issues for repeat detection. Returns dict with is_repeat and max_cycle."""
        if not issues:
            return {"is_repeat": False, "max_cycle": 0}

        is_repeat = False
        max_cycle = 0

        for issue in issues:
            issue_hash = hashlib.md5(issue.encode()).hexdigest()[:16]

            if issue_hash in self._issue_history:
                self._issue_history[issue_hash] += 1
                is_repeat = True
            else:
                self._issue_history[issue_hash] = 1

            max_cycle = max(max_cycle, self._issue_history[issue_hash])

        return {
            "is_repeat": is_repeat,
            "max_cycle": max_cycle
        }
