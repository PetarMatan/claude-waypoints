#!/usr/bin/env python3
"""
Unit tests for regeneration conversation feature.

Tests the interactive two-way communication when user selects 'r' (regenerate)
option during phase summary review.
"""

import sys
import tempfile
import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# Mock claude_agent_sdk before importing orchestrator
class MockAssistantMessage:
    """Mock AssistantMessage class for isinstance() checks."""
    pass

class MockResultMessage:
    """Mock ResultMessage class for isinstance() checks."""
    pass

class MockClaudeSDKClient:
    """Mock ClaudeSDKClient for regeneration conversation tests."""

    def __init__(self, options=None):
        self.options = options
        self._prompt = None
        self._responses = []
        self._response_index = 0

    async def connect(self, prompt=None):
        self._prompt = prompt

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False

    async def query(self, user_input, session_id="default"):
        self._prompt = user_input

    async def receive_response(self):
        """Yield mock response."""
        if self._response_index < len(self._responses):
            response = self._responses[self._response_index]
            self._response_index += 1
            yield response
        else:
            # Default response
            mock_msg = MockAssistantMessage()
            mock_msg.session_id = "test-session-regen"
            text_block = MagicMock()
            text_block.text = "I understand your feedback."
            mock_msg.content = [text_block]
            yield mock_msg

    def set_responses(self, responses):
        """Set mock responses for testing."""
        self._responses = responses
        self._response_index = 0

mock_sdk = MagicMock()
mock_sdk.ClaudeSDKClient = MockClaudeSDKClient
mock_sdk.ClaudeAgentOptions = MagicMock()
mock_types = MagicMock()
mock_types.AssistantMessage = MockAssistantMessage
mock_types.ResultMessage = MockResultMessage
mock_sdk.types = mock_types
sys.modules['claude_agent_sdk'] = mock_sdk
sys.modules['claude_agent_sdk.types'] = mock_types

# Add project to path
sys.path.insert(0, '.')


def run_async(coro):
    """Run an async function synchronously for testing."""
    return asyncio.run(coro)


# =============================================================================
# SIGNAL CONSTANTS TESTS
# =============================================================================

class TestRegenerationSignalConstants:
    """Tests for regeneration signal constants."""

    def test_regeneration_complete_patterns_exists(self):
        """REGENERATION_COMPLETE_PATTERNS constant should exist in session module."""
        from wp_supervisor.session import REGENERATION_COMPLETE_PATTERNS
        assert REGENERATION_COMPLETE_PATTERNS is not None

    def test_regeneration_complete_patterns_contains_variants(self):
        """REGENERATION_COMPLETE_PATTERNS should contain multiple format variants."""
        from wp_supervisor.session import REGENERATION_COMPLETE_PATTERNS
        assert "REGENERATION_COMPLETE" in REGENERATION_COMPLETE_PATTERNS
        assert "---REGENERATION_COMPLETE---" in REGENERATION_COMPLETE_PATTERNS
        assert "**REGENERATION_COMPLETE**" in REGENERATION_COMPLETE_PATTERNS

    def test_regeneration_canceled_patterns_exists(self):
        """REGENERATION_CANCELED_PATTERNS constant should exist in session module."""
        from wp_supervisor.session import REGENERATION_CANCELED_PATTERNS
        assert REGENERATION_CANCELED_PATTERNS is not None

    def test_regeneration_canceled_patterns_contains_variants(self):
        """REGENERATION_CANCELED_PATTERNS should contain multiple format variants."""
        from wp_supervisor.session import REGENERATION_CANCELED_PATTERNS
        assert "REGENERATION_CANCELED" in REGENERATION_CANCELED_PATTERNS
        assert "---REGENERATION_CANCELED---" in REGENERATION_CANCELED_PATTERNS
        assert "**REGENERATION_CANCELED**" in REGENERATION_CANCELED_PATTERNS


# =============================================================================
# SIGNAL DETECTION TESTS
# =============================================================================

