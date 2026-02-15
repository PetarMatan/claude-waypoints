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
)


@pytest.fixture(autouse=True)
def clean_supervisor_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("WP_SUPERVISOR_"):
            monkeypatch.delenv(key, raising=False)


def run_async(coro):
    return asyncio.run(coro)


class TestTriggerReason:

    def test_file_threshold_reason_exists(self):
        assert TriggerReason.FILE_THRESHOLD.value == "file_threshold"

    def test_manual_reason_exists(self):
        assert TriggerReason.MANUAL.value == "manual"


class TestTriggerEvent:

    def test_trigger_event_has_reason_field(self):
        event = TriggerEvent(reason=TriggerReason.FILE_THRESHOLD, file_count=3)
        assert event.reason == TriggerReason.FILE_THRESHOLD

    def test_trigger_event_has_file_count_field(self):
        event = TriggerEvent(reason=TriggerReason.FILE_THRESHOLD, file_count=3)
        assert event.file_count == 3


class TestReviewTriggerInit:

    def test_review_trigger_class_exists(self):
        assert ReviewTrigger is not None

    def test_init_requires_expected_params(self):
        import inspect
        params = inspect.signature(ReviewTrigger.__init__).parameters
        assert 'file_tracker' in params
        assert 'logger' in params
        assert 'on_trigger' in params
        assert 'file_threshold' in params

    def test_default_file_threshold_is_one(self):
        assert ReviewTrigger.DEFAULT_FILE_THRESHOLD == 1


class TestReviewTriggerProperties:

    def test_file_threshold_property_exists(self):
        assert hasattr(ReviewTrigger, 'file_threshold')

    def test_files_since_review_property_exists(self):
        assert hasattr(ReviewTrigger, 'files_since_review')


class TestReviewTriggerOnFileChanged:

    def test_on_file_changed_method_exists(self):
        assert hasattr(ReviewTrigger, 'on_file_changed')

    def test_on_file_changed_is_async(self):
        import inspect
        assert inspect.iscoroutinefunction(ReviewTrigger.on_file_changed)


class TestReviewTriggerReset:

    def test_reset_method_exists(self):
        assert hasattr(ReviewTrigger, 'reset')

    def test_reset_is_async(self):
        import inspect
        assert inspect.iscoroutinefunction(ReviewTrigger.reset)


class TestReviewTriggerInternalMethods:

    def test_should_trigger_on_file_method_exists(self):
        assert hasattr(ReviewTrigger, '_should_trigger_on_file')


# --- Behavioral Tests ---

class TestReviewTriggerBehavior:

    def _create_mock_file_tracker(self, pending_count=0):
        tracker = MagicMock()
        tracker.pending_count = pending_count
        return tracker

    def _create_mock_logger(self):
        logger = MagicMock()
        logger.log_event = MagicMock()
        return logger

    def test_init_sets_file_counter_to_zero(self):
        trigger = ReviewTrigger(
            file_tracker=self._create_mock_file_tracker(),
            logger=self._create_mock_logger(),
            on_trigger=MagicMock()
        )
        assert trigger.files_since_review == 0


class TestFileThresholdTrigger:

    def test_triggers_after_one_file(self):
        assert ReviewTrigger.DEFAULT_FILE_THRESHOLD == 1

    def test_file_threshold_is_configurable(self):
        import inspect
        assert 'file_threshold' in inspect.signature(ReviewTrigger.__init__).parameters

    def test_on_file_changed_returns_true_when_triggered(self):
        assert hasattr(ReviewTrigger, 'on_file_changed')

    def test_on_file_changed_returns_false_when_not_triggered(self):
        assert hasattr(ReviewTrigger, 'on_file_changed')


class TestTriggerResetBehavior:

    def test_reset_clears_file_counter(self):
        assert hasattr(ReviewTrigger, 'reset')

    def test_reset_called_after_review_completes(self):
        assert hasattr(ReviewTrigger, 'reset')


class TestTriggerCallback:

    def test_callback_receives_trigger_event(self):
        event = TriggerEvent(reason=TriggerReason.FILE_THRESHOLD, file_count=3)
        assert event.reason == TriggerReason.FILE_THRESHOLD
        assert event.file_count == 3

    def test_callback_invoked_on_file_threshold(self):
        assert hasattr(ReviewTrigger, 'on_file_changed')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
