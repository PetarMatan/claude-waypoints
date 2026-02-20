#!/usr/bin/env python3
"""Unit tests for wp_supervisor/review_trigger.py"""

import asyncio
import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, '.')
from wp_supervisor.review_trigger import (
    ReviewTrigger,
    TriggerReason,
    TriggerEvent,
    BUILD_KEYWORDS,
)


@pytest.fixture(autouse=True)
def clean_supervisor_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("WP_SUPERVISOR_"):
            monkeypatch.delenv(key, raising=False)


def run_async(coro):
    return asyncio.run(coro)


# =============================================================================
# REQ-5: TriggerReason Enum - BUILD_EXECUTION replaces FILE_THRESHOLD
# =============================================================================

class TestTriggerReason:

    def test_build_execution_reason_exists(self):
        """REQ-5: Add new TriggerReason.BUILD_EXECUTION enum value."""
        assert TriggerReason.BUILD_EXECUTION.value == "build_execution"

    def test_manual_reason_exists(self):
        """Manual trigger reason should still exist."""
        assert TriggerReason.MANUAL.value == "manual"

    def test_file_threshold_reason_removed(self):
        """REQ-4: FILE_THRESHOLD trigger mechanism fully removed."""
        assert not hasattr(TriggerReason, 'FILE_THRESHOLD')


# =============================================================================
# TriggerEvent Dataclass
# =============================================================================

class TestTriggerEvent:

    def test_trigger_event_has_reason_field(self):
        event = TriggerEvent(reason=TriggerReason.BUILD_EXECUTION, file_count=3)
        assert event.reason == TriggerReason.BUILD_EXECUTION

    def test_trigger_event_has_file_count_field(self):
        event = TriggerEvent(reason=TriggerReason.BUILD_EXECUTION, file_count=3)
        assert event.file_count == 3

    def test_trigger_event_with_manual_reason(self):
        event = TriggerEvent(reason=TriggerReason.MANUAL, file_count=5)
        assert event.reason == TriggerReason.MANUAL
        assert event.file_count == 5


# =============================================================================
# BUILD_KEYWORDS Constant
# =============================================================================

class TestBuildKeywords:

    def test_build_keywords_constant_exists(self):
        """BUILD_KEYWORDS constant should be defined."""
        assert BUILD_KEYWORDS is not None

    def test_build_keywords_contains_test(self):
        """REQ-1: Keywords include 'test'."""
        assert "test" in BUILD_KEYWORDS

    def test_build_keywords_contains_compile(self):
        """REQ-1: Keywords include 'compile'."""
        assert "compile" in BUILD_KEYWORDS

    def test_build_keywords_contains_build(self):
        """REQ-1: Keywords include 'build'."""
        assert "build" in BUILD_KEYWORDS


# =============================================================================
# ReviewTrigger Init - REQ-4: file_threshold removed
# =============================================================================

class TestReviewTriggerInit:

    def test_review_trigger_class_exists(self):
        assert ReviewTrigger is not None

    def test_init_requires_expected_params(self):
        """REQ-6: ReviewTrigger init takes file_tracker, logger, on_trigger."""
        import inspect
        params = inspect.signature(ReviewTrigger.__init__).parameters
        assert 'file_tracker' in params
        assert 'logger' in params
        assert 'on_trigger' in params

    def test_init_does_not_have_file_threshold_param(self):
        """REQ-4: file_threshold removed from ReviewTrigger."""
        import inspect
        params = inspect.signature(ReviewTrigger.__init__).parameters
        assert 'file_threshold' not in params

    def test_default_file_threshold_class_attr_removed(self):
        """REQ-4: DEFAULT_FILE_THRESHOLD class attribute removed."""
        assert not hasattr(ReviewTrigger, 'DEFAULT_FILE_THRESHOLD')


# =============================================================================
# ReviewTrigger Properties - REQ-4: file_threshold removed
# =============================================================================

class TestReviewTriggerProperties:

    def test_file_threshold_property_removed(self):
        """REQ-4: file_threshold property removed from ReviewTrigger."""
        assert not hasattr(ReviewTrigger, 'file_threshold')

    def test_files_since_review_property_removed(self):
        """REQ-4: files_since_review property removed (no longer tracking count)."""
        assert not hasattr(ReviewTrigger, 'files_since_review')


# =============================================================================
# REQ-6: on_build_executed Method
# =============================================================================

class TestReviewTriggerOnBuildExecuted:

    def test_on_build_executed_method_exists(self):
        """REQ-6: Add on_build_executed(command: str) method to ReviewTrigger."""
        assert hasattr(ReviewTrigger, 'on_build_executed')

    def test_on_build_executed_is_async(self):
        """REQ-6: on_build_executed should be async."""
        import inspect
        assert inspect.iscoroutinefunction(ReviewTrigger.on_build_executed)

    def test_on_build_executed_accepts_command_param(self):
        """REQ-6: on_build_executed takes command: str parameter."""
        import inspect
        params = inspect.signature(ReviewTrigger.on_build_executed).parameters
        assert 'command' in params


# =============================================================================
# REQ-4: on_file_changed Method Removed
# =============================================================================

class TestOnFileChangedRemoved:

    def test_on_file_changed_method_removed(self):
        """REQ-4: on_file_changed removed from ReviewTrigger (trigger moved to build)."""
        assert not hasattr(ReviewTrigger, 'on_file_changed')

    def test_should_trigger_on_file_method_removed(self):
        """REQ-4: _should_trigger_on_file removed (no file-based triggering)."""
        assert not hasattr(ReviewTrigger, '_should_trigger_on_file')


# =============================================================================
# ReviewTrigger Reset
# =============================================================================

