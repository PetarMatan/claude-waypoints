#!/usr/bin/env python3
"""
Tests for wp-activation.py PreToolUse hook.

Tests that the activation hook correctly intercepts wp_cli.py commands
and creates session-specific state.
"""

import json
import os
import subprocess
import sys
import tempfile
import pytest
from pathlib import Path

# Get the project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


def run_hook(hook_name: str, input_data: dict, env: dict = None) -> tuple:
    """
    Run a Python hook script with the given input.

    Args:
        hook_name: Name of the hook script (without .py)
        input_data: Dict to pass as JSON stdin
        env: Additional environment variables

    Returns (exit_code, stdout, stderr)
    """
    hook_path = PROJECT_ROOT / "hooks" / f"{hook_name}.py"

    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    result = subprocess.run(
        ["python3", str(hook_path)],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        env=full_env,
        timeout=30
    )
    return result.returncode, result.stdout, result.stderr


def generate_bash_hook_input(
    command: str,
    cwd: str = "/project",
    session_id: str = "test-session"
) -> dict:
    """Generate hook input JSON for Bash tool."""
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": cwd,
        "session_id": session_id,
        "hook_event_name": "PreToolUse",
        "stop_hook_active": False,
    }


def get_wp_state(markers_dir: Path) -> dict:
    """Read WP state from state.json file."""
    state_file = markers_dir / "state.json"
    if not state_file.exists():
        return None
    return json.loads(state_file.read_text())


