#!/usr/bin/env python3
"""
Unit tests for wp_supervisor/logger.py - SupervisorLogger class
"""

import tempfile
import pytest
from pathlib import Path

import sys
sys.path.insert(0, 'wp_supervisor')
from logger import SupervisorLogger


class TestSupervisorLoggerInit:
    """Tests for SupervisorLogger initialization."""

    def test_init_creates_log_file_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workflow_dir = Path(tmpdir) / "workflow-123"
            logger = SupervisorLogger(workflow_dir, "workflow-123")
            assert workflow_dir.exists()

    def test_init_sets_workflow_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SupervisorLogger(Path(tmpdir), "my-workflow")
            assert logger.workflow_id == "my-workflow"

    def test_log_file_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SupervisorLogger(Path(tmpdir), "test")
            assert logger.get_log_path().endswith("workflow.log")


class TestLogEvent:
    """Tests for log_event method."""

    def test_log_event_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SupervisorLogger(Path(tmpdir), "test")
            logger.log_event("TEST", "Test message")
            assert Path(logger.get_log_path()).exists()

    def test_log_event_writes_formatted_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SupervisorLogger(Path(tmpdir), "test")
            logger.log_event("CATEGORY", "Test message")

            content = logger.get_log_content()
            assert "[CATEGORY]" in content
            assert "Test message" in content

    def test_log_event_includes_timestamp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SupervisorLogger(Path(tmpdir), "test")
            logger.log_event("TEST", "Message")

            content = logger.get_log_content()
            # Should have timestamp format like [2026-01-11 10:30:00]
            assert "[20" in content

    def test_log_event_sanitizes_newlines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SupervisorLogger(Path(tmpdir), "test")
            logger.log_event("TEST", "Line1\nLine2\nLine3")

            content = logger.get_log_content()
            assert "\\n" in content
            # Should be on single line
            assert content.count("\n") == 1


class TestWorkflowEvents:
    """Tests for workflow event logging."""

    def test_log_workflow_start(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SupervisorLogger(Path(tmpdir), "test")
            logger.log_workflow_start("Build a calculator")

            content = logger.get_log_content()
            assert "[WORKFLOW]" in content
            assert "started" in content.lower()

    def test_log_workflow_complete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SupervisorLogger(Path(tmpdir), "test")
            logger.log_workflow_complete("1,500 tokens, $0.05")

            content = logger.get_log_content()
            assert "completed" in content.lower()
            assert "1,500 tokens" in content

    def test_log_workflow_aborted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SupervisorLogger(Path(tmpdir), "test")
            logger.log_workflow_aborted("User interrupted")

            content = logger.get_log_content()
            assert "aborted" in content.lower()
            assert "User interrupted" in content


class TestPhaseEvents:
    """Tests for phase event logging."""

    def test_log_phase_start(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SupervisorLogger(Path(tmpdir), "test")
            logger.log_phase_start(1, "Requirements")

            content = logger.get_log_content()
            assert "[PHASE]" in content
            assert "Phase 1" in content
            assert "Requirements" in content

    def test_log_phase_complete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SupervisorLogger(Path(tmpdir), "test")
            logger.log_phase_complete(2, "Interfaces")

            content = logger.get_log_content()
            assert "Phase 2" in content
            assert "completed" in content.lower()

    def test_log_phase_summary_saved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SupervisorLogger(Path(tmpdir), "test")
            logger.log_phase_summary_saved(1, "/path/to/doc.md")

            content = logger.get_log_content()
            assert "summary" in content.lower()
            assert "/path/to/doc.md" in content

    def test_log_phase_context_saved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SupervisorLogger(Path(tmpdir), "test")
            logger.log_phase_context_saved(2, "/path/to/context.md")

            content = logger.get_log_content()
            assert "context" in content.lower()


class TestUserEvents:
    """Tests for user event logging."""

    def test_log_user_input(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SupervisorLogger(Path(tmpdir), "test")
            logger.log_user_input("Build a REST API")

            content = logger.get_log_content()
            assert "[USER]" in content
            assert "Input" in content

    def test_log_user_input_truncates_long_input(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SupervisorLogger(Path(tmpdir), "test")
            long_input = "x" * 100
            logger.log_user_input(long_input)

            content = logger.get_log_content()
            assert "..." in content

    def test_log_user_confirmation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SupervisorLogger(Path(tmpdir), "test")
            logger.log_user_confirmation(2)

            content = logger.get_log_content()
            assert "Confirmed" in content
            assert "phase 2" in content

    def test_log_user_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SupervisorLogger(Path(tmpdir), "test")
            logger.log_user_command("/done")

            content = logger.get_log_content()
            assert "Command" in content
            assert "/done" in content


class TestErrorEvents:
    """Tests for error event logging."""

    def test_log_error_without_exception(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SupervisorLogger(Path(tmpdir), "test")
            logger.log_error("Something went wrong")

            content = logger.get_log_content()
            assert "[ERROR]" in content
            assert "Something went wrong" in content

    def test_log_error_with_exception(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SupervisorLogger(Path(tmpdir), "test")
            try:
                raise ValueError("Test error")
            except ValueError as e:
                logger.log_error("Operation failed", e)

            content = logger.get_log_content()
            assert "ValueError" in content
            assert "Test error" in content


class TestUsageEvents:
    """Tests for usage event logging."""

    def test_log_usage_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SupervisorLogger(Path(tmpdir), "test")
            logger.log_usage_summary(
                total_tokens=15000,
                total_cost=0.45,
                duration_sec=120.5
            )

            content = logger.get_log_content()
            assert "[USAGE]" in content
            assert "15,000" in content
            assert "$0.45" in content


class TestLogContent:
    """Tests for get_log_content method."""

    def test_get_log_content_returns_empty_for_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SupervisorLogger(Path(tmpdir), "test")
            # Don't write anything
            assert logger.get_log_content() == ""

    def test_get_log_content_returns_all_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SupervisorLogger(Path(tmpdir), "test")
            logger.log_workflow_start("Task 1")
            logger.log_phase_start(1, "Requirements")
            logger.log_phase_complete(1, "Requirements")

            content = logger.get_log_content()
            assert content.count("\n") == 3


class TestAgentEvents:
    """Tests for agent event logging (WPLogger compatibility)."""

    def test_log_wp_creates_wp_category(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = SupervisorLogger(Path(tmpdir), "test")
            logger.log_wp("Loading agent 'Uncle Bob' for phase 2")

            content = logger.get_log_content()
            assert "[WP]" in content
            assert "Uncle Bob" in content
            assert "phase 2" in content


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