class TestReviewTriggerReset:

    def test_reset_method_exists(self):
        assert hasattr(ReviewTrigger, 'reset')

    def test_reset_is_async(self):
        import inspect
        assert inspect.iscoroutinefunction(ReviewTrigger.reset)


# =============================================================================
# Behavioral Tests - on_build_executed
# =============================================================================

class TestOnBuildExecutedBehavior:
    """Behavioral tests for REQ-6: on_build_executed triggers reviews."""

    def _create_mock_file_tracker(self, pending_count=0):
        tracker = MagicMock()
        tracker.pending_count = pending_count
        return tracker

    def _create_mock_logger(self):
        logger = MagicMock()
        logger.log_event = MagicMock()
        return logger

    def _create_trigger(self, pending_count=0):
        return ReviewTrigger(
            file_tracker=self._create_mock_file_tracker(pending_count),
            logger=self._create_mock_logger(),
            on_trigger=MagicMock()
        )

    def test_on_build_executed_triggers_when_pending_changes_exist(self):
        """REQ-2: Only trigger review if there are pending file changes."""
        # given
        callback = MagicMock()
        trigger = ReviewTrigger(
            file_tracker=self._create_mock_file_tracker(pending_count=3),
            logger=self._create_mock_logger(),
            on_trigger=callback
        )

        # when
        result = run_async(trigger.on_build_executed("pytest"))

        # then
        assert result is True
        callback.assert_called_once()
        event = callback.call_args[0][0]
        assert isinstance(event, TriggerEvent)
        assert event.reason == TriggerReason.BUILD_EXECUTION
        assert event.file_count == 3

    def test_on_build_executed_skips_when_no_pending_changes(self):
        """EDGE-2: Build command with no pending file changes: Skip review."""
        # given
        callback = MagicMock()
        trigger = ReviewTrigger(
            file_tracker=self._create_mock_file_tracker(pending_count=0),
            logger=self._create_mock_logger(),
            on_trigger=callback
        )

        # when
        result = run_async(trigger.on_build_executed("pytest"))

        # then
        assert result is False
        callback.assert_not_called()

    def test_on_build_executed_returns_true_when_triggered(self):
        """on_build_executed returns True when review was triggered."""
        trigger = ReviewTrigger(
            file_tracker=self._create_mock_file_tracker(pending_count=5),
            logger=self._create_mock_logger(),
            on_trigger=MagicMock()
        )
        result = run_async(trigger.on_build_executed("make build"))
        assert result is True

    def test_on_build_executed_returns_false_when_skipped(self):
        """on_build_executed returns False when review was skipped."""
        trigger = ReviewTrigger(
            file_tracker=self._create_mock_file_tracker(pending_count=0),
            logger=self._create_mock_logger(),
            on_trigger=MagicMock()
        )
        result = run_async(trigger.on_build_executed("make build"))
        assert result is False


class TestTriggerEventFromBuildExecution:
    """Test TriggerEvent is properly created for build execution."""

    def _create_mock_file_tracker(self, pending_count=0):
        tracker = MagicMock()
        tracker.pending_count = pending_count
        return tracker

    def _create_mock_logger(self):
        logger = MagicMock()
        logger.log_event = MagicMock()
        return logger

    def test_trigger_event_has_build_execution_reason(self):
        """REQ-5: TriggerEvent should have BUILD_EXECUTION reason."""
        # given
        callback = MagicMock()
        trigger = ReviewTrigger(
            file_tracker=self._create_mock_file_tracker(pending_count=2),
            logger=self._create_mock_logger(),
            on_trigger=callback
        )

        # when
        run_async(trigger.on_build_executed("npm test"))

        # then
        callback.assert_called_once()
        event = callback.call_args[0][0]
        assert event.reason == TriggerReason.BUILD_EXECUTION

    def test_trigger_event_includes_file_count_from_tracker(self):
        """TriggerEvent file_count should match file_tracker.pending_count."""
        # given
        callback = MagicMock()
        trigger = ReviewTrigger(
            file_tracker=self._create_mock_file_tracker(pending_count=7),
            logger=self._create_mock_logger(),
            on_trigger=callback
        )

        # when
        run_async(trigger.on_build_executed("cargo build"))

        # then
        event = callback.call_args[0][0]
        assert event.file_count == 7


class TestTriggerResetBehavior:
    """Test reset clears trigger state."""

    def _create_mock_file_tracker(self, pending_count=0):
        tracker = MagicMock()
        tracker.pending_count = pending_count
        return tracker

    def _create_mock_logger(self):
        logger = MagicMock()
        logger.log_event = MagicMock()
        return logger

    def test_reset_can_be_called_after_trigger(self):
        """reset() should work after a trigger event."""
        trigger = ReviewTrigger(
            file_tracker=self._create_mock_file_tracker(pending_count=1),
            logger=self._create_mock_logger(),
            on_trigger=MagicMock()
        )
        run_async(trigger.on_build_executed("pytest"))
        # reset should not raise
        run_async(trigger.reset())

    def test_reset_allows_subsequent_triggers(self):
        """After reset(), subsequent build executions can trigger again."""
        callback = MagicMock()
        tracker = self._create_mock_file_tracker(pending_count=1)
        trigger = ReviewTrigger(
            file_tracker=tracker,
            logger=self._create_mock_logger(),
            on_trigger=callback
        )

        # First trigger
        run_async(trigger.on_build_executed("pytest"))
        assert callback.call_count == 1

        # Reset
        run_async(trigger.reset())

        # Second trigger (with pending changes still present)
        run_async(trigger.on_build_executed("pytest"))
        assert callback.call_count == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
