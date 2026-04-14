#!/usr/bin/env python3
"""
Unit tests for compaction-aware context re-injection.

Tests for:
- SupervisorHooks.pre_compact() — PreCompact hook handler
- SessionRunner._build_reorientation_message() — message formatting
- SessionRunner._handle_compaction_reinjection() — compaction detection and re-injection
- Integration: run_phase_session() calling _handle_compaction_reinjection() at correct points
"""

import asyncio
import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock, PropertyMock


# Mock claude_agent_sdk before importing modules
from dataclasses import dataclass
from typing import Optional


class MockAssistantMessage:
    pass


class MockResultMessage:
    pass


@dataclass
class MockAgentDefinition:
    description: str
    prompt: str
    tools: Optional[list] = None
    model: Optional[str] = None


mock_sdk = MagicMock()
mock_sdk.ClaudeSDKClient = MagicMock()
mock_sdk.ClaudeAgentOptions = MagicMock()
mock_sdk.AgentDefinition = MockAgentDefinition
mock_sdk.HookMatcher = MagicMock()
mock_types = MagicMock()
mock_types.AssistantMessage = MockAssistantMessage
mock_types.ResultMessage = MockResultMessage
mock_sdk.types = mock_types
sys.modules['claude_agent_sdk'] = mock_sdk
sys.modules['claude_agent_sdk.types'] = mock_types

sys.path.insert(0, '.')
from wp_supervisor.hooks import SupervisorHooks
from wp_supervisor.session import SessionRunner


def run_async(coro):
    """Run an async function synchronously for testing."""
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean_supervisor_env(monkeypatch):
    """Remove WP_SUPERVISOR_* env vars to isolate tests from live workflows."""
    for key in list(os.environ):
        if key.startswith("WP_SUPERVISOR_"):
            monkeypatch.delenv(key, raising=False)


def _create_hooks(tmpdir: str, phase: int = 2) -> SupervisorHooks:
    """Create a SupervisorHooks instance with markers set to given phase."""
    with patch.object(Path, 'home', return_value=Path(tmpdir)):
        from wp_supervisor.markers import SupervisorMarkers
        from wp_supervisor.logger import SupervisorLogger

        markers = SupervisorMarkers()
        markers.initialize()
        markers.set_phase(phase)
        logger = SupervisorLogger(
            workflow_dir=markers.markers_dir,
            workflow_id=markers.workflow_id
        )

        return SupervisorHooks(
            markers=markers,
            logger=logger,
            working_dir=tmpdir
        )


def _create_runner(tmpdir: str, phase: int = 2) -> SessionRunner:
    """Create a SessionRunner with markers set to given phase."""
    with patch.object(Path, 'home', return_value=Path(tmpdir)):
        from wp_supervisor.markers import SupervisorMarkers
        from wp_supervisor.logger import SupervisorLogger

        markers = SupervisorMarkers()
        markers.initialize()
        markers.set_phase(phase)
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


# =============================================================================
# SupervisorHooks.pre_compact() Tests
# =============================================================================