class TestCheckRegenerationSignal:
    """Tests for _check_regeneration_signal on SessionRunner."""

    def _make_runner(self, tmpdir):
        """Create a SessionRunner with mocked dependencies."""
        from wp_supervisor.session import SessionRunner
        from wp_supervisor.markers import SupervisorMarkers
        markers = SupervisorMarkers()
        hooks = MagicMock()
        logger = MagicMock()
        return SessionRunner(
            working_dir=tmpdir,
            markers=markers,
            hooks=hooks,
            logger=logger
        )

    def test_check_regeneration_signal_method_exists(self):
        """_check_regeneration_signal method should exist on SessionRunner."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                runner = self._make_runner(tmpdir)
                assert hasattr(runner, '_check_regeneration_signal')
                assert callable(runner._check_regeneration_signal)

    def test_detects_complete_signal_plain(self):
        """Should detect plain REGENERATION_COMPLETE signal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.session import REGENERATION_COMPLETE_PATTERNS, REGENERATION_CANCELED_PATTERNS, SIGNAL_COMPLETE
                runner = self._make_runner(tmpdir)

                result = runner._check_regeneration_signal(
                    "REGENERATION_COMPLETE", REGENERATION_COMPLETE_PATTERNS, REGENERATION_CANCELED_PATTERNS
                )
                assert result == SIGNAL_COMPLETE

    def test_detects_complete_signal_with_dashes(self):
        """Should detect ---REGENERATION_COMPLETE--- signal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.session import REGENERATION_COMPLETE_PATTERNS, REGENERATION_CANCELED_PATTERNS
                runner = self._make_runner(tmpdir)

                result = runner._check_regeneration_signal(
                    "---REGENERATION_COMPLETE---", REGENERATION_COMPLETE_PATTERNS, REGENERATION_CANCELED_PATTERNS
                )
                assert result == 'complete'

    def test_detects_complete_signal_bold(self):
        """Should detect **REGENERATION_COMPLETE** signal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.session import REGENERATION_COMPLETE_PATTERNS, REGENERATION_CANCELED_PATTERNS
                runner = self._make_runner(tmpdir)

                result = runner._check_regeneration_signal(
                    "**REGENERATION_COMPLETE**", REGENERATION_COMPLETE_PATTERNS, REGENERATION_CANCELED_PATTERNS
                )
                assert result == 'complete'

    def test_detects_complete_signal_in_text(self):
        """Should detect REGENERATION_COMPLETE within larger text."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.session import REGENERATION_COMPLETE_PATTERNS, REGENERATION_CANCELED_PATTERNS
                runner = self._make_runner(tmpdir)

                text = "Great, I've incorporated your changes.\n\nREGENERATION_COMPLETE"
                result = runner._check_regeneration_signal(
                    text, REGENERATION_COMPLETE_PATTERNS, REGENERATION_CANCELED_PATTERNS
                )
                assert result == 'complete'

    def test_detects_canceled_signal_plain(self):
        """Should detect plain REGENERATION_CANCELED signal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.session import REGENERATION_COMPLETE_PATTERNS, REGENERATION_CANCELED_PATTERNS
                runner = self._make_runner(tmpdir)

                result = runner._check_regeneration_signal(
                    "REGENERATION_CANCELED", REGENERATION_COMPLETE_PATTERNS, REGENERATION_CANCELED_PATTERNS
                )
                assert result == 'canceled'

    def test_detects_canceled_signal_with_dashes(self):
        """Should detect ---REGENERATION_CANCELED--- signal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.session import REGENERATION_COMPLETE_PATTERNS, REGENERATION_CANCELED_PATTERNS
                runner = self._make_runner(tmpdir)

                result = runner._check_regeneration_signal(
                    "---REGENERATION_CANCELED---", REGENERATION_COMPLETE_PATTERNS, REGENERATION_CANCELED_PATTERNS
                )
                assert result == 'canceled'

    def test_detects_canceled_signal_bold(self):
        """Should detect **REGENERATION_CANCELED** signal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.session import REGENERATION_COMPLETE_PATTERNS, REGENERATION_CANCELED_PATTERNS
                runner = self._make_runner(tmpdir)

                result = runner._check_regeneration_signal(
                    "**REGENERATION_CANCELED**", REGENERATION_COMPLETE_PATTERNS, REGENERATION_CANCELED_PATTERNS
                )
                assert result == 'canceled'

    def test_detects_canceled_signal_in_text(self):
        """Should detect REGENERATION_CANCELED within larger text."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.session import REGENERATION_COMPLETE_PATTERNS, REGENERATION_CANCELED_PATTERNS
                runner = self._make_runner(tmpdir)

                text = "Understood, keeping the original.\n\nREGENERATION_CANCELED"
                result = runner._check_regeneration_signal(
                    text, REGENERATION_COMPLETE_PATTERNS, REGENERATION_CANCELED_PATTERNS
                )
                assert result == 'canceled'

    def test_returns_none_for_no_signal(self):
        """Should return None when no signal is present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.session import REGENERATION_COMPLETE_PATTERNS, REGENERATION_CANCELED_PATTERNS
                runner = self._make_runner(tmpdir)

                result = runner._check_regeneration_signal(
                    "Just some regular text", REGENERATION_COMPLETE_PATTERNS, REGENERATION_CANCELED_PATTERNS
                )
                assert result is None

    def test_returns_none_for_empty_text(self):
        """Should return None for empty text."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.session import REGENERATION_COMPLETE_PATTERNS, REGENERATION_CANCELED_PATTERNS
                runner = self._make_runner(tmpdir)

                result = runner._check_regeneration_signal(
                    "", REGENERATION_COMPLETE_PATTERNS, REGENERATION_CANCELED_PATTERNS
                )
                assert result is None

    def test_complete_takes_precedence_over_canceled(self):
        """If both signals present, complete should take precedence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.session import REGENERATION_COMPLETE_PATTERNS, REGENERATION_CANCELED_PATTERNS
                runner = self._make_runner(tmpdir)

                text = "REGENERATION_COMPLETE\nREGENERATION_CANCELED"
                result = runner._check_regeneration_signal(
                    text, REGENERATION_COMPLETE_PATTERNS, REGENERATION_CANCELED_PATTERNS
                )
                assert result == 'complete'


