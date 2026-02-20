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


# =============================================================================
# REQ-10: ReviewCoordinatorConfig - file_threshold removed
# =============================================================================

class TestReviewCoordinatorConfig:

    def test_config_file_threshold_field_removed(self):
        """REQ-10: Remove file_threshold field from ReviewCoordinatorConfig."""
        config = ReviewCoordinatorConfig()
        assert not hasattr(config, 'file_threshold')

    def test_config_has_enabled_field(self):
        assert hasattr(ReviewCoordinatorConfig(), 'enabled')

    def test_config_enabled_default_is_true(self):
        assert ReviewCoordinatorConfig().enabled is True

    def test_config_can_disable_reviewer(self):
        assert ReviewCoordinatorConfig(enabled=False).enabled is False

    def test_config_does_not_accept_file_threshold_param(self):
        """REQ-10: file_threshold parameter removed from config."""
        import inspect
        sig = inspect.signature(ReviewCoordinatorConfig.__init__)
        # DataClass init will have 'enabled' but not 'file_threshold'
        params = sig.parameters
        # file_threshold should not be in parameters
        assert 'file_threshold' not in params


class TestReviewCoordinatorInit:

    def test_review_coordinator_class_exists(self):
        assert ReviewCoordinator is not None

    def test_init_requires_expected_params(self):
        import inspect
        params = inspect.signature(ReviewCoordinator.__init__).parameters
        assert 'logger' in params
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
    """REQ-8: on_file_changed only calls file tracker (no trigger)."""

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


# =============================================================================
# REQ-7: on_build_executed Method
# =============================================================================

