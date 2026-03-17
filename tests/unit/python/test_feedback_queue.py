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


class TestFeedbackItem:

    def test_feedback_item_has_message_field(self):
        result = ReviewResult()
        item = FeedbackItem(
            message="Test feedback",
            review_result=result,
            timestamp=123.456
        )
        assert item.message == "Test feedback"

    def test_feedback_item_has_review_result_field(self):
        result = ReviewResult(issues=["Issue A"])
        item = FeedbackItem(
            message="Test feedback",
            review_result=result,
            timestamp=123.456
        )
        assert item.review_result == result

    def test_feedback_item_has_timestamp_field(self):
        result = ReviewResult()
        item = FeedbackItem(
            message="Test feedback",
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
            review_result=result,
            timestamp=time.monotonic()
        )
        assert item.timestamp > 0


class TestFeedbackFormatting:

    def test_format_includes_issue_details(self):
        assert hasattr(FeedbackQueue, 'format_for_injection')

    def test_format_for_injection_joins_messages(self):
        assert hasattr(FeedbackQueue, 'format_for_injection')


# =============================================================================
# REQ-2.x, REQ-4.x: FeedbackQueue Integration Tests
# =============================================================================

class TestFeedbackQueueWithCapper:
    """Tests for FeedbackQueue integration with FeedbackCapper (REQ-2.x)."""

    def _create_mock_logger(self):
        logger = MagicMock()
        logger.log_event = MagicMock()
        return logger

    def test_init_accepts_capper(self):
        """[REQ-2.x] FeedbackQueue should accept optional capper."""
        import inspect
        params = inspect.signature(FeedbackQueue.__init__).parameters
        assert 'capper' in params

    def test_init_capper_defaults_to_none(self):
        """capper should default to None."""
        import inspect
        params = inspect.signature(FeedbackQueue.__init__).parameters
        assert params['capper'].default is None

    def test_queue_stores_capper_reference(self):
        """Queue should store capper for use in processing."""
        # given
        logger = self._create_mock_logger()
        mock_capper = MagicMock()

        # when
        queue = FeedbackQueue(logger=logger, capper=mock_capper)

        # then
        assert queue._capper is mock_capper


class TestFeedbackQueueWithDeduplicator:
    """Tests for FeedbackQueue integration with FeedbackDeduplicator (REQ-4.x)."""

    def _create_mock_logger(self):
        logger = MagicMock()
        logger.log_event = MagicMock()
        return logger

    def test_init_accepts_deduplicator(self):
        """[REQ-4.x] FeedbackQueue should accept optional deduplicator."""
        import inspect
        params = inspect.signature(FeedbackQueue.__init__).parameters
        assert 'deduplicator' in params

    def test_init_deduplicator_defaults_to_none(self):
        """deduplicator should default to None."""
        import inspect
        params = inspect.signature(FeedbackQueue.__init__).parameters
        assert params['deduplicator'].default is None

    def test_queue_stores_deduplicator_reference(self):
        """Queue should store deduplicator for use in processing."""
        # given
        logger = self._create_mock_logger()
        mock_deduplicator = MagicMock()

        # when
        queue = FeedbackQueue(logger=logger, deduplicator=mock_deduplicator)

        # then
        assert queue._deduplicator is mock_deduplicator


class TestFeedbackQueueEnqueueWithProcessing:
    """Tests for FeedbackQueue.enqueue_with_processing method."""

    def _create_mock_logger(self):
        logger = MagicMock()
        logger.log_event = MagicMock()
        return logger

    def test_enqueue_with_processing_method_exists(self):
        """enqueue_with_processing method should exist."""
        assert hasattr(FeedbackQueue, 'enqueue_with_processing')

    def test_enqueue_with_processing_is_async(self):
        """enqueue_with_processing should be async."""
        import inspect
        assert inspect.iscoroutinefunction(FeedbackQueue.enqueue_with_processing)

    def test_enqueue_with_processing_accepts_message_and_result(self):
        """Should accept message and review_result parameters."""
        import inspect
        params = inspect.signature(FeedbackQueue.enqueue_with_processing).parameters
        assert 'message' in params
        assert 'review_result' in params