class TestWPActivationHook:
    """Tests for wp-activation.py"""

    def test_init_command_creates_state(self):
        """Should create session-specific state when wp_cli.py init is executed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            markers_dir = Path(tmpdir) / ".claude" / "tmp" / "wp-test-session"

            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}
            input_data = generate_bash_hook_input(
                command="true # wp:init",
                session_id="test-session"
            )

            exit_code, stdout, stderr = run_hook("wp-activation", input_data, env)

            assert exit_code == 0
            # State should be created
            assert markers_dir.exists()
            state = get_wp_state(markers_dir)
            assert state is not None
            assert state.get("active") is True
            assert state.get("phase") == 1

    def test_init_command_idempotent(self):
        """Should be idempotent - calling init twice doesn't change state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            markers_dir = Path(tmpdir) / ".claude" / "tmp" / "wp-test-session"

            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}
            input_data = generate_bash_hook_input(
                command="true # wp:init",
                session_id="test-session"
            )

            # First call
            run_hook("wp-activation", input_data, env)
            state1 = get_wp_state(markers_dir)

            # Second call
            run_hook("wp-activation", input_data, env)
            state2 = get_wp_state(markers_dir)

            # State should be unchanged
            assert state1.get("phase") == state2.get("phase")
            assert state1.get("active") == state2.get("active")

    def test_mark_complete_requirements_updates_state(self):
        """Should mark requirements complete when wp_cli.py mark-complete requirements is executed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            markers_dir = Path(tmpdir) / ".claude" / "tmp" / "wp-test-session"

            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}

            # First initialize
            init_input = generate_bash_hook_input(
                command="true # wp:init",
                session_id="test-session"
            )
            run_hook("wp-activation", init_input, env)

            # Then mark requirements complete
            mark_input = generate_bash_hook_input(
                command="true # wp:mark-complete requirements",
                session_id="test-session"
            )
            exit_code, stdout, stderr = run_hook("wp-activation", mark_input, env)

            assert exit_code == 0
            state = get_wp_state(markers_dir)
            assert state.get("completedPhases", {}).get("requirements") is True

    def test_mark_complete_interfaces_updates_state(self):
        """Should mark interfaces complete when wp_cli.py mark-complete interfaces is executed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            markers_dir = Path(tmpdir) / ".claude" / "tmp" / "wp-test-session"

            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}

            # Initialize
            init_input = generate_bash_hook_input(
                command="true # wp:init",
                session_id="test-session"
            )
            run_hook("wp-activation", init_input, env)

            # Mark interfaces complete
            mark_input = generate_bash_hook_input(
                command="true # wp:mark-complete interfaces",
                session_id="test-session"
            )
            exit_code, stdout, stderr = run_hook("wp-activation", mark_input, env)

            assert exit_code == 0
            state = get_wp_state(markers_dir)
            assert state.get("completedPhases", {}).get("interfaces") is True

    def test_mark_complete_tests_updates_state(self):
        """Should mark tests complete when wp_cli.py mark-complete tests is executed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            markers_dir = Path(tmpdir) / ".claude" / "tmp" / "wp-test-session"

            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}

            # Initialize
            init_input = generate_bash_hook_input(
                command="true # wp:init",
                session_id="test-session"
            )
            run_hook("wp-activation", init_input, env)

            # Mark tests complete
            mark_input = generate_bash_hook_input(
                command="true # wp:mark-complete tests",
                session_id="test-session"
            )
            exit_code, stdout, stderr = run_hook("wp-activation", mark_input, env)

            assert exit_code == 0
            state = get_wp_state(markers_dir)
            assert state.get("completedPhases", {}).get("tests") is True

    def test_set_phase_updates_state(self):
        """Should set phase when wp_cli.py set-phase is executed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            markers_dir = Path(tmpdir) / ".claude" / "tmp" / "wp-test-session"

            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}

            # Initialize
            init_input = generate_bash_hook_input(
                command="true # wp:init",
                session_id="test-session"
            )
            run_hook("wp-activation", init_input, env)

            # Set phase to 3
            set_phase_input = generate_bash_hook_input(
                command="true # wp:set-phase 3",
                session_id="test-session"
            )
            exit_code, stdout, stderr = run_hook("wp-activation", set_phase_input, env)

            assert exit_code == 0
            state = get_wp_state(markers_dir)
            assert state.get("phase") == 3

    def test_reset_clears_workflow_state(self):
        """Should clear workflow state when wp_cli.py reset is executed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            markers_dir = Path(tmpdir) / ".claude" / "tmp" / "wp-test-session"

            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}

            # Initialize and set some state
            init_input = generate_bash_hook_input(
                command="true # wp:init",
                session_id="test-session"
            )
            run_hook("wp-activation", init_input, env)

            set_phase_input = generate_bash_hook_input(
                command="true # wp:set-phase 3",
                session_id="test-session"
            )
            run_hook("wp-activation", set_phase_input, env)

            # Reset without --full flag (just workflow state)
            reset_input = generate_bash_hook_input(
                command="true # wp:reset",
                session_id="test-session"
            )
            exit_code, stdout, stderr = run_hook("wp-activation", reset_input, env)

            assert exit_code == 0
            state = get_wp_state(markers_dir)
            # State should be reset to phase 1, inactive
            assert state.get("phase") == 1
            assert state.get("active") is False

    def test_reset_full_clears_session(self):
        """Should clear entire session when wp_cli.py reset --full is executed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            markers_dir = Path(tmpdir) / ".claude" / "tmp" / "wp-test-session"

            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}

            # Initialize
            init_input = generate_bash_hook_input(
                command="true # wp:init",
                session_id="test-session"
            )
            run_hook("wp-activation", init_input, env)
            assert markers_dir.exists()

            # Reset with --full flag
            reset_input = generate_bash_hook_input(
                command="true # wp:reset --full",
                session_id="test-session"
            )
            exit_code, stdout, stderr = run_hook("wp-activation", reset_input, env)

            assert exit_code == 0
            # Entire markers directory should be removed
            assert not markers_dir.exists()

    def test_non_wp_commands_ignored(self):
        """Should not intercept non-wp_cli.py bash commands."""
        with tempfile.TemporaryDirectory() as tmpdir:
            markers_dir = Path(tmpdir) / ".claude" / "tmp" / "wp-test-session"

            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}
            input_data = generate_bash_hook_input(
                command="ls -la /project",
                session_id="test-session"
            )

            exit_code, stdout, stderr = run_hook("wp-activation", input_data, env)

            assert exit_code == 0
            # No state should be created
            assert not markers_dir.exists()

    def test_non_bash_tools_ignored(self):
        """Should not intercept non-Bash tools."""
        with tempfile.TemporaryDirectory() as tmpdir:
            markers_dir = Path(tmpdir) / ".claude" / "tmp" / "wp-test-session"

            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}
            input_data = {
                "tool_name": "Write",
                "tool_input": {"file_path": "/test/file.py"},
                "cwd": "/project",
                "session_id": "test-session",
                "hook_event_name": "PreToolUse",
            }

            exit_code, stdout, stderr = run_hook("wp-activation", input_data, env)

            assert exit_code == 0
            # No state should be created
            assert not markers_dir.exists()

    def test_multiple_sessions_isolated(self):
        """Should keep state isolated between different sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            markers_dir_1 = Path(tmpdir) / ".claude" / "tmp" / "wp-session-1"
            markers_dir_2 = Path(tmpdir) / ".claude" / "tmp" / "wp-session-2"

            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}

            # Initialize session 1
            init_1 = generate_bash_hook_input(
                command="true # wp:init",
                session_id="session-1"
            )
            run_hook("wp-activation", init_1, env)

            # Set session 1 to phase 3
            set_phase_1 = generate_bash_hook_input(
                command="true # wp:set-phase 3",
                session_id="session-1"
            )
            run_hook("wp-activation", set_phase_1, env)

            # Initialize session 2
            init_2 = generate_bash_hook_input(
                command="true # wp:init",
                session_id="session-2"
            )
            run_hook("wp-activation", init_2, env)

            # Verify isolation
            state_1 = get_wp_state(markers_dir_1)
            state_2 = get_wp_state(markers_dir_2)

            assert state_1.get("phase") == 3
            assert state_2.get("phase") == 1  # Should still be at phase 1

    def test_status_command_does_not_modify_state(self):
        """Should not modify state when wp_cli.py status is executed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            markers_dir = Path(tmpdir) / ".claude" / "tmp" / "wp-test-session"

            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}

            # Initialize
            init_input = generate_bash_hook_input(
                command="true # wp:init",
                session_id="test-session"
            )
            run_hook("wp-activation", init_input, env)

            state_before = get_wp_state(markers_dir)

            # Run status
            status_input = generate_bash_hook_input(
                command="true # wp:status",
                session_id="test-session"
            )
            exit_code, stdout, stderr = run_hook("wp-activation", status_input, env)

            assert exit_code == 0
            state_after = get_wp_state(markers_dir)

            # State should be unchanged
            assert state_before == state_after

    def test_handles_empty_command(self):
        """Should handle empty command gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}
            input_data = {
                "tool_name": "Bash",
                "tool_input": {"command": ""},
                "cwd": "/project",
                "session_id": "test-session",
            }

            exit_code, stdout, stderr = run_hook("wp-activation", input_data, env)

            assert exit_code == 0

    def test_handles_missing_tool_input(self):
        """Should handle missing tool_input gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}
            input_data = {
                "tool_name": "Bash",
                "cwd": "/project",
                "session_id": "test-session",
            }

            exit_code, stdout, stderr = run_hook("wp-activation", input_data, env)

            assert exit_code == 0


