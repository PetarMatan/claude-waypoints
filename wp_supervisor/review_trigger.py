#!/usr/bin/env python3
"""Review trigger: fires when build/test/compile commands are executed."""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .file_tracker import FileChangeTracker
    from .logger import SupervisorLogger


class TriggerReason(Enum):
    """Reason why a review was triggered."""
    BUILD_EXECUTION = "build_execution"
    MANUAL = "manual"


@dataclass
class TriggerEvent:
    """Event indicating a review should be triggered."""
    reason: TriggerReason
    file_count: int


TriggerCallback = Callable[[TriggerEvent], None]


# Keywords that trigger a review when found in Bash commands (case-insensitive)
BUILD_KEYWORDS = ("test", "compile", "build")


class ReviewTrigger:
    """Monitors build command execution, fires callback when review should occur."""

    def __init__(
        self,
        file_tracker: "FileChangeTracker",
        logger: "SupervisorLogger",
        on_trigger: TriggerCallback,
    ) -> None:
        self._file_tracker = file_tracker
        self._logger = logger
        self._on_trigger = on_trigger
        self._lock = asyncio.Lock()

    async def on_build_executed(self, command: str) -> bool:
        """Called when Bash executes a build/test/compile command.

        Triggers a review if there are pending file changes.
        Returns True if review was triggered, False otherwise.

        Flow:
        1. Check if file_tracker.pending_count > 0
        2. If no pending changes, return False (skip review per EDGE-2)
        3. Create TriggerEvent with reason=BUILD_EXECUTION and file_count
        4. Call on_trigger callback
        5. Return True

        Args:
            command: The Bash command that was executed.
        """
        async with self._lock:
            # EDGE-2: Skip review if no pending file changes
            pending_count = self._file_tracker.pending_count
            if pending_count == 0:
                return False

            # Create trigger event and fire callback
            event = TriggerEvent(
                reason=TriggerReason.BUILD_EXECUTION,
                file_count=pending_count
            )
            self._on_trigger(event)
            return True

    async def reset(self) -> None:
        """Reset trigger state after review completes."""
        pass
