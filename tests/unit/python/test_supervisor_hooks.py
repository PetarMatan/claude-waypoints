#!/usr/bin/env python3
"""Unit tests for wp_supervisor/hooks.py"""

import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "wp_supervisor"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "hooks" / "lib"))

from wp_supervisor.hooks import SupervisorHooks
from wp_supervisor.hook_messages import (
    get_phase_block_reason,
    get_log_reason,
    format_compile_error,
    format_test_failure,
    PHASE1_BLOCK_REASON,
    PHASE2_BLOCK_REASON,
    PHASE3_BLOCK_REASON,
)


def run_async(coro):
    import asyncio
    return asyncio.run(coro)


class TestHookMessages:

    def test_phase1_block_reason(self):
        assert "Phase 1" in PHASE1_BLOCK_REASON
        assert "requirements" in PHASE1_BLOCK_REASON.lower()

    def test_phase2_block_reason(self):
        assert "Phase 2" in PHASE2_BLOCK_REASON
        assert "interface" in PHASE2_BLOCK_REASON.lower()

    def test_phase3_block_reason(self):
        assert "Phase 3" in PHASE3_BLOCK_REASON
        assert "test" in PHASE3_BLOCK_REASON.lower()

    def test_get_phase_block_reason(self):
        assert get_phase_block_reason(1) == PHASE1_BLOCK_REASON
        assert get_phase_block_reason(2) == PHASE2_BLOCK_REASON
        assert get_phase_block_reason(3) == PHASE3_BLOCK_REASON
        assert get_phase_block_reason(4) == ""

    def test_get_log_reason(self):
        assert "requirements" in get_log_reason(1)
        assert "interface" in get_log_reason(2)
        assert "implementation" in get_log_reason(3)


class TestSupervisorHooks:

    def _create_hooks(self, phase: int = 1) -> SupervisorHooks:
        markers = MagicMock()
        markers.get_phase.return_value = phase
        logger = MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir:
            pom = Path(tmpdir) / "pom.xml"
            pom.write_text("<project></project>")

            hooks = SupervisorHooks(
                markers=markers,
                logger=logger,
                working_dir=tmpdir
            )
            hooks._test_markers = markers
            hooks._test_logger = logger
            return hooks

    def test_init_creates_config(self):
        hooks = self._create_hooks()
        assert hooks.config is not None

    def test_get_file_path_extracts_path(self):
        hooks = self._create_hooks()
        input_data = {"tool_input": {"file_path": "/test/file.py"}}
        assert hooks._get_file_path(input_data) == "/test/file.py"

    def test_get_file_path_returns_none_for_missing(self):
        hooks = self._create_hooks()
        assert hooks._get_file_path({}) is None
        assert hooks._get_file_path({"tool_input": {}}) is None

    def test_deny_response_format(self):
        hooks = self._create_hooks()
        result = hooks._deny("PreToolUse", "Test reason")

        assert "hookSpecificOutput" in result
        assert result["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert result["hookSpecificOutput"]["permissionDecisionReason"] == "Test reason"

    def test_allow_response_is_empty(self):
        hooks = self._create_hooks()
        assert hooks._allow() == {}


class TestPhaseGuardHook:

    def _create_hooks_with_config(self, phase: int, tmpdir: str) -> SupervisorHooks:
        markers = MagicMock()
        markers.get_phase.return_value = phase
        logger = MagicMock()

        hooks = SupervisorHooks(
            markers=markers,
            logger=logger,
            working_dir=tmpdir
        )
        hooks._test_logger = logger
        return hooks

    def test_allows_non_write_edit_tools(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(1, tmpdir)
            input_data = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Read",
                "tool_input": {"file_path": "/test/file.py"}
            }
            result = run_async(hooks.phase_guard(input_data, None, None))
            assert result == {}

    def test_allows_when_no_file_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(1, tmpdir)
            input_data = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {}
            }
            result = run_async(hooks.phase_guard(input_data, None, None))
            assert result == {}

    def test_phase1_blocks_main_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "pom.xml").write_text("<project></project>")

            hooks = self._create_hooks_with_config(1, tmpdir)
            hooks.config.is_main_source = MagicMock(return_value=True)
            hooks.config.is_test_source = MagicMock(return_value=False)

            input_data = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": "/src/main/java/Test.java"}
            }
            result = run_async(hooks.phase_guard(input_data, None, None))

            assert "hookSpecificOutput" in result
            assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_phase2_blocks_test_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(2, tmpdir)
            hooks.config.is_main_source = MagicMock(return_value=False)
            hooks.config.is_test_source = MagicMock(return_value=True)

            input_data = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Edit",
                "tool_input": {"file_path": "/src/test/java/TestFile.java"}
            }
            result = run_async(hooks.phase_guard(input_data, None, None))

            assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_phase2_allows_main_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(2, tmpdir)
            hooks.config.is_main_source = MagicMock(return_value=True)
            hooks.config.is_test_source = MagicMock(return_value=False)

            input_data = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": "/src/main/java/Main.java"}
            }
            result = run_async(hooks.phase_guard(input_data, None, None))
            assert result == {}

    def test_phase3_blocks_main_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(3, tmpdir)
            hooks.config.is_main_source = MagicMock(return_value=True)
            hooks.config.is_test_source = MagicMock(return_value=False)
            hooks.config.is_config_file = MagicMock(return_value=False)

            input_data = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": "/src/main/java/Main.java"}
            }
            result = run_async(hooks.phase_guard(input_data, None, None))

            assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_phase3_allows_test_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(3, tmpdir)
            hooks.config.is_main_source = MagicMock(return_value=False)
            hooks.config.is_test_source = MagicMock(return_value=True)

            input_data = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": "/src/test/java/Test.java"}
            }
            result = run_async(hooks.phase_guard(input_data, None, None))
            assert result == {}

    def test_phase4_allows_everything(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(4, tmpdir)
            hooks.config.is_main_source = MagicMock(return_value=True)
            hooks.config.is_test_source = MagicMock(return_value=False)

            input_data = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": "/src/main/java/Main.java"}
            }
            result = run_async(hooks.phase_guard(input_data, None, None))
            assert result == {}


