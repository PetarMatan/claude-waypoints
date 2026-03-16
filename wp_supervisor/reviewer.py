#!/usr/bin/env python3
"""Concurrent reviewer agent for Phase 4 implementation validation."""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

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
class ParsedIssue:
    """
    A single parsed issue with severity.

    Implements [REQ-2.1]: Reviewer categorizes each finding by severity.
    """
    content: str
    severity: str  # "critical", "high", "medium", "low"
    file_path: Optional[str] = None


@dataclass
class ReviewResult:
    """Result of a review cycle."""
    issues: List[str] = field(default_factory=list)
    files_reviewed: Set[str] = field(default_factory=set)
    parsed_issues: List[ParsedIssue] = field(default_factory=list)


@dataclass
class ReviewerContext:
    """Context for reviewer: requirements, interfaces, tests, and changed files."""
    requirements_summary: str
    changed_files: dict  # Dict[str, str]: path -> content
    interfaces_summary: str = ""
    tests_summary: str = ""


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

    @property
    def state(self) -> ReviewerState:
        return self._state

    @staticmethod
    def _build_hooks_config() -> Dict[str, Any]:
        """Build hooks that block Write/Edit tools — reviewer is read-only."""
        from claude_agent_sdk import HookMatcher

        async def deny_write(
            input_data: Dict[str, Any],
            tool_use_id: Optional[str],
            context: Any
        ) -> Dict[str, Any]:
            return {
                "hookSpecificOutput": {
                    "hookEventName": input_data.get("hook_event_name", "PreToolUse"),
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "Reviewer is read-only: Write/Edit not allowed.",
                }
            }

        return {
            "PreToolUse": [
                HookMatcher(matcher="Write|Edit", hooks=[deny_write]),
            ],
        }

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
                hooks=self._build_hooks_config(),
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
            parsed_issues = self._parse_issues_with_severity(response_text)

            self._logger.log_event(
                "REVIEWER",
                f"Review complete: {len(issues)} issue(s) in {len(context.changed_files)} file(s)"
            )

            result = ReviewResult(
                issues=issues,
                files_reviewed=set(context.changed_files.keys()),
                parsed_issues=parsed_issues,
            )

            self._state = ReviewerState.READY
            return result

        except asyncio.TimeoutError:
            self._logger.log_event("REVIEWER", "Review timed out (120s)")
            self._state = ReviewerState.READY
            return ReviewResult()
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
            interfaces_section = (
                f"\n## Interfaces from Phase 2 (design-time stubs — may contain TODOs that are now implemented)\n"
                f"{context.interfaces_summary}\n"
            )

        tests_section = ""
        if context.tests_summary:
            tests_section = f"\n## Tests from Phase 3\n{context.tests_summary}\n"

        return REVIEWER_PROMPT_TEMPLATE.format(
            requirements_summary=context.requirements_summary,
            interfaces_section=interfaces_section,
            tests_section=tests_section,
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
        directly to the implementer. We parse primarily for accurate issue
        counts in logs.
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

    def _parse_issues_with_severity(self, text: str) -> List[ParsedIssue]:
        """
        Parse reviewer response into issues with severity categorization.

        Implements [REQ-2.1]: Extracts severity from issue text.
        Implements [ERR-2]: Defaults to "medium" if severity cannot be parsed.

        Expected format from reviewer:
        - [CRITICAL] Missing null check on `deviceId`...
        - [HIGH] `calculateDemand()` ignores the `roomSize` edge case...
        - [MEDIUM] Consider adding logging for debugging...
        - [LOW] Variable naming could be clearer...

        Args:
            text: Raw reviewer response text

        Returns:
            List of ParsedIssue objects with severity categorization
        """
        if not text or not text.strip():
            return []

        parsed_issues: List[ParsedIssue] = []

        # First extract raw issue items
        raw_issues = self._extract_issue_items(text)

        for issue_text in raw_issues:
            severity, clean_content = self._extract_severity_from_issue(issue_text)
            parsed_issues.append(ParsedIssue(
                content=clean_content,
                severity=severity,
                file_path=None  # Could be enhanced to extract file paths
            ))

        return parsed_issues

    def _extract_severity_from_issue(self, issue_text: str) -> tuple[str, str]:
        """
        Extract severity tag and clean content from an issue string.

        Implements [ERR-2]: Returns "medium" as default severity.

        Args:
            issue_text: Raw issue string potentially containing [SEVERITY] tag

        Returns:
            Tuple of (severity, clean_content) where severity is lowercase
        """
        import re

        # Valid severity levels
        valid_severities = {"critical", "high", "medium", "low"}

        # Look for [SEVERITY] pattern at the start of the issue
        match = re.match(r'\[(CRITICAL|HIGH|MEDIUM|LOW)\]\s*(.+)', issue_text, re.IGNORECASE)

        if match:
            severity = match.group(1).lower()
            content = match.group(2).strip()
            if severity in valid_severities:
                return (severity, content)

        # [ERR-2] Default to medium if no valid severity found
        return ("medium", issue_text)

    def format_feedback(self, result: ReviewResult) -> str:
        """Format review result as feedback text for implementer injection."""
        if not result.issues:
            return ""

        issues_text = "\n".join(f"- {issue}" for issue in result.issues)
        files_text = ", ".join(result.files_reviewed) if result.files_reviewed else "no files"

        return REVIEWER_FEEDBACK_TEMPLATE.format(
            files_text=files_text,
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