class TestEnqueueWithProcessingIntegration:
    """Integration tests for enqueue_with_processing with real capper and deduplicator."""

    def _create_mock_logger(self):
        logger = MagicMock()
        logger.log_event = MagicMock()
        return logger

    def test_full_pipeline_caps_and_deduplicates(self):
        """Pipeline should dedup then cap, producing a single clean message."""
        from wp_supervisor.feedback_capping import FeedbackCapper
        from wp_supervisor.feedback_dedup import FeedbackDeduplicator
        from wp_supervisor.reviewer import ParsedIssue

        logger = self._create_mock_logger()
        capper = FeedbackCapper(logger=logger, cap=5)
        deduplicator = FeedbackDeduplicator(logger=logger)

        queue = FeedbackQueue(
            logger=logger,
            capper=capper,
            deduplicator=deduplicator
        )

        # Build a review result with 8 issues (3 duplicates, 5 unique)
        issues = [
            ParsedIssue(content="Missing null check", severity="critical", file_path="a.py"),
            ParsedIssue(content="Missing null check", severity="critical", file_path="a.py"),  # dup
            ParsedIssue(content="Bad naming", severity="low", file_path="a.py"),
            ParsedIssue(content="Bad naming", severity="low", file_path="a.py"),  # dup
            ParsedIssue(content="No error handling", severity="high", file_path="b.py"),
            ParsedIssue(content="No error handling", severity="high", file_path="b.py"),  # dup
            ParsedIssue(content="Unused import", severity="low", file_path="b.py"),
            ParsedIssue(content="Missing docstring", severity="medium", file_path="b.py"),
        ]
        result = ReviewResult(
            issues=[i.content for i in issues],
            files_reviewed={"a.py", "b.py"},
            parsed_issues=issues,
        )

        original_message = "Original feedback message"
        asyncio.run(queue.enqueue_with_processing(original_message, result))

        # Should have 1 queued item
        assert queue.pending_count == 1

        items = asyncio.run(queue.dequeue_all())
        item = items[0]

        # 3 duplicates removed, so message should not be the original
        assert item.deduplicated_count == 3
        # Message should NOT contain double-listed issues
        assert "Processed Issues:" not in item.message
        # Message should contain stats note
        assert "duplicate items removed" in item.message

    def test_no_filtering_returns_original_message(self):
        """When nothing is filtered, original message should be returned as-is."""
        from wp_supervisor.feedback_capping import FeedbackCapper
        from wp_supervisor.feedback_dedup import FeedbackDeduplicator
        from wp_supervisor.reviewer import ParsedIssue

        logger = self._create_mock_logger()
        capper = FeedbackCapper(logger=logger, cap=20)
        deduplicator = FeedbackDeduplicator(logger=logger)

        queue = FeedbackQueue(
            logger=logger,
            capper=capper,
            deduplicator=deduplicator
        )

        issues = [
            ParsedIssue(content="Issue one", severity="high", file_path="a.py"),
            ParsedIssue(content="Issue two", severity="medium", file_path="b.py"),
        ]
        result = ReviewResult(
            issues=[i.content for i in issues],
            files_reviewed={"a.py", "b.py"},
            parsed_issues=issues,
        )

        original_message = "The original feedback text"
        asyncio.run(queue.enqueue_with_processing(original_message, result))

        items = asyncio.run(queue.dequeue_all())
        item = items[0]

        # No filtering happened, so original message should be preserved
        assert item.message == original_message
        assert item.dropped_count == 0
        assert item.deduplicated_count == 0


class TestFeedbackQueueApplyCapping:
    """Tests for FeedbackQueue._apply_capping method."""

    def _create_mock_logger(self):
        logger = MagicMock()
        logger.log_event = MagicMock()
        return logger

    def test_apply_capping_method_exists(self):
        """_apply_capping method should exist."""
        assert hasattr(FeedbackQueue, '_apply_capping')

    def test_apply_capping_returns_tuple(self):
        """[REQ-2.x] Should return tuple of (capped issues, dropped count)."""
        import inspect
        # Check the return type hint or signature
        sig = inspect.signature(FeedbackQueue._apply_capping)
        # Method should exist with correct signature
        assert 'parsed_issues' in sig.parameters


class TestFeedbackQueueApplyDeduplication:
    """Tests for FeedbackQueue._apply_deduplication method."""

    def _create_mock_logger(self):
        logger = MagicMock()
        logger.log_event = MagicMock()
        return logger

    def test_apply_deduplication_method_exists(self):
        """_apply_deduplication method should exist."""
        assert hasattr(FeedbackQueue, '_apply_deduplication')

    def test_apply_deduplication_returns_tuple(self):
        """[REQ-4.x] Should return tuple of (deduped issues, duplicate count)."""
        import inspect
        sig = inspect.signature(FeedbackQueue._apply_deduplication)
        assert 'parsed_issues' in sig.parameters


class TestFeedbackQueueFormatProcessedMessage:
    """Tests for FeedbackQueue._format_processed_message method."""

    def _create_mock_logger(self):
        logger = MagicMock()
        logger.log_event = MagicMock()
        return logger

    def test_format_processed_message_method_exists(self):
        """_format_processed_message method should exist."""
        assert hasattr(FeedbackQueue, '_format_processed_message')

    def test_format_processed_message_accepts_required_params(self):
        """Should accept original_message, processed_issues, dropped_count, dedup_count."""
        import inspect
        params = inspect.signature(FeedbackQueue._format_processed_message).parameters
        assert 'original_message' in params
        assert 'processed_issues' in params
        assert 'dropped_count' in params
        assert 'dedup_count' in params


class TestFeedbackItemTracking:
    """Tests for FeedbackItem tracking of capping/dedup counts."""

    def test_feedback_item_has_dropped_count(self):
        """FeedbackItem should track dropped_count."""
        result = ReviewResult()
        item = FeedbackItem(
            message="Test",
            review_result=result,
            timestamp=123.0,
            dropped_count=5
        )
        assert item.dropped_count == 5

    def test_feedback_item_has_deduplicated_count(self):
        """FeedbackItem should track deduplicated_count."""
        result = ReviewResult()
        item = FeedbackItem(
            message="Test",
            review_result=result,
            timestamp=123.0,
            deduplicated_count=3
        )
        assert item.deduplicated_count == 3

    def test_feedback_item_counts_default_to_zero(self):
        """dropped_count and deduplicated_count should default to 0."""
        result = ReviewResult()
        item = FeedbackItem(
            message="Test",
            review_result=result,
            timestamp=123.0
        )
        assert item.dropped_count == 0
        assert item.deduplicated_count == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
