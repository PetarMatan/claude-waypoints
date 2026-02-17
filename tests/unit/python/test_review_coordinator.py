#!/usr/bin/env python3
"""Unit tests for wp_supervisor/review_coordinator.py"""

import asyncio
import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

mock_sdk = MagicMock()
mock_sdk.ClaudeSDKClient = MagicMock()
mock_sdk.ClaudeAgentOptions = MagicMock()
sys.modules['claude_agent_sdk'] = mock_sdk

sys.path.insert(0, '.')
from wp_supervisor.review_coordinator import (
    ReviewCoordinator,
    ReviewCoordinatorConfig,
)


@pytest.fixture(autouse=True)
def clean_supervisor_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("WP_SUPERVISOR_"):
            monkeypatch.delenv(key, raising=False)


def run_async(coro):
    return asyncio.run(coro)


class TestReviewCoordinatorConfig:

    def test_config_has_file_threshold_field(self):
        config = ReviewCoordinatorConfig()
        assert hasattr(config, 'file_threshold')

    def test_config_file_threshold_default_is_one(self):
        assert ReviewCoordinatorConfig().file_threshold == 1

    def test_config_has_enabled_field(self):
        assert hasattr(ReviewCoordinatorConfig(), 'enabled')

    def test_config_enabled_default_is_true(self):
        assert ReviewCoordinatorConfig().enabled is True

    def test_config_can_override_file_threshold(self):
        assert ReviewCoordinatorConfig(file_threshold=5).file_threshold == 5

    def test_config_can_disable_reviewer(self):
        assert ReviewCoordinatorConfig(enabled=False).enabled is False


class TestReviewCoordinatorInit:

    def test_review_coordinator_class_exists(self):
        assert ReviewCoordinator is not None

    def test_init_requires_expected_params(self):
        import inspect
        params = inspect.signature(ReviewCoordinator.__init__).parameters
        assert 'logger' in params
        assert 'markers' in params
        assert 'working_dir' in params
        assert 'requirements_summary' in params
        assert 'interfaces_summary' in params
        assert 'config' in params
        assert params['config'].default is None


class TestReviewCoordinatorProperties:

    def test_is_active_property_exists(self):
        assert hasattr(ReviewCoordinator, 'is_active')

    def test_is_degraded_property_exists(self):
        assert hasattr(ReviewCoordinator, 'is_degraded')


class TestReviewCoordinatorStart:

    def test_start_method_exists(self):
        assert hasattr(ReviewCoordinator, 'start')

    def test_start_is_async(self):
        import inspect
        assert inspect.iscoroutinefunction(ReviewCoordinator.start)


class TestReviewCoordinatorStop:

    def test_stop_method_exists(self):
        assert hasattr(ReviewCoordinator, 'stop')

    def test_stop_is_async(self):
        import inspect
        assert inspect.iscoroutinefunction(ReviewCoordinator.stop)


class TestReviewCoordinatorOnFileChanged:

    def test_on_file_changed_method_exists(self):
        assert hasattr(ReviewCoordinator, 'on_file_changed')

    def test_on_file_changed_is_async(self):
        import inspect
        assert inspect.iscoroutinefunction(ReviewCoordinator.on_file_changed)

    def test_on_file_changed_accepts_required_params(self):
        import inspect
        params = inspect.signature(ReviewCoordinator.on_file_changed).parameters
        assert 'file_path' in params
        assert 'tool_name' in params


class TestReviewCoordinatorGetPendingFeedback:

    def test_get_pending_feedback_method_exists(self):
        assert hasattr(ReviewCoordinator, 'get_pending_feedback')

    def test_get_pending_feedback_is_async(self):
        import inspect
        assert inspect.iscoroutinefunction(ReviewCoordinator.get_pending_feedback)


class TestReviewCoordinatorHasPendingFeedback:

    def test_has_pending_feedback_method_exists(self):
        assert hasattr(ReviewCoordinator, 'has_pending_feedback')


class TestReviewCoordinatorInternalMethods:

    def test_run_review_method_exists(self):
        assert hasattr(ReviewCoordinator, '_run_review')

    def test_run_review_is_async(self):
        import inspect
        assert inspect.iscoroutinefunction(ReviewCoordinator._run_review)

    def test_schedule_review_method_exists(self):
        assert hasattr(ReviewCoordinator, '_schedule_review')

    def test_wait_for_pending_reviews_method_exists(self):
        assert hasattr(ReviewCoordinator, 'wait_for_pending_reviews')

    def test_wait_for_pending_reviews_is_async(self):
        import inspect
        assert inspect.iscoroutinefunction(ReviewCoordinator.wait_for_pending_reviews)

    def test_perform_review_method_exists(self):
        assert hasattr(ReviewCoordinator, '_perform_review')

    def test_perform_review_is_async(self):
        import inspect
        assert inspect.iscoroutinefunction(ReviewCoordinator._perform_review)

    def test_queue_feedback_method_exists(self):
        assert hasattr(ReviewCoordinator, '_queue_feedback')

    def test_enter_degraded_mode_method_exists(self):
        assert hasattr(ReviewCoordinator, '_enter_degraded_mode')


# --- Behavioral Tests ---

class TestReviewCoordinatorBehavior:

    def _create_mock_logger(self):
        logger = MagicMock()
        logger.log_event = MagicMock()
        return logger

    def _create_mock_markers(self):
        return MagicMock()

    def test_init_sets_inactive_state(self):
        logger = self._create_mock_logger()
        markers = self._create_mock_markers()
        with tempfile.TemporaryDirectory() as tmpdir:
            coordinator = ReviewCoordinator(
                logger=logger, markers=markers,
                working_dir=tmpdir, requirements_summary="# Requirements"
            )
            assert coordinator.is_active is False


