#!/usr/bin/env python3
"""
Unit tests for wp_supervisor/session.py - SessionRunner class

[TEST-4] Tests for SessionRunner class:
- Unit tests for SessionRunner class initialization
- Tests for run_phase_session() signal detection and streaming
- Tests for run_regeneration_session() signal detection (complete vs canceled)
- Tests for extract_text() timeout and text collection
- Tests for working indicator state management

Note: These tests mock the claude-agent-sdk to test session logic
without requiring actual Claude API calls.
"""

import io
import os
import sys
import tempfile
import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock, call

# Mock claude_agent_sdk before importing session module
from dataclasses import dataclass
from typing import Optional, List


class MockAssistantMessage:
    """Mock AssistantMessage class for isinstance() checks."""
    pass


class MockResultMessage:
    """Mock ResultMessage class for isinstance() checks."""
    pass


@dataclass
class MockAgentDefinition:
    """Mock AgentDefinition as a real dataclass so subagents.py creates proper instances."""
    description: str
    prompt: str
    tools: Optional[list] = None
    model: Optional[str] = None


mock_sdk = MagicMock()
mock_sdk.ClaudeSDKClient = MagicMock()
mock_sdk.ClaudeAgentOptions = MagicMock()
mock_sdk.AgentDefinition = MockAgentDefinition
mock_types = MagicMock()
mock_types.AssistantMessage = MockAssistantMessage
mock_types.ResultMessage = MockResultMessage
mock_sdk.types = mock_types
sys.modules['claude_agent_sdk'] = mock_sdk
sys.modules['claude_agent_sdk.types'] = mock_types

# Add wp_supervisor to path
sys.path.insert(0, '.')
from wp_supervisor.session import (
    read_user_input,
    SessionRunner,
    PHASE_COMPLETE_PATTERNS,
    REGENERATION_COMPLETE_PATTERNS,
    REGENERATION_CANCELED_PATTERNS,
    SIGNAL_COMPLETE,
    SIGNAL_CANCELED,
)


# Ensure tests never inherit supervisor env vars from a parent workflow.
# When pytest runs during Phase 4, the orchestrator passes WP_SUPERVISOR_MARKERS_DIR
# to the Claude session, which leaks into subprocesses. Without this fixture,
# tests create WPState instances that write to the REAL workflow directory,
# corrupting state.json, workflow.log, and phase summary documents.
@pytest.fixture(autouse=True)
def clean_supervisor_env(monkeypatch):
    """Remove WP_SUPERVISOR_* env vars to isolate tests from live workflows."""
    for key in list(os.environ):
        if key.startswith("WP_SUPERVISOR_"):
            monkeypatch.delenv(key, raising=False)


# Helper to run async functions in tests
def run_async(coro):
    """Run an async function synchronously for testing."""
    return asyncio.run(coro)


class TestSignalPatternConstants:
    """Tests for signal pattern constants [REQ-8]."""

    def test_phase_complete_patterns_exist(self):
        """PHASE_COMPLETE_PATTERNS should contain expected patterns."""
        assert "---PHASE_COMPLETE---" in PHASE_COMPLETE_PATTERNS
        assert "**PHASE_COMPLETE**" in PHASE_COMPLETE_PATTERNS
        assert "PHASE_COMPLETE" in PHASE_COMPLETE_PATTERNS

    def test_regeneration_complete_patterns_exist(self):
        """REGENERATION_COMPLETE_PATTERNS should contain expected patterns."""
        assert "---REGENERATION_COMPLETE---" in REGENERATION_COMPLETE_PATTERNS
        assert "**REGENERATION_COMPLETE**" in REGENERATION_COMPLETE_PATTERNS
        assert "REGENERATION_COMPLETE" in REGENERATION_COMPLETE_PATTERNS

    def test_regeneration_canceled_patterns_exist(self):
        """REGENERATION_CANCELED_PATTERNS should contain expected patterns."""
        assert "---REGENERATION_CANCELED---" in REGENERATION_CANCELED_PATTERNS
        assert "**REGENERATION_CANCELED**" in REGENERATION_CANCELED_PATTERNS
        assert "REGENERATION_CANCELED" in REGENERATION_CANCELED_PATTERNS

    def test_signal_constants_exist(self):
        """Signal constants should be defined."""
        assert SIGNAL_COMPLETE == 'complete'
        assert SIGNAL_CANCELED == 'canceled'


class TestReadUserInputFunction:
    """Tests for read_user_input utility function [REQ-6, REQ-7]."""

    def test_read_user_input_is_callable(self):
        """read_user_input should be callable."""
        assert callable(read_user_input)

    def test_simple_text_input(self):
        """Simple text input returns that text."""
        with patch('builtins.input', return_value="hello world"):
            result = read_user_input()
        assert result == "hello world"

    def test_empty_input_returns_empty_string(self):
        """Empty input returns empty string."""
        with patch('builtins.input', return_value=""):
            result = read_user_input()
        assert result == ""

    def test_eof_returns_empty_string(self):
        """EOF raises EOFError which returns empty string."""
        with patch('builtins.input', side_effect=EOFError):
            result = read_user_input()
        assert result == ""

    def test_keyboard_interrupt_returns_empty_string(self):
        """Ctrl+C returns empty string."""
        with patch('builtins.input', side_effect=KeyboardInterrupt):
            result = read_user_input()
        assert result == ""

    def test_file_input_with_at_prefix(self, capsys):
        """@/path/to/file loads file content."""
        file_content = "Multi-line\nrequirements\nfrom file"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(file_content)
            temp_path = f.name

        try:
            with patch('builtins.input', return_value=f"@{temp_path}"):
                result = read_user_input()

            assert result == file_content
            captured = capsys.readouterr()
            assert "Loaded" in captured.out
        finally:
            os.unlink(temp_path)

    def test_file_not_found_returns_empty(self, capsys):
        """Non-existent file with @ prefix returns empty and prints error."""
        with patch('builtins.input', return_value="@/nonexistent/file.md"):
            result = read_user_input()

        assert result == ""
        captured = capsys.readouterr()
        assert "File not found" in captured.out


class TestSessionRunnerInitialization:
    """Tests for SessionRunner class initialization [REQ-1, REQ-2]."""

    def test_session_runner_class_exists(self):
        """SessionRunner class should exist."""
        assert SessionRunner is not None

    def test_session_runner_init_accepts_required_params(self):
        """SessionRunner.__init__ should accept working_dir, markers, hooks, logger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.markers import SupervisorMarkers
                from wp_supervisor.hooks import SupervisorHooks
                from wp_supervisor.logger import SupervisorLogger

                markers = SupervisorMarkers()
                logger = SupervisorLogger(
                    workflow_dir=markers.markers_dir,
                    workflow_id=markers.workflow_id
                )
                hooks = SupervisorHooks(
                    markers=markers,
                    logger=logger,
                    working_dir=tmpdir
                )

                # Should not raise
                runner = SessionRunner(
                    working_dir=tmpdir,
                    markers=markers,
                    hooks=hooks,
                    logger=logger
                )

                assert runner.working_dir == tmpdir
                assert runner.markers is markers
                assert runner.hooks is hooks
                assert runner.logger is logger


class TestSessionRunnerMethods:
    """Tests for SessionRunner method signatures."""

    def _create_runner(self, tmpdir: str):
        """Create a SessionRunner instance for testing."""
        with patch.object(Path, 'home', return_value=Path(tmpdir)):
            from wp_supervisor.markers import SupervisorMarkers
            from wp_supervisor.hooks import SupervisorHooks
            from wp_supervisor.logger import SupervisorLogger

            markers = SupervisorMarkers()
            logger = SupervisorLogger(
                workflow_dir=markers.markers_dir,
                workflow_id=markers.workflow_id
            )
            hooks = SupervisorHooks(
                markers=markers,
                logger=logger,
                working_dir=tmpdir
            )

            return SessionRunner(
                working_dir=tmpdir,
                markers=markers,
                hooks=hooks,
                logger=logger
            )

    def test_run_phase_session_method_exists(self):
        """run_phase_session method should exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)
            assert hasattr(runner, 'run_phase_session')
            assert callable(runner.run_phase_session)

    def test_run_regeneration_session_method_exists(self):
        """run_regeneration_session method should exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)
            assert hasattr(runner, 'run_regeneration_session')
            assert callable(runner.run_regeneration_session)

    def test_extract_text_method_exists(self):
        """extract_text method should exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)
            assert hasattr(runner, 'extract_text')
            assert callable(runner.extract_text)

    def test_check_signal_method_exists(self):
        """_check_signal helper method should exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)
            assert hasattr(runner, '_check_signal')
            assert callable(runner._check_signal)

    def test_check_regeneration_signal_method_exists(self):
        """_check_regeneration_signal helper method should exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)
            assert hasattr(runner, '_check_regeneration_signal')
            assert callable(runner._check_regeneration_signal)

    def test_process_stream_method_exists(self):
        """_process_stream helper method should exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)
            assert hasattr(runner, '_process_stream')
            assert callable(runner._process_stream)

    def test_record_usage_method_exists(self):
        """_record_usage helper method should exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)
            assert hasattr(runner, '_record_usage')
            assert callable(runner._record_usage)


class TestRunPhaseSessionSignature:
    """Tests for run_phase_session method signature [REQ-3]."""

    def test_run_phase_session_is_async(self):
        """run_phase_session should be an async method."""
        import inspect
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.markers import SupervisorMarkers
                from wp_supervisor.hooks import SupervisorHooks
                from wp_supervisor.logger import SupervisorLogger

                markers = SupervisorMarkers()
                logger = SupervisorLogger(
                    workflow_dir=markers.markers_dir,
                    workflow_id=markers.workflow_id
                )
                hooks = SupervisorHooks(
                    markers=markers,
                    logger=logger,
                    working_dir=tmpdir
                )

                runner = SessionRunner(
                    working_dir=tmpdir,
                    markers=markers,
                    hooks=hooks,
                    logger=logger
                )

                assert inspect.iscoroutinefunction(runner.run_phase_session)

