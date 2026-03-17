#!/usr/bin/env python3
"""Feedback queue for non-blocking reviewer-to-implementer feedback injection."""

import asyncio
import time
from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .logger import SupervisorLogger
    from .reviewer import ReviewResult, ParsedIssue
    from .feedback_capping import FeedbackCapper, CategorizedFinding
    from .feedback_dedup import FeedbackDeduplicator


@dataclass
class FeedbackItem:
    """A queued feedback item for injection."""
    message: str
    review_result: "ReviewResult"
    timestamp: float
    # Track if capping/dedup was applied
    dropped_count: int = 0
    deduplicated_count: int = 0


class FeedbackQueue:
    """
    Manages feedback queue for non-blocking injection into implementer context.

    Integrates with:
    - FeedbackCapper: Limits feedback to 20 items by severity [REQ-2.x]
    - FeedbackDeduplicator: Prevents duplicate issues [REQ-4.x]
    """

    def __init__(
        self,
        logger: "SupervisorLogger",
        capper: Optional["FeedbackCapper"] = None,
        deduplicator: Optional["FeedbackDeduplicator"] = None
    ) -> None:
        """
        Initialize the feedback queue.

        Args:
            logger: Logger for events
            capper: Optional capper for severity-based limiting [REQ-2.x]
            deduplicator: Optional deduplicator for duplicate prevention [REQ-4.x]
        """
        self._logger = logger
        self._capper = capper
        self._deduplicator = deduplicator
        self._queue: List[FeedbackItem] = []
        self._lock = asyncio.Lock()

    @property
    def pending_count(self) -> int:
        return len(self._queue)

    def has_pending(self) -> bool:
        return len(self._queue) > 0

    async def enqueue(
        self,
        message: str,
        review_result: "ReviewResult"
    ) -> None:
        """Add feedback to the queue. Thread-safe."""
        async with self._lock:
            item = FeedbackItem(
                message=message,
                review_result=review_result,
                timestamp=time.monotonic()
            )
            self._queue.append(item)

    async def dequeue_all(self) -> List[FeedbackItem]:
        """Get and remove all pending feedback items in FIFO order. Thread-safe."""
        async with self._lock:
            items = self._queue.copy()
            self._queue.clear()
            return items

    async def peek(self) -> Optional[FeedbackItem]:
        """Get next pending feedback without removing it."""
        async with self._lock:
            if self._queue:
                return self._queue[0]
            return None

    def format_for_injection(self, items: List[FeedbackItem]) -> str:
        """Join queued feedback messages into a single injection string."""
        if not items:
            return ""
        return "\n\n".join(item.message for item in items)

    def _to_categorized(
        self,
        parsed_issues: List["ParsedIssue"],
        use_severity: bool = True
    ) -> List["CategorizedFinding"]:
        """
        Convert ParsedIssue list to CategorizedFinding list.

        Args:
            parsed_issues: Issues to convert
            use_severity: If True and capper available, parse severity from issue.
                          If False, default to MEDIUM (used when severity is irrelevant).

        Returns:
            List of CategorizedFinding objects
        """
        from .feedback_capping import CategorizedFinding, Severity

        return [
            CategorizedFinding(
                content=issue.content,
                severity=(
                    self._capper.parse_severity(issue.severity)
                    if use_severity and self._capper
                    else Severity.MEDIUM
                ),
                file_path=issue.file_path
            )
            for issue in parsed_issues
        ]

    async def enqueue_with_processing(
        self,
        message: str,
        review_result: "ReviewResult"
    ) -> None:
        """
        Enqueue feedback after applying capping and deduplication.

        Args:
            message: The formatted feedback message (used as-is if no filtering)
            review_result: The full review result with parsed issues
        """
        parsed_issues = list(review_result.parsed_issues)  # Copy to avoid mutation
        dropped_count = 0
        dedup_count = 0

        try:
            # Apply deduplication first (removes duplicates from previous reviews)
            if self._deduplicator and parsed_issues:
                parsed_issues, dedup_count = self._apply_deduplication(parsed_issues)

            # Apply capping after deduplication (sort by severity, keep top 20)
            if self._capper and parsed_issues:
                parsed_issues, dropped_count = self._apply_capping(parsed_issues)

            # Format final message — only rebuild if filtering actually removed items
            files_text = ", ".join(review_result.files_reviewed) if review_result.files_reviewed else "reviewed files"
            final_message = self._format_processed_message(
                message, parsed_issues, dropped_count, dedup_count,
                files_text=files_text
            )

            # Record the processed findings for future deduplication
            if self._deduplicator and parsed_issues:
                self._deduplicator.record_findings(self._to_categorized(parsed_issues))
        except Exception as e:
            # Log error but don't lose feedback - use original message
            self._logger.log_event("FEEDBACK", f"Processing failed: {e}, using raw feedback")
            final_message = message

        # Enqueue
        async with self._lock:
            item = FeedbackItem(
                message=final_message,
                review_result=review_result,
                timestamp=time.monotonic(),
                dropped_count=dropped_count,
                deduplicated_count=dedup_count
            )
            self._queue.append(item)

    def _apply_capping(
        self,
        parsed_issues: List["ParsedIssue"]
    ) -> tuple[List["ParsedIssue"], int]:
        """
        Apply severity-based capping to issues.

        Args:
            parsed_issues: List of parsed issues with severity

        Returns:
            Tuple of (capped issues, number dropped)
        """
        if not self._capper:
            return (parsed_issues, 0)

        categorized = self._to_categorized(parsed_issues)
        result = self._capper.apply_cap(categorized)

        # Replicate apply_cap's deterministic sort on indices to map back
        # to ParsedIssues without relying on object identity.
        sorted_indices = sorted(
            range(len(categorized)),
            key=lambda i: categorized[i].severity.value
        )
        kept_indices = sorted_indices[:len(result.findings)]
        capped_issues = [parsed_issues[i] for i in kept_indices]

        return (capped_issues, result.dropped_count)

    def _apply_deduplication(
        self,
        parsed_issues: List["ParsedIssue"]
    ) -> tuple[List["ParsedIssue"], int]:
        """
        Apply deduplication to issues.

        Args:
            parsed_issues: List of parsed issues

        Returns:
            Tuple of (deduplicated issues, number of duplicates removed)
        """
        if not self._deduplicator:
            return (parsed_issues, 0)

        categorized = self._to_categorized(parsed_issues, use_severity=False)
        result = self._deduplicator.deduplicate(categorized)

        # Map back via content hash instead of object identity.
        surviving_hashes = {
            self._deduplicator.compute_issue_hash(f.content, f.file_path)
            for f in result.unique_findings
        }
        seen: set = set()
        deduped_issues = []
        for i, cat in enumerate(categorized):
            h = self._deduplicator.compute_issue_hash(cat.content, cat.file_path)
            if h in surviving_hashes and h not in seen:
                deduped_issues.append(parsed_issues[i])
                seen.add(h)

        return (deduped_issues, result.duplicate_count)

    def _format_processed_message(
        self,
        original_message: str,
        processed_issues: List["ParsedIssue"],
        dropped_count: int,
        dedup_count: int,
        files_text: str = "reviewed files"
    ) -> str:
        """
        Format the final feedback message after capping/dedup.

        Returns the original message if nothing was filtered. Otherwise
        rebuilds with only surviving issues to avoid double-listing.
        """
        if not processed_issues or (dropped_count == 0 and dedup_count == 0):
            return original_message

        # Rebuild with only surviving issues (avoids double-listing)
        issues_lines = []
        for issue in processed_issues:
            if issue.severity:
                issues_lines.append(f"- [{issue.severity.upper()}] {issue.content}")
            else:
                issues_lines.append(f"- {issue.content}")

        issues_text = "\n".join(issues_lines)

        stats_parts = []
        if dropped_count > 0:
            stats_parts.append(f"{dropped_count} low-priority items capped")
        if dedup_count > 0:
            stats_parts.append(f"{dedup_count} duplicate items removed")

        stats_note = f"\n\n(Note: {', '.join(stats_parts)})"

        from .templates import REVIEWER_FEEDBACK_TEMPLATE, REVIEWER_FEEDBACK_ACTION
        return REVIEWER_FEEDBACK_TEMPLATE.format(
            files_text=files_text,
            issues_text=issues_text,
            action_instruction=REVIEWER_FEEDBACK_ACTION,
        ) + stats_note
