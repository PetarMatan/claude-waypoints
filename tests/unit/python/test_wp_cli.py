#!/usr/bin/env python3
"""
Unit tests for wp_cli.py - CLI for state management.

These tests verify that wp_cli.py correctly updates state.json,
which is the fix for the marker file bug.
"""

import os
import sys
import subprocess
import tempfile
import json
import pytest
from pathlib import Path
from unittest.mock import patch

# Add hooks/lib to path
sys.path.insert(0, 'hooks/lib')
from wp_state import WPState


class TestWpCliInit:
    """Tests for 'wp_cli.py init' command."""

    def test_init_creates_state_file(self):
        """Init should create state.json with active=true."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "wp-test"

            result = subprocess.run(
                [sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "init"],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert "Waypoints initialized" in result.stdout

            # Verify state.json was created correctly
            state_file = state_dir / "state.json"
            assert state_file.exists()

            with open(state_file) as f:
                state = json.load(f)

            assert state["active"] is True
            assert state["phase"] == 1

    def test_init_with_session_id(self):
        """Init with --session-id should create correct directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                result = subprocess.run(
                    [sys.executable, "hooks/lib/wp_cli.py", "init", "--session-id", "my-session"],
                    capture_output=True,
                    text=True,
                    env={**os.environ, "HOME": tmpdir}
                )

                assert result.returncode == 0
                # State directory should be created
                state_dir = Path(tmpdir) / ".claude" / "tmp" / "wp-my-session"
                assert state_dir.exists()