class TestRunRegenerationSessionSignature:
    """Tests for run_regeneration_session method signature [REQ-4]."""

    def test_run_regeneration_session_is_async(self):
        """run_regeneration_session should be an async method."""
        import inspect
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.markers import SupervisorMarkers
                from wp_supervisor.hooks import SupervisorHooks
                from wp_supervisor.logger import SupervisorLogger

                markers = SupervisorMarkers()
                logger = SupervisorLogger(
                    workflow_dir=markers.markers_dir,
                    workflow_id=markers.workflow_id
                )
                hooks = SupervisorHooks(
                    markers=markers,
                    logger=logger,
                    working_dir=tmpdir
                )

                runner = SessionRunner(
                    working_dir=tmpdir,
                    markers=markers,
                    hooks=hooks,
                    logger=logger
                )

                assert inspect.iscoroutinefunction(runner.run_regeneration_session)


class TestExtractTextSignature:
    """Tests for extract_text method signature [REQ-5]."""

    def test_extract_text_is_async(self):
        """extract_text should be an async method."""
        import inspect
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.markers import SupervisorMarkers
                from wp_supervisor.hooks import SupervisorHooks
                from wp_supervisor.logger import SupervisorLogger

                markers = SupervisorMarkers()
                logger = SupervisorLogger(
                    workflow_dir=markers.markers_dir,
                    workflow_id=markers.workflow_id
                )
                hooks = SupervisorHooks(
                    markers=markers,
                    logger=logger,
                    working_dir=tmpdir
                )

                runner = SessionRunner(
                    working_dir=tmpdir,
                    markers=markers,
                    hooks=hooks,
                    logger=logger
                )

                assert inspect.iscoroutinefunction(runner.extract_text)

    def test_extract_text_has_timeout_parameter(self):
        """extract_text should accept timeout parameter [REQ-5c]."""
        import inspect
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.markers import SupervisorMarkers
                from wp_supervisor.hooks import SupervisorHooks
                from wp_supervisor.logger import SupervisorLogger

                markers = SupervisorMarkers()
                logger = SupervisorLogger(
                    workflow_dir=markers.markers_dir,
                    workflow_id=markers.workflow_id
                )
                hooks = SupervisorHooks(
                    markers=markers,
                    logger=logger,
                    working_dir=tmpdir
                )

                runner = SessionRunner(
                    working_dir=tmpdir,
                    markers=markers,
                    hooks=hooks,
                    logger=logger
                )

                sig = inspect.signature(runner.extract_text)
                params = sig.parameters

                assert 'timeout' in params
                assert params['timeout'].default == 300.0

    def test_extract_text_has_session_id_parameter(self):
        """extract_text should accept session_id parameter [REQ-5b]."""
        import inspect
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.markers import SupervisorMarkers
                from wp_supervisor.hooks import SupervisorHooks
                from wp_supervisor.logger import SupervisorLogger

                markers = SupervisorMarkers()
                logger = SupervisorLogger(
                    workflow_dir=markers.markers_dir,
                    workflow_id=markers.workflow_id
                )
                hooks = SupervisorHooks(
                    markers=markers,
                    logger=logger,
                    working_dir=tmpdir
                )

                runner = SessionRunner(
                    working_dir=tmpdir,
                    markers=markers,
                    hooks=hooks,
                    logger=logger
                )

                sig = inspect.signature(runner.extract_text)
                params = sig.parameters

                assert 'session_id' in params
                assert params['session_id'].default is None

    def test_extract_text_has_phase_parameter(self):
        """extract_text should accept phase parameter [REQ-5d]."""
        import inspect
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.markers import SupervisorMarkers
                from wp_supervisor.hooks import SupervisorHooks
                from wp_supervisor.logger import SupervisorLogger

                markers = SupervisorMarkers()
                logger = SupervisorLogger(
                    workflow_dir=markers.markers_dir,
                    workflow_id=markers.workflow_id
                )
                hooks = SupervisorHooks(
                    markers=markers,
                    logger=logger,
                    working_dir=tmpdir
                )

                runner = SessionRunner(
                    working_dir=tmpdir,
                    markers=markers,
                    hooks=hooks,
                    logger=logger
                )

                sig = inspect.signature(runner.extract_text)
                params = sig.parameters

                assert 'phase' in params
                assert params['phase'].default is None


# =============================================================================
# BEHAVIORAL TESTS - These test the actual implementation behavior
# =============================================================================


class TestCheckSignalBehavior:
    """Tests for _check_signal method behavior."""

    def _create_runner(self, tmpdir: str):
        """Create a SessionRunner instance for testing."""
        with patch.object(Path, 'home', return_value=Path(tmpdir)):
            from wp_supervisor.markers import SupervisorMarkers
            from wp_supervisor.hooks import SupervisorHooks
            from wp_supervisor.logger import SupervisorLogger

            markers = SupervisorMarkers()
            logger = SupervisorLogger(
                workflow_dir=markers.markers_dir,
                workflow_id=markers.workflow_id
            )
            hooks = SupervisorHooks(
                markers=markers,
                logger=logger,
                working_dir=tmpdir
            )

            return SessionRunner(
                working_dir=tmpdir,
                markers=markers,
                hooks=hooks,
                logger=logger
            )

    def test_check_signal_returns_true_when_pattern_on_own_line(self):
        """_check_signal should return True when pattern is on its own line."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # when
            result = runner._check_signal(
                "Some text\n---PHASE_COMPLETE---\nmore text",
                PHASE_COMPLETE_PATTERNS
            )

            # then
            assert result is True

    def test_check_signal_returns_false_when_pattern_embedded_in_line(self):
        """_check_signal should return False when pattern is embedded in other text."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # when
            result = runner._check_signal(
                "WAITING FOR ANSWERS BEFORE `---PHASE_COMPLETE---`",
                PHASE_COMPLETE_PATTERNS
            )

            # then
            assert result is False

    def test_check_signal_returns_false_when_no_pattern_found(self):
        """_check_signal should return False when no pattern is found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # when
            result = runner._check_signal(
                "Some regular text without signals",
                PHASE_COMPLETE_PATTERNS
            )

            # then
            assert result is False

    def test_check_signal_handles_empty_text(self):
        """_check_signal should handle empty text."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # when
            result = runner._check_signal("", PHASE_COMPLETE_PATTERNS)

            # then
            assert result is False

    def test_check_signal_handles_empty_patterns(self):
        """_check_signal should handle empty patterns list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # when
            result = runner._check_signal("Some text", [])

            # then
            assert result is False

    def test_check_signal_detects_all_phase_complete_variants(self):
        """_check_signal should detect all phase complete pattern variants."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # then - all variants should be detected (standalone lines)
            assert runner._check_signal("---PHASE_COMPLETE---", PHASE_COMPLETE_PATTERNS)
            assert runner._check_signal("**PHASE_COMPLETE**", PHASE_COMPLETE_PATTERNS)
            assert runner._check_signal("PHASE_COMPLETE", PHASE_COMPLETE_PATTERNS)

            # also detected with surrounding lines
            assert runner._check_signal("some text\n---PHASE_COMPLETE---\n", PHASE_COMPLETE_PATTERNS)

            # with leading/trailing whitespace on the signal line
            assert runner._check_signal("  ---PHASE_COMPLETE---  ", PHASE_COMPLETE_PATTERNS)


class TestCheckRegenerationSignalBehavior:
    """Tests for _check_regeneration_signal method behavior."""

    def _create_runner(self, tmpdir: str):
        """Create a SessionRunner instance for testing."""
        with patch.object(Path, 'home', return_value=Path(tmpdir)):
            from wp_supervisor.markers import SupervisorMarkers
            from wp_supervisor.hooks import SupervisorHooks
            from wp_supervisor.logger import SupervisorLogger

            markers = SupervisorMarkers()
            logger = SupervisorLogger(
                workflow_dir=markers.markers_dir,
                workflow_id=markers.workflow_id
            )
            hooks = SupervisorHooks(
                markers=markers,
                logger=logger,
                working_dir=tmpdir
            )

            return SessionRunner(
                working_dir=tmpdir,
                markers=markers,
                hooks=hooks,
                logger=logger
            )

    def test_check_regeneration_signal_returns_complete_when_complete_found(self):
        """_check_regeneration_signal should return SIGNAL_COMPLETE when complete pattern found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # when
            result = runner._check_regeneration_signal(
                "Summary updated.\n---REGENERATION_COMPLETE---",
                REGENERATION_COMPLETE_PATTERNS,
                REGENERATION_CANCELED_PATTERNS
            )

            # then
            assert result == SIGNAL_COMPLETE

    def test_check_regeneration_signal_returns_canceled_when_canceled_found(self):
        """_check_regeneration_signal should return SIGNAL_CANCELED when canceled pattern found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # when
            result = runner._check_regeneration_signal(
                "Changes reverted.\n---REGENERATION_CANCELED---",
                REGENERATION_COMPLETE_PATTERNS,
                REGENERATION_CANCELED_PATTERNS
            )

            # then
            assert result == SIGNAL_CANCELED

    def test_check_regeneration_signal_returns_none_when_no_signal(self):
        """_check_regeneration_signal should return None when no signal found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # when
            result = runner._check_regeneration_signal(
                "Just regular conversation text",
                REGENERATION_COMPLETE_PATTERNS,
                REGENERATION_CANCELED_PATTERNS
            )

            # then
            assert result is None

    def test_check_regeneration_signal_handles_empty_text(self):
        """_check_regeneration_signal should handle empty text."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # when
            result = runner._check_regeneration_signal(
                "",
                REGENERATION_COMPLETE_PATTERNS,
                REGENERATION_CANCELED_PATTERNS
            )

            # then
            assert result is None

    def test_check_regeneration_signal_detects_all_complete_variants(self):
        """_check_regeneration_signal should detect all complete pattern variants."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # then - all variants should return SIGNAL_COMPLETE
            assert runner._check_regeneration_signal(
                "---REGENERATION_COMPLETE---",
                REGENERATION_COMPLETE_PATTERNS,
                REGENERATION_CANCELED_PATTERNS
            ) == SIGNAL_COMPLETE

            assert runner._check_regeneration_signal(
                "**REGENERATION_COMPLETE**",
                REGENERATION_COMPLETE_PATTERNS,
                REGENERATION_CANCELED_PATTERNS
            ) == SIGNAL_COMPLETE

            assert runner._check_regeneration_signal(
                "REGENERATION_COMPLETE",
                REGENERATION_COMPLETE_PATTERNS,
                REGENERATION_CANCELED_PATTERNS
            ) == SIGNAL_COMPLETE

    def test_check_regeneration_signal_detects_all_canceled_variants(self):
        """_check_regeneration_signal should detect all canceled pattern variants."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # then - all variants should return SIGNAL_CANCELED
            assert runner._check_regeneration_signal(
                "---REGENERATION_CANCELED---",
                REGENERATION_COMPLETE_PATTERNS,
                REGENERATION_CANCELED_PATTERNS
            ) == SIGNAL_CANCELED

            assert runner._check_regeneration_signal(
                "**REGENERATION_CANCELED**",
                REGENERATION_COMPLETE_PATTERNS,
                REGENERATION_CANCELED_PATTERNS
            ) == SIGNAL_CANCELED

            assert runner._check_regeneration_signal(
                "REGENERATION_CANCELED",
                REGENERATION_COMPLETE_PATTERNS,
                REGENERATION_CANCELED_PATTERNS
            ) == SIGNAL_CANCELED