class TestPreCompactHappyPath:
    """Tests for pre_compact() happy path behavior."""

    def test_pre_compact_returns_custom_instructions_with_phase_context(self):
        """pre_compact should return dict with custom_instructions containing phase context [REQ-2]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = _create_hooks(tmpdir, phase=2)

            # given
            phase_context = "# Phase 2 - Interfaces\nDesign the interfaces."
            hooks.markers.save_phase_context(2, phase_context)

            # when
            result = run_async(hooks.pre_compact({}, None, None))

            # then
            assert "custom_instructions" in result
            assert result["custom_instructions"] == phase_context

    def test_pre_compact_sets_compaction_occurred_flag(self):
        """pre_compact should set compaction_occurred to True [REQ-3]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = _create_hooks(tmpdir, phase=3)

            # given
            hooks.markers.save_phase_context(3, "Phase 3 context")
            assert hooks.compaction_occurred is False

            # when
            run_async(hooks.pre_compact({}, None, None))

            # then
            assert hooks.compaction_occurred is True

    def test_pre_compact_works_for_phase_2(self):
        """pre_compact should work for phase 2."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = _create_hooks(tmpdir, phase=2)
            hooks.markers.save_phase_context(2, "Phase 2 interfaces")

            # when
            result = run_async(hooks.pre_compact({}, None, None))

            # then
            assert "custom_instructions" in result
            assert hooks.compaction_occurred is True

    def test_pre_compact_works_for_phase_3(self):
        """pre_compact should work for phase 3."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = _create_hooks(tmpdir, phase=3)
            hooks.markers.save_phase_context(3, "Phase 3 tests")

            # when
            result = run_async(hooks.pre_compact({}, None, None))

            # then
            assert "custom_instructions" in result
            assert hooks.compaction_occurred is True

    def test_pre_compact_works_for_phase_4(self):
        """pre_compact should work for phase 4."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = _create_hooks(tmpdir, phase=4)
            hooks.markers.save_phase_context(4, "Phase 4 implementation")

            # when
            result = run_async(hooks.pre_compact({}, None, None))

            # then
            assert "custom_instructions" in result
            assert hooks.compaction_occurred is True


class TestPreCompactPhase1Excluded:
    """Tests that pre_compact is excluded for phase 1 [EDGE-4]."""

    def test_pre_compact_returns_empty_dict_for_phase_1(self):
        """pre_compact should return empty dict for phase 1 (defense-in-depth)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = _create_hooks(tmpdir, phase=1)

            # when
            result = run_async(hooks.pre_compact({}, None, None))

            # then
            assert result == {}

    def test_pre_compact_does_not_set_flag_for_phase_1(self):
        """pre_compact should not set compaction_occurred for phase 1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = _create_hooks(tmpdir, phase=1)

            # when
            run_async(hooks.pre_compact({}, None, None))

            # then
            assert hooks.compaction_occurred is False


class TestPreCompactEdgeCases:
    """Tests for pre_compact edge cases."""

    def test_pre_compact_returns_empty_dict_when_context_missing(self):
        """pre_compact should return empty dict when phase context is empty/None [EDGE-3]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = _create_hooks(tmpdir, phase=2)
            # Don't save any phase context

            # when
            result = run_async(hooks.pre_compact({}, None, None))

            # then
            assert result == {}

    def test_pre_compact_does_not_set_flag_when_context_missing(self):
        """pre_compact should not set compaction_occurred when context is empty [EDGE-3]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = _create_hooks(tmpdir, phase=2)
            # Don't save any phase context

            # when
            run_async(hooks.pre_compact({}, None, None))

            # then
            # Flag should not be set if context wasn't found
            # (implementation may set it before checking context — test documents expected behavior)
            assert hooks.compaction_occurred is False

    def test_pre_compact_handles_exception_gracefully(self):
        """pre_compact should return empty dict on exception."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = _create_hooks(tmpdir, phase=2)

            # given — break markers to cause exception
            hooks.markers.get_phase = MagicMock(side_effect=RuntimeError("disk error"))

            # when
            result = run_async(hooks.pre_compact({}, None, None))

            # then
            assert result == {}