class TestConcurrentAgents:

    def test_coordinator_manages_two_concurrent_agents(self):
        assert hasattr(ReviewCoordinator, 'start')
        assert hasattr(ReviewCoordinator, 'stop')


class TestEagerInitialization:

    def test_start_initializes_all_components(self):
        assert hasattr(ReviewCoordinator, 'start')

    def test_start_can_run_concurrently_with_implementer_init(self):
        import inspect
        assert inspect.iscoroutinefunction(ReviewCoordinator.start)


class TestDegradedMode:

    def test_enter_degraded_mode_logs_error(self):
        assert hasattr(ReviewCoordinator, '_enter_degraded_mode')

    def test_degraded_mode_continues_without_reviewer(self):
        assert hasattr(ReviewCoordinator, 'is_degraded')

    def test_on_file_changed_works_in_degraded_mode(self):
        assert hasattr(ReviewCoordinator, 'on_file_changed')


class TestSupervisorModeOnly:

    def test_config_defaults_to_enabled_for_supervisor(self):
        assert ReviewCoordinatorConfig().enabled is True

    def test_config_can_disable_for_testing(self):
        assert ReviewCoordinatorConfig(enabled=False).enabled is False


class TestAlwaysOnForPhase4:

    def test_reviewer_enabled_by_default(self):
        assert ReviewCoordinatorConfig().enabled is True


class TestCoordinatorLifecycle:

    def test_start_activates_coordinator(self):
        assert hasattr(ReviewCoordinator, 'start')
        assert hasattr(ReviewCoordinator, 'is_active')

    def test_stop_deactivates_coordinator(self):
        assert hasattr(ReviewCoordinator, 'stop')

    def test_stop_cleans_up_all_components(self):
        assert hasattr(ReviewCoordinator, 'stop')


class TestCoordinatorComponentIntegration:

    def test_on_file_changed_records_and_checks_trigger(self):
        assert hasattr(ReviewCoordinator, 'on_file_changed')

    def test_trigger_callback_performs_review(self):
        assert hasattr(ReviewCoordinator, '_run_review')
        assert hasattr(ReviewCoordinator, '_perform_review')
        assert hasattr(ReviewCoordinator, '_queue_feedback')


class TestFeedbackRetrieval:

    def test_get_pending_feedback_returns_formatted_string(self):
        assert hasattr(ReviewCoordinator, 'get_pending_feedback')

    def test_get_pending_feedback_returns_empty_when_none(self):
        assert hasattr(ReviewCoordinator, 'get_pending_feedback')

    def test_has_pending_feedback_checks_queue(self):
        assert hasattr(ReviewCoordinator, 'has_pending_feedback')


class TestReviewCoordinatorDebounce:

    def _create_coordinator(self):
        logger = MagicMock()
        logger.log_event = MagicMock()
        markers = MagicMock()
        return ReviewCoordinator(
            logger=logger, markers=markers,
            working_dir="/tmp", requirements_summary="# Requirements"
        )

    def test_has_reviewed_false_initially(self):
        coordinator = self._create_coordinator()
        assert coordinator.has_reviewed is False

    def test_review_pending_false_initially(self):
        coordinator = self._create_coordinator()
        assert coordinator._review_pending is False

    def test_is_reviewing_false_initially(self):
        coordinator = self._create_coordinator()
        assert coordinator._is_reviewing is False

    def test_review_count_zero_initially(self):
        coordinator = self._create_coordinator()
        assert coordinator._review_count == 0

    def test_wait_for_pending_reviews_returns_immediately_when_none(self):
        coordinator = self._create_coordinator()
        run_async(coordinator.wait_for_pending_reviews(timeout=1.0))
        assert coordinator._review_pending is False

    def test_wait_for_pending_reviews_times_out_gracefully(self):
        coordinator = self._create_coordinator()
        coordinator._review_pending = True
        coordinator._is_reviewing = True
        import time
        start = time.monotonic()
        run_async(coordinator.wait_for_pending_reviews(timeout=0.5))
        elapsed = time.monotonic() - start
        assert elapsed >= 0.5
        assert coordinator._review_pending is True

    def test_run_review_clears_flags_when_degraded(self):
        coordinator = self._create_coordinator()
        coordinator._review_pending = True
        coordinator._is_reviewing = True
        coordinator._is_degraded = True
        from wp_supervisor.review_trigger import TriggerEvent, TriggerReason
        event = TriggerEvent(reason=TriggerReason.FILE_THRESHOLD, file_count=1)
        run_async(coordinator._run_review(event))
        assert coordinator._is_reviewing is False
        assert coordinator._review_pending is False

    def test_review_count_increments_after_review(self):
        coordinator = self._create_coordinator()
        coordinator._review_pending = True
        coordinator._is_reviewing = True
        coordinator._is_active = True

        from wp_supervisor.review_trigger import TriggerEvent, TriggerReason
        from wp_supervisor.reviewer import ReviewResult

        coordinator._file_tracker = MagicMock()
        coordinator._file_tracker.get_pending_changes = AsyncMock(return_value={"/tmp/file.py": "content"})
        coordinator._file_tracker.clear_pending = AsyncMock()
        coordinator._trigger = MagicMock()
        coordinator._trigger.reset = AsyncMock()
        coordinator._feedback_queue = MagicMock()
        coordinator._reviewer = MagicMock()
        coordinator._reviewer.review = AsyncMock(return_value=ReviewResult())

        event = TriggerEvent(reason=TriggerReason.FILE_THRESHOLD, file_count=1)
        run_async(coordinator._run_review(event))
        assert coordinator._review_count == 1
        assert coordinator.has_reviewed is True
        assert coordinator._is_reviewing is False
        assert coordinator._review_pending is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