class TestKnowledgeIntegration:
    """Tests for knowledge management integration in wp-activation.py"""

    def test_init_loads_knowledge_context(self):
        """Should load knowledge files and include in response when wp:init is called."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            knowledge_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge" / "test-project"
            knowledge_dir.mkdir(parents=True)
            (knowledge_dir / "architecture.md").write_text("# Architecture\nService A connects to B")

            project_dir = Path(tmpdir) / "test-project"
            project_dir.mkdir()
            (project_dir / ".waypoints-project").write_text("test-project")

            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}
            input_data = generate_bash_hook_input(
                command="true # wp:init",
                cwd=str(project_dir),
                session_id="test-session"
            )

            # when
            exit_code, stdout, stderr = run_hook("wp-activation", input_data, env)

            # then
            assert exit_code == 0
            response = json.loads(stdout)
            context = response.get("hookSpecificOutput", {}).get("additionalContext", "")
            assert "Project Knowledge" in context
            assert "Service A connects to B" in context

    def test_init_skips_knowledge_when_no_files(self):
        """Should work without errors when no knowledge files exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            project_dir = Path(tmpdir) / "empty-project"
            project_dir.mkdir()

            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}
            input_data = generate_bash_hook_input(
                command="true # wp:init",
                cwd=str(project_dir),
                session_id="test-session"
            )

            # when
            exit_code, stdout, stderr = run_hook("wp-activation", input_data, env)

            # then
            assert exit_code == 0
            response = json.loads(stdout)
            context = response.get("hookSpecificOutput", {}).get("additionalContext", "")
            assert "Project Knowledge" not in context

    def test_mark_complete_implementation_applies_learnings(self):
        """Should apply staged learnings to permanent files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            project_dir = Path(tmpdir) / "test-project"
            project_dir.mkdir()
            (project_dir / ".waypoints-project").write_text("test-project")

            staging_dir = Path(tmpdir) / ".claude" / "waypoints" / "staging" / "test-session"
            staging_dir.mkdir(parents=True)
            staged_learnings = [
                {"category": "architecture", "title": "New Service", "content": "Does something", "source_phase": 2}
            ]
            (staging_dir / "staged-learnings.json").write_text(json.dumps(staged_learnings))

            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}

            # Initialize first
            init_input = generate_bash_hook_input(
                command="true # wp:init",
                cwd=str(project_dir),
                session_id="test-session"
            )
            run_hook("wp-activation", init_input, env)

            # when
            mark_input = generate_bash_hook_input(
                command="true # wp:mark-complete implementation",
                cwd=str(project_dir),
                session_id="test-session"
            )
            exit_code, stdout, stderr = run_hook("wp-activation", mark_input, env)

            # then
            assert exit_code == 0
            arch_file = Path(tmpdir) / ".claude" / "waypoints" / "knowledge" / "test-project" / "architecture.md"
            assert arch_file.exists()
            content = arch_file.read_text()
            assert "New Service" in content

    def test_mark_complete_implementation_cleans_staging(self):
        """Should remove staging directory after applying learnings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            project_dir = Path(tmpdir) / "test-project"
            project_dir.mkdir()
            (project_dir / ".waypoints-project").write_text("test-project")

            staging_dir = Path(tmpdir) / ".claude" / "waypoints" / "staging" / "test-session"
            staging_dir.mkdir(parents=True)
            staged_learnings = [
                {"category": "lessons-learned", "title": "Test Lesson", "content": "Learn this", "source_phase": 4}
            ]
            (staging_dir / "staged-learnings.json").write_text(json.dumps(staged_learnings))

            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}

            # Initialize first
            init_input = generate_bash_hook_input(
                command="true # wp:init",
                cwd=str(project_dir),
                session_id="test-session"
            )
            run_hook("wp-activation", init_input, env)

            # when
            mark_input = generate_bash_hook_input(
                command="true # wp:mark-complete implementation",
                cwd=str(project_dir),
                session_id="test-session"
            )
            run_hook("wp-activation", mark_input, env)

            # then
            assert not staging_dir.exists()

    def test_mark_complete_implementation_shows_summary(self):
        """Should include knowledge update summary in response."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            project_dir = Path(tmpdir) / "test-project"
            project_dir.mkdir()
            (project_dir / ".waypoints-project").write_text("test-project")

            staging_dir = Path(tmpdir) / ".claude" / "waypoints" / "staging" / "test-session"
            staging_dir.mkdir(parents=True)
            staged_learnings = [
                {"category": "architecture", "title": "T1", "content": "C1", "source_phase": 2},
                {"category": "architecture", "title": "T2", "content": "C2", "source_phase": 2},
                {"category": "lessons-learned", "title": "T3", "content": "C3", "source_phase": 4}
            ]
            (staging_dir / "staged-learnings.json").write_text(json.dumps(staged_learnings))

            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}

            # Initialize first
            init_input = generate_bash_hook_input(
                command="true # wp:init",
                cwd=str(project_dir),
                session_id="test-session"
            )
            run_hook("wp-activation", init_input, env)

            # when
            mark_input = generate_bash_hook_input(
                command="true # wp:mark-complete implementation",
                cwd=str(project_dir),
                session_id="test-session"
            )
            exit_code, stdout, stderr = run_hook("wp-activation", mark_input, env)

            # then
            assert exit_code == 0
            response = json.loads(stdout)
            context = response.get("hookSpecificOutput", {}).get("additionalContext", "")
            assert "Knowledge updated" in context or "📚" in context

    def test_mark_complete_implementation_skips_when_no_learnings(self):
        """Should not show summary when no staged learnings exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            project_dir = Path(tmpdir) / "test-project"
            project_dir.mkdir()

            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}

            # Initialize first
            init_input = generate_bash_hook_input(
                command="true # wp:init",
                cwd=str(project_dir),
                session_id="test-session"
            )
            run_hook("wp-activation", init_input, env)

            # when
            mark_input = generate_bash_hook_input(
                command="true # wp:mark-complete implementation",
                cwd=str(project_dir),
                session_id="test-session"
            )
            exit_code, stdout, stderr = run_hook("wp-activation", mark_input, env)

            # then
            assert exit_code == 0
            response = json.loads(stdout)
            context = response.get("hookSpecificOutput", {}).get("additionalContext", "")
            assert "Knowledge updated" not in context