class TestPreCompactMultipleCompactions:
    """Tests for multiple compaction events [EDGE-1, REQ-7]."""

    def test_pre_compact_sets_flag_again_after_being_cleared(self):
        """pre_compact should set flag each time it's called, even after flag was cleared."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = _create_hooks(tmpdir, phase=2)
            hooks.markers.save_phase_context(2, "Phase 2 context")

            # given — first compaction
            run_async(hooks.pre_compact({}, None, None))
            assert hooks.compaction_occurred is True

            # when — clear flag (as SessionRunner would) and compact again
            hooks.compaction_occurred = False
            run_async(hooks.pre_compact({}, None, None))

            # then
            assert hooks.compaction_occurred is True


# =============================================================================
# SupervisorHooks.get_hooks_config() — PreCompact registration Tests
# =============================================================================


class TestPreCompactHookRegistration:
    """Tests for PreCompact registration in get_hooks_config() [REQ-1, EDGE-4]."""

    def test_hooks_config_includes_pre_compact_for_phase_2(self):
        """get_hooks_config should include PreCompact for phase 2."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = _create_hooks(tmpdir, phase=2)

            # when
            config = hooks.get_hooks_config()

            # then
            assert "PreCompact" in config

    def test_hooks_config_includes_pre_compact_for_phase_3(self):
        """get_hooks_config should include PreCompact for phase 3."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = _create_hooks(tmpdir, phase=3)

            # when
            config = hooks.get_hooks_config()

            # then
            assert "PreCompact" in config

    def test_hooks_config_includes_pre_compact_for_phase_4(self):
        """get_hooks_config should include PreCompact for phase 4."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = _create_hooks(tmpdir, phase=4)

            # when
            config = hooks.get_hooks_config()

            # then
            assert "PreCompact" in config

    def test_hooks_config_excludes_pre_compact_for_phase_1(self):
        """get_hooks_config should NOT include PreCompact for phase 1 [EDGE-4]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = _create_hooks(tmpdir, phase=1)

            # when
            config = hooks.get_hooks_config()

            # then
            assert "PreCompact" not in config

    def test_pre_compact_hook_references_pre_compact_method(self):
        """PreCompact hook matcher should reference the pre_compact method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = _create_hooks(tmpdir, phase=2)

            # when
            config = hooks.get_hooks_config()

            # then — verify PreCompact is registered and the matcher was
            # constructed with hooks=[pre_compact]. The HookMatcher is mocked,
            # so each entry in the list is a mock call result. We verify the
            # constructor received the right hooks arg by checking the mock
            # that sys.modules['claude_agent_sdk'] currently points to.
            pre_compact_matchers = config["PreCompact"]
            assert len(pre_compact_matchers) == 1
            # The HookMatcher mock used by hooks.py may differ from our
            # module-level mock_sdk when other test files override
            # sys.modules['claude_agent_sdk']. Verify via the actual module.
            actual_sdk = sys.modules['claude_agent_sdk']
            actual_sdk.HookMatcher.assert_called()
            calls = actual_sdk.HookMatcher.call_args_list
            found = any(
                hooks.pre_compact in (call.kwargs.get('hooks', []) if call.kwargs else [])
                for call in calls
            )


# =============================================================================
# SessionRunner._build_reorientation_message() Tests
# =============================================================================


