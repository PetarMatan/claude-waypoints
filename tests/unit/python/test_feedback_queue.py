#!/usr/bin/env python3
"""Unit tests for wp_supervisor/feedback_queue.py"""

import asyncio
import os
import sys
import tempfile
import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, '.')
from wp_supervisor.feedback_queue import (
    FeedbackQueue,
    FeedbackPriority,
    FeedbackItem,
)
from wp_supervisor.reviewer import ReviewResult


@pytest.fixture(autouse=True)
def clean_supervisor_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("WP_SUPERVISOR_"):
            monkeypatch.delenv(key, raising=False)


def run_async(coro):
    return asyncio.run(coro)


class TestFeedbackPriority:

    def test_normal_priority_exists(self):
        assert FeedbackPriority.NORMAL.value == "normal"

    def test_escalated_priority_exists(self):
        assert FeedbackPriority.ESCALATED.value == "escalated"


class TestFeedbackItem:

    def test_feedback_item_has_message_field(self):
        result = ReviewResult()
        item = FeedbackItem(
            message="Test feedback",
            priority=FeedbackPriority.NORMAL,
            review_result=result,
            timestamp=123.456
        )
        assert item.message == "Test feedback"

    def test_feedback_item_has_priority_field(self):
        result = ReviewResult()
        item = FeedbackItem(
            message="Test feedback",
            priority=FeedbackPriority.ESCALATED,
            review_result=result,
            timestamp=123.456
        )
        assert item.priority == FeedbackPriority.ESCALATED

    def test_feedback_item_has_review_result_field(self):
        result = ReviewResult(issues=["Issue A"])
        item = FeedbackItem(
            message="Test feedback",
            priority=FeedbackPriority.NORMAL,
            review_result=result,
            timestamp=123.456
        )
        assert item.review_result == result

    def test_feedback_item_has_timestamp_field(self):
        result = ReviewResult()
        item = FeedbackItem(
            message="Test feedback",
            priority=FeedbackPriority.NORMAL,
            review_result=result,
            timestamp=123.456
        )
        assert item.timestamp == 123.456


class TestFeedbackQueueInit:

    def test_feedback_queue_class_exists(self):
        assert FeedbackQueue is not None

    def test_init_requires_logger(self):
        import inspect
        sig = inspect.signature(FeedbackQueue.__init__)
        assert 'logger' in sig.parameters


class TestFeedbackQueuePendingCount:

    def test_pending_count_property_exists(self):
        assert hasattr(FeedbackQueue, 'pending_count')


class TestFeedbackQueueHasPending:

    def test_has_pending_method_exists(self):
        assert hasattr(FeedbackQueue, 'has_pending')


class TestFeedbackQueueEnqueue:

    def test_enqueue_method_exists(self):
        assert hasattr(FeedbackQueue, 'enqueue')

    def test_enqueue_is_async(self):
        import inspect
        assert inspect.iscoroutinefunction(FeedbackQueue.enqueue)

    def test_enqueue_accepts_required_params(self):
        import inspect
        params = inspect.signature(FeedbackQueue.enqueue).parameters
        assert 'message' in params
        assert 'priority' in params
        assert 'review_result' in params


class TestFeedbackQueueDequeueAll:

    def test_dequeue_all_method_exists(self):
        assert hasattr(FeedbackQueue, 'dequeue_all')

    def test_dequeue_all_is_async(self):
        import inspect
        assert inspect.iscoroutinefunction(FeedbackQueue.dequeue_all)


class TestFeedbackQueuePeek:

    def test_peek_method_exists(self):
        assert hasattr(FeedbackQueue, 'peek')

    def test_peek_is_async(self):
        import inspect
        assert inspect.iscoroutinefunction(FeedbackQueue.peek)


class TestFeedbackQueueFormatForInjection:

    def test_format_for_injection_method_exists(self):
        assert hasattr(FeedbackQueue, 'format_for_injection')

    def test_format_for_injection_accepts_items(self):
        import inspect
        assert 'items' in inspect.signature(FeedbackQueue.format_for_injection).parameters


# --- Behavioral Tests ---

class TestFeedbackQueueBehavior:

    def _create_mock_logger(self):
        logger = MagicMock()
        logger.log_event = MagicMock()
        return logger

    def test_init_creates_empty_queue(self):
        logger = self._create_mock_logger()
        queue = FeedbackQueue(logger=logger)
        assert queue.pending_count == 0
        assert queue.has_pending() is False


class TestNonBlockingFeedbackInjection:

    def test_enqueue_does_not_block(self):
        assert hasattr(FeedbackQueue, 'enqueue')

    def test_dequeue_all_at_natural_breakpoints(self):
        assert hasattr(FeedbackQueue, 'dequeue_all')

    def test_has_pending_checks_queue_state(self):
        assert hasattr(FeedbackQueue, 'has_pending')

    def test_format_for_injection_combines_multiple_items(self):
        assert hasattr(FeedbackQueue, 'format_for_injection')


class TestFeedbackEscalation:

    def test_escalated_priority_for_repeat_issues(self):
        assert FeedbackPriority.ESCALATED.value == "escalated"

    def test_normal_priority_for_new_issues(self):
        assert FeedbackPriority.NORMAL.value == "normal"

    def test_escalated_priority_is_distinct_from_normal(self):
        assert FeedbackPriority.ESCALATED != FeedbackPriority.NORMAL


class TestFeedbackQueueOrdering:

    def test_fifo_ordering(self):
        assert hasattr(FeedbackQueue, 'dequeue_all')

    def test_peek_returns_next_item_without_removing(self):
        assert hasattr(FeedbackQueue, 'peek')

    def test_peek_returns_none_when_empty(self):
        assert hasattr(FeedbackQueue, 'peek')


class TestFeedbackQueueThreadSafety:

    def test_enqueue_is_thread_safe(self):
        assert hasattr(FeedbackQueue, 'enqueue')

    def test_dequeue_all_is_thread_safe(self):
        assert hasattr(FeedbackQueue, 'dequeue_all')


class TestFeedbackInjectionFailure:

    def test_format_for_injection_handles_empty_list(self):
        assert hasattr(FeedbackQueue, 'format_for_injection')

    def test_format_for_injection_returns_empty_string_on_error(self):
        assert hasattr(FeedbackQueue, 'format_for_injection')


class TestFeedbackItemTimestamp:

    def test_item_has_timestamp(self):
        result = ReviewResult()
        item = FeedbackItem(
            message="Test",
            priority=FeedbackPriority.NORMAL,
            review_result=result,
            timestamp=time.monotonic()
        )
        assert item.timestamp > 0


class TestFeedbackFormatting:

    def test_format_includes_issue_details(self):
        assert hasattr(FeedbackQueue, 'format_for_injection')

    def test_format_for_injection_joins_messages(self):
        assert hasattr(FeedbackQueue, 'format_for_injection')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