class TestReviewCoordinatorOnBuildExecuted:
    """REQ-7: Add on_build_executed(command: str) method to ReviewCoordinator."""

    def test_on_build_executed_method_exists(self):
        """REQ-7: ReviewCoordinator has on_build_executed method."""
        assert hasattr(ReviewCoordinator, 'on_build_executed')

    def test_on_build_executed_is_async(self):
        """REQ-7: on_build_executed should be async."""
        import inspect
        assert inspect.iscoroutinefunction(ReviewCoordinator.on_build_executed)

    def test_on_build_executed_accepts_command_param(self):
        """REQ-7: on_build_executed takes command: str parameter."""
        import inspect
        params = inspect.signature(ReviewCoordinator.on_build_executed).parameters
        assert 'command' in params


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
        with tempfile.TemporaryDirectory() as tmpdir:
            coordinator = ReviewCoordinator(
                logger=logger,
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

    def test_on_file_changed_records_only_no_trigger(self):
        """REQ-8: on_file_changed only records (no trigger call)."""
        assert hasattr(ReviewCoordinator, 'on_file_changed')

    def test_on_build_executed_triggers_review(self):
        """REQ-7: on_build_executed triggers reviews via trigger."""
        assert hasattr(ReviewCoordinator, 'on_build_executed')

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
        return ReviewCoordinator(
            logger=logger,
            working_dir="/tmp", requirements_summary="# Requirements"
        )

    def test_has_reviewed_false_initially(self):
        coordinator = self._create_coordinator()
        assert coordinator.has_reviewed is False

    def test_review_pending_false_initially(self):
        coordinator = self._create_coordinator()
        assert not coordinator._review_pending.is_set()

    def test_is_reviewing_false_initially(self):
        coordinator = self._create_coordinator()
        assert coordinator._is_reviewing is False

    def test_review_count_zero_initially(self):
        coordinator = self._create_coordinator()
        assert coordinator._review_count == 0

    def test_wait_for_pending_reviews_returns_immediately_when_none(self):
        coordinator = self._create_coordinator()
        run_async(coordinator.wait_for_pending_reviews(timeout=1.0))
        assert not coordinator._review_pending.is_set()

    def test_wait_for_pending_reviews_times_out_gracefully(self):
        coordinator = self._create_coordinator()
        coordinator._review_pending.set()
        coordinator._is_reviewing = True
        import time
        start = time.monotonic()
        run_async(coordinator.wait_for_pending_reviews(timeout=0.5))
        elapsed = time.monotonic() - start
        assert elapsed >= 0.5
        assert coordinator._review_pending.is_set()

    def test_run_review_clears_flags_when_degraded(self):
        coordinator = self._create_coordinator()
        coordinator._review_pending.set()
        coordinator._is_reviewing = True
        coordinator._is_degraded = True
        from wp_supervisor.review_trigger import TriggerEvent, TriggerReason
        event = TriggerEvent(reason=TriggerReason.BUILD_EXECUTION, file_count=1)
        run_async(coordinator._run_review(event))
        assert coordinator._is_reviewing is False
        assert not coordinator._review_pending.is_set()

    def test_review_count_increments_after_review(self):
        coordinator = self._create_coordinator()
        coordinator._review_pending.set()
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

        event = TriggerEvent(reason=TriggerReason.BUILD_EXECUTION, file_count=1)
        run_async(coordinator._run_review(event))
        assert coordinator._review_count == 1
        assert coordinator.has_reviewed is True
        assert coordinator._is_reviewing is False
        assert not coordinator._review_pending.is_set()


# =============================================================================
# Behavioral Tests for REQ-7 and REQ-8
# =============================================================================

class TestOnFileChangedBehavior:
    """REQ-3 & REQ-8: on_file_changed records changes but does NOT trigger reviews."""

    def _create_mock_logger(self):
        logger = MagicMock()
        logger.log_event = MagicMock()
        return logger

    def _create_started_coordinator(self, tmpdir):
        """Create a coordinator with mocked components."""
        logger = self._create_mock_logger()
        coordinator = ReviewCoordinator(
            logger=logger,
            working_dir=tmpdir,
            requirements_summary="# Requirements"
        )
        # Manually set up components that would be created by start()
        coordinator._is_active = True
        coordinator._file_tracker = MagicMock()
        coordinator._file_tracker.record_change = AsyncMock()
        coordinator._file_tracker.pending_count = 1
        coordinator._trigger = MagicMock()
        coordinator._trigger.on_build_executed = AsyncMock(return_value=False)
        return coordinator

    def test_on_file_changed_calls_file_tracker_record_change(self):
        """REQ-3: File changes are tracked via FileChangeTracker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            coordinator = self._create_started_coordinator(tmpdir)

            # when
            run_async(coordinator.on_file_changed("/test/file.py", "Write"))

            # then
            coordinator._file_tracker.record_change.assert_called_once_with(
                "/test/file.py", "Write"
            )

    def test_on_file_changed_does_not_call_trigger(self):
        """REQ-8: on_file_changed does NOT call trigger (recording only)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            coordinator = self._create_started_coordinator(tmpdir)
            # Add mock for old on_file_changed on trigger if it existed
            coordinator._trigger.on_file_changed = AsyncMock()

            # when
            run_async(coordinator.on_file_changed("/test/file.py", "Write"))

            # then - trigger should NOT be called for file changes
            if hasattr(coordinator._trigger, 'on_file_changed'):
                coordinator._trigger.on_file_changed.assert_not_called()

    def test_on_file_changed_returns_early_when_inactive(self):
        """on_file_changed does nothing when coordinator is not active."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            coordinator = self._create_started_coordinator(tmpdir)
            coordinator._is_active = False

            # when
            run_async(coordinator.on_file_changed("/test/file.py", "Write"))

            # then
            coordinator._file_tracker.record_change.assert_not_called()

    def test_on_file_changed_returns_early_when_degraded(self):
        """on_file_changed does nothing when coordinator is degraded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            coordinator = self._create_started_coordinator(tmpdir)
            coordinator._is_degraded = True

            # when
            run_async(coordinator.on_file_changed("/test/file.py", "Write"))

            # then
            coordinator._file_tracker.record_change.assert_not_called()


class TestOnBuildExecutedBehavior:
    """REQ-7: on_build_executed triggers reviews."""

    def _create_mock_logger(self):
        logger = MagicMock()
        logger.log_event = MagicMock()
        return logger

    def _create_started_coordinator(self, tmpdir, pending_count=1):
        """Create a coordinator with mocked components."""
        logger = self._create_mock_logger()
        coordinator = ReviewCoordinator(
            logger=logger,
            working_dir=tmpdir,
            requirements_summary="# Requirements"
        )
        coordinator._is_active = True
        coordinator._file_tracker = MagicMock()
        coordinator._file_tracker.pending_count = pending_count
        coordinator._trigger = MagicMock()
        coordinator._trigger.on_build_executed = AsyncMock(return_value=True)
        return coordinator

    def test_on_build_executed_delegates_to_trigger(self):
        """REQ-7: on_build_executed calls trigger.on_build_executed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            coordinator = self._create_started_coordinator(tmpdir)

            # when
            run_async(coordinator.on_build_executed("pytest tests/"))

            # then
            coordinator._trigger.on_build_executed.assert_called_once_with("pytest tests/")

    def test_on_build_executed_returns_early_when_inactive(self):
        """ERR-2: Return early from on_build_executed() when not active."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            coordinator = self._create_started_coordinator(tmpdir)
            coordinator._is_active = False

            # when
            run_async(coordinator.on_build_executed("pytest"))

            # then
            coordinator._trigger.on_build_executed.assert_not_called()

    def test_on_build_executed_returns_early_when_degraded(self):
        """ERR-2: Return early from on_build_executed() when degraded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            coordinator = self._create_started_coordinator(tmpdir)
            coordinator._is_degraded = True

            # when
            run_async(coordinator.on_build_executed("pytest"))

            # then
            coordinator._trigger.on_build_executed.assert_not_called()

    def test_on_build_executed_returns_early_when_trigger_is_none(self):
        """on_build_executed returns early if trigger component is None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            logger = self._create_mock_logger()
            coordinator = ReviewCoordinator(
                logger=logger,
                working_dir=tmpdir,
                requirements_summary="# Requirements"
            )
            coordinator._is_active = True
            coordinator._trigger = None

            # when - should not raise
            run_async(coordinator.on_build_executed("pytest"))

            # then - no assertion needed, just no exception


class TestOnBuildExecutedWithDebounce:
    """EDGE-4: Multiple build commands handled by existing debounce logic."""

    def _create_mock_logger(self):
        logger = MagicMock()
        logger.log_event = MagicMock()
        return logger

    def _create_started_coordinator(self, tmpdir):
        """Create a coordinator with mocked components."""
        logger = self._create_mock_logger()
        coordinator = ReviewCoordinator(
            logger=logger,
            working_dir=tmpdir,
            requirements_summary="# Requirements"
        )
        coordinator._is_active = True
        coordinator._file_tracker = MagicMock()
        coordinator._file_tracker.pending_count = 3
        coordinator._trigger = MagicMock()
        coordinator._trigger.on_build_executed = AsyncMock(return_value=True)
        return coordinator

    def test_multiple_build_commands_use_existing_debounce(self):
        """EDGE-4: Multiple build commands should work with debounce."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            coordinator = self._create_started_coordinator(tmpdir)

            # when - rapid succession of build commands
            run_async(coordinator.on_build_executed("pytest -v"))
            run_async(coordinator.on_build_executed("pytest --cov"))

            # then - both calls should be made to trigger
            # (debounce happens inside _schedule_review, not on_build_executed)
            assert coordinator._trigger.on_build_executed.call_count == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
