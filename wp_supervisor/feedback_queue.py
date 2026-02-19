#!/usr/bin/env python3
"""Feedback queue for non-blocking reviewer-to-implementer feedback injection."""

import asyncio
import time
from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .logger import SupervisorLogger
    from .reviewer import ReviewResult


@dataclass
class FeedbackItem:
    """A queued feedback item for injection."""
    message: str
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