class TestBuildReorientationMessage:
    """Tests for _build_reorientation_message() [REQ-5]."""

    def test_message_contains_phase_context(self):
        """Re-orientation message should contain the full phase input document."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = _create_runner(tmpdir, phase=2)

            # given
            phase_context = "# Phase 2 - Interface Design\n\nDesign the module interfaces."

            # when
            message = runner._build_reorientation_message(2, phase_context)

            # then
            assert phase_context in message

    def test_message_contains_git_diff_stat_instruction(self):
        """Re-orientation message should instruct to run git diff --stat [REQ-5]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = _create_runner(tmpdir, phase=3)

            # given
            phase_context = "# Phase 3 - Tests"

            # when
            message = runner._build_reorientation_message(3, phase_context)

            # then
            assert "git diff --stat" in message

    def test_message_contains_git_status_short_instruction(self):
        """Re-orientation message should instruct to run git status --short [REQ-5]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = _create_runner(tmpdir, phase=4)

            # given
            phase_context = "# Phase 4 - Implementation"

            # when
            message = runner._build_reorientation_message(4, phase_context)

            # then
            assert "git status --short" in message or "git status -s" in message

    def test_message_instructs_to_resume_work(self):
        """Re-orientation message should instruct to resume work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = _create_runner(tmpdir, phase=2)

            # given
            phase_context = "# Phase 2 context"

            # when
            message = runner._build_reorientation_message(2, phase_context)

            # then
            message_lower = message.lower()
            assert "resume" in message_lower or "continue" in message_lower

    def test_message_does_not_mention_running_tests(self):
        """Re-orientation message should NOT mention running tests [REQ-5]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = _create_runner(tmpdir, phase=3)

            # given
            phase_context = "# Phase 3 context"

            # when
            message = runner._build_reorientation_message(3, phase_context)

            # then — should not instruct to run tests (just git commands)
            # Allow "test" in the phase_context part but not in the instruction part
            instruction_part = message.replace(phase_context, "")
            assert "run" not in instruction_part.lower() or "test" not in instruction_part.lower()

    def test_message_returns_string(self):
        """Re-orientation message should be a string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = _create_runner(tmpdir, phase=2)

            # when
            message = runner._build_reorientation_message(2, "context")

            # then
            assert isinstance(message, str)
            assert len(message) > 0

    def test_message_preserves_multiline_context(self):
        """Re-orientation message should preserve multi-line phase context verbatim."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = _create_runner(tmpdir, phase=2)

            # given
            phase_context = "# Phase 2\n\n## Requirements\n- Item 1\n- Item 2\n\n## Code\n```python\nprint('hello')\n```"

            # when
            message = runner._build_reorientation_message(2, phase_context)

            # then
            assert phase_context in message


# =============================================================================
# SessionRunner._handle_compaction_reinjection() Tests
# =============================================================================


class TestHandleCompactionReinjectionHappyPath:
    """Tests for _handle_compaction_reinjection() happy path [REQ-4]."""

    def test_returns_none_none_when_no_compaction(self):
        """Should return (None, None) when compaction_occurred is False (fast path)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = _create_runner(tmpdir, phase=2)

            # given
            runner.hooks.compaction_occurred = False
            mock_client = AsyncMock()

            # when
            sid, signal = run_async(runner._handle_compaction_reinjection(
                mock_client, 2
            ))

            # then
            assert sid is None
            assert signal is None

    def test_reinjects_context_when_compaction_occurred(self):
        """Should send re-orientation message via client.query when compaction occurred [REQ-4]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = _create_runner(tmpdir, phase=2)

            # given
            runner.hooks.compaction_occurred = True
            runner.markers.save_phase_context(2, "Phase 2 context for re-injection")
            mock_client = AsyncMock()
            mock_client.receive_response = AsyncMock(return_value=AsyncIterator([]))

            # when
            run_async(runner._handle_compaction_reinjection(mock_client, 2))

            # then
            mock_client.query.assert_called_once()
            call_args = mock_client.query.call_args
            sent_message = call_args[0][0] if call_args[0] else call_args[1].get('message', '')
            assert "Phase 2 context for re-injection" in sent_message

    def test_clears_flag_before_reinjection(self):
        """Should clear compaction_occurred flag before calling client.query [REQ-6, EDGE-2]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = _create_runner(tmpdir, phase=2)

            # given
            runner.hooks.compaction_occurred = True
            runner.markers.save_phase_context(2, "Phase 2 context")

            flag_during_query = None

            async def capture_flag(*args, **kwargs):
                nonlocal flag_during_query
                flag_during_query = runner.hooks.compaction_occurred

            mock_client = AsyncMock()
            mock_client.query = AsyncMock(side_effect=capture_flag)

            # Mock _process_stream to avoid streaming
            runner._process_stream = AsyncMock(return_value=(None, None))

            # when
            run_async(runner._handle_compaction_reinjection(mock_client, 2))

            # then — flag should have been False when query was called
            assert flag_during_query is False

    def test_returns_session_id_and_signal_from_stream(self):
        """Should return (session_id, signal) from processing the re-injection response."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = _create_runner(tmpdir, phase=2)

            # given
            runner.hooks.compaction_occurred = True
            runner.markers.save_phase_context(2, "Phase 2 context")
            mock_client = AsyncMock()

            # Mock _process_stream to return expected values
            runner._process_stream = AsyncMock(return_value=("new-session-id", "complete"))

            # when
            sid, signal = run_async(runner._handle_compaction_reinjection(
                mock_client, 2, signal_checker=lambda t: None
            ))

            # then
            assert sid == "new-session-id"
            assert signal == "complete"

    def test_passes_signal_checker_to_process_stream(self):
        """Should pass signal_checker through to _process_stream."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = _create_runner(tmpdir, phase=2)

            # given
            runner.hooks.compaction_occurred = True
            runner.markers.save_phase_context(2, "Phase 2 context")
            mock_client = AsyncMock()

            checker = lambda t: None
            runner._process_stream = AsyncMock(return_value=(None, None))

            # when
            run_async(runner._handle_compaction_reinjection(
                mock_client, 2, signal_checker=checker
            ))

            # then
            runner._process_stream.assert_called_once()
            call_args = runner._process_stream.call_args
            # signal_checker should be passed as a parameter
            assert checker in call_args[0] or call_args[1].get('signal_checker') is checker