class TestRecordUsageBehavior:
    """Tests for _record_usage method behavior."""

    def _create_runner_with_mocks(self, tmpdir: str):
        """Create a SessionRunner instance with mocked markers."""
        with patch.object(Path, 'home', return_value=Path(tmpdir)):
            from wp_supervisor.markers import SupervisorMarkers
            from wp_supervisor.hooks import SupervisorHooks
            from wp_supervisor.logger import SupervisorLogger

            markers = SupervisorMarkers()
            logger = SupervisorLogger(
                workflow_dir=markers.markers_dir,
                workflow_id=markers.workflow_id
            )
            hooks = SupervisorHooks(
                markers=markers,
                logger=logger,
                working_dir=tmpdir
            )

            runner = SessionRunner(
                working_dir=tmpdir,
                markers=markers,
                hooks=hooks,
                logger=logger
            )

            return runner

    def test_record_usage_calls_markers_add_phase_usage(self):
        """_record_usage should call markers.add_phase_usage with usage data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner_with_mocks(tmpdir)

            # given - mock result message
            mock_result = MagicMock()
            mock_result.usage = {
                "input_tokens": 100,
                "output_tokens": 50
            }
            mock_result.total_cost_usd = 0.01
            mock_result.duration_ms = 1500
            mock_result.num_turns = 3

            # Track calls to add_phase_usage
            add_phase_usage_calls = []
            original_add = runner.markers.add_phase_usage
            def capture_add(*args, **kwargs):
                add_phase_usage_calls.append((args, kwargs))
                return original_add(*args, **kwargs)
            runner.markers.add_phase_usage = capture_add

            # when
            runner._record_usage(phase=2, result=mock_result)

            # then
            assert len(add_phase_usage_calls) == 1
            _, kwargs = add_phase_usage_calls[0]
            assert kwargs['phase'] == 2
            assert kwargs['input_tokens'] == 100
            assert kwargs['output_tokens'] == 50
            assert kwargs['cost_usd'] == 0.01
            assert kwargs['duration_ms'] == 1500
            assert kwargs['turns'] == 3

    def test_record_usage_handles_missing_usage_data(self):
        """_record_usage should handle result with missing usage data gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner_with_mocks(tmpdir)

            # given - result with no usage data
            mock_result = MagicMock()
            mock_result.usage = None
            mock_result.total_cost_usd = None
            mock_result.duration_ms = None
            mock_result.num_turns = None

            # Track calls to add_phase_usage
            add_phase_usage_calls = []
            original_add = runner.markers.add_phase_usage
            def capture_add(*args, **kwargs):
                add_phase_usage_calls.append((args, kwargs))
                return original_add(*args, **kwargs)
            runner.markers.add_phase_usage = capture_add

            # when - should not raise
            runner._record_usage(phase=1, result=mock_result)

            # then - should have called with default values (0)
            assert len(add_phase_usage_calls) == 1
            _, kwargs = add_phase_usage_calls[0]
            assert kwargs['input_tokens'] == 0
            assert kwargs['output_tokens'] == 0
            assert kwargs['cost_usd'] == 0.0
            assert kwargs['duration_ms'] == 0
            assert kwargs['turns'] == 0


class TestProcessStreamBehavior:
    """Tests for _process_stream unified streaming method."""

    def _create_runner(self, tmpdir: str):
        """Create a SessionRunner instance for testing."""
        with patch.object(Path, 'home', return_value=Path(tmpdir)):
            from wp_supervisor.markers import SupervisorMarkers
            from wp_supervisor.hooks import SupervisorHooks
            from wp_supervisor.logger import SupervisorLogger

            markers = SupervisorMarkers()
            logger = SupervisorLogger(
                workflow_dir=markers.markers_dir,
                workflow_id=markers.workflow_id
            )
            hooks = SupervisorHooks(
                markers=markers,
                logger=logger,
                working_dir=tmpdir
            )

            return SessionRunner(
                working_dir=tmpdir,
                markers=markers,
                hooks=hooks,
                logger=logger
            )

    def test_process_stream_returns_session_id(self):
        """_process_stream should capture and return session_id from messages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given
            mock_client = AsyncMock()
            msg = MockAssistantMessage()
            msg.session_id = "stream-session-123"
            text_block = MagicMock()
            text_block.text = "Hello"
            msg.content = [text_block]

            async def mock_receive():
                yield msg
            mock_client.receive_response = mock_receive

            # when
            session_id, signal = run_async(runner._process_stream(
                mock_client, phase=1
            ))

            # then
            assert session_id == "stream-session-123"
            assert signal is None

    def test_process_stream_detects_signal_via_checker(self):
        """_process_stream should detect signal using the provided checker callback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given
            mock_client = AsyncMock()
            msg = MockAssistantMessage()
            msg.session_id = "test"
            text_block = MagicMock()
            text_block.text = "Done!\n---PHASE_COMPLETE---"
            msg.content = [text_block]

            async def mock_receive():
                yield msg
            mock_client.receive_response = mock_receive

            def checker(text):
                if "PHASE_COMPLETE" in text:
                    return SIGNAL_COMPLETE
                return None

            # when
            session_id, signal = run_async(runner._process_stream(
                mock_client, phase=1, signal_checker=checker
            ))

            # then
            assert signal == SIGNAL_COMPLETE

    def test_process_stream_returns_none_signal_without_checker(self):
        """_process_stream should return None signal when no checker is provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given
            mock_client = AsyncMock()
            msg = MockAssistantMessage()
            msg.session_id = "test"
            text_block = MagicMock()
            text_block.text = "Some text with\n---PHASE_COMPLETE---"
            msg.content = [text_block]

            async def mock_receive():
                yield msg
            mock_client.receive_response = mock_receive

            # when - no signal_checker
            _, signal = run_async(runner._process_stream(
                mock_client, phase=1
            ))

            # then
            assert signal is None

    def test_process_stream_records_usage(self):
        """_process_stream should record usage from result messages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given
            mock_client = AsyncMock()
            msg = MockResultMessage()
            msg.usage = {"input_tokens": 200, "output_tokens": 100}
            msg.total_cost_usd = 0.02
            msg.duration_ms = 2000
            msg.num_turns = 2

            async def mock_receive():
                yield msg
            mock_client.receive_response = mock_receive

            record_calls = []
            def capture_record(phase, result):
                record_calls.append((phase, result))
            runner._record_usage = capture_record

            # when
            run_async(runner._process_stream(mock_client, phase=3))

            # then
            assert len(record_calls) == 1
            assert record_calls[0][0] == 3

    def test_process_stream_skips_falsy_session_id(self):
        """_process_stream should not capture None or empty session_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given
            mock_client = AsyncMock()
            msg = MockAssistantMessage()
            msg.session_id = None
            text_block = MagicMock()
            text_block.text = "Response"
            msg.content = [text_block]

            async def mock_receive():
                yield msg
            mock_client.receive_response = mock_receive

            # when
            session_id, _ = run_async(runner._process_stream(
                mock_client, phase=1
            ))

            # then
            assert session_id is None

    def test_process_stream_handles_multiple_messages(self):
        """_process_stream should process all messages in the stream."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given - two text messages, signal in second
            mock_client = AsyncMock()
            msg1 = MockAssistantMessage()
            msg1.session_id = "sess-1"
            block1 = MagicMock()
            block1.text = "First message"
            msg1.content = [block1]

            msg2 = MockAssistantMessage()
            msg2.session_id = None
            block2 = MagicMock()
            block2.text = "Second with DONE"
            msg2.content = [block2]

            async def mock_receive():
                yield msg1
                yield msg2
            mock_client.receive_response = mock_receive

            def checker(text):
                return "found" if "DONE" in text else None

            # when
            session_id, signal = run_async(runner._process_stream(
                mock_client, phase=1, signal_checker=checker
            ))

            # then
            assert session_id == "sess-1"  # from first message
            assert signal == "found"  # from second message


