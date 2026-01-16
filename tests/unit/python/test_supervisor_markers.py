#!/usr/bin/env python3
"""
Unit tests for wp_supervisor/markers.py - SupervisorMarkers class
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime

# Add wp_supervisor to path
sys.path.insert(0, '.')
from wp_supervisor.markers import SupervisorMarkers


class TestSupervisorMarkersInit:
    """Tests for SupervisorMarkers initialization."""

    def test_init_creates_markers_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test-workflow")
                assert markers.markers_dir.exists()

    def test_init_with_custom_workflow_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("custom-id-123")
                assert markers.workflow_id == "custom-id-123"
                assert "wp-supervisor-custom-id-123" in str(markers.markers_dir)

    def test_init_generates_workflow_id_when_none_provided(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers()
                assert markers.workflow_id is not None
                assert len(markers.workflow_id) > 0

    def test_init_sets_base_dir_to_claude_tmp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                assert ".claude" in str(markers.base_dir)
                assert "tmp" in str(markers.base_dir)


class TestGenerateWorkflowId:
    """Tests for workflow ID generation."""

    def test_generate_workflow_id_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers()
                # Format should be YYYYMMDD-HHMMSS
                parts = markers.workflow_id.split("-")
                assert len(parts) == 2
                assert len(parts[0]) == 8  # YYYYMMDD
                assert len(parts[1]) == 6  # HHMMSS

    def test_generate_workflow_id_is_valid_timestamp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers()
                # Should be parseable as datetime
                try:
                    datetime.strptime(markers.workflow_id, "%Y%m%d-%H%M%S")
                except ValueError:
                    pytest.fail("Workflow ID is not a valid timestamp format")


class TestInitialize:
    """Tests for initialize method."""

    def test_initialize_activates_wp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                markers.initialize()
                assert markers.is_active() is True

    def test_initialize_sets_phase_to_1(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                markers.initialize()
                assert markers.get_phase() == 1


class TestPhaseManagement:
    """Tests for phase get/set methods."""

    def test_get_phase_returns_1_when_not_initialized(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                assert markers.get_phase() == 1

    def test_get_phase_reads_correct_value(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                for phase in [1, 2, 3, 4]:
                    markers.set_phase(phase)
                    assert markers.get_phase() == phase


class TestPhaseCompletion:
    """Tests for phase completion methods."""

    def test_requirements_complete_cycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                assert markers.is_requirements_complete() is False
                markers.mark_requirements_complete()
                assert markers.is_requirements_complete() is True

    def test_interfaces_complete_cycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                assert markers.is_interfaces_complete() is False
                markers.mark_interfaces_complete()
                assert markers.is_interfaces_complete() is True

    def test_tests_complete_cycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                assert markers.is_tests_complete() is False
                markers.mark_tests_complete()
                assert markers.is_tests_complete() is True

    def test_implementation_complete_cycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                assert markers.is_implementation_complete() is False
                markers.mark_implementation_complete()
                assert markers.is_implementation_complete() is True


class TestIsActive:
    """Tests for is_active method."""

    def test_is_active_false_when_not_initialized(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                assert markers.is_active() is False

    def test_is_active_true_after_initialize(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                markers.initialize()
                assert markers.is_active() is True


class TestContextStorage:
    """Tests for context save/get methods."""

    def test_save_and_get_requirements_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                summary = "# Requirements\n- Feature A\n- Feature B"
                markers.save_requirements_summary(summary)
                assert markers.get_requirements_summary() == summary

    def test_get_requirements_summary_returns_empty_when_not_set(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                assert markers.get_requirements_summary() == ""

    def test_save_and_get_interfaces_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                interfaces = "# Interfaces\n- UserService\n- AuthHandler"
                markers.save_interfaces_list(interfaces)
                assert markers.get_interfaces_list() == interfaces

    def test_get_interfaces_list_returns_empty_when_not_set(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                assert markers.get_interfaces_list() == ""

    def test_save_and_get_tests_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                tests = "# Tests\n- test_user_creation\n- test_auth_flow"
                markers.save_tests_list(tests)
                assert markers.get_tests_list() == tests

    def test_get_tests_list_returns_empty_when_not_set(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                assert markers.get_tests_list() == ""

    def test_save_overwrites_existing_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                markers.save_requirements_summary("first")
                markers.save_requirements_summary("second")
                assert markers.get_requirements_summary() == "second"


class TestCleanup:
    """Tests for cleanup method."""

    def test_cleanup_removes_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                markers.initialize()
                markers.save_requirements_summary("test")

                markers.cleanup()

                assert not markers.markers_dir.exists()

    def test_cleanup_handles_nonexistent_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                # Remove directory manually first
                markers.markers_dir.rmdir()

                # Should not raise
                markers.cleanup()


class TestGetMarkerDir:
    """Tests for get_marker_dir method."""

    def test_get_marker_dir_returns_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test-id")
                path = markers.get_marker_dir()
                assert "wp-supervisor-test-id" in path
                assert isinstance(path, str)


class TestGetEnvVars:
    """Tests for get_env_vars method."""

    def test_get_env_vars_contains_workflow_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test-workflow-id")
                env_vars = markers.get_env_vars()
                assert "WP_SUPERVISOR_WORKFLOW_ID" in env_vars
                assert env_vars["WP_SUPERVISOR_WORKFLOW_ID"] == "test-workflow-id"

    def test_get_env_vars_contains_markers_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                env_vars = markers.get_env_vars()
                assert "WP_SUPERVISOR_MARKERS_DIR" in env_vars
                assert env_vars["WP_SUPERVISOR_MARKERS_DIR"] == str(markers.markers_dir)

    def test_get_env_vars_contains_active_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                env_vars = markers.get_env_vars()
                assert "WP_SUPERVISOR_ACTIVE" in env_vars
                assert env_vars["WP_SUPERVISOR_ACTIVE"] == "1"

    def test_get_env_vars_returns_all_required_vars(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                env_vars = markers.get_env_vars()
                required_keys = [
                    "WP_SUPERVISOR_WORKFLOW_ID",
                    "WP_SUPERVISOR_MARKERS_DIR",
                    "WP_SUPERVISOR_ACTIVE",
                ]
                for key in required_keys:
                    assert key in env_vars


class TestUsageTracking:
    """Tests for usage tracking methods."""

    def test_add_phase_usage_stores_data(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                markers.add_phase_usage(
                    phase=1,
                    input_tokens=1000,
                    output_tokens=500,
                    cost_usd=0.05,
                    duration_ms=5000,
                    turns=3
                )
                usage = markers.get_phase_usage(1)
                assert usage["input_tokens"] == 1000
                assert usage["output_tokens"] == 500
                assert usage["cost_usd"] == 0.05
                assert usage["duration_ms"] == 5000
                assert usage["turns"] == 3

    def test_add_phase_usage_accumulates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                markers.add_phase_usage(phase=2, input_tokens=100, output_tokens=50)
                markers.add_phase_usage(phase=2, input_tokens=200, output_tokens=100)

                usage = markers.get_phase_usage(2)
                assert usage["input_tokens"] == 300
                assert usage["output_tokens"] == 150

    def test_get_phase_usage_returns_zero_for_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                usage = markers.get_phase_usage(1)
                assert usage["input_tokens"] == 0
                assert usage["output_tokens"] == 0
                assert usage["cost_usd"] == 0.0

    def test_get_total_usage_sums_all_phases(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                markers.add_phase_usage(phase=1, input_tokens=100, output_tokens=50, cost_usd=0.01)
                markers.add_phase_usage(phase=2, input_tokens=200, output_tokens=100, cost_usd=0.02)
                markers.add_phase_usage(phase=3, input_tokens=300, output_tokens=150, cost_usd=0.03)
                markers.add_phase_usage(phase=4, input_tokens=400, output_tokens=200, cost_usd=0.04)

                total = markers.get_total_usage()
                assert total["input_tokens"] == 1000
                assert total["output_tokens"] == 500
                assert total["cost_usd"] == 0.10

    def test_get_all_usage_includes_phases_and_total(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                markers.add_phase_usage(phase=1, input_tokens=100, turns=2)
                markers.add_phase_usage(phase=2, input_tokens=200, turns=3)

                all_usage = markers.get_all_usage()
                assert "phase1" in all_usage
                assert "phase2" in all_usage
                assert "phase3" in all_usage
                assert "phase4" in all_usage
                assert "total" in all_usage
                assert all_usage["phase1"]["input_tokens"] == 100
                assert all_usage["phase2"]["input_tokens"] == 200
                assert all_usage["total"]["input_tokens"] == 300
                assert all_usage["total"]["turns"] == 5

    def test_invalid_phase_ignored(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                markers.add_phase_usage(phase=0, input_tokens=100)
                markers.add_phase_usage(phase=5, input_tokens=100)

                total = markers.get_total_usage()
                assert total["input_tokens"] == 0

    def test_get_total_tokens(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                markers.add_phase_usage(phase=1, input_tokens=100, output_tokens=50)
                markers.add_phase_usage(phase=2, input_tokens=200, output_tokens=100)

                assert markers.get_total_tokens() == 450

    def test_get_total_cost(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                markers.add_phase_usage(phase=1, cost_usd=0.05)
                markers.add_phase_usage(phase=2, cost_usd=0.10)

                assert markers.get_total_cost() == pytest.approx(0.15)

    def test_get_total_duration_sec(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                markers.add_phase_usage(phase=1, duration_ms=5000)
                markers.add_phase_usage(phase=2, duration_ms=3000)

                assert markers.get_total_duration_sec() == 8.0

    def test_get_usage_summary_text(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                markers.add_phase_usage(phase=1, input_tokens=1000, output_tokens=500, cost_usd=0.05)

                summary = markers.get_usage_summary_text()
                assert "1,500 tokens" in summary
                assert "$0.0500" in summary


class TestDocumentStorage:
    """Tests for document storage methods."""

    def test_save_and_get_phase_document(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                content = "# Requirements\n\n- Feature A\n- Feature B"

                path = markers.save_phase_document(1, content)
                assert path != ""
                assert "phase1-requirements.md" in path

                retrieved = markers.get_phase_document(1)
                assert retrieved == content

    def test_save_and_get_phase_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                context = "You are a Waypoints assistant. Here is the task..."

                path = markers.save_phase_context(2, context)
                assert path != ""
                assert "phase2-input.md" in path
                assert "context" in path

                retrieved = markers.get_phase_context(2)
                assert retrieved == context

    def test_get_phase_document_returns_empty_for_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                assert markers.get_phase_document(1) == ""

    def test_get_phase_context_returns_empty_for_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                assert markers.get_phase_context(1) == ""

    def test_invalid_phase_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                assert markers.save_phase_document(0, "content") == ""
                assert markers.save_phase_document(5, "content") == ""
                assert markers.get_phase_document(0) == ""

    def test_list_documents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                markers.save_phase_document(1, "Requirements")
                markers.save_phase_document(2, "Interfaces")
                markers.save_phase_context(1, "Context for phase 1")

                docs = markers.list_documents()
                assert "phase1" in docs
                assert "phase2" in docs
                assert "phase1_context" in docs

    def test_get_phase_document_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test")
                path = markers.get_phase_document_path(3)
                assert "phase3-tests.md" in path


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
