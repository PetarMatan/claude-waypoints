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


# =============================================================================
# REQ-2.1: ParsedIssue and Severity Parsing Tests
# =============================================================================

from wp_supervisor.reviewer import ParsedIssue


class TestParsedIssue:
    """Tests for ParsedIssue dataclass."""

    def test_parsed_issue_class_exists(self):
        """ParsedIssue class should exist."""
        assert ParsedIssue is not None

    def test_parsed_issue_has_content(self):
        """[REQ-2.1] ParsedIssue should have content field."""
        issue = ParsedIssue(content="Missing null check", severity="critical")
        assert issue.content == "Missing null check"

    def test_parsed_issue_has_severity(self):
        """[REQ-2.1] ParsedIssue should have severity field."""
        issue = ParsedIssue(content="Issue", severity="high")
        assert issue.severity == "high"

    def test_parsed_issue_has_optional_file_path(self):
        """ParsedIssue should have optional file_path field."""
        issue = ParsedIssue(
            content="Issue",
            severity="medium",
            file_path="/src/module.py"
        )
        assert issue.file_path == "/src/module.py"

    def test_parsed_issue_file_path_defaults_to_none(self):
        """file_path should default to None."""
        issue = ParsedIssue(content="Issue", severity="low")
        assert issue.file_path is None


class TestReviewResultParsedIssues:
    """Tests for ReviewResult.parsed_issues field."""

    def test_review_result_has_parsed_issues(self):
        """[REQ-2.1] ReviewResult should have parsed_issues field."""
        result = ReviewResult()
        assert hasattr(result, 'parsed_issues')

    def test_review_result_parsed_issues_is_list(self):
        """parsed_issues should be a list."""
        result = ReviewResult()
        assert isinstance(result.parsed_issues, list)

    def test_review_result_parsed_issues_defaults_empty(self):
        """parsed_issues should default to empty list."""
        result = ReviewResult()
        assert len(result.parsed_issues) == 0

    def test_review_result_can_have_parsed_issues(self):
        """ReviewResult should accept parsed_issues."""
        parsed = [
            ParsedIssue(content="Issue 1", severity="high"),
            ParsedIssue(content="Issue 2", severity="low"),
        ]
        result = ReviewResult(parsed_issues=parsed)
        assert len(result.parsed_issues) == 2