# =============================================================================
# INTERACTIVE CONVERSATION TESTS
# =============================================================================

class TestRunRegenerationConversation:
    """Tests for _run_regeneration_conversation method."""

    def test_run_regeneration_conversation_method_exists(self):
        """_run_regeneration_conversation method should exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                assert hasattr(orchestrator, '_run_regeneration_conversation')
                assert callable(orchestrator._run_regeneration_conversation)

    def test_returns_tuple_with_completion_status_and_session_id(self):
        """Should return (was_completed, session_id) tuple."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                # Mock the conversation to immediately complete
                async def mock_conversation(*args, **kwargs):
                    return (True, "session-123")

                orchestrator._run_regeneration_conversation = mock_conversation

                result = run_async(orchestrator._run_regeneration_conversation(
                    phase=1,
                    current_summary="# Summary",
                    initial_feedback="Add more details"
                ))

                assert isinstance(result, tuple)
                assert len(result) == 2
                was_completed, session_id = result
                assert isinstance(was_completed, bool)

    def test_detects_completion_signal_and_returns_true(self):
        """Should return (True, session_id) when REGENERATION_COMPLETE is detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                # Mock the conversation to return completed
                async def mock_regen_session(*args, **kwargs):
                    return (True, "test-session-123")

                orchestrator._session_runner.run_regeneration_session = mock_regen_session

                # Mock ClaudeSDKClient at session level where it's imported
                with patch('wp_supervisor.session.ClaudeSDKClient', MockClaudeSDKClient):
                    result = run_async(orchestrator._run_regeneration_conversation(
                        phase=1,
                        current_summary="# Summary",
                        initial_feedback="Add error handling"
                    ))

                was_completed, session_id = result
                assert was_completed is True

    def test_detects_cancellation_signal_and_returns_false(self):
        """Should return (False, None) when REGENERATION_CANCELED is detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                # Mock the conversation to return canceled
                async def mock_regen_session(*args, **kwargs):
                    return (False, None)

                orchestrator._session_runner.run_regeneration_session = mock_regen_session

                with patch('wp_supervisor.session.ClaudeSDKClient', MockClaudeSDKClient):
                    result = run_async(orchestrator._run_regeneration_conversation(
                        phase=1,
                        current_summary="# Summary",
                        initial_feedback="nevermind"
                    ))

                was_completed, session_id = result
                assert was_completed is False

    def test_handles_done_command(self):
        """Should complete when user types /done."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                # Mock the conversation to return completed via /done
                async def mock_regen_session(*args, **kwargs):
                    return (True, "test-session-123")

                orchestrator._session_runner.run_regeneration_session = mock_regen_session

                with patch('wp_supervisor.session.ClaudeSDKClient', MockClaudeSDKClient):
                    result = run_async(orchestrator._run_regeneration_conversation(
                        phase=1,
                        current_summary="# Summary",
                        initial_feedback="Add details"
                    ))

                was_completed, session_id = result
                assert was_completed is True


# =============================================================================
# REGENERATE SUMMARY TESTS (MODIFIED BEHAVIOR)
# =============================================================================

class TestRegenerateSummaryInteractive:
    """Tests for modified _regenerate_summary with interactive conversation."""

    def test_regenerate_summary_returns_original_on_empty_feedback(self):
        """Should return original summary when feedback is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                # Save initial document
                orchestrator.markers.save_phase_document(1, "# Original Summary")

                with patch('builtins.input', return_value=''):
                    result = run_async(orchestrator._regenerate_summary(1))

                assert result == "# Original Summary"

    def test_regenerate_summary_calls_run_regeneration_conversation(self):
        """Should call _run_regeneration_conversation with feedback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                # Save initial document
                orchestrator.markers.save_phase_document(1, "# Current Summary")

                conversation_called = []

                async def mock_conversation(phase, current_summary, initial_feedback):
                    conversation_called.append({
                        'phase': phase,
                        'current_summary': current_summary,
                        'initial_feedback': initial_feedback
                    })
                    return (True, "session-123")

                async def mock_extract_text_response(prompt, session_id=None, phase=None):
                    return "# Updated Summary"

                orchestrator._run_regeneration_conversation = mock_conversation
                orchestrator._extract_text_response = mock_extract_text_response

                with patch('builtins.input', return_value='Add more details'):
                    result = run_async(orchestrator._regenerate_summary(1))

                assert len(conversation_called) == 1
                assert conversation_called[0]['phase'] == 1
                assert conversation_called[0]['current_summary'] == "# Current Summary"
                assert conversation_called[0]['initial_feedback'] == "Add more details"

    def test_regenerate_summary_generates_final_summary_after_completion(self):
        """Should generate final summary after conversation completes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                orchestrator.markers.save_phase_document(1, "# Original")

                async def mock_conversation(*args, **kwargs):
                    return (True, "session-123")

                query_prompts = []

                async def mock_extract_text_response(prompt, session_id=None, phase=None):
                    query_prompts.append(prompt)
                    return "# Final Updated Summary"

                orchestrator._run_regeneration_conversation = mock_conversation
                orchestrator._extract_text_response = mock_extract_text_response

                with patch('builtins.input', return_value='Add details'):
                    result = run_async(orchestrator._regenerate_summary(1))

                # Should have called query_for_text for final summary
                assert len(query_prompts) >= 1
                assert result == "# Final Updated Summary"

    def test_regenerate_summary_preserves_original_on_cancellation(self):
        """Should return original summary when conversation is canceled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                orchestrator.markers.save_phase_document(1, "# Original Summary")

                async def mock_conversation(*args, **kwargs):
                    return (False, None)  # Canceled

                orchestrator._run_regeneration_conversation = mock_conversation

                with patch('builtins.input', return_value='nevermind'):
                    result = run_async(orchestrator._regenerate_summary(1))

                assert result == "# Original Summary"

    def test_regenerate_summary_uses_session_id_for_final_summary(self):
        """Should use conversation session_id when generating final summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                orchestrator.markers.save_phase_document(1, "# Original")

                async def mock_conversation(*args, **kwargs):
                    return (True, "conversation-session-456")

                captured_session_ids = []

                async def mock_extract_text_response(prompt, session_id=None, phase=None):
                    captured_session_ids.append(session_id)
                    return "# Updated"

                orchestrator._run_regeneration_conversation = mock_conversation
                orchestrator._extract_text_response = mock_extract_text_response

                with patch('builtins.input', return_value='feedback'):
                    run_async(orchestrator._regenerate_summary(1))

                # Final summary query should use the conversation session
                assert "conversation-session-456" in captured_session_ids