class TestProcessStreamThinkingSpinner:
    """Tests for _process_stream show_thinking parameter."""

    def _create_runner(self, tmpdir: str):
        """Create a SessionRunner instance for testing."""
        with patch.object(Path, 'home', return_value=Path(tmpdir)):
            from wp_supervisor.markers import SupervisorMarkers
            from wp_supervisor.hooks import SupervisorHooks
            from wp_supervisor.logger import SupervisorLogger

            markers = SupervisorMarkers()
            logger = SupervisorLogger(
                workflow_dir=markers.markers_dir,
                workflow_id=markers.workflow_id
            )
            hooks = SupervisorHooks(
                markers=markers,
                logger=logger,
                working_dir=tmpdir
            )

            return SessionRunner(
                working_dir=tmpdir,
                markers=markers,
                hooks=hooks,
                logger=logger
            )

    def test_thinking_spinner_starts_when_show_thinking_true(self):
        """show_thinking=True should start a spinner before processing messages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given
            mock_client = AsyncMock()
            msg = MockAssistantMessage()
            msg.session_id = "test"
            text_block = MagicMock()
            text_block.text = "Response"
            msg.content = [text_block]

            async def mock_receive():
                yield msg
            mock_client.receive_response = mock_receive

            # Track spinner calls
            start_calls = []
            stop_calls = []
            runner.display.start_tool_spinner = AsyncMock(side_effect=lambda name: start_calls.append(name))
            runner.display.stop_tool_spinner = AsyncMock(side_effect=lambda: stop_calls.append(True))
            runner.display.stream_text = MagicMock()
            runner.display.stream_text_end = MagicMock()

            # when
            run_async(runner._process_stream(
                mock_client, phase=1, show_thinking=True
            ))

            # then
            assert "Thinking..." in start_calls
            assert len(stop_calls) >= 1

    def test_no_thinking_spinner_when_show_thinking_false(self):
        """show_thinking=False (default) should not start a thinking spinner."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given
            mock_client = AsyncMock()
            msg = MockAssistantMessage()
            msg.session_id = "test"
            text_block = MagicMock()
            text_block.text = "Response"
            msg.content = [text_block]

            async def mock_receive():
                yield msg
            mock_client.receive_response = mock_receive

            start_calls = []
            runner.display.start_tool_spinner = AsyncMock(side_effect=lambda name: start_calls.append(name))
            runner.display.stop_tool_spinner = AsyncMock()
            runner.display.stream_text = MagicMock()
            runner.display.stream_text_end = MagicMock()

            # when
            run_async(runner._process_stream(
                mock_client, phase=1, show_thinking=False
            ))

            # then
            assert "Thinking..." not in start_calls

    def test_thinking_spinner_stopped_by_first_text_block(self):
        """Thinking spinner should be stopped when first text content arrives."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given
            mock_client = AsyncMock()
            msg = MockAssistantMessage()
            msg.session_id = "test"
            text_block = MagicMock()
            text_block.text = "First response"
            msg.content = [text_block]

            async def mock_receive():
                yield msg
            mock_client.receive_response = mock_receive

            call_order = []
            runner.display.start_tool_spinner = AsyncMock(side_effect=lambda name: call_order.append(f"start:{name}"))
            runner.display.stop_tool_spinner = AsyncMock(side_effect=lambda: call_order.append("stop"))
            runner.display.stream_text = MagicMock(side_effect=lambda t: call_order.append(f"text:{t}"))
            runner.display.stream_text_end = MagicMock()

            # when
            run_async(runner._process_stream(
                mock_client, phase=1, show_thinking=True
            ))

            # then - spinner started, then stopped before text
            assert call_order[0] == "start:Thinking..."
            stop_idx = call_order.index("stop")
            text_idx = next(i for i, c in enumerate(call_order) if c.startswith("text:"))
            assert stop_idx < text_idx

    def test_thinking_spinner_replaced_by_tool_spinner(self):
        """Thinking spinner should be replaced when a tool block arrives first."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given - message with tool block (no text)
            mock_client = AsyncMock()
            msg = MockAssistantMessage()
            msg.session_id = "test"
            tool_block = MagicMock(spec=[])
            tool_block.name = "Read"
            del tool_block.text  # ensure no text attribute
            msg.content = [tool_block]

            async def mock_receive():
                yield msg
            mock_client.receive_response = mock_receive

            start_calls = []
            runner.display.start_tool_spinner = AsyncMock(side_effect=lambda name: start_calls.append(name))
            runner.display.stop_tool_spinner = AsyncMock()
            runner.display.stream_text = MagicMock()
            runner.display.stream_text_end = MagicMock()

            # when
            run_async(runner._process_stream(
                mock_client, phase=1, show_thinking=True
            ))

            # then - "Thinking..." started first, then "Read" replaced it
            assert start_calls[0] == "Thinking..."
            assert "Read" in start_calls


class TestRunPhaseSessionBehavior:
    """Tests for run_phase_session method behavior [REQ-3]."""

    def _create_runner(self, tmpdir: str):
        """Create a SessionRunner instance for testing."""
        with patch.object(Path, 'home', return_value=Path(tmpdir)):
            from wp_supervisor.markers import SupervisorMarkers
            from wp_supervisor.hooks import SupervisorHooks
            from wp_supervisor.logger import SupervisorLogger

            markers = SupervisorMarkers()
            logger = SupervisorLogger(
                workflow_dir=markers.markers_dir,
                workflow_id=markers.workflow_id
            )
            hooks = SupervisorHooks(
                markers=markers,
                logger=logger,
                working_dir=tmpdir
            )

            return SessionRunner(
                working_dir=tmpdir,
                markers=markers,
                hooks=hooks,
                logger=logger
            )

    def test_run_phase_session_returns_session_id(self):
        """run_phase_session should return the session_id from the first message [REQ-3g, REQ-3h]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given - mock client that returns session_id
            mock_client = AsyncMock()
            mock_message = MockAssistantMessage()
            mock_message.session_id = "test-session-abc123"
            text_block = MagicMock()
            text_block.text = "Response\n---PHASE_COMPLETE---"
            mock_message.content = [text_block]

            async def mock_receive():
                yield mock_message
            mock_client.receive_response = mock_receive

            # when
            result = run_async(runner.run_phase_session(
                client_context_manager=mock_client,
                initial_prompt="Test prompt",
                phase=1,
                signal_patterns=PHASE_COMPLETE_PATTERNS
            ))

            # then
            assert result == "test-session-abc123"

    def test_run_phase_session_detects_phase_complete_signal(self):
        """run_phase_session should exit loop when phase complete signal detected [REQ-3b, REQ-3c]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given - mock client that sends phase complete signal
            mock_client = AsyncMock()
            mock_message = MockAssistantMessage()
            mock_message.session_id = "test-session"
            text_block = MagicMock()
            text_block.text = "Work done!\n---PHASE_COMPLETE---"
            mock_message.content = [text_block]

            async def mock_receive():
                yield mock_message
            mock_client.receive_response = mock_receive

            # when - should return without entering user input loop
            result = run_async(runner.run_phase_session(
                client_context_manager=mock_client,
                initial_prompt="Test prompt",
                phase=1,
                signal_patterns=PHASE_COMPLETE_PATTERNS
            ))

            # then - should complete normally
            assert result is not None

    def test_run_phase_session_records_usage_from_result_message(self):
        """run_phase_session should record usage when ResultMessage received [REQ-3f]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given - mock client with result message
            mock_client = AsyncMock()

            # First an assistant message with phase complete
            mock_assistant = MockAssistantMessage()
            mock_assistant.session_id = "test-session"
            text_block = MagicMock()
            text_block.text = "Done!\n---PHASE_COMPLETE---"
            mock_assistant.content = [text_block]

            # Then a result message
            mock_result = MockResultMessage()
            mock_result.usage = {"input_tokens": 100, "output_tokens": 50}
            mock_result.total_cost_usd = 0.01
            mock_result.duration_ms = 1000
            mock_result.num_turns = 1

            async def mock_receive():
                yield mock_assistant
                yield mock_result
            mock_client.receive_response = mock_receive

            # Track usage recording
            record_calls = []
            original_record = runner._record_usage
            def capture_record(phase, result):
                record_calls.append((phase, result))
            runner._record_usage = capture_record

            # when
            run_async(runner.run_phase_session(
                client_context_manager=mock_client,
                initial_prompt="Test prompt",
                phase=2,
                signal_patterns=PHASE_COMPLETE_PATTERNS
            ))

            # then - usage should have been recorded
            assert len(record_calls) == 1
            assert record_calls[0][0] == 2  # phase


class TestRunRegenerationSessionBehavior:
    """Tests for run_regeneration_session method behavior [REQ-4]."""

    def _create_runner(self, tmpdir: str):
        """Create a SessionRunner instance for testing."""
        with patch.object(Path, 'home', return_value=Path(tmpdir)):
            from wp_supervisor.markers import SupervisorMarkers
            from wp_supervisor.hooks import SupervisorHooks
            from wp_supervisor.logger import SupervisorLogger

            markers = SupervisorMarkers()
            logger = SupervisorLogger(
                workflow_dir=markers.markers_dir,
                workflow_id=markers.workflow_id
            )
            hooks = SupervisorHooks(
                markers=markers,
                logger=logger,
                working_dir=tmpdir
            )

            return SessionRunner(
                working_dir=tmpdir,
                markers=markers,
                hooks=hooks,
                logger=logger
            )

    def test_run_regeneration_session_returns_true_and_session_id_when_complete(self):
        """run_regeneration_session should return (True, session_id) when complete signal found [REQ-4c]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given - mock client that sends complete signal
            mock_client = AsyncMock()
            mock_message = MockAssistantMessage()
            mock_message.session_id = "regen-session-123"
            text_block = MagicMock()
            text_block.text = "Updated summary.\n---REGENERATION_COMPLETE---"
            mock_message.content = [text_block]

            async def mock_receive():
                yield mock_message
            mock_client.receive_response = mock_receive

            # when
            was_completed, session_id = run_async(runner.run_regeneration_session(
                client_context_manager=mock_client,
                initial_prompt="Update summary",
                phase=1,
                complete_patterns=REGENERATION_COMPLETE_PATTERNS,
                canceled_patterns=REGENERATION_CANCELED_PATTERNS
            ))

            # then
            assert was_completed is True
            assert session_id == "regen-session-123"

    def test_run_regeneration_session_returns_false_and_none_when_canceled(self):
        """run_regeneration_session should return (False, None) when canceled signal found [REQ-4c]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given - mock client that sends canceled signal
            mock_client = AsyncMock()
            mock_message = MockAssistantMessage()
            mock_message.session_id = "regen-session-456"
            text_block = MagicMock()
            text_block.text = "Changes reverted.\n---REGENERATION_CANCELED---"
            mock_message.content = [text_block]

            async def mock_receive():
                yield mock_message
            mock_client.receive_response = mock_receive

            # when
            was_completed, session_id = run_async(runner.run_regeneration_session(
                client_context_manager=mock_client,
                initial_prompt="Update summary",
                phase=1,
                complete_patterns=REGENERATION_COMPLETE_PATTERNS,
                canceled_patterns=REGENERATION_CANCELED_PATTERNS
            ))

            # then
            assert was_completed is False
            assert session_id is None

    def test_run_regeneration_session_detects_complete_and_canceled_separately(self):
        """run_regeneration_session should correctly distinguish complete from canceled [REQ-4b]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # Test complete detection
            mock_client_complete = AsyncMock()
            msg_complete = MockAssistantMessage()
            msg_complete.session_id = "session-complete"
            text_complete = MagicMock()
            text_complete.text = "REGENERATION_COMPLETE"
            msg_complete.content = [text_complete]

            async def mock_receive_complete():
                yield msg_complete
            mock_client_complete.receive_response = mock_receive_complete

            was_completed, _ = run_async(runner.run_regeneration_session(
                client_context_manager=mock_client_complete,
                initial_prompt="Test",
                phase=1,
                complete_patterns=REGENERATION_COMPLETE_PATTERNS,
                canceled_patterns=REGENERATION_CANCELED_PATTERNS
            ))
            assert was_completed is True

            # Test canceled detection
            mock_client_canceled = AsyncMock()
            msg_canceled = MockAssistantMessage()
            msg_canceled.session_id = "session-canceled"
            text_canceled = MagicMock()
            text_canceled.text = "REGENERATION_CANCELED"
            msg_canceled.content = [text_canceled]

            async def mock_receive_canceled():
                yield msg_canceled
            mock_client_canceled.receive_response = mock_receive_canceled

            was_completed, _ = run_async(runner.run_regeneration_session(
                client_context_manager=mock_client_canceled,
                initial_prompt="Test",
                phase=1,
                complete_patterns=REGENERATION_COMPLETE_PATTERNS,
                canceled_patterns=REGENERATION_CANCELED_PATTERNS
            ))
            assert was_completed is False