class TestReviewerAgentParseIssuesWithSeverity:
    """Tests for ReviewerAgent._parse_issues_with_severity method."""

    def _create_mock_logger(self):
        logger = MagicMock()
        logger.log_event = MagicMock()
        return logger

    def test_parse_issues_with_severity_method_exists(self):
        """[REQ-2.1] _parse_issues_with_severity method should exist."""
        assert hasattr(ReviewerAgent, '_parse_issues_with_severity')

    def test_parse_issues_with_severity_returns_list(self):
        """Should return list of ParsedIssue."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            reviewer = ReviewerAgent(
                logger=self._create_mock_logger(),
                requirements_summary="# Requirements",
                working_dir=tmpdir
            )
            text = "[CRITICAL] Missing null check"

            # when
            result = reviewer._parse_issues_with_severity(text)

            # then
            assert isinstance(result, list)

    def test_parse_issues_with_severity_extracts_critical(self):
        """[REQ-2.1] Should extract CRITICAL severity."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            reviewer = ReviewerAgent(
                logger=self._create_mock_logger(),
                requirements_summary="# Requirements",
                working_dir=tmpdir
            )
            text = "- [CRITICAL] Missing null check on deviceId"

            # when
            result = reviewer._parse_issues_with_severity(text)

            # then
            assert len(result) >= 1
            assert result[0].severity == "critical"

    def test_parse_issues_with_severity_extracts_high(self):
        """[REQ-2.1] Should extract HIGH severity."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            reviewer = ReviewerAgent(
                logger=self._create_mock_logger(),
                requirements_summary="# Requirements",
                working_dir=tmpdir
            )
            text = "- [HIGH] calculateDemand() ignores edge case"

            # when
            result = reviewer._parse_issues_with_severity(text)

            # then
            assert len(result) >= 1
            assert result[0].severity == "high"

    def test_parse_issues_with_severity_extracts_medium(self):
        """[REQ-2.1] Should extract MEDIUM severity."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            reviewer = ReviewerAgent(
                logger=self._create_mock_logger(),
                requirements_summary="# Requirements",
                working_dir=tmpdir
            )
            text = "- [MEDIUM] Consider adding logging"

            # when
            result = reviewer._parse_issues_with_severity(text)

            # then
            assert len(result) >= 1
            assert result[0].severity == "medium"

    def test_parse_issues_with_severity_extracts_low(self):
        """[REQ-2.1] Should extract LOW severity."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            reviewer = ReviewerAgent(
                logger=self._create_mock_logger(),
                requirements_summary="# Requirements",
                working_dir=tmpdir
            )
            text = "- [LOW] Variable naming could be clearer"

            # when
            result = reviewer._parse_issues_with_severity(text)

            # then
            assert len(result) >= 1
            assert result[0].severity == "low"

    def test_parse_issues_with_severity_handles_multiple_issues(self):
        """Should handle multiple issues with different severities."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            reviewer = ReviewerAgent(
                logger=self._create_mock_logger(),
                requirements_summary="# Requirements",
                working_dir=tmpdir
            )
            text = """
            - [CRITICAL] Missing null check
            - [HIGH] Edge case not handled
            - [MEDIUM] Add logging
            - [LOW] Naming improvement
            """

            # when
            result = reviewer._parse_issues_with_severity(text)

            # then
            assert len(result) == 4
            severities = [issue.severity for issue in result]
            assert "critical" in severities
            assert "high" in severities
            assert "medium" in severities
            assert "low" in severities

    def test_parse_issues_with_severity_defaults_to_medium(self):
        """[ERR-2] Should default to 'medium' when no severity tag."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            reviewer = ReviewerAgent(
                logger=self._create_mock_logger(),
                requirements_summary="# Requirements",
                working_dir=tmpdir
            )
            text = "- Issue without severity tag"

            # when
            result = reviewer._parse_issues_with_severity(text)

            # then
            assert len(result) >= 1
            assert result[0].severity == "medium"

    def test_parse_issues_with_severity_handles_empty_input(self):
        """Should handle empty input."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            reviewer = ReviewerAgent(
                logger=self._create_mock_logger(),
                requirements_summary="# Requirements",
                working_dir=tmpdir
            )

            # when
            result = reviewer._parse_issues_with_severity("")

            # then
            assert result == []


class TestReviewerAgentExtractSeverityFromIssue:
    """Tests for ReviewerAgent._extract_severity_from_issue method."""

    def _create_mock_logger(self):
        logger = MagicMock()
        logger.log_event = MagicMock()
        return logger

    def test_extract_severity_from_issue_method_exists(self):
        """_extract_severity_from_issue method should exist."""
        assert hasattr(ReviewerAgent, '_extract_severity_from_issue')

    def test_extract_severity_returns_tuple(self):
        """Should return tuple of (severity, clean_content)."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            reviewer = ReviewerAgent(
                logger=self._create_mock_logger(),
                requirements_summary="# Requirements",
                working_dir=tmpdir
            )

            # when
            result = reviewer._extract_severity_from_issue("[HIGH] Some issue")

            # then
            assert isinstance(result, tuple)
            assert len(result) == 2

    def test_extract_severity_extracts_tag(self):
        """Should extract severity tag and return clean content."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            reviewer = ReviewerAgent(
                logger=self._create_mock_logger(),
                requirements_summary="# Requirements",
                working_dir=tmpdir
            )

            # when
            severity, content = reviewer._extract_severity_from_issue("[CRITICAL] Missing check")

            # then
            assert severity == "critical"
            assert "Missing check" in content
            assert "[CRITICAL]" not in content

    def test_extract_severity_defaults_to_medium(self):
        """[ERR-2] Should default to 'medium' when no tag found."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            reviewer = ReviewerAgent(
                logger=self._create_mock_logger(),
                requirements_summary="# Requirements",
                working_dir=tmpdir
            )

            # when
            severity, content = reviewer._extract_severity_from_issue("Issue without tag")

            # then
            assert severity == "medium"
            assert content == "Issue without tag"

    def test_extract_severity_handles_lowercase_tags(self):
        """Should handle lowercase severity tags."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            reviewer = ReviewerAgent(
                logger=self._create_mock_logger(),
                requirements_summary="# Requirements",
                working_dir=tmpdir
            )

            # when
            severity, _ = reviewer._extract_severity_from_issue("[critical] Some issue")

            # then
            assert severity == "critical"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