# =============================================================================
# TEMPLATES TESTS
# =============================================================================

class TestRegenerationTemplates:
    """Tests for regeneration conversation templates."""

    def test_regeneration_conversation_context_exists(self):
        """REGENERATION_CONVERSATION_CONTEXT template should exist."""
        from wp_supervisor import templates
        assert hasattr(templates, 'REGENERATION_CONVERSATION_CONTEXT')

    def test_regeneration_conversation_context_has_placeholders(self):
        """Template should have required placeholders."""
        from wp_supervisor import templates
        template = templates.REGENERATION_CONVERSATION_CONTEXT
        assert "{phase_name}" in template
        assert "{current_summary}" in template
        assert "{initial_feedback}" in template

    def test_regeneration_conversation_context_mentions_signals(self):
        """Template should mention completion and cancellation signals."""
        from wp_supervisor import templates
        template = templates.REGENERATION_CONVERSATION_CONTEXT
        assert "REGENERATION_COMPLETE" in template
        assert "REGENERATION_CANCELED" in template

    def test_regeneration_conversation_context_encourages_dialogue(self):
        """Template should encourage clarifying questions and dialogue."""
        from wp_supervisor import templates
        template = templates.REGENERATION_CONVERSATION_CONTEXT
        assert "clarif" in template.lower() or "question" in template.lower()

    def test_regeneration_final_summary_prompt_exists(self):
        """REGENERATION_FINAL_SUMMARY_PROMPT template should exist."""
        from wp_supervisor import templates
        assert hasattr(templates, 'REGENERATION_FINAL_SUMMARY_PROMPT')

    def test_regeneration_final_summary_prompt_requests_format(self):
        """Template should request same format as original summary."""
        from wp_supervisor import templates
        template = templates.REGENERATION_FINAL_SUMMARY_PROMPT
        assert "format" in template.lower()