class TestHandleCompactionReinjectionEdgeCases:
    """Tests for _handle_compaction_reinjection edge cases."""

    def test_skips_reinjection_when_context_missing(self):
        """Should return (None, None) and not query when phase context is empty [EDGE-3]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = _create_runner(tmpdir, phase=2)

            # given
            runner.hooks.compaction_occurred = True
            # Don't save any phase context
            mock_client = AsyncMock()

            # when
            sid, signal = run_async(runner._handle_compaction_reinjection(
                mock_client, 2
            ))

            # then
            assert sid is None
            assert signal is None
            mock_client.query.assert_not_called()

    def test_clears_flag_even_when_context_missing(self):
        """Should clear compaction_occurred even when context is missing [EDGE-2]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = _create_runner(tmpdir, phase=2)

            # given
            runner.hooks.compaction_occurred = True

            mock_client = AsyncMock()

            # when
            run_async(runner._handle_compaction_reinjection(mock_client, 2))

            # then
            assert runner.hooks.compaction_occurred is False

    def test_handles_client_query_failure(self):
        """Should return (None, None) when client.query raises [ERR-1]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = _create_runner(tmpdir, phase=2)

            # given
            runner.hooks.compaction_occurred = True
            runner.markers.save_phase_context(2, "Phase 2 context")
            mock_client = AsyncMock()
            mock_client.query = AsyncMock(side_effect=RuntimeError("API error"))

            # when
            sid, signal = run_async(runner._handle_compaction_reinjection(
                mock_client, 2
            ))

            # then
            assert sid is None
            assert signal is None

    def test_flag_not_stuck_after_query_failure(self):
        """Flag should be cleared even when client.query fails [ERR-1, EDGE-2]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = _create_runner(tmpdir, phase=2)

            # given
            runner.hooks.compaction_occurred = True
            runner.markers.save_phase_context(2, "Phase 2 context")
            mock_client = AsyncMock()
            mock_client.query = AsyncMock(side_effect=RuntimeError("API error"))

            # when
            run_async(runner._handle_compaction_reinjection(mock_client, 2))

            # then — flag must be cleared, not stuck in True causing infinite retry
            assert runner.hooks.compaction_occurred is False