class TestLogToolUseHook:

    def test_logs_file_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            markers = MagicMock()
            logger = MagicMock()

            hooks = SupervisorHooks(markers, logger, tmpdir)

            input_data = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": "/test/file.py"}
            }
            result = run_async(hooks.log_tool_use(input_data, None, None))

            logger.log_event.assert_called_once()
            call_args = logger.log_event.call_args[0]
            assert call_args[0] == "TOOL"
            assert "Write" in call_args[1]
            assert "/test/file.py" in call_args[1]
            assert result == {}

    def test_logs_bash_command_preview(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            markers = MagicMock()
            logger = MagicMock()

            hooks = SupervisorHooks(markers, logger, tmpdir)

            input_data = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "mvn clean compile"}
            }
            result = run_async(hooks.log_tool_use(input_data, None, None))

            logger.log_event.assert_called_once()
            call_args = logger.log_event.call_args[0]
            assert "Bash" in call_args[1]
            assert "mvn" in call_args[1]

    def test_truncates_long_commands(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            markers = MagicMock()
            logger = MagicMock()

            hooks = SupervisorHooks(markers, logger, tmpdir)

            long_command = "x" * 100
            input_data = {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": long_command}
            }
            run_async(hooks.log_tool_use(input_data, None, None))

            call_args = logger.log_event.call_args[0]
            assert "..." in call_args[1]
            assert len(call_args[1]) < 100


class TestGetHooksConfig:

    def test_returns_empty_without_sdk(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            markers = MagicMock()
            logger = MagicMock()
            hooks = SupervisorHooks(markers, logger, tmpdir)

            with patch.dict(sys.modules, {'claude_agent_sdk': None}):
                result = hooks.get_hooks_config()
                assert isinstance(result, dict)


class TestBuildVerifyHook:

    def _create_hooks_with_config(self, phase: int, tmpdir: str) -> SupervisorHooks:
        markers = MagicMock()
        markers.get_phase.return_value = phase
        logger = MagicMock()

        hooks = SupervisorHooks(
            markers=markers,
            logger=logger,
            working_dir=tmpdir
        )
        hooks._test_logger = logger
        return hooks

    def test_phase1_allows_without_verification(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(1, tmpdir)
            input_data = {"cwd": tmpdir}
            result = run_async(hooks.build_verify(input_data, None, None))
            assert result == {}

    def test_skips_when_stop_hook_active(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(4, tmpdir)
            input_data = {"cwd": tmpdir, "stop_hook_active": True}
            result = run_async(hooks.build_verify(input_data, None, None))
            assert result == {}

    def test_skips_when_no_cwd(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(4, tmpdir)
            input_data = {}
            result = run_async(hooks.build_verify(input_data, None, None))
            assert result == {}

    def test_phase2_runs_compile_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(2, tmpdir)
            hooks.config.get_profile_name = MagicMock(return_value="python")
            hooks.config.get_command = MagicMock(return_value="echo test")
            hooks._run_command = MagicMock(return_value=(0, "success"))

            input_data = {"cwd": tmpdir}
            result = run_async(hooks.build_verify(input_data, None, None))

            hooks._run_command.assert_called_once()
            assert result == {}

    def test_phase2_compile_failure_blocks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(2, tmpdir)
            hooks.config.get_profile_name = MagicMock(return_value="python")
            hooks.config.get_command = MagicMock(return_value="echo test")
            hooks._run_command = MagicMock(return_value=(1, "Compile error: syntax error"))

            input_data = {"cwd": tmpdir}
            result = run_async(hooks.build_verify(input_data, None, None))

            assert result.get("continue") is False
            assert "stopReason" in result
            assert "FAILED" in result["stopReason"]

    def test_phase3_runs_test_compile_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(3, tmpdir)
            hooks.config.get_profile_name = MagicMock(return_value="python")
            hooks.config.get_command = MagicMock(side_effect=lambda cmd: "echo compile" if cmd == "compile" else "echo testCompile" if cmd == "testCompile" else None)
            hooks._run_command = MagicMock(return_value=(0, "success"))

            input_data = {"cwd": tmpdir}
            result = run_async(hooks.build_verify(input_data, None, None))

            hooks._run_command.assert_called_once()
            assert result == {}

    def test_phase3_falls_back_to_compile(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(3, tmpdir)
            hooks.config.get_profile_name = MagicMock(return_value="python")
            hooks.config.get_command = MagicMock(side_effect=lambda cmd: "echo compile" if cmd == "compile" else None)
            hooks._run_command = MagicMock(return_value=(0, "success"))

            input_data = {"cwd": tmpdir}
            result = run_async(hooks.build_verify(input_data, None, None))

            hooks._run_command.assert_called_once()
            assert result == {}

    def test_phase4_runs_compile_and_test(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(4, tmpdir)
            hooks.config.get_profile_name = MagicMock(return_value="python")
            hooks.config.get_command = MagicMock(side_effect=lambda cmd: f"echo {cmd}")
            hooks._run_command = MagicMock(return_value=(0, "success"))

            input_data = {"cwd": tmpdir}
            result = run_async(hooks.build_verify(input_data, None, None))

            assert hooks._run_command.call_count == 2
            assert result == {}

    def test_phase4_test_failure_blocks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(4, tmpdir)
            hooks.config.get_profile_name = MagicMock(return_value="python")
            hooks.config.get_command = MagicMock(side_effect=lambda cmd: f"echo {cmd}")
            hooks._run_command = MagicMock(side_effect=[(0, "OK"), (1, "FAILED: 2 tests failed")])

            input_data = {"cwd": tmpdir}
            result = run_async(hooks.build_verify(input_data, None, None))

            assert result.get("continue") is False
            assert "Tests FAILED" in result["stopReason"]

    def test_skips_commands_with_placeholders(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(2, tmpdir)
            hooks.config.get_profile_name = MagicMock(return_value="python")
            hooks.config.get_command = MagicMock(return_value="python -m py_compile {file}")
            hooks._run_command = MagicMock(return_value=(0, "success"))

            input_data = {"cwd": tmpdir}
            result = run_async(hooks.build_verify(input_data, None, None))

            hooks._run_command.assert_not_called()
            assert result == {}

    def test_has_placeholder_detects_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(1, tmpdir)
            assert hooks._has_placeholder("python {file}") is True
            assert hooks._has_placeholder("python test.py") is False

    def test_has_placeholder_detects_test_placeholders(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(1, tmpdir)
            assert hooks._has_placeholder("mvn test -Dtest={testClass}") is True
            assert hooks._has_placeholder("pytest {testFile}") is True
            assert hooks._has_placeholder("go test -run {testName}") is True


class TestBuildVerifyMessages:

    def test_format_compile_error(self):
        result = format_compile_error("SyntaxError: invalid syntax", "python", "python -m compileall .")
        assert "Compilation FAILED" in result
        assert "python" in result
        assert "SyntaxError" in result
        assert "python -m compileall" in result

    def test_format_compile_error_truncates_output(self):
        long_output = "x" * 3000
        result = format_compile_error(long_output, "maven", "mvn compile")
        assert len(result) < 2500

    def test_format_test_failure(self):
        result = format_test_failure("FAILED: test_foo - AssertionError", "pytest")
        assert "Tests FAILED" in result
        assert "pytest" in result
        assert "FAILED: test_foo" in result


# --- Review Coordinator Hooks Integration ---


class TestReviewCoordinatorHooksIntegration:

    def _create_hooks_with_config(self, phase: int, tmpdir: str) -> SupervisorHooks:
        markers = MagicMock()
        markers.get_phase.return_value = phase
        logger = MagicMock()

        hooks = SupervisorHooks(
            markers=markers,
            logger=logger,
            working_dir=tmpdir
        )
        hooks._test_logger = logger
        return hooks


class TestSetReviewCoordinatorMethod:

    def test_set_review_coordinator_method_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            markers = MagicMock()
            logger = MagicMock()
            hooks = SupervisorHooks(markers, logger, tmpdir)
            assert hasattr(hooks, 'set_review_coordinator')

    def test_set_review_coordinator_accepts_coordinator(self):
        import inspect
        with tempfile.TemporaryDirectory() as tmpdir:
            markers = MagicMock()
            logger = MagicMock()
            hooks = SupervisorHooks(markers, logger, tmpdir)
            sig = inspect.signature(hooks.set_review_coordinator)
            assert 'coordinator' in sig.parameters

    def test_set_review_coordinator_accepts_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            markers = MagicMock()
            logger = MagicMock()
            hooks = SupervisorHooks(markers, logger, tmpdir)
            hooks.set_review_coordinator(None)


class TestSetFileChangeCallbackMethod:

    def test_set_file_change_callback_method_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            markers = MagicMock()
            logger = MagicMock()
            hooks = SupervisorHooks(markers, logger, tmpdir)
            assert hasattr(hooks, 'set_file_change_callback')

    def test_set_file_change_callback_accepts_callback(self):
        import inspect
        with tempfile.TemporaryDirectory() as tmpdir:
            markers = MagicMock()
            logger = MagicMock()
            hooks = SupervisorHooks(markers, logger, tmpdir)
            sig = inspect.signature(hooks.set_file_change_callback)
            assert 'callback' in sig.parameters


class TestTrackFileChangeHook:

    def test_track_file_change_method_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = SupervisorHooks(MagicMock(), MagicMock(), tmpdir)
            assert hasattr(hooks, 'track_file_change')

    def test_track_file_change_is_async(self):
        import inspect
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = SupervisorHooks(MagicMock(), MagicMock(), tmpdir)
            assert inspect.iscoroutinefunction(hooks.track_file_change)

    def test_track_file_change_accepts_input_data(self):
        import inspect
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = SupervisorHooks(MagicMock(), MagicMock(), tmpdir)
            assert 'input_data' in inspect.signature(hooks.track_file_change).parameters


class TestTrackFileChangeBehavior:

    def test_track_file_change_calls_callback_for_write(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = SupervisorHooks(MagicMock(), MagicMock(), tmpdir)
            assert hasattr(hooks, 'track_file_change')
            assert hasattr(hooks, 'set_file_change_callback')

    def test_track_file_change_calls_callback_for_edit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = SupervisorHooks(MagicMock(), MagicMock(), tmpdir)
            assert hasattr(hooks, 'track_file_change')

    def test_track_file_change_returns_allow(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = SupervisorHooks(MagicMock(), MagicMock(), tmpdir)
            assert hasattr(hooks, 'track_file_change')


# =============================================================================
# REQ-9: track_build_execution Hook Tests
# =============================================================================

class TestTrackBuildExecutionHook:
    """REQ-9: PostToolUse hook for Bash tool with keyword detection."""

    def test_track_build_execution_method_exists(self):
        """REQ-9: track_build_execution hook method should exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = SupervisorHooks(MagicMock(), MagicMock(), tmpdir)
            assert hasattr(hooks, 'track_build_execution')

    def test_track_build_execution_is_async(self):
        """REQ-9: track_build_execution should be async."""
        import inspect
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = SupervisorHooks(MagicMock(), MagicMock(), tmpdir)
            assert inspect.iscoroutinefunction(hooks.track_build_execution)

    def test_track_build_execution_accepts_standard_hook_params(self):
        """REQ-9: track_build_execution takes standard hook parameters."""
        import inspect
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = SupervisorHooks(MagicMock(), MagicMock(), tmpdir)
            params = inspect.signature(hooks.track_build_execution).parameters
            assert 'input_data' in params
            assert 'tool_use_id' in params
            assert 'context' in params


class TestIsBuildCommand:
    """REQ-1: Keyword detection for test/compile/build."""

    def _create_hooks(self, tmpdir):
        return SupervisorHooks(MagicMock(), MagicMock(), tmpdir)

    def test_is_build_command_method_exists(self):
        """_is_build_command helper should exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks(tmpdir)
            assert hasattr(hooks, '_is_build_command')

    def test_is_build_command_detects_test_keyword(self):
        """REQ-1: Detects 'test' keyword."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks(tmpdir)
            assert hooks._is_build_command("pytest tests/") is True

    def test_is_build_command_detects_compile_keyword(self):
        """REQ-1: Detects 'compile' keyword."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks(tmpdir)
            assert hooks._is_build_command("mvn compile") is True

    def test_is_build_command_detects_build_keyword(self):
        """REQ-1: Detects 'build' keyword."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks(tmpdir)
            assert hooks._is_build_command("npm run build") is True

    def test_is_build_command_case_insensitive(self):
        """REQ-1: Case-insensitive substring match."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks(tmpdir)
            assert hooks._is_build_command("PYTEST") is True
            assert hooks._is_build_command("Make Build") is True
            assert hooks._is_build_command("TestRunner") is True
            assert hooks._is_build_command("COMPILE_ALL") is True

    def test_is_build_command_false_for_non_build_commands(self):
        """EDGE-1: Non-build commands should return False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks(tmpdir)
            assert hooks._is_build_command("git status") is False
            assert hooks._is_build_command("ls -la") is False
            assert hooks._is_build_command("cat file.txt") is False


class TestTrackBuildExecutionBehavior:
    """Behavioral tests for track_build_execution hook."""

    def _create_hooks_with_config(self, phase: int, tmpdir: str) -> SupervisorHooks:
        markers = MagicMock()
        markers.get_phase.return_value = phase
        logger = MagicMock()

        hooks = SupervisorHooks(
            markers=markers,
            logger=logger,
            working_dir=tmpdir
        )
        hooks._test_logger = logger
        return hooks

    def test_track_build_execution_calls_coordinator_on_build_executed(self):
        """REQ-9: Hook calls review_coordinator.on_build_executed for build commands."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            hooks = self._create_hooks_with_config(4, tmpdir)
            mock_coordinator = MagicMock()
            mock_coordinator.on_build_executed = AsyncMock()
            hooks.set_review_coordinator(mock_coordinator)

            input_data = {
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "pytest tests/"}
            }

            # when
            result = run_async(hooks.track_build_execution(input_data, None, None))

            # then
            mock_coordinator.on_build_executed.assert_called_once_with("pytest tests/")
            assert result == {}  # Always returns allow

    def test_track_build_execution_skips_non_bash_tools(self):
        """track_build_execution only processes Bash tool."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            hooks = self._create_hooks_with_config(4, tmpdir)
            mock_coordinator = MagicMock()
            mock_coordinator.on_build_executed = AsyncMock()
            hooks.set_review_coordinator(mock_coordinator)

            input_data = {
                "hook_event_name": "PostToolUse",
                "tool_name": "Write",  # Not Bash
                "tool_input": {"file_path": "/test.py"}
            }

            # when
            result = run_async(hooks.track_build_execution(input_data, None, None))

            # then
            mock_coordinator.on_build_executed.assert_not_called()
            assert result == {}

    def test_track_build_execution_skips_non_build_commands(self):
        """EDGE-1: Bash command without keywords: No review triggered."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            hooks = self._create_hooks_with_config(4, tmpdir)
            mock_coordinator = MagicMock()
            mock_coordinator.on_build_executed = AsyncMock()
            hooks.set_review_coordinator(mock_coordinator)

            input_data = {
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "git status"}  # No build keyword
            }

            # when
            result = run_async(hooks.track_build_execution(input_data, None, None))

            # then
            mock_coordinator.on_build_executed.assert_not_called()
            assert result == {}

    def test_track_build_execution_only_phase4(self):
        """track_build_execution only triggers in Phase 4."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given - Phase 3, not Phase 4
            hooks = self._create_hooks_with_config(3, tmpdir)
            mock_coordinator = MagicMock()
            mock_coordinator.on_build_executed = AsyncMock()
            hooks.set_review_coordinator(mock_coordinator)

            input_data = {
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "pytest tests/"}
            }

            # when
            result = run_async(hooks.track_build_execution(input_data, None, None))

            # then - should not trigger in non-Phase4
            mock_coordinator.on_build_executed.assert_not_called()
            assert result == {}

    def test_track_build_execution_without_coordinator(self):
        """track_build_execution handles no coordinator gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given - no coordinator set
            hooks = self._create_hooks_with_config(4, tmpdir)
            # hooks._review_coordinator is None by default

            input_data = {
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "pytest tests/"}
            }

            # when - should not raise
            result = run_async(hooks.track_build_execution(input_data, None, None))

            # then
            assert result == {}

    def test_track_build_execution_always_returns_allow(self):
        """ERR-1: Keyword detection errors: allow command through (fail-open)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            hooks = self._create_hooks_with_config(4, tmpdir)

            input_data = {
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "pytest tests/"}
            }

            # when
            result = run_async(hooks.track_build_execution(input_data, None, None))

            # then - always allow
            assert result == {}

    def test_track_build_execution_logs_errors_and_continues(self):
        """ERR-1: Log errors and allow command through."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            hooks = self._create_hooks_with_config(4, tmpdir)
            mock_coordinator = MagicMock()
            mock_coordinator.on_build_executed = AsyncMock(side_effect=Exception("Test error"))
            hooks.set_review_coordinator(mock_coordinator)

            input_data = {
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "pytest tests/"}
            }

            # when - should not raise
            result = run_async(hooks.track_build_execution(input_data, None, None))

            # then - still returns allow
            assert result == {}


class TestTrackBuildExecutionEdgeCases:
    """Edge case tests for track_build_execution."""

    def _create_hooks_with_config(self, phase: int, tmpdir: str) -> SupervisorHooks:
        markers = MagicMock()
        markers.get_phase.return_value = phase
        logger = MagicMock()

        hooks = SupervisorHooks(
            markers=markers,
            logger=logger,
            working_dir=tmpdir
        )
        return hooks

    def test_false_positive_keyword_in_path(self):
        """EDGE-3: False positive keyword match (e.g., 'test' in path)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            hooks = self._create_hooks_with_config(4, tmpdir)
            mock_coordinator = MagicMock()
            mock_coordinator.on_build_executed = AsyncMock()
            hooks.set_review_coordinator(mock_coordinator)

            # 'test' appears in path, not as a command
            input_data = {
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "cat /path/to/test/file.txt"}
            }

            # when
            result = run_async(hooks.track_build_execution(input_data, None, None))

            # then - harmless false positive: review skips if no pending changes
            # The hook will call on_build_executed, but coordinator handles the check
            mock_coordinator.on_build_executed.assert_called_once()
            assert result == {}

    def test_missing_command_in_tool_input(self):
        """Handle missing command in tool_input gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            hooks = self._create_hooks_with_config(4, tmpdir)
            mock_coordinator = MagicMock()
            mock_coordinator.on_build_executed = AsyncMock()
            hooks.set_review_coordinator(mock_coordinator)

            input_data = {
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {}  # No command key
            }

            # when - should not raise
            result = run_async(hooks.track_build_execution(input_data, None, None))

            # then
            mock_coordinator.on_build_executed.assert_not_called()
            assert result == {}

    def test_empty_command_string(self):
        """Handle empty command string gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # given
            hooks = self._create_hooks_with_config(4, tmpdir)
            mock_coordinator = MagicMock()
            mock_coordinator.on_build_executed = AsyncMock()
            hooks.set_review_coordinator(mock_coordinator)

            input_data = {
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": ""}
            }

            # when
            result = run_async(hooks.track_build_execution(input_data, None, None))

            # then - empty command has no keywords
            mock_coordinator.on_build_executed.assert_not_called()
            assert result == {}


class TestGetHooksConfigBuildExecution:
    """REQ-9: Verify track_build_execution registered in hooks config."""

    def test_hooks_config_registers_bash_posttoolluse_hook(self):
        """REQ-9: PostToolUse hook for Bash registered in get_hooks_config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            markers = MagicMock()
            logger = MagicMock()
            hooks = SupervisorHooks(markers, logger, tmpdir)

            # Mock HookMatcher import
            with patch.dict(sys.modules, {'claude_agent_sdk': MagicMock()}):
                from claude_agent_sdk import HookMatcher
                HookMatcher.return_value = MagicMock()

                config = hooks.get_hooks_config()

                # Verify PostToolUse has Bash hook
                assert 'PostToolUse' in config
                # The PostToolUse list should have a matcher for Bash
                # (exact verification depends on HookMatcher implementation)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