class TestStageCommand:
    """Tests for wp:stage command in wp-activation.py"""

    def test_stage_learning_success(self):
        """Should stage a learning when valid command is provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            project_dir = Path(tmpdir) / "test-project"
            project_dir.mkdir()
            (project_dir / ".waypoints-project").write_text("test-project")

            staging_dir = Path(tmpdir) / ".claude" / "waypoints" / "staging" / "test-session"

            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}

            # Initialize first
            init_input = generate_bash_hook_input(
                command="true # wp:init",
                cwd=str(project_dir),
                session_id="test-session"
            )
            run_hook("wp-activation", init_input, env)

            # when
            stage_input = generate_bash_hook_input(
                command='true # wp:stage architecture "Service Topology" "ServiceA calls ServiceB"',
                cwd=str(project_dir),
                session_id="test-session"
            )
            exit_code, stdout, stderr = run_hook("wp-activation", stage_input, env)

            # then
            assert exit_code == 0
            staging_file = staging_dir / "staged-learnings.json"
            assert staging_file.exists()
            learnings = json.loads(staging_file.read_text())
            assert len(learnings) == 1
            assert learnings[0]["category"] == "architecture"
            assert learnings[0]["title"] == "Service Topology"
            assert learnings[0]["content"] == "ServiceA calls ServiceB"

    def test_stage_learning_includes_current_phase(self):
        """Should include current phase as source_phase in staged learning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            project_dir = Path(tmpdir) / "test-project"
            project_dir.mkdir()

            staging_dir = Path(tmpdir) / ".claude" / "waypoints" / "staging" / "test-session"

            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}

            # Initialize and advance to phase 2
            init_input = generate_bash_hook_input(
                command="true # wp:init",
                cwd=str(project_dir),
                session_id="test-session"
            )
            run_hook("wp-activation", init_input, env)

            mark_input = generate_bash_hook_input(
                command="true # wp:mark-complete requirements",
                cwd=str(project_dir),
                session_id="test-session"
            )
            run_hook("wp-activation", mark_input, env)

            # when
            stage_input = generate_bash_hook_input(
                command='true # wp:stage decisions "Async Pattern" "Chose async for scalability"',
                cwd=str(project_dir),
                session_id="test-session"
            )
            run_hook("wp-activation", stage_input, env)

            # then
            staging_file = staging_dir / "staged-learnings.json"
            learnings = json.loads(staging_file.read_text())
            assert learnings[0]["source_phase"] == 2

    def test_stage_learning_invalid_category(self):
        """Should return error for invalid category."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            project_dir = Path(tmpdir) / "test-project"
            project_dir.mkdir()

            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}

            # Initialize first
            init_input = generate_bash_hook_input(
                command="true # wp:init",
                cwd=str(project_dir),
                session_id="test-session"
            )
            run_hook("wp-activation", init_input, env)

            # when
            stage_input = generate_bash_hook_input(
                command='true # wp:stage invalid-category "Title" "Content"',
                cwd=str(project_dir),
                session_id="test-session"
            )
            exit_code, stdout, stderr = run_hook("wp-activation", stage_input, env)

            # then
            assert exit_code == 0
            response = json.loads(stdout)
            context = response.get("hookSpecificOutput", {}).get("additionalContext", "")
            assert "Invalid category" in context
            assert "invalid-category" in context

    def test_stage_learning_malformed_command(self):
        """Should return usage help for malformed command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            project_dir = Path(tmpdir) / "test-project"
            project_dir.mkdir()

            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}

            # Initialize first
            init_input = generate_bash_hook_input(
                command="true # wp:init",
                cwd=str(project_dir),
                session_id="test-session"
            )
            run_hook("wp-activation", init_input, env)

            # when - missing quotes
            stage_input = generate_bash_hook_input(
                command='true # wp:stage architecture Title Content',
                cwd=str(project_dir),
                session_id="test-session"
            )
            exit_code, stdout, stderr = run_hook("wp-activation", stage_input, env)

            # then
            assert exit_code == 0
            response = json.loads(stdout)
            context = response.get("hookSpecificOutput", {}).get("additionalContext", "")
            assert "Usage:" in context

    def test_stage_multiple_learnings_accumulate(self):
        """Should accumulate multiple staged learnings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            project_dir = Path(tmpdir) / "test-project"
            project_dir.mkdir()

            staging_dir = Path(tmpdir) / ".claude" / "waypoints" / "staging" / "test-session"

            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}

            # Initialize first
            init_input = generate_bash_hook_input(
                command="true # wp:init",
                cwd=str(project_dir),
                session_id="test-session"
            )
            run_hook("wp-activation", init_input, env)

            # when - stage first learning
            stage_input1 = generate_bash_hook_input(
                command='true # wp:stage architecture "First" "Content1"',
                cwd=str(project_dir),
                session_id="test-session"
            )
            run_hook("wp-activation", stage_input1, env)

            # stage second learning
            stage_input2 = generate_bash_hook_input(
                command='true # wp:stage decisions "Second" "Content2"',
                cwd=str(project_dir),
                session_id="test-session"
            )
            run_hook("wp-activation", stage_input2, env)

            # then
            staging_file = staging_dir / "staged-learnings.json"
            learnings = json.loads(staging_file.read_text())
            assert len(learnings) == 2
            assert learnings[0]["title"] == "First"
            assert learnings[1]["title"] == "Second"

    def test_stage_lessons_learned_category(self):
        """Should handle lessons-learned category with hyphen."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            project_dir = Path(tmpdir) / "test-project"
            project_dir.mkdir()

            staging_dir = Path(tmpdir) / ".claude" / "waypoints" / "staging" / "test-session"

            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}

            # Initialize first
            init_input = generate_bash_hook_input(
                command="true # wp:init",
                cwd=str(project_dir),
                session_id="test-session"
            )
            run_hook("wp-activation", init_input, env)

            # when
            stage_input = generate_bash_hook_input(
                command='true # wp:stage lessons-learned "[MongoDB] BsonId" "Always use @BsonId annotation"',
                cwd=str(project_dir),
                session_id="test-session"
            )
            exit_code, stdout, stderr = run_hook("wp-activation", stage_input, env)

            # then
            assert exit_code == 0
            staging_file = staging_dir / "staged-learnings.json"
            learnings = json.loads(staging_file.read_text())
            assert learnings[0]["category"] == "lessons-learned"
            assert "[MongoDB]" in learnings[0]["title"]

    def test_stage_response_confirms_staging(self):
        """Should respond with confirmation message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            project_dir = Path(tmpdir) / "test-project"
            project_dir.mkdir()

            env = {"HOME": tmpdir, "WP_INSTALL_DIR": str(PROJECT_ROOT)}

            # Initialize first
            init_input = generate_bash_hook_input(
                command="true # wp:init",
                cwd=str(project_dir),
                session_id="test-session"
            )
            run_hook("wp-activation", init_input, env)

            # when
            stage_input = generate_bash_hook_input(
                command='true # wp:stage architecture "My Title" "My Content"',
                cwd=str(project_dir),
                session_id="test-session"
            )
            exit_code, stdout, stderr = run_hook("wp-activation", stage_input, env)

            # then
            assert exit_code == 0
            response = json.loads(stdout)
            context = response.get("hookSpecificOutput", {}).get("additionalContext", "")
            assert "Staged" in context
            assert "My Title" in context
            assert "architecture" in context


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