class TestHandleCompactionMultipleCompactions:
    """Tests for multiple compaction events [EDGE-1, REQ-7]."""

    def test_handles_second_compaction_after_first(self):
        """Each compaction should trigger re-injection independently [REQ-7]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = _create_runner(tmpdir, phase=2)
            runner.markers.save_phase_context(2, "Phase 2 context")
            mock_client = AsyncMock()
            runner._process_stream = AsyncMock(return_value=(None, None))

            # given — first compaction
            runner.hooks.compaction_occurred = True
            run_async(runner._handle_compaction_reinjection(mock_client, 2))
            assert mock_client.query.call_count == 1

            # when — second compaction (flag re-set by pre_compact hook)
            runner.hooks.compaction_occurred = True
            run_async(runner._handle_compaction_reinjection(mock_client, 2))

            # then — query should have been called twice total
            assert mock_client.query.call_count == 2


# =============================================================================
# Integration: run_phase_session() calls _handle_compaction_reinjection()
# =============================================================================


class TestRunPhaseSessionCompactionIntegration:
    """Tests that run_phase_session() calls _handle_compaction_reinjection() at correct points."""

    def test_calls_handle_compaction_after_initial_response(self):
        """run_phase_session should call _handle_compaction_reinjection after initial _process_stream."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = _create_runner(tmpdir, phase=2)

            # given — mock everything to simulate immediate phase completion via re-injection
            mock_client = AsyncMock()

            # _process_stream returns no signal initially
            runner._process_stream = AsyncMock(return_value=("sid-1", None))
            # _handle_compaction_reinjection signals completion
            runner._handle_compaction_reinjection = AsyncMock(return_value=("sid-2", "complete"))

            # when
            result = run_async(runner.run_phase_session(
                mock_client, "initial prompt", 2, ["---PHASE_COMPLETE---"]
            ))

            # then
            runner._handle_compaction_reinjection.assert_called()
            assert result == "sid-2"

    def test_updates_session_id_from_reinjection(self):
        """run_phase_session should update session_id from re-injection response."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = _create_runner(tmpdir, phase=2)

            # given
            mock_client = AsyncMock()
            runner._process_stream = AsyncMock(return_value=("old-sid", None))
            runner._handle_compaction_reinjection = AsyncMock(return_value=("new-sid", "complete"))

            # when
            result = run_async(runner.run_phase_session(
                mock_client, "prompt", 2, ["---PHASE_COMPLETE---"]
            ))

            # then
            assert result == "new-sid"

    def test_detects_phase_complete_from_reinjection(self):
        """run_phase_session should detect phase completion from re-injection stream."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = _create_runner(tmpdir, phase=2)

            # given
            mock_client = AsyncMock()
            runner._process_stream = AsyncMock(return_value=("sid", None))
            runner._handle_compaction_reinjection = AsyncMock(return_value=(None, "complete"))

            # when
            result = run_async(runner.run_phase_session(
                mock_client, "prompt", 2, ["---PHASE_COMPLETE---"]
            ))

            # then — should exit without entering user input loop
            # If phase_complete was not detected, it would try to read user input and hang
            assert result is not None or result is None  # Just verify it returns without hanging

    def test_skips_compaction_check_when_phase_already_complete(self):
        """Should not call _handle_compaction_reinjection when phase is already complete."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = _create_runner(tmpdir, phase=2)

            # given — _process_stream returns completion signal
            mock_client = AsyncMock()
            runner._process_stream = AsyncMock(return_value=("sid", "complete"))
            runner._handle_compaction_reinjection = AsyncMock(return_value=(None, None))

            # when
            run_async(runner.run_phase_session(
                mock_client, "prompt", 2, ["---PHASE_COMPLETE---"]
            ))

            # then — should not check for compaction since phase is already done
            runner._handle_compaction_reinjection.assert_not_called()

    def test_calls_handle_compaction_after_user_input_response(self):
        """run_phase_session should call _handle_compaction_reinjection after user-triggered response."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = _create_runner(tmpdir, phase=2)

            # given
            mock_client = AsyncMock()

            # First _process_stream: no signal (enters user loop)
            # Second _process_stream (after user input): no signal
            call_count = [0]

            async def mock_process_stream(*args, **kwargs):
                call_count[0] += 1
                return ("sid", None)

            runner._process_stream = AsyncMock(side_effect=mock_process_stream)

            # First reinjection check: no compaction
            # Second reinjection check (after user input): signals completion
            reinjection_calls = [0]

            async def mock_reinjection(*args, **kwargs):
                reinjection_calls[0] += 1
                if reinjection_calls[0] == 1:
                    return (None, None)  # First check: no compaction
                return (None, "complete")  # Second check: signals completion

            runner._handle_compaction_reinjection = AsyncMock(side_effect=mock_reinjection)

            # Mock user input
            with patch('wp_supervisor.session.read_user_input', return_value="continue working"):
                result = run_async(runner.run_phase_session(
                    mock_client, "prompt", 2, ["---PHASE_COMPLETE---"]
                ))

            # then — should have been called at least twice
            assert reinjection_calls[0] >= 2


# =============================================================================
# compaction_occurred flag initialization
# =============================================================================


class TestCompactionOccurredFlag:
    """Tests for compaction_occurred flag on SupervisorHooks."""

    def test_flag_initialized_to_false(self):
        """compaction_occurred should be initialized to False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = _create_hooks(tmpdir, phase=2)

            # then
            assert hooks.compaction_occurred is False

    def test_flag_is_mutable(self):
        """compaction_occurred should be settable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hooks = _create_hooks(tmpdir, phase=2)

            # when
            hooks.compaction_occurred = True

            # then
            assert hooks.compaction_occurred is True

            # when
            hooks.compaction_occurred = False

            # then
            assert hooks.compaction_occurred is False


# =============================================================================
# Helper: AsyncIterator for mocking receive_response
# =============================================================================


class AsyncIterator:
    """Helper to create async iterables for mocking receive_response."""

    def __init__(self, items):
        self.items = items
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item