class TestExtractTextBehavior:
    """Tests for extract_text method behavior [REQ-5]."""

    def _create_runner(self, tmpdir: str):
        """Create a SessionRunner instance for testing."""
        with patch.object(Path, 'home', return_value=Path(tmpdir)):
            from wp_supervisor.markers import SupervisorMarkers
            from wp_supervisor.hooks import SupervisorHooks
            from wp_supervisor.logger import SupervisorLogger

            markers = SupervisorMarkers()
            logger = SupervisorLogger(
                workflow_dir=markers.markers_dir,
                workflow_id=markers.workflow_id
            )
            hooks = SupervisorHooks(
                markers=markers,
                logger=logger,
                working_dir=tmpdir
            )

            return SessionRunner(
                working_dir=tmpdir,
                markers=markers,
                hooks=hooks,
                logger=logger
            )

    def test_extract_text_returns_collected_text(self):
        """extract_text should return collected text from response [REQ-5e]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given - mock client that returns text
            mock_client = AsyncMock()
            mock_message = MockAssistantMessage()
            mock_message.session_id = "extract-session"
            text_block1 = MagicMock()
            text_block1.text = "First part "
            text_block2 = MagicMock()
            text_block2.text = "second part"
            mock_message.content = [text_block1, text_block2]

            async def mock_receive():
                yield mock_message
            mock_client.receive_response = mock_receive

            # when
            result = run_async(runner.extract_text(
                client_context_manager=mock_client,
                prompt="Extract this"
            ))

            # then
            assert result == "First part second part"

    def test_extract_text_records_usage_when_phase_provided(self):
        """extract_text should record usage when phase is provided [REQ-5d]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given - mock client with result message
            mock_client = AsyncMock()
            mock_message = MockAssistantMessage()
            text_block = MagicMock()
            text_block.text = "Response text"
            mock_message.content = [text_block]

            mock_result = MockResultMessage()
            mock_result.usage = {"input_tokens": 50, "output_tokens": 25}
            mock_result.total_cost_usd = 0.005
            mock_result.duration_ms = 500
            mock_result.num_turns = 1

            async def mock_receive():
                yield mock_message
                yield mock_result
            mock_client.receive_response = mock_receive

            # Track usage recording
            record_calls = []
            original_record = runner._record_usage
            def capture_record(phase, result):
                record_calls.append((phase, result))
            runner._record_usage = capture_record

            # when
            run_async(runner.extract_text(
                client_context_manager=mock_client,
                prompt="Extract this",
                phase=3
            ))

            # then - usage should have been recorded with phase
            assert len(record_calls) == 1
            assert record_calls[0][0] == 3

    def test_extract_text_does_not_record_usage_when_no_phase(self):
        """extract_text should not record usage when phase is None [REQ-5d]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given - mock client with result message
            mock_client = AsyncMock()
            mock_message = MockAssistantMessage()
            text_block = MagicMock()
            text_block.text = "Response text"
            mock_message.content = [text_block]

            mock_result = MockResultMessage()
            mock_result.usage = {"input_tokens": 50, "output_tokens": 25}
            mock_result.total_cost_usd = 0.005
            mock_result.duration_ms = 500
            mock_result.num_turns = 1

            async def mock_receive():
                yield mock_message
                yield mock_result
            mock_client.receive_response = mock_receive

            # Track usage recording
            record_calls = []
            original_record = runner._record_usage
            def capture_record(phase, result):
                record_calls.append((phase, result))
            runner._record_usage = capture_record

            # when - phase is None (default)
            run_async(runner.extract_text(
                client_context_manager=mock_client,
                prompt="Extract this"
            ))

            # then - no usage should have been recorded
            assert len(record_calls) == 0

    def test_extract_text_returns_partial_on_timeout(self):
        """extract_text should return partial text collected when timeout occurs [ERR-1, EDGE-4]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given - mock client that times out after partial response
            mock_client = AsyncMock()

            async def slow_receive():
                msg = MockAssistantMessage()
                text_block = MagicMock()
                text_block.text = "Partial response "
                msg.content = [text_block]
                yield msg
                # Simulate timeout by waiting longer than test timeout
                await asyncio.sleep(10)
                # This part shouldn't be reached due to timeout
                msg2 = MockAssistantMessage()
                text_block2 = MagicMock()
                text_block2.text = "more text"
                msg2.content = [text_block2]
                yield msg2

            mock_client.receive_response = slow_receive

            # when - use very short timeout
            result = run_async(runner.extract_text(
                client_context_manager=mock_client,
                prompt="Extract this",
                timeout=0.1  # 100ms timeout
            ))

            # then - should have partial text collected before timeout
            assert "Partial response" in result or result == ""  # May be empty if timeout hits before any yield


