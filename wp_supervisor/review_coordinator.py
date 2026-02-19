#!/usr/bin/env python3
"""Coordinates the concurrent reviewer system during Phase 4."""

import asyncio
import time
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .logger import SupervisorLogger

from .reviewer import ReviewerAgent, ReviewerState, ReviewerContext, ReviewResult
from .file_tracker import FileChangeTracker
from .review_trigger import ReviewTrigger, TriggerEvent
from .feedback_queue import FeedbackQueue


@dataclass
class ReviewCoordinatorConfig:
    """Configuration for the review coordinator."""
    file_threshold: int = 1
    enabled: bool = True


class ReviewCoordinator:
    """Coordinates reviewer, file tracker, trigger, and feedback queue for Phase 4."""

    def __init__(
        self,
        logger: "SupervisorLogger",
        working_dir: str,
        requirements_summary: str,
        interfaces_summary: str = "",
        tests_summary: str = "",
        config: Optional[ReviewCoordinatorConfig] = None
    ) -> None:
        self._logger = logger
        self._working_dir = working_dir
        self._requirements_summary = requirements_summary
        self._interfaces_summary = interfaces_summary
        self._tests_summary = tests_summary
        self._config = config or ReviewCoordinatorConfig()

        self._reviewer: Optional[ReviewerAgent] = None
        self._file_tracker: Optional[FileChangeTracker] = None
        self._trigger: Optional[ReviewTrigger] = None
        self._feedback_queue: Optional[FeedbackQueue] = None

        self._is_active = False
        self._is_degraded = False
        self._review_pending = asyncio.Event()
        self._is_reviewing = False
        self._review_count: int = 0

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def is_degraded(self) -> bool:
        return self._is_degraded

    @property
    def has_reviewed(self) -> bool:
        return self._review_count > 0

    async def start(self) -> None:
        """Start the review coordinator and all components."""
        if not self._config.enabled:
            self._logger.log_event("REVIEWER", "Reviewer disabled by config")
            self._is_degraded = True
            self._is_active = True
            return

        try:
            self._logger.log_event("REVIEWER", "Starting review coordinator")

            self._file_tracker = FileChangeTracker(
                logger=self._logger,
                working_dir=self._working_dir
            )

            self._feedback_queue = FeedbackQueue(logger=self._logger)

            self._trigger = ReviewTrigger(
                file_tracker=self._file_tracker,
                logger=self._logger,
                on_trigger=self._schedule_review,
                file_threshold=self._config.file_threshold
            )

            self._reviewer = ReviewerAgent(
                logger=self._logger,
                requirements_summary=self._requirements_summary,
                working_dir=self._working_dir
            )

            await self._reviewer.start()

            if self._reviewer.state == ReviewerState.DEGRADED:
                self._enter_degraded_mode(Exception("Reviewer failed to start"))
            else:
                self._is_active = True
                self._logger.log_event("REVIEWER", "Review coordinator ready")

        except Exception as e:
            self._enter_degraded_mode(e)

    async def stop(self) -> None:
        """Stop the coordinator and clean up all components."""
        self._logger.log_event("REVIEWER", "Stopping review coordinator")

        if self._reviewer is not None:
            try:
                await self._reviewer.stop()
            except Exception as e:
                self._logger.log_event("REVIEWER", f"Error stopping reviewer: {e}")

        self._reviewer = None
        self._file_tracker = None
        self._trigger = None
        self._feedback_queue = None

        self._is_active = False

    async def on_file_changed(self, file_path: str, tool_name: str) -> None:
        """Called when Write/Edit tool completes. Records change and checks triggers."""
        if not self._is_active or self._is_degraded:
            return

        if self._file_tracker is None or self._trigger is None:
            return

        try:
            await self._file_tracker.record_change(file_path, tool_name)
            await self._trigger.on_file_changed()
        except Exception as e:
            self._logger.log_event("REVIEWER", f"File change handling error: {e}")

    async def get_pending_feedback(self) -> str:
        """Get and clear pending feedback. Returns formatted string or empty."""
        if self._feedback_queue is None or not self._feedback_queue.has_pending():
            return ""

        try:
            items = await self._feedback_queue.dequeue_all()
            return self._feedback_queue.format_for_injection(items)
        except Exception as e:
            self._logger.log_event("REVIEWER", f"Feedback retrieval error: {e}")
            return ""

    def has_pending_feedback(self) -> bool:
        if self._feedback_queue is None:
            return False
        return self._feedback_queue.has_pending()

    async def wait_for_pending_reviews(self, timeout: float = 60.0) -> None:
        """Wait for pending reviews to complete, with timeout."""
        if not self._review_pending.is_set():
            return
        self._logger.log_event("REVIEWER", "Waiting for pending review to complete")
        start = time.monotonic()
        while self._review_pending.is_set():
            if time.monotonic() - start >= timeout:
                self._logger.log_event(
                    "REVIEWER",
                    "Timed out waiting for pending review"
                )
                return
            await asyncio.sleep(0.5)

    def _schedule_review(self, event: TriggerEvent) -> None:
        """Schedule a review. Debounces: if already reviewing, merges into one follow-up."""
        self._review_pending.set()
        if self._is_reviewing:
            self._logger.log_event("REVIEWER", "Review already in progress, changes will be included in follow-up")
            return
        self._is_reviewing = True
        asyncio.create_task(self._run_review(event))

    async def _run_review(self, event: TriggerEvent) -> None:
        """Run review loop. Continues until no more changes accumulate."""
        if self._is_degraded:
            self._is_reviewing = False
            self._review_pending.clear()
            return

        try:
            review_iteration = 0
            while self._review_pending.is_set():
                self._review_pending.clear()
                review_iteration += 1

                if review_iteration > 1:
                    self._logger.log_event("REVIEWER", f"Follow-up review #{review_iteration} (changes accumulated during previous review)")

                self._logger.log_event(
                    "REVIEWER",
                    f"Review triggered: {event.reason.value} ({event.file_count} files)"
                )

                result = await self._perform_review()

                if result is None:
                    self._logger.log_event("REVIEWER", "No pending changes to review, skipping")
                    break

                if result.issues:
                    await self._queue_feedback(result)

                if self._trigger is not None:
                    await self._trigger.reset()

                if self._file_tracker is not None:
                    await self._file_tracker.clear_pending()

                self._review_count += 1

        except Exception as e:
            self._logger.log_event("REVIEWER", f"Review cycle error: {e}")
        finally:
            self._is_reviewing = False
            self._review_pending.clear()
            self._logger.log_event("REVIEWER", f"Review session done ({self._review_count} total reviews)")

    async def _perform_review(self) -> Optional[ReviewResult]:
        """Perform a review cycle. Returns None if degraded or no changes."""
        if self._is_degraded or self._reviewer is None:
            return None

        if self._file_tracker is None:
            return None

        try:
            changed_files = await self._file_tracker.get_pending_changes()

            if not changed_files:
                return None

            context = ReviewerContext(
                requirements_summary=self._requirements_summary,
                changed_files=changed_files,
                interfaces_summary=self._interfaces_summary,
                tests_summary=self._tests_summary
            )

            result = await self._reviewer.review(context)
            return result

        except Exception as e:
            self._logger.log_event("REVIEWER", f"Review error: {e}")
            return None

    async def _queue_feedback(self, result: ReviewResult) -> None:
        """Queue feedback from review result."""
        if self._feedback_queue is None or self._reviewer is None:
            return

        try:
            feedback = self._reviewer.format_feedback(result)
            await self._feedback_queue.enqueue(feedback, result)

        except Exception as e:
            self._logger.log_event("REVIEWER", f"Feedback queueing error: {e}")

    def _enter_degraded_mode(self, error: Exception) -> None:
        """Enter degraded mode - log error and continue without reviewer."""
        self._logger.log_event("REVIEWER", f"Entering degraded mode: {error}")
        self._is_degraded = True
        self._is_active = True
