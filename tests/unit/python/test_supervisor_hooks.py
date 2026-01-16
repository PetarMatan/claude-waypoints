#!/usr/bin/env python3
"""
Unit tests for wp_supervisor/hooks.py
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add paths for imports
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
    """Helper to run async functions in tests."""
    import asyncio
    return asyncio.run(coro)


class TestHookMessages:
    """Tests for hook_messages.py"""

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
    """Tests for SupervisorHooks class"""

    def _create_hooks(self, phase: int = 1) -> SupervisorHooks:
        """Create SupervisorHooks with mocked dependencies."""
        markers = MagicMock()
        markers.get_phase.return_value = phase

        logger = MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a minimal pom.xml for profile detection
            pom = Path(tmpdir) / "pom.xml"
            pom.write_text("<project></project>")

            hooks = SupervisorHooks(
                markers=markers,
                logger=logger,
                working_dir=tmpdir
            )
            # Store refs for assertions
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
    """Tests for phase_guard hook callback"""

    def _create_hooks_with_config(self, phase: int, tmpdir: str) -> SupervisorHooks:
        """Create hooks with proper config setup."""
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
            # Create pom.xml for Maven profile detection
            (Path(tmpdir) / "pom.xml").write_text("<project></project>")

            hooks = self._create_hooks_with_config(1, tmpdir)
            # Force config to recognize as main source
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
    """Tests for log_tool_use hook callback"""

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
    """Tests for get_hooks_config method"""

    def test_returns_empty_without_sdk(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            markers = MagicMock()
            logger = MagicMock()
            hooks = SupervisorHooks(markers, logger, tmpdir)

            # Mock ImportError for HookMatcher
            with patch.dict(sys.modules, {'claude_agent_sdk': None}):
                # Force reimport to trigger ImportError
                result = hooks.get_hooks_config()
                # Should return empty dict or valid config
                assert isinstance(result, dict)


class TestBuildVerifyHook:
    """Tests for build_verify Stop hook callback"""

    def _create_hooks_with_config(self, phase: int, tmpdir: str) -> SupervisorHooks:
        """Create hooks with mocked config."""
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
        """Phase 1 should not run any build verification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(1, tmpdir)
            input_data = {"cwd": tmpdir}
            result = run_async(hooks.build_verify(input_data, None, None))
            assert result == {}

    def test_skips_when_stop_hook_active(self):
        """Should skip if stop_hook_active flag is set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(4, tmpdir)
            input_data = {"cwd": tmpdir, "stop_hook_active": True}
            result = run_async(hooks.build_verify(input_data, None, None))
            assert result == {}

    def test_skips_when_no_cwd(self):
        """Should skip if no cwd provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(4, tmpdir)
            input_data = {}
            result = run_async(hooks.build_verify(input_data, None, None))
            assert result == {}

    def test_phase2_runs_compile_command(self):
        """Phase 2 should run compile command."""
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
        """Phase 2 compile failure should block."""
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
        """Phase 3 should run testCompile command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(3, tmpdir)
            hooks.config.get_profile_name = MagicMock(return_value="python")
            hooks.config.get_command = MagicMock(side_effect=lambda cmd: "echo compile" if cmd == "compile" else "echo testCompile" if cmd == "testCompile" else None)
            hooks._run_command = MagicMock(return_value=(0, "success"))

            input_data = {"cwd": tmpdir}
            result = run_async(hooks.build_verify(input_data, None, None))

            # Should have called _run_command once with testCompile
            hooks._run_command.assert_called_once()
            assert result == {}

    def test_phase3_falls_back_to_compile(self):
        """Phase 3 should fall back to compile if no testCompile."""
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
        """Phase 4 should run compile and test commands."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(4, tmpdir)
            hooks.config.get_profile_name = MagicMock(return_value="python")
            hooks.config.get_command = MagicMock(side_effect=lambda cmd: f"echo {cmd}")
            hooks._run_command = MagicMock(return_value=(0, "success"))

            input_data = {"cwd": tmpdir}
            result = run_async(hooks.build_verify(input_data, None, None))

            # Should have called compile and test
            assert hooks._run_command.call_count == 2
            assert result == {}

    def test_phase4_test_failure_blocks(self):
        """Phase 4 test failure should block."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(4, tmpdir)
            hooks.config.get_profile_name = MagicMock(return_value="python")
            hooks.config.get_command = MagicMock(side_effect=lambda cmd: f"echo {cmd}")
            # First call (compile) succeeds, second (test) fails
            hooks._run_command = MagicMock(side_effect=[(0, "OK"), (1, "FAILED: 2 tests failed")])

            input_data = {"cwd": tmpdir}
            result = run_async(hooks.build_verify(input_data, None, None))

            assert result.get("continue") is False
            assert "Tests FAILED" in result["stopReason"]

    def test_skips_commands_with_placeholders(self):
        """Should skip commands with unreplaced placeholders."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(2, tmpdir)
            hooks.config.get_profile_name = MagicMock(return_value="python")
            hooks.config.get_command = MagicMock(return_value="python -m py_compile {file}")
            hooks._run_command = MagicMock(return_value=(0, "success"))

            input_data = {"cwd": tmpdir}
            result = run_async(hooks.build_verify(input_data, None, None))

            # Should not call _run_command because of {file} placeholder
            hooks._run_command.assert_not_called()
            assert result == {}

    def test_has_placeholder_detects_file(self):
        """_has_placeholder should detect {file}."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(1, tmpdir)
            assert hooks._has_placeholder("python {file}") is True
            assert hooks._has_placeholder("python test.py") is False

    def test_has_placeholder_detects_test_placeholders(self):
        """_has_placeholder should detect test placeholders."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = self._create_hooks_with_config(1, tmpdir)
            assert hooks._has_placeholder("mvn test -Dtest={testClass}") is True
            assert hooks._has_placeholder("pytest {testFile}") is True
            assert hooks._has_placeholder("go test -run {testName}") is True


class TestBuildVerifyMessages:
    """Tests for build verification message templates."""

    def test_format_compile_error(self):
        result = format_compile_error("SyntaxError: invalid syntax", "python", "python -m compileall .")
        assert "Compilation FAILED" in result
        assert "python" in result
        assert "SyntaxError" in result
        assert "python -m compileall" in result

    def test_format_compile_error_truncates_output(self):
        long_output = "x" * 3000
        result = format_compile_error(long_output, "maven", "mvn compile")
        # Should be truncated to 2000 chars
        assert len(result) < 2500

    def test_format_test_failure(self):
        result = format_test_failure("FAILED: test_foo - AssertionError", "pytest")
        assert "Tests FAILED" in result
        assert "pytest" in result
        assert "FAILED: test_foo" in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
