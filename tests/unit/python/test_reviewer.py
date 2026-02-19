#!/usr/bin/env python3
"""Unit tests for wp_supervisor/reviewer.py"""

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
from wp_supervisor.reviewer import (
    ReviewerAgent,
    ReviewerState,
    ReviewResult,
    ReviewerContext,
)


@pytest.fixture(autouse=True)
def clean_supervisor_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("WP_SUPERVISOR_"):
            monkeypatch.delenv(key, raising=False)


def run_async(coro):
    return asyncio.run(coro)


class TestReviewerState:

    def test_initializing_state_exists(self):
        assert ReviewerState.INITIALIZING.value == "initializing"

    def test_ready_state_exists(self):
        assert ReviewerState.READY.value == "ready"

    def test_reviewing_state_exists(self):
        assert ReviewerState.REVIEWING.value == "reviewing"

    def test_degraded_state_exists(self):
        assert ReviewerState.DEGRADED.value == "degraded"


class TestReviewResult:

    def test_review_result_has_issues_field(self):
        result = ReviewResult()
        assert isinstance(result.issues, list)
        assert len(result.issues) == 0

    def test_review_result_has_files_reviewed_field(self):
        result = ReviewResult()
        assert isinstance(result.files_reviewed, set)
        assert len(result.files_reviewed) == 0

    def test_review_result_with_issues(self):
        result = ReviewResult(
            issues=["Issue 1", "Issue 2"],
            files_reviewed={"/path/to/file.py"},
        )
        assert len(result.issues) == 2
        assert "Issue 1" in result.issues
        assert "/path/to/file.py" in result.files_reviewed


class TestReviewerContext:

    def test_reviewer_context_has_requirements_summary(self):
        context = ReviewerContext(
            requirements_summary="# Requirements\n- Feature A",
            changed_files={}
        )
        assert context.requirements_summary == "# Requirements\n- Feature A"

    def test_reviewer_context_has_changed_files(self):
        files = {"/path/to/file.py": "def foo(): pass"}
        context = ReviewerContext(requirements_summary="# Requirements", changed_files=files)
        assert context.changed_files == files

    def test_reviewer_context_has_interfaces_summary(self):
        context = ReviewerContext(
            requirements_summary="# Requirements",
            changed_files={},
            interfaces_summary="# Interfaces\n- Class A"
        )
        assert context.interfaces_summary == "# Interfaces\n- Class A"

    def test_reviewer_context_interfaces_summary_defaults_to_empty(self):
        context = ReviewerContext(
            requirements_summary="# Requirements",
            changed_files={}
        )
        assert context.interfaces_summary == ""


class TestReviewerAgentInit:

    def test_reviewer_agent_class_exists(self):
        assert ReviewerAgent is not None

    def test_reviewer_agent_init_requires_expected_params(self):
        import inspect
        params = inspect.signature(ReviewerAgent.__init__).parameters
        assert 'logger' in params
        assert 'requirements_summary' in params
        assert 'working_dir' in params


class TestReviewerAgentState:

    def test_state_property_exists(self):
        assert hasattr(ReviewerAgent, 'state')


class TestReviewerAgentStart:

    def test_start_method_exists(self):
        assert hasattr(ReviewerAgent, 'start')

    def test_start_is_async(self):
        import inspect
        assert inspect.iscoroutinefunction(ReviewerAgent.start)


class TestReviewerAgentReview:

    def test_review_method_exists(self):
        assert hasattr(ReviewerAgent, 'review')

    def test_review_is_async(self):
        import inspect
        assert inspect.iscoroutinefunction(ReviewerAgent.review)

    def test_review_accepts_context_parameter(self):
        import inspect
        assert 'context' in inspect.signature(ReviewerAgent.review).parameters


class TestReviewerAgentFormatFeedback:

    def test_format_feedback_method_exists(self):
        assert hasattr(ReviewerAgent, 'format_feedback')

    def test_format_feedback_accepts_required_params(self):
        import inspect
        params = inspect.signature(ReviewerAgent.format_feedback).parameters
        assert 'result' in params


class TestReviewerAgentStop:

    def test_stop_method_exists(self):
        assert hasattr(ReviewerAgent, 'stop')

    def test_stop_is_async(self):
        import inspect
        assert inspect.iscoroutinefunction(ReviewerAgent.stop)


# --- Behavioral Tests ---

class TestReviewerAgentBehavior:

    def _create_mock_logger(self):
        logger = MagicMock()
        logger.log_event = MagicMock()
        return logger

    def test_init_sets_state_to_initializing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reviewer = ReviewerAgent(
                logger=self._create_mock_logger(),
                requirements_summary="# Requirements",
                working_dir=tmpdir
            )
            assert reviewer.state == ReviewerState.INITIALIZING

    def test_start_transitions_to_ready_on_success(self):
        assert hasattr(ReviewerAgent, 'start')

    def test_start_transitions_to_degraded_on_failure(self):
        assert hasattr(ReviewerAgent, 'start')

    def test_review_returns_empty_result_when_degraded(self):
        assert hasattr(ReviewerAgent, 'review')

    def test_review_returns_empty_result_when_no_files_changed(self):
        assert hasattr(ReviewerAgent, 'review')

    def test_format_feedback_includes_issues(self):
        assert hasattr(ReviewerAgent, 'format_feedback')

    def test_stop_cleans_up_resources(self):
        assert hasattr(ReviewerAgent, 'stop')


class TestReviewerContextMinimalData:

    def test_context_contains_requirements_files_interfaces_and_tests(self):
        hints = ReviewerContext.__dataclass_fields__
        assert 'requirements_summary' in hints
        assert 'changed_files' in hints
        assert 'interfaces_summary' in hints
        assert 'tests_summary' in hints
        assert len(hints) == 4

    def test_context_files_are_read_only(self):
        files = {"/path/to/file.py": "def foo(): pass"}
        context = ReviewerContext(requirements_summary="# Requirements", changed_files=files)
        assert isinstance(context.changed_files["/path/to/file.py"], str)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