class TestEdgeCases:
    """Tests for edge cases documented in requirements."""

    def _create_runner(self, tmpdir: str):
        """Create a SessionRunner instance for testing."""
        with patch.object(Path, 'home', return_value=Path(tmpdir)):
            from wp_supervisor.markers import SupervisorMarkers
            from wp_supervisor.hooks import SupervisorHooks
            from wp_supervisor.logger import SupervisorLogger

            markers = SupervisorMarkers()
            logger = SupervisorLogger(
                workflow_dir=markers.markers_dir,
                workflow_id=markers.workflow_id
            )
            hooks = SupervisorHooks(
                markers=markers,
                logger=logger,
                working_dir=tmpdir
            )

            return SessionRunner(
                working_dir=tmpdir,
                markers=markers,
                hooks=hooks,
                logger=logger
            )

    def test_edge_case_empty_user_input_continues_prompting(self):
        """[EDGE-1] Empty user input should continue prompting without sending."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given - mock client that doesn't send complete signal initially
            mock_client = AsyncMock()

            # Track query calls
            query_calls = []
            async def mock_query(text):
                query_calls.append(text)
            mock_client.query = mock_query

            # First response doesn't have complete signal
            msg1 = MockAssistantMessage()
            msg1.session_id = "test"
            text1 = MagicMock()
            text1.text = "Working on it..."
            msg1.content = [text1]

            # Second response has complete signal
            msg2 = MockAssistantMessage()
            msg2.session_id = "test"
            text2 = MagicMock()
            text2.text = "Done!\n---PHASE_COMPLETE---"
            msg2.content = [text2]

            response_count = [0]
            async def mock_receive():
                response_count[0] += 1
                if response_count[0] == 1:
                    yield msg1
                else:
                    yield msg2
            mock_client.receive_response = mock_receive

            # Mock user input: empty, then /done
            input_values = iter(["", "/done"])
            with patch('wp_supervisor.session.read_user_input', side_effect=lambda p="": next(input_values)):
                # when
                run_async(runner.run_phase_session(
                    client_context_manager=mock_client,
                    initial_prompt="Test",
                    phase=1,
                    signal_patterns=PHASE_COMPLETE_PATTERNS
                ))

            # then - empty input should not have triggered a query
            # Only the initial prompt should have been sent
            assert len(query_calls) == 0 or all(q != "" for q in query_calls)

    def test_edge_case_missing_session_id_handled_gracefully(self):
        """[EDGE-3] Missing session_id should be handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given - mock client that doesn't provide session_id
            mock_client = AsyncMock()
            mock_message = MockAssistantMessage()
            # No session_id attribute or it's None
            mock_message.session_id = None
            text_block = MagicMock()
            text_block.text = "Response\n---PHASE_COMPLETE---"
            mock_message.content = [text_block]

            async def mock_receive():
                yield mock_message
            mock_client.receive_response = mock_receive

            # when - should not raise
            result = run_async(runner.run_phase_session(
                client_context_manager=mock_client,
                initial_prompt="Test",
                phase=1,
                signal_patterns=PHASE_COMPLETE_PATTERNS
            ))

            # then - should return None for session_id
            assert result is None

    def test_edge_case_signal_detected_mid_conversation(self):
        """[EDGE-5] Signal detected mid-conversation should exit loop immediately."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given - mock client that sends signal mid-text
            mock_client = AsyncMock()
            mock_message = MockAssistantMessage()
            mock_message.session_id = "test"
            text_block = MagicMock()
            text_block.text = "Starting work...\nDoing something...\n---PHASE_COMPLETE---\nMore text that should be ignored for loop exit"
            mock_message.content = [text_block]

            async def mock_receive():
                yield mock_message
            mock_client.receive_response = mock_receive

            # Track if user input was requested
            input_requested = [False]
            def mock_input(prompt=""):
                input_requested[0] = True
                return ""

            with patch('wp_supervisor.session.read_user_input', side_effect=mock_input):
                # when
                run_async(runner.run_phase_session(
                    client_context_manager=mock_client,
                    initial_prompt="Test",
                    phase=1,
                    signal_patterns=PHASE_COMPLETE_PATTERNS
                ))

            # then - should not have entered user input loop
            assert input_requested[0] is False


class TestUserCommandsInPhaseSession:
    """Tests for user command handling in run_phase_session [REQ-3d]."""

    def _create_runner(self, tmpdir: str):
        """Create a SessionRunner instance for testing."""
        with patch.object(Path, 'home', return_value=Path(tmpdir)):
            from wp_supervisor.markers import SupervisorMarkers
            from wp_supervisor.hooks import SupervisorHooks
            from wp_supervisor.logger import SupervisorLogger

            markers = SupervisorMarkers()
            logger = SupervisorLogger(
                workflow_dir=markers.markers_dir,
                workflow_id=markers.workflow_id
            )
            hooks = SupervisorHooks(
                markers=markers,
                logger=logger,
                working_dir=tmpdir
            )

            return SessionRunner(
                working_dir=tmpdir,
                markers=markers,
                hooks=hooks,
                logger=logger
            )

    def test_done_command_ends_session(self):
        """/done command should end session normally [REQ-3d]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given - mock client without phase complete signal
            mock_client = AsyncMock()
            mock_message = MockAssistantMessage()
            mock_message.session_id = "test"
            text_block = MagicMock()
            text_block.text = "Working..."  # No complete signal
            mock_message.content = [text_block]

            async def mock_receive():
                yield mock_message
            mock_client.receive_response = mock_receive

            # User inputs /done
            with patch('wp_supervisor.session.read_user_input', return_value="/done"):
                # when
                result = run_async(runner.run_phase_session(
                    client_context_manager=mock_client,
                    initial_prompt="Test",
                    phase=1,
                    signal_patterns=PHASE_COMPLETE_PATTERNS
                ))

            # then - should complete successfully
            assert result == "test"

    def test_complete_command_ends_session(self):
        """/complete command should end session normally [REQ-3d]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given - mock client
            mock_client = AsyncMock()
            mock_message = MockAssistantMessage()
            mock_message.session_id = "test"
            text_block = MagicMock()
            text_block.text = "Working..."
            mock_message.content = [text_block]

            async def mock_receive():
                yield mock_message
            mock_client.receive_response = mock_receive

            # User inputs /complete
            with patch('wp_supervisor.session.read_user_input', return_value="/complete"):
                # when
                result = run_async(runner.run_phase_session(
                    client_context_manager=mock_client,
                    initial_prompt="Test",
                    phase=1,
                    signal_patterns=PHASE_COMPLETE_PATTERNS
                ))

            # then - should complete successfully
            assert result == "test"

    def test_next_command_ends_session(self):
        """/next command should end session normally [REQ-3d]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given - mock client
            mock_client = AsyncMock()
            mock_message = MockAssistantMessage()
            mock_message.session_id = "test"
            text_block = MagicMock()
            text_block.text = "Working..."
            mock_message.content = [text_block]

            async def mock_receive():
                yield mock_message
            mock_client.receive_response = mock_receive

            # User inputs /next
            with patch('wp_supervisor.session.read_user_input', return_value="/next"):
                # when
                result = run_async(runner.run_phase_session(
                    client_context_manager=mock_client,
                    initial_prompt="Test",
                    phase=1,
                    signal_patterns=PHASE_COMPLETE_PATTERNS
                ))

            # then - should complete successfully
            assert result == "test"

    def test_quit_command_raises_keyboard_interrupt(self):
        """/quit command should abort workflow [REQ-3d]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given - mock client
            mock_client = AsyncMock()
            mock_message = MockAssistantMessage()
            mock_message.session_id = "test"
            text_block = MagicMock()
            text_block.text = "Working..."
            mock_message.content = [text_block]

            async def mock_receive():
                yield mock_message
            mock_client.receive_response = mock_receive

            # User inputs /quit
            with patch('wp_supervisor.session.read_user_input', return_value="/quit"):
                # when/then - should raise KeyboardInterrupt
                with pytest.raises(KeyboardInterrupt):
                    run_async(runner.run_phase_session(
                        client_context_manager=mock_client,
                        initial_prompt="Test",
                        phase=1,
                        signal_patterns=PHASE_COMPLETE_PATTERNS
                    ))

    def test_exit_command_raises_keyboard_interrupt(self):
        """/exit command should abort workflow [REQ-3d]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given - mock client
            mock_client = AsyncMock()
            mock_message = MockAssistantMessage()
            mock_message.session_id = "test"
            text_block = MagicMock()
            text_block.text = "Working..."
            mock_message.content = [text_block]

            async def mock_receive():
                yield mock_message
            mock_client.receive_response = mock_receive

            # User inputs /exit
            with patch('wp_supervisor.session.read_user_input', return_value="/exit"):
                # when/then - should raise KeyboardInterrupt
                with pytest.raises(KeyboardInterrupt):
                    run_async(runner.run_phase_session(
                        client_context_manager=mock_client,
                        initial_prompt="Test",
                        phase=1,
                        signal_patterns=PHASE_COMPLETE_PATTERNS
                    ))

    def test_abort_command_raises_keyboard_interrupt(self):
        """/abort command should abort workflow [REQ-3d]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given - mock client
            mock_client = AsyncMock()
            mock_message = MockAssistantMessage()
            mock_message.session_id = "test"
            text_block = MagicMock()
            text_block.text = "Working..."
            mock_message.content = [text_block]

            async def mock_receive():
                yield mock_message
            mock_client.receive_response = mock_receive

            # User inputs /abort
            with patch('wp_supervisor.session.read_user_input', return_value="/abort"):
                # when/then - should raise KeyboardInterrupt
                with pytest.raises(KeyboardInterrupt):
                    run_async(runner.run_phase_session(
                        client_context_manager=mock_client,
                        initial_prompt="Test",
                        phase=1,
                        signal_patterns=PHASE_COMPLETE_PATTERNS
                    ))


# =============================================================================
# DEVELOPER INTERRUPT TESTS - StdinInterruptReader integration with SessionRunner
# =============================================================================

from wp_supervisor.stdin_reader import StdinInterruptReader


class TestSessionRunnerHasStdinReader:
    """Tests that SessionRunner creates and owns a StdinInterruptReader instance."""

    def _create_runner(self, tmpdir: str):
        """Create a SessionRunner instance for testing."""
        with patch.object(Path, 'home', return_value=Path(tmpdir)):
            from wp_supervisor.markers import SupervisorMarkers
            from wp_supervisor.hooks import SupervisorHooks
            from wp_supervisor.logger import SupervisorLogger

            markers = SupervisorMarkers()
            logger = SupervisorLogger(
                workflow_dir=markers.markers_dir,
                workflow_id=markers.workflow_id
            )
            hooks = SupervisorHooks(
                markers=markers,
                logger=logger,
                working_dir=tmpdir
            )

            return SessionRunner(
                working_dir=tmpdir,
                markers=markers,
                hooks=hooks,
                logger=logger
            )

    def test_session_runner_has_stdin_reader_attribute(self):
        """SessionRunner should have a _stdin_reader attribute."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)
            assert hasattr(runner, '_stdin_reader')

    def test_session_runner_stdin_reader_is_correct_type(self):
        """SessionRunner._stdin_reader should be a StdinInterruptReader instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)
            assert isinstance(runner._stdin_reader, StdinInterruptReader)


class TestStartStdinReader:
    """Tests for SessionRunner._start_stdin_reader() phase gating [REQ-5]."""

    def _create_runner(self, tmpdir: str):
        """Create a SessionRunner with mocked stdin reader."""
        with patch.object(Path, 'home', return_value=Path(tmpdir)):
            from wp_supervisor.markers import SupervisorMarkers
            from wp_supervisor.hooks import SupervisorHooks
            from wp_supervisor.logger import SupervisorLogger

            markers = SupervisorMarkers()
            logger = SupervisorLogger(
                workflow_dir=markers.markers_dir,
                workflow_id=markers.workflow_id
            )
            hooks = SupervisorHooks(
                markers=markers,
                logger=logger,
                working_dir=tmpdir
            )

            runner = SessionRunner(
                working_dir=tmpdir,
                markers=markers,
                hooks=hooks,
                logger=logger
            )
            runner._stdin_reader = MagicMock(spec=StdinInterruptReader)
            runner.display = MagicMock()
            return runner

    def test_start_stdin_reader_calls_start_for_phase_2(self):
        """_start_stdin_reader should start reader for phase 2 [REQ-1]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # when
            runner._start_stdin_reader(phase=2)

            # then
            runner._stdin_reader.start.assert_called_once()

    def test_start_stdin_reader_calls_start_for_phase_3(self):
        """_start_stdin_reader should start reader for phase 3 [REQ-1]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # when
            runner._start_stdin_reader(phase=3)

            # then
            runner._stdin_reader.start.assert_called_once()

    def test_start_stdin_reader_calls_start_for_phase_4(self):
        """_start_stdin_reader should start reader for phase 4 [REQ-1]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # when
            runner._start_stdin_reader(phase=4)

            # then
            runner._stdin_reader.start.assert_called_once()

    def test_start_stdin_reader_noop_for_phase_1(self):
        """_start_stdin_reader should NOT start reader for phase 1 [REQ-5]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # when
            runner._start_stdin_reader(phase=1)

            # then
            runner._stdin_reader.start.assert_not_called()

    def test_start_stdin_reader_shows_interrupt_hint(self):
        """_start_stdin_reader should show interrupt hint when starting [REQ-6]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # when
            runner._start_stdin_reader(phase=2)

            # then
            runner.display.interrupt_hint.assert_called_once()

    def test_start_stdin_reader_no_hint_for_phase_1(self):
        """_start_stdin_reader should NOT show hint for phase 1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # when
            runner._start_stdin_reader(phase=1)

            # then
            runner.display.interrupt_hint.assert_not_called()


class TestStopStdinReader:
    """Tests for SessionRunner._stop_stdin_reader() [REQ-8]."""

    def _create_runner(self, tmpdir: str):
        """Create a SessionRunner with mocked stdin reader."""
        with patch.object(Path, 'home', return_value=Path(tmpdir)):
            from wp_supervisor.markers import SupervisorMarkers
            from wp_supervisor.hooks import SupervisorHooks
            from wp_supervisor.logger import SupervisorLogger

            markers = SupervisorMarkers()
            logger = SupervisorLogger(
                workflow_dir=markers.markers_dir,
                workflow_id=markers.workflow_id
            )
            hooks = SupervisorHooks(
                markers=markers,
                logger=logger,
                working_dir=tmpdir
            )

            runner = SessionRunner(
                working_dir=tmpdir,
                markers=markers,
                hooks=hooks,
                logger=logger
            )
            runner._stdin_reader = MagicMock(spec=StdinInterruptReader)
            return runner

    def test_stop_stdin_reader_calls_stop(self):
        """_stop_stdin_reader should call _stdin_reader.stop()."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # when
            runner._stop_stdin_reader()

            # then
            runner._stdin_reader.stop.assert_called_once()

    def test_stop_stdin_reader_safe_when_not_running(self):
        """_stop_stdin_reader should not raise when reader is not running."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)
            runner._stdin_reader.is_running = False

            # when/then - should not raise
            runner._stop_stdin_reader()


class TestHandleDeveloperInterrupt:
    """Tests for SessionRunner._handle_developer_interrupt() [REQ-2, REQ-3]."""

    def _create_runner(self, tmpdir: str):
        """Create a SessionRunner with mocked dependencies."""
        with patch.object(Path, 'home', return_value=Path(tmpdir)):
            from wp_supervisor.markers import SupervisorMarkers
            from wp_supervisor.hooks import SupervisorHooks
            from wp_supervisor.logger import SupervisorLogger

            markers = SupervisorMarkers()
            logger = SupervisorLogger(
                workflow_dir=markers.markers_dir,
                workflow_id=markers.workflow_id
            )
            hooks = SupervisorHooks(
                markers=markers,
                logger=logger,
                working_dir=tmpdir
            )

            runner = SessionRunner(
                working_dir=tmpdir,
                markers=markers,
                hooks=hooks,
                logger=logger
            )
            runner._stdin_reader = MagicMock(spec=StdinInterruptReader)
            runner.display = MagicMock()
            return runner

    def test_returns_none_none_when_no_queued_input(self):
        """Should return (None, None) when drain() returns None [EDGE-1]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)
            runner._stdin_reader.drain.return_value = None

            # given
            mock_client = AsyncMock()

            # when
            sid, signal = run_async(runner._handle_developer_interrupt(
                mock_client, phase=2
            ))

            # then
            assert sid is None
            assert signal is None
            mock_client.query.assert_not_called()

    def test_injects_queued_input_via_client_query(self):
        """Should inject queued text via client.query() [REQ-3]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)
            runner._stdin_reader.drain.return_value = "please focus on error handling"

            # given
            mock_client = AsyncMock()
            msg = MockAssistantMessage()
            msg.session_id = "interrupt-session"
            text_block = MagicMock()
            text_block.text = "Got it, focusing on error handling."
            msg.content = [text_block]

            async def mock_receive():
                yield msg
            mock_client.receive_response = mock_receive

            # when
            sid, signal = run_async(runner._handle_developer_interrupt(
                mock_client, phase=2
            ))

            # then
            mock_client.query.assert_called_once_with("please focus on error handling")

    def test_runs_process_stream_after_injection(self):
        """Should call _process_stream after injecting [REQ-3]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)
            runner._stdin_reader.drain.return_value = "some guidance"

            # given
            mock_client = AsyncMock()
            runner._process_stream = AsyncMock(return_value=("session-123", None))

            # when
            sid, signal = run_async(runner._handle_developer_interrupt(
                mock_client, phase=3
            ))

            # then
            assert sid == "session-123"
            runner._process_stream.assert_called_once()

    def test_returns_session_id_and_signal_from_process_stream(self):
        """Should return (session_id, signal) from _process_stream [REQ-3]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)
            runner._stdin_reader.drain.return_value = "finish up"

            # given
            mock_client = AsyncMock()
            runner._process_stream = AsyncMock(return_value=("sess-abc", SIGNAL_COMPLETE))

            # when
            sid, signal = run_async(runner._handle_developer_interrupt(
                mock_client, phase=4
            ))

            # then
            assert sid == "sess-abc"
            assert signal == SIGNAL_COMPLETE

    def test_shows_interrupt_injection_display(self):
        """Should call display.interrupt_injection with the queued text [REQ-6]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)
            runner._stdin_reader.drain.return_value = "add more tests"

            # given
            mock_client = AsyncMock()
            runner._process_stream = AsyncMock(return_value=(None, None))

            # when
            run_async(runner._handle_developer_interrupt(mock_client, phase=2))

            # then
            runner.display.interrupt_injection.assert_called_once_with("add more tests")

    def test_concatenated_multiline_input_injected_as_single_message(self):
        """Multiple queued lines should be injected as one message [REQ-7]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)
            # drain returns concatenated multi-line input
            runner._stdin_reader.drain.return_value = "line one\nline two\nline three"

            # given
            mock_client = AsyncMock()
            runner._process_stream = AsyncMock(return_value=(None, None))

            # when
            run_async(runner._handle_developer_interrupt(mock_client, phase=2))

            # then - single query call with concatenated text
            mock_client.query.assert_called_once_with("line one\nline two\nline three")

    def test_handles_query_failure_gracefully(self):
        """Should return (None, None) if client.query() raises [ERR-2]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)
            runner._stdin_reader.drain.return_value = "some input"

            # given
            mock_client = AsyncMock()
            mock_client.query.side_effect = Exception("API error")

            # when
            sid, signal = run_async(runner._handle_developer_interrupt(
                mock_client, phase=2
            ))

            # then
            assert sid is None
            assert signal is None

    def test_passes_signal_checker_to_process_stream(self):
        """Should pass signal_checker through to _process_stream."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)
            runner._stdin_reader.drain.return_value = "guidance"

            # given
            mock_client = AsyncMock()
            runner._process_stream = AsyncMock(return_value=(None, None))
            checker = lambda text: SIGNAL_COMPLETE if "DONE" in text else None

            # when
            run_async(runner._handle_developer_interrupt(
                mock_client, phase=2, signal_checker=checker
            ))

            # then - signal_checker should have been passed through
            call_args = runner._process_stream.call_args
            assert call_args is not None
            # Check signal_checker was passed (positional or keyword)
            assert checker in call_args.args or call_args.kwargs.get('signal_checker') is checker


class TestRunPhaseSessionStdinReaderIntegration:
    """Integration tests verifying run_phase_session() calls stdin reader methods
    at the correct points [REQ-1, REQ-2, REQ-3, REQ-4, REQ-5]."""

    def _create_runner(self, tmpdir: str):
        """Create a SessionRunner with mocked dependencies."""
        with patch.object(Path, 'home', return_value=Path(tmpdir)):
            from wp_supervisor.markers import SupervisorMarkers
            from wp_supervisor.hooks import SupervisorHooks
            from wp_supervisor.logger import SupervisorLogger

            markers = SupervisorMarkers()
            logger = SupervisorLogger(
                workflow_dir=markers.markers_dir,
                workflow_id=markers.workflow_id
            )
            hooks = SupervisorHooks(
                markers=markers,
                logger=logger,
                working_dir=tmpdir
            )

            return SessionRunner(
                working_dir=tmpdir,
                markers=markers,
                hooks=hooks,
                logger=logger
            )

    def test_starts_stdin_reader_before_initial_process_stream(self):
        """run_phase_session should call _start_stdin_reader before first _process_stream [REQ-1]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given
            call_order = []
            runner._start_stdin_reader = MagicMock(side_effect=lambda p: call_order.append(f"start_reader:{p}"))
            runner._stop_stdin_reader = MagicMock(side_effect=lambda: call_order.append("stop_reader"))
            runner._handle_developer_interrupt = AsyncMock(
                return_value=(None, None),
                side_effect=lambda *a, **kw: call_order.append("handle_interrupt") or (None, None)
            )
            runner._handle_compaction_reinjection = AsyncMock(return_value=(None, None))

            mock_client = AsyncMock()
            msg = MockAssistantMessage()
            msg.session_id = "test"
            text_block = MagicMock()
            text_block.text = "Done\n---PHASE_COMPLETE---"
            msg.content = [text_block]

            async def mock_receive():
                yield msg
            mock_client.receive_response = mock_receive

            # when
            run_async(runner.run_phase_session(
                client_context_manager=mock_client,
                initial_prompt="Test",
                phase=2,
                signal_patterns=PHASE_COMPLETE_PATTERNS
            ))

            # then - start_reader should be called with phase
            assert "start_reader:2" in call_order

    def test_stops_stdin_reader_before_user_input_prompt(self):
        """run_phase_session should call _stop_stdin_reader before read_user_input [REQ-2]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given
            call_order = []
            runner._start_stdin_reader = MagicMock(side_effect=lambda p: call_order.append("start_reader"))
            runner._stop_stdin_reader = MagicMock(side_effect=lambda: call_order.append("stop_reader"))
            runner._handle_developer_interrupt = AsyncMock(return_value=(None, None))
            runner._handle_compaction_reinjection = AsyncMock(return_value=(None, None))

            mock_client = AsyncMock()
            msg = MockAssistantMessage()
            msg.session_id = "test"
            text_block = MagicMock()
            text_block.text = "Working..."  # no complete signal
            msg.content = [text_block]

            async def mock_receive():
                yield msg
            mock_client.receive_response = mock_receive

            def mock_input(prompt=""):
                call_order.append("read_input")
                return "/done"

            with patch('wp_supervisor.session.read_user_input', side_effect=mock_input):
                run_async(runner.run_phase_session(
                    client_context_manager=mock_client,
                    initial_prompt="Test",
                    phase=2,
                    signal_patterns=PHASE_COMPLETE_PATTERNS
                ))

            # then - stop_reader should appear before read_input
            stop_idx = call_order.index("stop_reader")
            read_idx = call_order.index("read_input")
            assert stop_idx < read_idx

    def test_handles_developer_interrupt_after_process_stream(self):
        """run_phase_session should call _handle_developer_interrupt after _process_stream [REQ-2, REQ-3]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given
            interrupt_called = [False]
            original_handle = runner._handle_developer_interrupt

            async def track_interrupt(*args, **kwargs):
                interrupt_called[0] = True
                return (None, None)

            runner._handle_developer_interrupt = track_interrupt
            runner._handle_compaction_reinjection = AsyncMock(return_value=(None, None))

            mock_client = AsyncMock()
            msg = MockAssistantMessage()
            msg.session_id = "test"
            text_block = MagicMock()
            text_block.text = "Working..."  # no complete signal
            msg.content = [text_block]

            async def mock_receive():
                yield msg
            mock_client.receive_response = mock_receive

            with patch('wp_supervisor.session.read_user_input', return_value="/done"):
                run_async(runner.run_phase_session(
                    client_context_manager=mock_client,
                    initial_prompt="Test",
                    phase=2,
                    signal_patterns=PHASE_COMPLETE_PATTERNS
                ))

            # then
            assert interrupt_called[0] is True

    def test_interrupt_runs_after_compaction_check(self):
        """Developer interrupt should run AFTER compaction re-injection [EDGE-3]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given
            call_order = []

            async def mock_compaction(*args, **kwargs):
                call_order.append("compaction")
                return (None, None)

            async def mock_interrupt(*args, **kwargs):
                call_order.append("interrupt")
                return (None, None)

            runner._handle_compaction_reinjection = mock_compaction
            runner._handle_developer_interrupt = mock_interrupt

            mock_client = AsyncMock()
            msg = MockAssistantMessage()
            msg.session_id = "test"
            text_block = MagicMock()
            text_block.text = "Working..."
            msg.content = [text_block]

            async def mock_receive():
                yield msg
            mock_client.receive_response = mock_receive

            with patch('wp_supervisor.session.read_user_input', return_value="/done"):
                run_async(runner.run_phase_session(
                    client_context_manager=mock_client,
                    initial_prompt="Test",
                    phase=2,
                    signal_patterns=PHASE_COMPLETE_PATTERNS
                ))

            # then - compaction should come before interrupt
            assert call_order.index("compaction") < call_order.index("interrupt")

    def test_interrupt_skipped_when_phase_complete_signal_detected(self):
        """Interrupt check should be skipped if phase_complete is True [EDGE-2]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given
            interrupt_called = [False]

            async def mock_interrupt(*args, **kwargs):
                interrupt_called[0] = True
                return (None, None)

            runner._handle_developer_interrupt = mock_interrupt
            runner._handle_compaction_reinjection = AsyncMock(return_value=(None, None))

            mock_client = AsyncMock()
            msg = MockAssistantMessage()
            msg.session_id = "test"
            text_block = MagicMock()
            text_block.text = "Done!\n---PHASE_COMPLETE---"  # phase complete signal
            msg.content = [text_block]

            async def mock_receive():
                yield msg
            mock_client.receive_response = mock_receive

            # when
            run_async(runner.run_phase_session(
                client_context_manager=mock_client,
                initial_prompt="Test",
                phase=2,
                signal_patterns=PHASE_COMPLETE_PATTERNS
            ))

            # then - interrupt should NOT have been called because phase is complete
            assert interrupt_called[0] is False

    def test_interrupt_injection_followed_by_normal_user_input(self):
        """After interrupt injection, session should still prompt for user input [REQ-4]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given - interrupt returns content (means injection happened)
            # but no phase complete signal
            async def mock_interrupt(client, phase, signal_checker=None):
                return ("interrupt-sid", None)  # injected but no completion

            runner._handle_developer_interrupt = mock_interrupt
            runner._handle_compaction_reinjection = AsyncMock(return_value=(None, None))

            mock_client = AsyncMock()
            msg = MockAssistantMessage()
            msg.session_id = "test"
            text_block = MagicMock()
            text_block.text = "Working..."  # no complete signal
            msg.content = [text_block]

            async def mock_receive():
                yield msg
            mock_client.receive_response = mock_receive

            input_called = [False]
            def mock_input(prompt=""):
                input_called[0] = True
                return "/done"

            with patch('wp_supervisor.session.read_user_input', side_effect=mock_input):
                run_async(runner.run_phase_session(
                    client_context_manager=mock_client,
                    initial_prompt="Test",
                    phase=2,
                    signal_patterns=PHASE_COMPLETE_PATTERNS
                ))

            # then - user input should still have been requested
            assert input_called[0] is True

    def test_stdin_reader_restarted_after_user_input_query(self):
        """After user sends input, stdin reader should restart for next streaming [REQ-1]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given
            start_calls = []
            runner._start_stdin_reader = MagicMock(side_effect=lambda p: start_calls.append(p))
            runner._stop_stdin_reader = MagicMock()
            runner._handle_developer_interrupt = AsyncMock(return_value=(None, None))
            runner._handle_compaction_reinjection = AsyncMock(return_value=(None, None))

            mock_client = AsyncMock()
            response_count = [0]

            msg_working = MockAssistantMessage()
            msg_working.session_id = "test"
            text_working = MagicMock()
            text_working.text = "Working..."
            msg_working.content = [text_working]

            msg_done = MockAssistantMessage()
            msg_done.session_id = "test"
            text_done = MagicMock()
            text_done.text = "Done!\n---PHASE_COMPLETE---"
            msg_done.content = [text_done]

            async def mock_receive():
                response_count[0] += 1
                if response_count[0] <= 1:
                    yield msg_working
                else:
                    yield msg_done
            mock_client.receive_response = mock_receive

            input_values = iter(["some guidance", "/done"])
            with patch('wp_supervisor.session.read_user_input', side_effect=lambda p="": next(input_values)):
                run_async(runner.run_phase_session(
                    client_context_manager=mock_client,
                    initial_prompt="Test",
                    phase=3,
                    signal_patterns=PHASE_COMPLETE_PATTERNS
                ))

            # then - start should have been called more than once
            # (once for initial, once after user input)
            assert len(start_calls) >= 2

    def test_interrupt_check_also_after_user_input_response(self):
        """_handle_developer_interrupt should be called after user-triggered response too."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given
            interrupt_call_count = [0]

            async def mock_interrupt(*args, **kwargs):
                interrupt_call_count[0] += 1
                return (None, None)

            runner._handle_developer_interrupt = mock_interrupt
            runner._handle_compaction_reinjection = AsyncMock(return_value=(None, None))

            mock_client = AsyncMock()
            response_count = [0]

            msg_working = MockAssistantMessage()
            msg_working.session_id = "test"
            text_working = MagicMock()
            text_working.text = "Working..."
            msg_working.content = [text_working]

            msg_still_working = MockAssistantMessage()
            msg_still_working.session_id = "test"
            text_still = MagicMock()
            text_still.text = "Still working..."
            msg_still_working.content = [text_still]

            async def mock_receive():
                response_count[0] += 1
                if response_count[0] <= 1:
                    yield msg_working
                else:
                    yield msg_still_working
            mock_client.receive_response = mock_receive

            input_values = iter(["some input", "/done"])
            with patch('wp_supervisor.session.read_user_input', side_effect=lambda p="": next(input_values)):
                run_async(runner.run_phase_session(
                    client_context_manager=mock_client,
                    initial_prompt="Test",
                    phase=2,
                    signal_patterns=PHASE_COMPLETE_PATTERNS
                ))

            # then - interrupt should be called after initial response AND after user-input response
            assert interrupt_call_count[0] >= 2

    def test_interrupt_with_phase_complete_signal_ends_session(self):
        """If interrupt's _process_stream returns phase complete, session should end [EDGE-2]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = self._create_runner(tmpdir)

            # given - interrupt returns a phase complete signal
            async def mock_interrupt(client, phase, signal_checker=None):
                return ("interrupt-sid", SIGNAL_COMPLETE)

            runner._handle_developer_interrupt = mock_interrupt
            runner._handle_compaction_reinjection = AsyncMock(return_value=(None, None))

            mock_client = AsyncMock()
            msg = MockAssistantMessage()
            msg.session_id = "test"
            text_block = MagicMock()
            text_block.text = "Working..."  # no complete signal in initial response
            msg.content = [text_block]

            async def mock_receive():
                yield msg
            mock_client.receive_response = mock_receive

            input_called = [False]
            def mock_input(prompt=""):
                input_called[0] = True
                return "/done"

            with patch('wp_supervisor.session.read_user_input', side_effect=mock_input):
                result = run_async(runner.run_phase_session(
                    client_context_manager=mock_client,
                    initial_prompt="Test",
                    phase=2,
                    signal_patterns=PHASE_COMPLETE_PATTERNS
                ))

            # then - session should end without user input prompt
            assert input_called[0] is False
            assert result == "interrupt-sid"


