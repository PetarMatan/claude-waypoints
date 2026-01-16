#!/usr/bin/env python3
"""
Unit tests for markers.py - MarkerManager class
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch

# Add hooks/lib to path
sys.path.insert(0, 'hooks/lib')
from markers import MarkerManager


class TestMarkerManager:
    """Tests for MarkerManager class."""

    def test_init_creates_markers_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                manager = MarkerManager("test-session")
                assert manager.markers_dir.exists()
                assert "wp-test-session" in str(manager.markers_dir)

    def test_is_wp_active_false_when_not_initialized(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                manager = MarkerManager("test-session")
                assert manager.is_wp_active() is False

    def test_is_wp_active_true_after_initialize(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                manager = MarkerManager("test-session")
                manager._state.initialize()
                assert manager.is_wp_active() is True

    def test_get_phase_defaults_to_1(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                manager = MarkerManager("test-session")
                assert manager.get_phase() == 1

    def test_set_and_get_phase(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                manager = MarkerManager("test-session")
                manager.set_phase(3)
                assert manager.get_phase() == 3

    def test_phase_exists_false_when_not_initialized(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                manager = MarkerManager("test-session")
                assert manager.phase_exists() is False

    def test_phase_exists_true_after_initialize(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                manager = MarkerManager("test-session")
                manager._state.initialize()
                assert manager.phase_exists() is True


class TestPhaseCompletion:
    """Tests for phase completion methods."""

    def test_requirements_complete_false_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                manager = MarkerManager("test-session")
                assert manager.is_requirements_complete() is False

    def test_mark_requirements_complete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                manager = MarkerManager("test-session")
                manager.mark_requirements_complete()
                assert manager.is_requirements_complete() is True

    def test_mark_requirements_incomplete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                manager = MarkerManager("test-session")
                manager.mark_requirements_complete()
                manager.mark_requirements_incomplete()
                assert manager.is_requirements_complete() is False

    def test_interfaces_complete_cycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                manager = MarkerManager("test-session")
                assert manager.is_interfaces_complete() is False
                manager.mark_interfaces_complete()
                assert manager.is_interfaces_complete() is True
                manager.mark_interfaces_incomplete()
                assert manager.is_interfaces_complete() is False

    def test_tests_complete_cycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                manager = MarkerManager("test-session")
                assert manager.is_tests_complete() is False
                manager.mark_tests_complete()
                assert manager.is_tests_complete() is True
                manager.mark_tests_incomplete()
                assert manager.is_tests_complete() is False

    def test_implementation_complete_cycle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                manager = MarkerManager("test-session")
                assert manager.is_implementation_complete() is False
                manager.mark_implementation_complete()
                assert manager.is_implementation_complete() is True
                manager.mark_implementation_incomplete()
                assert manager.is_implementation_complete() is False


class TestCleanup:
    """Tests for cleanup methods."""

    def test_cleanup_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                manager = MarkerManager("test-session")
                manager._state.initialize()
                manager.set_phase(2)
                manager.mark_requirements_complete()

                manager.cleanup_session()

                assert not manager.markers_dir.exists()

    def test_cleanup_workflow_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                manager = MarkerManager("test-session")
                manager._state.initialize()
                manager.set_phase(3)
                manager.mark_requirements_complete()
                manager.mark_interfaces_complete()
                manager.mark_implementation_complete()

                manager.cleanup_workflow_state()

                # Directory should still exist
                assert manager.markers_dir.exists()
                # State should be reset
                assert manager.is_wp_active() is False
                assert manager.get_phase() == 1
                assert manager.is_requirements_complete() is False
                assert manager.is_interfaces_complete() is False
                # Implementation stays complete as success indicator
                assert manager.is_implementation_complete() is True

    def test_get_marker_dir_display(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                manager = MarkerManager("abc123")
                display = manager.get_marker_dir_display()
                assert display == "~/.claude/tmp/wp-abc123"


class TestSupervisorMode:
    """Tests for supervisor mode functionality."""

    def test_is_supervisor_mode_false_by_default(self):
        """Supervisor mode should be false when no env vars set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                env = os.environ.copy()
                env.pop("WP_SUPERVISOR_ACTIVE", None)
                env.pop("WP_SUPERVISOR_MARKERS_DIR", None)

                with patch.dict(os.environ, env, clear=True):
                    manager = MarkerManager("test-session")
                    assert manager.is_supervisor_mode() is False

    def test_is_supervisor_mode_true_with_active_env_var(self):
        """Supervisor mode should be true when WP_SUPERVISOR_ACTIVE=1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.dict(os.environ, {"WP_SUPERVISOR_ACTIVE": "1"}):
                    manager = MarkerManager("test-session")
                    assert manager.is_supervisor_mode() is True

    def test_is_supervisor_mode_true_with_markers_dir_env_var(self):
        """Supervisor mode should be true when WP_SUPERVISOR_MARKERS_DIR is set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                supervisor_dir = Path(tmpdir) / "supervisor-markers"
                supervisor_dir.mkdir(parents=True)

                with patch.dict(os.environ, {"WP_SUPERVISOR_MARKERS_DIR": str(supervisor_dir)}, clear=False):
                    manager = MarkerManager("test-session")
                    assert manager.is_supervisor_mode() is True

    def test_init_uses_supervisor_dir_when_env_set(self):
        """MarkerManager should use supervisor's marker directory when env var set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                supervisor_dir = Path(tmpdir) / "custom-supervisor-dir"
                supervisor_dir.mkdir(parents=True)

                with patch.dict(os.environ, {"WP_SUPERVISOR_MARKERS_DIR": str(supervisor_dir)}, clear=False):
                    manager = MarkerManager("test-session")
                    assert manager.markers_dir == supervisor_dir

    def test_init_uses_session_dir_when_no_supervisor_env(self):
        """MarkerManager should use session-based directory when not in supervisor mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                env = os.environ.copy()
                env.pop("WP_SUPERVISOR_MARKERS_DIR", None)
                env.pop("WP_SUPERVISOR_ACTIVE", None)

                with patch.dict(os.environ, env, clear=True):
                    manager = MarkerManager("my-session")
                    assert "wp-my-session" in str(manager.markers_dir)

    def test_supervisor_mode_markers_shared(self):
        """Multiple MarkerManagers in supervisor mode should share the same directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                supervisor_dir = Path(tmpdir) / "shared-supervisor-dir"
                supervisor_dir.mkdir(parents=True)

                with patch.dict(os.environ, {"WP_SUPERVISOR_MARKERS_DIR": str(supervisor_dir)}, clear=False):
                    manager1 = MarkerManager("session-1")
                    manager2 = MarkerManager("session-2")

                    # Both should use the same supervisor directory
                    assert manager1.markers_dir == manager2.markers_dir
                    assert manager1.markers_dir == supervisor_dir


class TestWpCliUpdatesStateJson:
    """
    Regression tests ensuring wp_cli.py commands properly update state.json.

    This validates the fix for the CLI mode bug where:
    - OLD (broken): Prompts told Claude to use 'touch' commands
    - NEW (fixed): Prompts tell Claude to use 'wp_cli.py' commands

    The wp-activation.py PreToolUse hook intercepts these commands and
    updates state.json using MarkerManager, ensuring hooks can read the state.
    """

    def test_mark_requirements_updates_state(self):
        """wp_cli.py mark-complete requirements should update state.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                manager = MarkerManager("test-session")
                manager._state.initialize()

                # This is what the wp-activation hook does when it intercepts
                # the command: python3 wp_cli.py mark-complete requirements
                manager.mark_requirements_complete()

                # Verify state is updated and readable by hooks
                assert manager.is_requirements_complete() is True

    def test_mark_interfaces_updates_state(self):
        """wp_cli.py mark-complete interfaces should update state.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                manager = MarkerManager("test-session")
                manager._state.initialize()

                manager.mark_interfaces_complete()

                assert manager.is_interfaces_complete() is True

    def test_mark_tests_updates_state(self):
        """wp_cli.py mark-complete tests should update state.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                manager = MarkerManager("test-session")
                manager._state.initialize()

                manager.mark_tests_complete()

                assert manager.is_tests_complete() is True

    def test_init_activates_workflow(self):
        """wp_cli.py init should activate the workflow in state.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                manager = MarkerManager("test-session")

                # This is what the wp-activation hook does when it intercepts
                # the command: python3 wp_cli.py init
                manager._state.initialize()

                assert manager.is_wp_active() is True

    def test_set_phase_updates_state(self):
        """wp_cli.py set-phase should update the phase in state.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                manager = MarkerManager("test-session")
                manager._state.initialize()

                # This is what the wp-activation hook does when it intercepts
                # the command: python3 wp_cli.py set-phase 3
                manager.set_phase(3)

                assert manager.get_phase() == 3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