class TestWpCliMarkComplete:
    """Tests for 'wp_cli.py mark-complete' command."""

    def test_mark_requirements_complete(self):
        """mark-complete requirements should update state.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "wp-test"
            state_dir.mkdir(parents=True)

            # Initialize first
            subprocess.run(
                [sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "init"],
                capture_output=True
            )

            # Mark requirements complete
            result = subprocess.run(
                [sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "mark-complete", "requirements"],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert "Marked requirements as complete" in result.stdout

            # Verify state.json was updated
            with open(state_dir / "state.json") as f:
                state = json.load(f)

            assert state["completedPhases"]["requirements"] is True

    def test_mark_interfaces_complete(self):
        """mark-complete interfaces should update state.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "wp-test"
            state_dir.mkdir(parents=True)

            subprocess.run(
                [sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "init"],
                capture_output=True
            )

            result = subprocess.run(
                [sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "mark-complete", "interfaces"],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0

            with open(state_dir / "state.json") as f:
                state = json.load(f)

            assert state["completedPhases"]["interfaces"] is True

    def test_mark_tests_complete(self):
        """mark-complete tests should update state.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "wp-test"
            state_dir.mkdir(parents=True)

            subprocess.run(
                [sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "init"],
                capture_output=True
            )

            result = subprocess.run(
                [sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "mark-complete", "tests"],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0

            with open(state_dir / "state.json") as f:
                state = json.load(f)

            assert state["completedPhases"]["tests"] is True

    def test_mark_implementation_complete(self):
        """mark-complete implementation should update state.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "wp-test"
            state_dir.mkdir(parents=True)

            subprocess.run(
                [sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "init"],
                capture_output=True
            )

            result = subprocess.run(
                [sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "mark-complete", "implementation"],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0

            with open(state_dir / "state.json") as f:
                state = json.load(f)

            assert state["completedPhases"]["implementation"] is True

    def test_mark_invalid_phase_fails(self):
        """mark-complete with invalid phase should fail."""
        result = subprocess.run(
            [sys.executable, "hooks/lib/wp_cli.py", "mark-complete", "invalid"],
            capture_output=True,
            text=True
        )

        assert result.returncode != 0


class TestWpCliSetPhase:
    """Tests for 'wp_cli.py set-phase' command."""

    def test_set_phase_updates_state(self):
        """set-phase should update phase in state.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "wp-test"
            state_dir.mkdir(parents=True)

            subprocess.run(
                [sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "init"],
                capture_output=True
            )

            result = subprocess.run(
                [sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "set-phase", "3"],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert "Set phase to 3" in result.stdout

            with open(state_dir / "state.json") as f:
                state = json.load(f)

            assert state["phase"] == 3

    def test_set_phase_invalid_number_fails(self):
        """set-phase with invalid number should fail."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "wp-test"
            state_dir.mkdir(parents=True)

            result = subprocess.run(
                [sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "set-phase", "5"],
                capture_output=True,
                text=True
            )

            assert result.returncode != 0
            assert "Phase must be between 1 and 4" in result.stdout


class TestWpCliStatus:
    """Tests for 'wp_cli.py status' command."""

    def test_status_shows_current_state(self):
        """status should display current state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "wp-test"
            state_dir.mkdir(parents=True)

            subprocess.run(
                [sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "init"],
                capture_output=True
            )

            subprocess.run(
                [sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "mark-complete", "requirements"],
                capture_output=True
            )

            result = subprocess.run(
                [sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "status"],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert "Active:" in result.stdout
            assert "Phase:" in result.stdout
            assert "Requirements:" in result.stdout


class TestWpCliReset:
    """Tests for 'wp_cli.py reset' command."""

    def test_reset_clears_state(self):
        """reset should clear workflow state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "wp-test"
            state_dir.mkdir(parents=True)

            subprocess.run(
                [sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "init"],
                capture_output=True
            )

            result = subprocess.run(
                [sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "reset"],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0
            assert "reset" in result.stdout.lower()


class TestWpCliIntegrationWithHooks:
    """
    Integration tests verifying wp_cli.py updates are visible to hooks.

    This is the key test - it verifies the fix for the marker file bug:
    CLI updates state.json -> hooks read state.json correctly.
    """

    def test_cli_updates_visible_to_marker_manager(self):
        """State changes via CLI should be visible to MarkerManager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "wp-test"
            state_dir.mkdir(parents=True)

            # Use CLI to initialize and mark complete
            subprocess.run(
                [sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "init"],
                capture_output=True
            )
            subprocess.run(
                [sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "mark-complete", "requirements"],
                capture_output=True
            )
            subprocess.run(
                [sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "set-phase", "2"],
                capture_output=True
            )

            # Now verify WPState (used by hooks) sees these changes
            os.environ["WP_SUPERVISOR_MARKERS_DIR"] = str(state_dir)
            try:
                state = WPState(session_id="test")

                assert state.is_active() is True, "WPState should see active=true"
                assert state.is_requirements_complete() is True, "WPState should see requirements complete"
                assert state.get_phase() == 2, "WPState should see phase=2"
            finally:
                del os.environ["WP_SUPERVISOR_MARKERS_DIR"]

    def test_full_workflow_via_cli(self):
        """Simulate full workflow using only CLI commands."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "wp-test"

            # Phase 1: Init and complete requirements
            subprocess.run([sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "init"], capture_output=True)
            subprocess.run([sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "mark-complete", "requirements"], capture_output=True)
            subprocess.run([sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "set-phase", "2"], capture_output=True)

            # Phase 2: Complete interfaces
            subprocess.run([sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "mark-complete", "interfaces"], capture_output=True)
            subprocess.run([sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "set-phase", "3"], capture_output=True)

            # Phase 3: Complete tests
            subprocess.run([sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "mark-complete", "tests"], capture_output=True)
            subprocess.run([sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "set-phase", "4"], capture_output=True)

            # Phase 4: Complete implementation
            subprocess.run([sys.executable, "hooks/lib/wp_cli.py", "--dir", str(state_dir), "mark-complete", "implementation"], capture_output=True)

            # Verify final state
            os.environ["WP_SUPERVISOR_MARKERS_DIR"] = str(state_dir)
            try:
                state = WPState(session_id="test")

                assert state.is_active() is True
                assert state.get_phase() == 4
                assert state.is_requirements_complete() is True
                assert state.is_interfaces_complete() is True
                assert state.is_tests_complete() is True
                assert state.is_implementation_complete() is True
            finally:
                del os.environ["WP_SUPERVISOR_MARKERS_DIR"]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