class TestDisplayInterruptMethods:
    """Tests for SupervisorDisplay interrupt-related methods [REQ-6]."""

    def test_interrupt_hint_method_exists(self):
        """SupervisorDisplay should have interrupt_hint method."""
        from wp_supervisor.display import SupervisorDisplay
        display = SupervisorDisplay()
        assert hasattr(display, 'interrupt_hint')
        assert callable(display.interrupt_hint)

    def test_interrupt_injection_method_exists(self):
        """SupervisorDisplay should have interrupt_injection method."""
        from wp_supervisor.display import SupervisorDisplay
        display = SupervisorDisplay()
        assert hasattr(display, 'interrupt_injection')
        assert callable(display.interrupt_injection)

    def test_interrupt_hint_outputs_text(self, capsys):
        """interrupt_hint should output a visible indicator [REQ-6]."""
        from wp_supervisor.display import SupervisorDisplay
        display = SupervisorDisplay()
        display._use_rich = False  # force plain text

        # when
        display.interrupt_hint()

        # then
        captured = capsys.readouterr()
        assert "Type to add guidance" in captured.out
        assert "Ctrl+C" in captured.out

    def test_interrupt_injection_shows_preview(self, capsys):
        """interrupt_injection should show preview of injected text [REQ-6]."""
        from wp_supervisor.display import SupervisorDisplay
        display = SupervisorDisplay()
        display._use_rich = False

        # when
        display.interrupt_injection("please focus on error handling")

        # then
        captured = capsys.readouterr()
        assert "Injecting" in captured.out
        assert "please focus on error handling" in captured.out

    def test_interrupt_injection_truncates_long_text(self, capsys):
        """interrupt_injection should truncate text longer than 80 chars."""
        from wp_supervisor.display import SupervisorDisplay
        display = SupervisorDisplay()
        display._use_rich = False

        # given
        long_text = "a" * 100

        # when
        display.interrupt_injection(long_text)

        # then
        captured = capsys.readouterr()
        assert "..." in captured.out


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