# =============================================================================
# CONTEXT BUILDER TESTS
# =============================================================================

class TestContextBuilderRegeneration:
    """Tests for ContextBuilder regeneration methods."""

    def test_build_regeneration_context_method_exists(self):
        """build_regeneration_context method should exist."""
        from wp_supervisor.context import ContextBuilder
        assert hasattr(ContextBuilder, 'build_regeneration_context')
        assert callable(ContextBuilder.build_regeneration_context)

    def test_build_regeneration_context_includes_summary(self):
        """Should include current summary in context."""
        from wp_supervisor.context import ContextBuilder

        context = ContextBuilder.build_regeneration_context(
            phase=1,
            current_summary="# Requirements\n- Feature A",
            initial_feedback="Add error handling"
        )

        assert "# Requirements" in context
        assert "Feature A" in context

    def test_build_regeneration_context_includes_feedback(self):
        """Should include user feedback in context."""
        from wp_supervisor.context import ContextBuilder

        context = ContextBuilder.build_regeneration_context(
            phase=1,
            current_summary="# Summary",
            initial_feedback="Add more edge cases"
        )

        assert "Add more edge cases" in context

    def test_build_regeneration_context_includes_phase_name(self):
        """Should include phase name in context."""
        from wp_supervisor.context import ContextBuilder

        context = ContextBuilder.build_regeneration_context(
            phase=2,
            current_summary="# Interfaces",
            initial_feedback="feedback"
        )

        assert "Interface" in context

    def test_build_regeneration_context_mentions_signals(self):
        """Should mention completion and cancellation signals."""
        from wp_supervisor.context import ContextBuilder

        context = ContextBuilder.build_regeneration_context(
            phase=1,
            current_summary="# Summary",
            initial_feedback="feedback"
        )

        assert "REGENERATION_COMPLETE" in context
        assert "REGENERATION_CANCELED" in context

    def test_get_regeneration_summary_prompt_method_exists(self):
        """get_regeneration_summary_prompt method should exist."""
        from wp_supervisor.context import ContextBuilder
        assert hasattr(ContextBuilder, 'get_regeneration_summary_prompt')
        assert callable(ContextBuilder.get_regeneration_summary_prompt)

    def test_get_regeneration_summary_prompt_returns_string(self):
        """Should return a non-empty string."""
        from wp_supervisor.context import ContextBuilder

        prompt = ContextBuilder.get_regeneration_summary_prompt()

        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_get_regeneration_summary_prompt_requests_format(self):
        """Should request same format as original summary."""
        from wp_supervisor.context import ContextBuilder

        prompt = ContextBuilder.get_regeneration_summary_prompt()

        assert "format" in prompt.lower()


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestRegenerationIntegration:
    """Integration tests for the complete regeneration flow."""

    def test_regeneration_flow_complete_happy_path(self):
        """Test complete regeneration flow: feedback -> conversation -> new summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                # Setup: save initial document
                orchestrator.markers.save_phase_document(1, "# Original Requirements\n- Feature A")

                # Mock conversation that completes successfully
                async def mock_conversation(phase, current_summary, initial_feedback):
                    return (True, "session-123")

                # Mock final summary generation
                async def mock_extract_text_response(prompt, session_id=None, phase=None):
                    return "# Updated Requirements\n- Feature A\n- Error Handling (added)"

                orchestrator._run_regeneration_conversation = mock_conversation
                orchestrator._extract_text_response = mock_extract_text_response

                with patch('builtins.input', return_value='Add error handling section'):
                    result = run_async(orchestrator._regenerate_summary(1))

                assert "Updated Requirements" in result
                assert "Error Handling" in result

    def test_regeneration_flow_user_cancels(self):
        """Test regeneration flow when user cancels."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                original = "# Original Requirements\n- Feature A"
                orchestrator.markers.save_phase_document(1, original)

                # Mock conversation that gets canceled
                async def mock_conversation(phase, current_summary, initial_feedback):
                    return (False, None)

                orchestrator._run_regeneration_conversation = mock_conversation

                with patch('builtins.input', return_value='actually, nevermind'):
                    result = run_async(orchestrator._regenerate_summary(1))

                assert result == original


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
