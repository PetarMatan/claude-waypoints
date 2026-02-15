#!/usr/bin/env python3
"""Review trigger: fires after N files written."""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .file_tracker import FileChangeTracker
    from .logger import SupervisorLogger


class TriggerReason(Enum):
    FILE_THRESHOLD = "file_threshold"
    MANUAL = "manual"


@dataclass
class TriggerEvent:
    """Event indicating a review should be triggered."""
    reason: TriggerReason
    file_count: int


TriggerCallback = Callable[[TriggerEvent], None]


class ReviewTrigger:
    """Monitors file changes, fires callback when review should occur."""

    DEFAULT_FILE_THRESHOLD = 1

    def __init__(
        self,
        file_tracker: "FileChangeTracker",
        logger: "SupervisorLogger",
        on_trigger: TriggerCallback,
        file_threshold: int = DEFAULT_FILE_THRESHOLD
    ) -> None:
        self._file_tracker = file_tracker
        self._logger = logger
        self._on_trigger = on_trigger
        self._file_threshold = file_threshold
        self._files_since_review = 0
        self._lock = asyncio.Lock()

    @property
    def file_threshold(self) -> int:
        return self._file_threshold

    @property
    def files_since_review(self) -> int:
        return self._files_since_review

    async def on_file_changed(self) -> bool:
        """Called when Write/Edit completes. Returns True if review was triggered."""
        async with self._lock:
            self._files_since_review += 1

            if self._should_trigger_on_file():
                event = TriggerEvent(
                    reason=TriggerReason.FILE_THRESHOLD,
                    file_count=self._files_since_review
                )
                self._logger.log_event(
                    "REVIEWER",
                    f"File threshold reached ({self._files_since_review} files)"
                )
                try:
                    self._on_trigger(event)
                except Exception as e:
                    self._logger.log_event(
                        "REVIEWER",
                        f"Trigger callback error: {e}"
                    )
                return True

            return False

    async def reset(self) -> None:
        """Reset file counter after review completes."""
        async with self._lock:
            self._files_since_review = 0

    def _should_trigger_on_file(self) -> bool:
        return self._files_since_review >= self._file_threshold
