#!/usr/bin/env python3
"""Feedback queue for non-blocking reviewer-to-implementer feedback injection."""

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .logger import SupervisorLogger
    from .reviewer import ReviewResult


class FeedbackPriority(Enum):
    """Priority level for feedback injection."""
    NORMAL = "normal"
    ESCALATED = "escalated"


@dataclass
class FeedbackItem:
    """A queued feedback item for injection."""
    message: str
    priority: FeedbackPriority
    review_result: "ReviewResult"
    timestamp: float


class FeedbackQueue:
    """Manages feedback queue for non-blocking injection into implementer context."""

    def __init__(self, logger: "SupervisorLogger") -> None:
        self._logger = logger
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
        priority: FeedbackPriority,
        review_result: "ReviewResult"
    ) -> None:
        """Add feedback to the queue. Thread-safe."""
        async with self._lock:
            item = FeedbackItem(
                message=message,
                priority=priority,
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
        """Format feedback items into a single injection string."""
        try:
            if not items:
                return ""

            formatted_parts = []
            for item in items:
                if item.priority == FeedbackPriority.ESCALATED:
                    formatted_parts.append(self._format_escalated_feedback(item))
                else:
                    formatted_parts.append(self._format_normal_feedback(item))

            return "\n\n".join(formatted_parts)
        except Exception as e:
            try:
                self._logger.log_event(
                    "REVIEWER",
                    f"Feedback formatting error: {e}"
                )
            except Exception:
                pass
            return ""

    def _format_normal_feedback(self, item: FeedbackItem) -> str:
        header = "📝 **Reviewer Feedback**"
        return f"{header}\n{item.message}"

    def _format_escalated_feedback(self, item: FeedbackItem) -> str:
        header = "⚠️ **IMPORTANT: Repeat Issue Detected**"
        cycle_info = ""
        if item.review_result and item.review_result.cycle_count > 1:
            cycle_info = f"\n_(This issue has appeared {item.review_result.cycle_count} times)_"
        return f"{header}{cycle_info}\n{item.message}"
