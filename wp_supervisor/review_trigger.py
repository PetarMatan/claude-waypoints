#!/usr/bin/env python3
"""Review trigger: fires when build/test/compile commands are executed."""

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, TYPE_CHECKING

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


# Default debounce interval in seconds [REQ-3.2]
DEFAULT_DEBOUNCE_INTERVAL = 60.0


class ReviewTrigger:
    """
    Monitors build command execution, fires callback when review should occur.

    Implements:
    - [REQ-3.1] Only trigger reviews after tests pass
    - [REQ-3.2] Enforce minimum interval between reviews (debouncing)
    - [REQ-3.3] Track last review timestamp
    - [EDGE-3] Accumulate changes during debounce for next review
    """

    def __init__(
        self,
        file_tracker: "FileChangeTracker",
        logger: "SupervisorLogger",
        on_trigger: TriggerCallback,
        debounce_interval: float = DEFAULT_DEBOUNCE_INTERVAL,
    ) -> None:
        """
        Initialize the review trigger.

        Args:
            file_tracker: Tracks pending file changes
            logger: Logger for events
            on_trigger: Callback to invoke when review should occur
            debounce_interval: Minimum seconds between reviews [REQ-3.2]
        """
        self._file_tracker = file_tracker
        self._logger = logger
        self._on_trigger = on_trigger
        self._debounce_interval = debounce_interval
        self._last_review_timestamp: Optional[float] = None
        self._lock = asyncio.Lock()

    @property
    def debounce_interval(self) -> float:
        """Return the configured debounce interval in seconds."""
        return self._debounce_interval

    @property
    def last_review_timestamp(self) -> Optional[float]:
        """Return the timestamp of the last review, or None if never reviewed."""
        return self._last_review_timestamp

    def is_debounce_active(self) -> bool:
        """
        Check if debounce interval is currently active.

        Implements [REQ-3.2]: Enforce minimum interval between reviews.

        Returns:
            True if within debounce interval, False if review is allowed
        """
        if self._last_review_timestamp is None:
            return False

        elapsed = time.monotonic() - self._last_review_timestamp
        return elapsed < self._debounce_interval

    def seconds_until_debounce_expires(self) -> float:
        """
        Calculate seconds remaining until debounce expires.

        Returns:
            Seconds until next review is allowed, or 0 if allowed now
        """
        if self._last_review_timestamp is None:
            return 0.0

        elapsed = time.monotonic() - self._last_review_timestamp
        remaining = self._debounce_interval - elapsed
        return max(0.0, remaining)

    def parse_test_result(self, command_output: str) -> bool:
        """
        Parse test command output to determine pass/fail status.

        Implements [REQ-3.1]: Only trigger reviews after tests pass.
        Implements [Q1]: Parses pytest output for pass/fail indicators.

        Args:
            command_output: The stdout/stderr from the test command

        Returns:
            True if tests passed, False if tests failed
        """
        import re

        if not command_output:
            # No output means we can't determine, treat as passing
            return True

        output_lower = command_output.lower()

        # Check for failure indicators first
        failure_patterns = [
            r'\d+\s+failed',           # "1 failed", "3 failed"
            r'\d+\s+error',            # "2 errors"
            r'=+\s*failures\s*=+',     # pytest failure banner
        ]

        for pattern in failure_patterns:
            if re.search(pattern, output_lower):
                return False

        # Check for success indicators
        success_patterns = [
            r'\d+\s+passed',           # "10 passed", "5 passed"
            r'all\s+tests\s+passed',   # Generic success
            r'ok\s*$',                 # Common test output
        ]

        for pattern in success_patterns:
            if re.search(pattern, output_lower):
                return True

        # If no clear indicator, assume passing (to not block review)
        return True

    async def on_build_executed(
        self,
        command: str,
        command_output: Optional[str] = None
    ) -> bool:
        """
        Called when Bash executes a build/test/compile command.

        Triggers a review if:
        1. There are pending file changes
        2. Tests passed (if output provided) [REQ-3.1]
        3. Debounce interval has elapsed [REQ-3.2]

        Implements [EDGE-3]: If debounced, changes accumulate for next review.

        Args:
            command: The Bash command that was executed
            command_output: Optional output from command for pass/fail detection

        Returns:
            True if review was triggered, False otherwise
        """
        async with self._lock:
            # EDGE-2: Skip review if no pending file changes
            pending_count = self._file_tracker.pending_count
            if pending_count == 0:
                return False

            # [REQ-3.1] Check if tests passed (if output provided)
            if command_output is not None:
                if not self.parse_test_result(command_output):
                    self._logger.log_event(
                        "REVIEWER",
                        "Skipping review: tests failed"
                    )
                    return False

            # [REQ-3.2] Check debounce interval
            if self.is_debounce_active():
                remaining = self.seconds_until_debounce_expires()
                self._logger.log_event(
                    "REVIEWER",
                    f"Debounce active: {remaining:.0f}s until next review allowed"
                )
                # [EDGE-3] Changes accumulate, will be picked up in next review
                return False

            # Create trigger event and fire callback
            event = TriggerEvent(
                reason=TriggerReason.BUILD_EXECUTION,
                file_count=pending_count
            )
            self._on_trigger(event)

            # Update timestamp AFTER triggering to start debounce interval
            self._last_review_timestamp = time.monotonic()
            return True

    async def reset(self) -> None:
        """
        Reset trigger state after review completes.

        Clears debounce state to allow subsequent triggers.
        The debounce is enforced between on_build_executed calls,
        and reset() marks the end of a review cycle.
        """
        # Clear debounce to allow next trigger
        self._last_review_timestamp = None

    def clear_debounce(self) -> None:
        """
        Clear debounce state, allowing immediate review.

        Useful for testing or manual override.
        """
        self._last_review_timestamp = None
