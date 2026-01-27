#!/usr/bin/env python3
"""
Unit tests for wp_supervisor/orchestrator.py - WPOrchestrator class

Note: These tests mock the claude-agent-sdk to test orchestrator logic
without requiring actual Claude API calls.
"""

import io
import os
import sys
import tempfile
import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# Mock claude_agent_sdk before importing orchestrator
# Define mock classes as real classes (not MagicMock instances) for isinstance() checks
class MockAssistantMessage:
    """Mock AssistantMessage class for isinstance() checks."""
    pass

class MockResultMessage:
    """Mock ResultMessage class for isinstance() checks."""
    pass

class MockClaudeSDKClient:
    """Mock ClaudeSDKClient class for E2E tests."""
    _mock_responses = []  # Class-level storage for mock responses

    def __init__(self, options=None):
        self.options = options
        self._connected = False
        self._prompt = None

    async def connect(self, prompt=None):
        self._connected = True
        self._prompt = prompt

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
        return False

    async def receive_messages(self):
        """Yield mock messages based on the prompt."""
        if MockClaudeSDKClient._mock_responses:
            for msg in MockClaudeSDKClient._mock_responses:
                yield msg
        else:
            # Default mock response
            mock_msg = MockAssistantMessage()
            mock_msg.session_id = "test-session-123"
            text_block = MagicMock()
            text_block.text = "---PHASE_COMPLETE---"
            mock_msg.content = [text_block]
            yield mock_msg

    async def query(self, user_input, session_id="default"):
        self._prompt = user_input

    async def receive_response(self):
        """Yield mock response based on stored prompt."""
        mock_msg = MockAssistantMessage()
        mock_msg.session_id = "test-session-123"
        text_block = MagicMock()
        text_block.text = "---PHASE_COMPLETE---"
        mock_msg.content = [text_block]
        yield mock_msg

    async def disconnect(self):
        self._connected = False

mock_sdk = MagicMock()
mock_sdk.ClaudeSDKClient = MockClaudeSDKClient
mock_sdk.ClaudeAgentOptions = MagicMock()
mock_types = MagicMock()
mock_types.AssistantMessage = MockAssistantMessage
mock_types.ResultMessage = MockResultMessage
mock_sdk.types = mock_types
sys.modules['claude_agent_sdk'] = mock_sdk
sys.modules['claude_agent_sdk.types'] = mock_types

# Add wp_supervisor to path
sys.path.insert(0, '.')
from wp_supervisor.markers import SupervisorMarkers
from wp_supervisor.context import ContextBuilder
from wp_supervisor.orchestrator import read_user_input


# Helper to run async functions in tests
def run_async(coro):
    """Run an async function synchronously for testing."""
    return asyncio.run(coro)


class TestReadUserInput:
    """Tests for read_user_input function with file support."""

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

    def test_file_input_absolute_path(self, capsys):
        """Absolute path to existing file loads content."""
        file_content = "Content from absolute path"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(file_content)
            temp_path = f.name

        try:
            with patch('builtins.input', return_value=temp_path):
                result = read_user_input()

            assert result == file_content
        finally:
            os.unlink(temp_path)

    def test_file_input_relative_path(self, capsys):
        """Relative path ./file loads content."""
        file_content = "Content from relative path"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, dir='.') as f:
            f.write(file_content)
            temp_name = os.path.basename(f.name)

        try:
            with patch('builtins.input', return_value=f"./{temp_name}"):
                result = read_user_input()

            assert result == file_content
        finally:
            os.unlink(temp_name)

    def test_file_input_home_path(self, capsys):
        """Home path ~/file loads content."""
        file_content = "Content from home path"
        home_dir = os.path.expanduser("~")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, dir=home_dir) as f:
            f.write(file_content)
            temp_name = os.path.basename(f.name)

        try:
            with patch('builtins.input', return_value=f"~/{temp_name}"):
                result = read_user_input()

            assert result == file_content
        finally:
            os.unlink(os.path.join(home_dir, temp_name))

    def test_file_not_found_returns_empty(self, capsys):
        """Non-existent file with @ prefix returns empty and prints error."""
        with patch('builtins.input', return_value="@/nonexistent/file.md"):
            result = read_user_input()

        assert result == ""
        captured = capsys.readouterr()
        assert "File not found" in captured.out

    def test_path_like_text_not_existing_file(self):
        """Path-like text that's not a file returns as text."""
        # This looks like a path but doesn't exist, so treat as regular text
        with patch('builtins.input', return_value="/not/a/real/file"):
            result = read_user_input()

        assert result == "/not/a/real/file"

    def test_structured_requirements_from_file(self, capsys):
        """Complex structured requirements from file."""
        jira_content = """# User Authentication Feature

## Description
Implement OAuth2 login for the application.

## Acceptance Criteria
- Users can login with Google
- Users can login with GitHub
- Session persists for 7 days

## Technical Notes
Use JWT tokens for session management.
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(jira_content)
            temp_path = f.name

        try:
            with patch('builtins.input', return_value=f"@{temp_path}"):
                result = read_user_input()

            assert "User Authentication Feature" in result
            assert "Acceptance Criteria" in result
            assert "- Users can login with Google" in result
            assert "JWT tokens" in result
        finally:
            os.unlink(temp_path)


class TestWPOrchestratorInit:
    """Tests for WPOrchestrator initialization."""

    def test_init_sets_working_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                assert orchestrator.working_dir == Path(tmpdir).resolve()

    def test_init_defaults_to_cwd(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch('os.getcwd', return_value=tmpdir):
                    from wp_supervisor.orchestrator import WPOrchestrator
                    orchestrator = WPOrchestrator()
                    assert orchestrator.working_dir == Path(tmpdir).resolve()

    def test_init_creates_markers_instance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                assert isinstance(orchestrator.markers, SupervisorMarkers)

    def test_init_raises_for_invalid_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                with pytest.raises(ValueError) as exc_info:
                    WPOrchestrator(working_dir="/nonexistent/path/xyz")
                assert "does not exist" in str(exc_info.value)

    def test_init_resolves_relative_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                # Use current directory which should exist
                orchestrator = WPOrchestrator(working_dir=".")
                assert orchestrator.working_dir.is_absolute()


class TestOrchestratorSignals:
    """Tests for orchestrator signal constants."""

    def test_phase_complete_signal_exists(self):
        from wp_supervisor.orchestrator import WPOrchestrator
        assert hasattr(WPOrchestrator, 'PHASE_COMPLETE_SIGNAL')
        assert WPOrchestrator.PHASE_COMPLETE_SIGNAL == "---PHASE_COMPLETE---"

    def test_summary_verified_signal_exists(self):
        from wp_supervisor.orchestrator import WPOrchestrator
        assert hasattr(WPOrchestrator, 'SUMMARY_VERIFIED_SIGNAL')
        assert WPOrchestrator.SUMMARY_VERIFIED_SIGNAL == "SUMMARY_VERIFIED"

    def test_gaps_found_signal_exists(self):
        from wp_supervisor.orchestrator import WPOrchestrator
        assert hasattr(WPOrchestrator, 'GAPS_FOUND_SIGNAL')
        assert WPOrchestrator.GAPS_FOUND_SIGNAL == "GAPS_FOUND"

    def test_phase_names_dict_exists(self):
        from wp_supervisor.templates import PHASE_NAMES
        assert 1 in PHASE_NAMES
        assert 2 in PHASE_NAMES
        assert 3 in PHASE_NAMES
        assert 4 in PHASE_NAMES


class TestRunPhase:
    """Tests for _run_phase method."""

    def test_run_phase_sets_phase_marker(self):
        """Test that _run_phase sets the correct phase marker for each phase."""
        for phase in [1, 2, 3, 4]:
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.object(Path, 'home', return_value=Path(tmpdir)):
                    from wp_supervisor.orchestrator import WPOrchestrator
                    orchestrator = WPOrchestrator(working_dir=tmpdir)

                    # Set up prerequisites for phases 2-4
                    if phase >= 2:
                        orchestrator.markers.save_requirements_summary("# Requirements")
                    if phase >= 3:
                        orchestrator.markers.save_interfaces_list("# Interfaces")
                    if phase == 4:
                        orchestrator.markers.save_tests_list("# Tests")

                    phase_during_session = None

                    async def mock_run_session(*args, **kwargs):
                        nonlocal phase_during_session
                        phase_during_session = orchestrator.markers.get_phase()

                    async def mock_generate_and_verify(*args, **kwargs):
                        return "# Summary"

                    async def mock_confirm(*args, **kwargs):
                        return 'proceed'

                    orchestrator._run_phase_session = mock_run_session
                    orchestrator._generate_and_verify_summary = mock_generate_and_verify
                    orchestrator._confirm_phase_completion = mock_confirm

                    run_async(orchestrator._run_phase(phase, "test task" if phase == 1 else None))

                    assert phase_during_session == phase

    def test_run_phase_saves_requirements_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                async def mock_run_session(*args, **kwargs):
                    pass

                async def mock_generate_and_verify(*args, **kwargs):
                    return "# Requirements\n- Feature A"

                async def mock_confirm(*args, **kwargs):
                    return 'proceed'

                orchestrator._run_phase_session = mock_run_session
                orchestrator._generate_and_verify_summary = mock_generate_and_verify
                orchestrator._confirm_phase_completion = mock_confirm

                run_async(orchestrator._run_phase(1, "test"))

                saved = orchestrator.markers.get_requirements_summary()
                assert "# Requirements" in saved

    def test_run_phase_saves_interfaces_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                orchestrator.markers.save_requirements_summary("# Requirements")

                async def mock_run_session(*args, **kwargs):
                    pass

                async def mock_generate_and_verify(*args, **kwargs):
                    return "# Interfaces\n- ServiceA"

                async def mock_confirm(*args, **kwargs):
                    return 'proceed'

                orchestrator._run_phase_session = mock_run_session
                orchestrator._generate_and_verify_summary = mock_generate_and_verify
                orchestrator._confirm_phase_completion = mock_confirm

                run_async(orchestrator._run_phase(2))

                saved = orchestrator.markers.get_interfaces_list()
                assert "# Interfaces" in saved

    def test_run_phase_saves_tests_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                orchestrator.markers.save_requirements_summary("# Requirements")
                orchestrator.markers.save_interfaces_list("# Interfaces")

                async def mock_run_session(*args, **kwargs):
                    pass

                async def mock_generate_and_verify(*args, **kwargs):
                    return "# Tests\n- test_feature"

                async def mock_confirm(*args, **kwargs):
                    return 'proceed'

                orchestrator._run_phase_session = mock_run_session
                orchestrator._generate_and_verify_summary = mock_generate_and_verify
                orchestrator._confirm_phase_completion = mock_confirm

                run_async(orchestrator._run_phase(3))

                saved = orchestrator.markers.get_tests_list()
                assert "# Tests" in saved

    def test_run_phase4_keeps_documents_removes_state(self):
        """Test that phase 4 removes state.json but keeps document files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                orchestrator.markers.initialize()
                orchestrator.markers.save_requirements_summary("# Requirements")
                orchestrator.markers.save_interfaces_list("# Interfaces")
                orchestrator.markers.save_tests_list("# Tests")

                async def mock_run_session(*args, **kwargs):
                    pass

                orchestrator._run_phase_session = mock_run_session

                run_async(orchestrator._run_phase(4))

                # Directory should still exist (documents preserved)
                assert orchestrator.markers.markers_dir.exists()
                # But state.json should be removed
                state_file = orchestrator.markers.markers_dir / "state.json"
                assert not state_file.exists()
                # Document files should still exist
                assert (orchestrator.markers.markers_dir / "phase1-requirements.md").exists()
                assert (orchestrator.markers.markers_dir / "phase2-interfaces.md").exists()
                assert (orchestrator.markers.markers_dir / "phase3-tests.md").exists()

    def test_run_phase_edit_reloads_document(self):
        """Test that 'edit' action re-reads the document file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                async def mock_run_session(*args, **kwargs):
                    pass

                async def mock_generate_and_verify(*args, **kwargs):
                    return "# Original Requirements"

                # First call returns 'edit', second returns 'proceed'
                confirm_calls = []
                async def mock_confirm(phase, doc_path="", session_id=None):
                    confirm_calls.append(phase)
                    if len(confirm_calls) == 1:
                        # Simulate user editing the file
                        orchestrator.markers.save_phase_document(phase, "# Edited Requirements")
                        return 'edit'
                    return 'proceed'

                orchestrator._run_phase_session = mock_run_session
                orchestrator._generate_and_verify_summary = mock_generate_and_verify
                orchestrator._confirm_phase_completion = mock_confirm

                run_async(orchestrator._run_phase(1, "test"))

                # Verify the edited content was saved to markers
                saved = orchestrator.markers.get_requirements_summary()
                assert "# Edited Requirements" in saved

    def test_run_phase_regenerate_calls_regenerate_summary(self):
        """Test that 'regenerate' action calls _regenerate_summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                async def mock_run_session(*args, **kwargs):
                    pass

                async def mock_generate_and_verify(*args, **kwargs):
                    return "# Original Requirements"

                regenerate_called = []
                async def mock_regenerate(phase, session_id=None):
                    regenerate_called.append(phase)
                    return "# Regenerated Requirements"

                # First call returns 'regenerate', second returns 'proceed'
                confirm_calls = []
                async def mock_confirm(phase, doc_path="", session_id=None):
                    confirm_calls.append(phase)
                    if len(confirm_calls) == 1:
                        return 'regenerate'
                    return 'proceed'

                orchestrator._run_phase_session = mock_run_session
                orchestrator._generate_and_verify_summary = mock_generate_and_verify
                orchestrator._confirm_phase_completion = mock_confirm
                orchestrator._regenerate_summary = mock_regenerate

                run_async(orchestrator._run_phase(1, "test"))

                # Verify regenerate was called
                assert 1 in regenerate_called
                # Verify the regenerated content was saved
                saved = orchestrator.markers.get_requirements_summary()
                assert "# Regenerated Requirements" in saved


class TestRegenerateSummary:
    """Tests for _regenerate_summary method."""

    def test_regenerate_summary_returns_current_on_empty_feedback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                # Save initial document
                orchestrator.markers.save_phase_document(1, "# Current Summary")

                with patch('builtins.input', return_value=''):
                    result = run_async(orchestrator._regenerate_summary(1))

                assert result == "# Current Summary"

    def test_regenerate_summary_calls_conversation_with_feedback(self):
        """Test that _regenerate_summary calls _run_regeneration_conversation with feedback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                # Save initial document
                orchestrator.markers.save_phase_document(1, "# Current Summary")

                # Track conversation calls
                conversation_calls = []

                async def mock_run_conversation(phase, current_summary, initial_feedback):
                    conversation_calls.append({
                        'phase': phase,
                        'current_summary': current_summary,
                        'initial_feedback': initial_feedback
                    })
                    return (True, "session-123")

                async def mock_extract_text_response(prompt, session_id=None, phase=None):
                    return "# Updated Summary"

                orchestrator._run_regeneration_conversation = mock_run_conversation
                orchestrator._extract_text_response = mock_extract_text_response

                with patch('builtins.input', return_value='Add error handling section'):
                    result = run_async(orchestrator._regenerate_summary(1))

                assert result == "# Updated Summary"
                assert len(conversation_calls) == 1
                assert conversation_calls[0]['phase'] == 1
                assert conversation_calls[0]['initial_feedback'] == "Add error handling section"
                assert "# Current Summary" in conversation_calls[0]['current_summary']


class TestGenerateAndVerifySummary:
    """Tests for _generate_and_verify_summary method."""

    def test_generate_and_verify_returns_empty_for_phase4(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                # Phase 4 has no summary prompt, should return empty
                result = run_async(orchestrator._generate_and_verify_summary(4))
                assert result == ""

    def test_generate_and_verify_calls_extract_text_response(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                call_count = 0

                async def mock_extract_text_response(prompt, session_id=None, phase=None):
                    nonlocal call_count
                    call_count += 1
                    if call_count == 1:
                        return "# Initial Summary"
                    else:
                        return "SUMMARY_VERIFIED\n# Initial Summary"

                orchestrator._extract_text_response = mock_extract_text_response

                result = run_async(orchestrator._generate_and_verify_summary(1))

                # Should call query twice: once for summary, once for review
                assert call_count == 2

    def test_generate_and_verify_handles_gaps_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                call_count = 0

                async def mock_extract_text_response(prompt, session_id=None, phase=None):
                    nonlocal call_count
                    call_count += 1
                    if call_count == 1:
                        return "# Initial Summary"
                    else:
                        return "GAPS_FOUND\n# Updated Summary with additions"

                orchestrator._extract_text_response = mock_extract_text_response

                result = run_async(orchestrator._generate_and_verify_summary(1))

                assert "Updated Summary" in result

    def test_generate_and_verify_handles_verified(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                call_count = 0

                async def mock_extract_text_response(prompt, session_id=None, phase=None):
                    nonlocal call_count
                    call_count += 1
                    if call_count == 1:
                        return "# Initial Summary"
                    else:
                        return "SUMMARY_VERIFIED\n# Verified Summary"

                orchestrator._extract_text_response = mock_extract_text_response

                result = run_async(orchestrator._generate_and_verify_summary(1))

                assert "Verified Summary" in result

    def test_generate_and_verify_handles_non_standard_response(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                call_count = 0

                async def mock_extract_text_response(prompt, session_id=None, phase=None):
                    nonlocal call_count
                    call_count += 1
                    if call_count == 1:
                        return "# Initial Summary"
                    else:
                        # Response doesn't follow expected format
                        return "# Some other response"

                orchestrator._extract_text_response = mock_extract_text_response

                result = run_async(orchestrator._generate_and_verify_summary(1))

                # Should use the review response as-is
                assert "Some other response" in result


class TestRunSupervisor:
    """Tests for run_supervisor function."""

    def test_run_supervisor_function_exists(self):
        from wp_supervisor.orchestrator import run_supervisor
        assert callable(run_supervisor)


class TestKeyboardInterruptHandling:
    """Tests for keyboard interrupt handling."""

    def test_keyboard_interrupt_cleans_up_markers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                orchestrator.markers.initialize()

                # Simulate keyboard interrupt during phase
                async def raise_interrupt(*args, **kwargs):
                    raise KeyboardInterrupt()

                orchestrator._run_phase = raise_interrupt

                # The orchestrator catches KeyboardInterrupt internally
                # and cleans up markers
                run_async(orchestrator.run())

                # Markers should be cleaned up on interrupt
                assert not orchestrator.markers.markers_dir.exists()


class TestConfirmPhaseCompletion:
    """Tests for _confirm_phase_completion method."""

    def test_confirm_phase_completion_accepts_y(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                with patch('builtins.input', return_value='y'):
                    result = run_async(orchestrator._confirm_phase_completion(1))
                    assert result == 'proceed'

    def test_confirm_phase_completion_accepts_yes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                with patch('builtins.input', return_value='yes'):
                    result = run_async(orchestrator._confirm_phase_completion(1))
                    assert result == 'proceed'

    def test_confirm_phase_completion_accepts_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                with patch('builtins.input', return_value=''):
                    result = run_async(orchestrator._confirm_phase_completion(1))
                    assert result == 'proceed'

    def test_confirm_phase_completion_retries_on_invalid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                # First invalid, then valid
                inputs = iter(['invalid', 'y'])
                with patch('builtins.input', lambda _: next(inputs)):
                    result = run_async(orchestrator._confirm_phase_completion(1))
                    assert result == 'proceed'

    def test_confirm_phase_completion_edit_option(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                # 'e' then Enter to confirm done editing
                inputs = iter(['e', ''])
                with patch('builtins.input', lambda _: next(inputs)):
                    result = run_async(orchestrator._confirm_phase_completion(1, "/path/to/doc.md"))
                    assert result == 'edit'

    def test_confirm_phase_completion_regenerate_option(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                with patch('builtins.input', return_value='r'):
                    result = run_async(orchestrator._confirm_phase_completion(1))
                    assert result == 'regenerate'


class TestContextPassing:
    """Tests for context passing between phases."""

    def test_phase2_receives_requirements_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                orchestrator.markers.save_requirements_summary("# Saved Requirements")

                captured_context = None

                async def capture_context(context, phase):
                    nonlocal captured_context
                    captured_context = context

                async def mock_generate_and_verify(*args, **kwargs):
                    return "# Interfaces"

                async def mock_confirm(*args, **kwargs):
                    return 'proceed'

                orchestrator._run_phase_session = capture_context
                orchestrator._generate_and_verify_summary = mock_generate_and_verify
                orchestrator._confirm_phase_completion = mock_confirm

                run_async(orchestrator._run_phase(2))

                assert "# Saved Requirements" in captured_context

    def test_phase3_receives_requirements_and_interfaces(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                orchestrator.markers.save_requirements_summary("# Requirements Summary")
                orchestrator.markers.save_interfaces_list("# Interfaces List")

                captured_context = None

                async def capture_context(context, phase):
                    nonlocal captured_context
                    captured_context = context

                async def mock_generate_and_verify(*args, **kwargs):
                    return "# Tests"

                async def mock_confirm(*args, **kwargs):
                    return 'proceed'

                orchestrator._run_phase_session = capture_context
                orchestrator._generate_and_verify_summary = mock_generate_and_verify
                orchestrator._confirm_phase_completion = mock_confirm

                run_async(orchestrator._run_phase(3))

                assert "# Requirements Summary" in captured_context
                assert "# Interfaces List" in captured_context

    def test_phase4_receives_all_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                orchestrator.markers.save_requirements_summary("# Req Summary")
                orchestrator.markers.save_interfaces_list("# Int List")
                orchestrator.markers.save_tests_list("# Test List")

                captured_context = None

                async def capture_context(context, phase):
                    nonlocal captured_context
                    captured_context = context

                orchestrator._run_phase_session = capture_context

                run_async(orchestrator._run_phase(4))

                assert "# Req Summary" in captured_context
                assert "# Int List" in captured_context
                assert "# Test List" in captured_context

    def test_phase_context_includes_agents(self):
        """Should load and append phase-bound agents to context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                # Create agents directory with a phase 1 agent
                agents_dir = Path(tmpdir) / ".claude" / "waypoints" / "agents"
                agents_dir.mkdir(parents=True)

                agent_file = agents_dir / "test-agent.md"
                agent_file.write_text("""---
name: Test Agent
phases: [1]
---

# Test Agent Instructions

This is test agent content.
""")

                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                captured_context = None

                async def capture_context(context, phase):
                    nonlocal captured_context
                    captured_context = context

                async def mock_generate_and_verify(*args, **kwargs):
                    return "# Requirements"

                async def mock_confirm(*args, **kwargs):
                    return 'proceed'

                orchestrator._run_phase_session = capture_context
                orchestrator._generate_and_verify_summary = mock_generate_and_verify
                orchestrator._confirm_phase_completion = mock_confirm

                # Set WP_INSTALL_DIR to our temp dir so agent loader finds agents
                with patch.dict(os.environ, {"WP_INSTALL_DIR": str(Path(tmpdir) / ".claude" / "waypoints")}):
                    # Reinitialize agent_loader with the patched env
                    from wp_agents import AgentLoader
                    orchestrator.agent_loader = AgentLoader()

                    run_async(orchestrator._run_phase(1, initial_task="Build a feature"))

                assert captured_context is not None
                assert "# Phase Agents" in captured_context
                assert "Test Agent" in captured_context
                assert "This is test agent content" in captured_context


@pytest.mark.skipif(
    os.environ.get('RUN_E2E_TESTS') != '1',
    reason="E2E tests skipped by default. Use --e2e flag or set RUN_E2E_TESTS=1"
)
class TestSupervisorEndToEnd:
    """End-to-end tests for full supervisor workflow."""

    def _create_mock_client_class(self, phases_executed: list, captured_prompts: list = None):
        """
        Create a mock ClaudeSDKClient class that tracks phases.

        Args:
            phases_executed: List to track which phases were executed
            captured_prompts: Optional list to capture prompts

        Returns:
            Mock ClaudeSDKClient class
        """
        class MockClient:
            def __init__(self, options=None):
                self.options = options
                self._prompt = None

            async def connect(self, prompt=None):
                if prompt:
                    self._prompt = prompt

            async def __aenter__(self):
                await self.connect()
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                await self.disconnect()
                return False

            async def query(self, user_input, session_id="default"):
                self._prompt = user_input
                if captured_prompts is not None:
                    captured_prompts.append(user_input)

            async def receive_response(self):
                prompt = self._prompt or ""

                # Determine response based on prompt content
                if "Phase 4:" in prompt or "Phase 4 of" in prompt:
                    phases_executed.append(4)
                    text = "All tests passing! ---PHASE_COMPLETE---"
                elif "Phase 3:" in prompt or "Phase 3 of" in prompt:
                    phases_executed.append(3)
                    text = "I've written the tests. ---PHASE_COMPLETE---"
                elif "Phase 2:" in prompt or "Phase 2 of" in prompt:
                    phases_executed.append(2)
                    text = "I've designed the interfaces. ---PHASE_COMPLETE---"
                elif "Phase 1:" in prompt or "Phase 1 of" in prompt:
                    phases_executed.append(1)
                    text = "I understand you want to build a feature. ---PHASE_COMPLETE---"
                elif "summary" in prompt.lower():
                    text = "# Summary\n- Item 1\n- Item 2"
                elif "review" in prompt.lower() or "verify" in prompt.lower():
                    text = "SUMMARY_VERIFIED\n# Summary\n- Item 1\n- Item 2"
                else:
                    text = "OK, continuing..."

                mock_msg = MockAssistantMessage()
                mock_msg.session_id = "test-session-123"
                text_block = MagicMock()
                text_block.text = text
                mock_msg.content = [text_block]
                yield mock_msg

            async def disconnect(self):
                pass

        return MockClient

    def test_complete_workflow_all_four_phases(self):
        """
        End-to-end test: Run complete Waypoints workflow through all 4 phases.

        This test verifies:
        1. All 4 phases execute in order
        2. Summaries are generated and saved between phases
        3. Context is passed correctly between phases
        4. Markers are cleaned up at the end
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator

                # Track which phases were executed
                phases_executed = []

                # Create orchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                # Create mock client class
                MockClient = self._create_mock_client_class(phases_executed)

                # Mock user confirmations (always say 'y' to proceed)
                with patch('builtins.input', return_value='y'):
                    # Patch ClaudeSDKClient
                    with patch('wp_supervisor.orchestrator.ClaudeSDKClient', MockClient):
                        with patch('wp_supervisor.orchestrator.AssistantMessage', MockAssistantMessage):
                            with patch('wp_supervisor.orchestrator.ResultMessage', MockResultMessage):
                                # Run the complete workflow
                                run_async(orchestrator.run(initial_task="Build a test feature"))

                # Verify all 4 phases were executed
                assert 1 in phases_executed, "Phase 1 should have executed"
                assert 2 in phases_executed, "Phase 2 should have executed"
                assert 3 in phases_executed, "Phase 3 should have executed"
                assert 4 in phases_executed, "Phase 4 should have executed"

                # Verify phases executed in order
                phase_order = [p for p in phases_executed if p in [1, 2, 3, 4]]
                assert phase_order == [1, 2, 3, 4], f"Phases should execute in order, got {phase_order}"

                # Verify state.json was cleaned up but documents preserved
                assert orchestrator.markers.markers_dir.exists(), \
                    "Documents directory should be preserved after successful completion"
                state_file = orchestrator.markers.markers_dir / "state.json"
                assert not state_file.exists(), \
                    "state.json should be removed after successful completion"

    def test_workflow_saves_summaries_between_phases(self):
        """
        End-to-end test: Verify summaries are saved and passed between phases.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator

                phases_executed = []
                saved_documents = {}

                # Create orchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                # Capture documents as they're saved
                original_save_doc = orchestrator.markers.save_phase_document

                def capture_document(phase, content):
                    saved_documents[phase] = content
                    return original_save_doc(phase, content)

                orchestrator.markers.save_phase_document = capture_document

                MockClient = self._create_mock_client_class(phases_executed)

                with patch('builtins.input', return_value='y'):
                    with patch('wp_supervisor.orchestrator.ClaudeSDKClient', MockClient):
                        with patch('wp_supervisor.orchestrator.AssistantMessage', MockAssistantMessage):
                            with patch('wp_supervisor.orchestrator.ResultMessage', MockResultMessage):
                                run_async(orchestrator.run(initial_task="Build a feature"))

                # Verify documents were saved for phases 1-3
                assert 1 in saved_documents, "Phase 1 document should be saved"
                assert 2 in saved_documents, "Phase 2 document should be saved"
                assert 3 in saved_documents, "Phase 3 document should be saved"

                # Verify documents have content
                assert len(saved_documents[1]) > 0, "Phase 1 document should have content"
                assert len(saved_documents[2]) > 0, "Phase 2 document should have content"
                assert len(saved_documents[3]) > 0, "Phase 3 document should have content"

    def test_workflow_with_initial_task(self):
        """
        End-to-end test: Verify initial task is passed to phase 1.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator

                phases_executed = []
                captured_prompts = []

                MockClient = self._create_mock_client_class(phases_executed, captured_prompts)

                orchestrator = WPOrchestrator(working_dir=tmpdir)

                with patch('builtins.input', return_value='y'):
                    with patch('wp_supervisor.orchestrator.ClaudeSDKClient', MockClient):
                        with patch('wp_supervisor.orchestrator.AssistantMessage', MockAssistantMessage):
                            with patch('wp_supervisor.orchestrator.ResultMessage', MockResultMessage):
                                run_async(orchestrator.run(initial_task="Build a REST API for users"))

                # Verify initial task appears in phase 1 prompt
                phase1_prompts = [p for p in captured_prompts if "Phase 1" in p]
                assert len(phase1_prompts) > 0, "Should have phase 1 prompt"
                assert "Build a REST API for users" in phase1_prompts[0], \
                    "Initial task should be in phase 1 context"


class TestExtractAndStageKnowledge:
    """
    Integration tests for _extract_and_stage_knowledge method.

    These tests verify the orchestrator correctly integrates:
    - _extract_text_response (mocked)
    - extract_from_text (real)
    - markers.stage_knowledge (real)

    Unit tests for individual components are in test_knowledge_extraction.py.
    """

    def test_stages_knowledge_when_claude_returns_valid_content(self):
        """When Claude returns valid knowledge, it should be staged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                # Mock response with valid knowledge format
                mock_response = """ARCHITECTURE:
- Service Pattern: The service uses a pipeline pattern for processing

DECISIONS:
- Chose REST: REST was chosen over GraphQL for simplicity
"""

                async def mock_query(*args, **kwargs):
                    return mock_response

                orchestrator._extract_text_response = mock_query

                # when
                run_async(orchestrator._extract_and_stage_knowledge(phase=1))

                # then
                assert orchestrator.markers.has_staged_knowledge()

    def test_does_not_stage_when_claude_returns_no_knowledge_extracted(self):
        """When Claude returns NO_KNOWLEDGE_EXTRACTED, nothing should be staged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                mock_response = "NO_KNOWLEDGE_EXTRACTED"

                async def mock_query(*args, **kwargs):
                    return mock_response

                orchestrator._extract_text_response = mock_query

                # when
                run_async(orchestrator._extract_and_stage_knowledge(phase=1))

                # then
                assert not orchestrator.markers.has_staged_knowledge()

    def test_does_not_stage_when_response_has_empty_sections(self):
        """When Claude returns format but no actual entries, nothing should be staged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                # Empty sections - format present but no entries
                mock_response = """ARCHITECTURE:

DECISIONS:

LESSONS_LEARNED:
"""

                async def mock_query(*args, **kwargs):
                    return mock_response

                orchestrator._extract_text_response = mock_query

                # when
                run_async(orchestrator._extract_and_stage_knowledge(phase=1))

                # then
                assert not orchestrator.markers.has_staged_knowledge()

    def test_continues_workflow_when_query_raises_exception(self):
        """When _extract_text_response raises exception, workflow should continue without staging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                async def mock_query_that_fails(*args, **kwargs):
                    raise ConnectionError("Network error")

                orchestrator._extract_text_response = mock_query_that_fails

                # when - should not raise
                run_async(orchestrator._extract_and_stage_knowledge(phase=1))

                # then - no knowledge staged, but no crash
                assert not orchestrator.markers.has_staged_knowledge()

    def test_logs_error_when_query_fails(self):
        """When _extract_text_response fails, error should be logged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                async def mock_query_that_fails(*args, **kwargs):
                    raise ValueError("Test error")

                orchestrator._extract_text_response = mock_query_that_fails

                # Capture log calls
                log_calls = []
                original_log_error = orchestrator.logger.log_error
                def capture_log_error(msg, error=None):
                    log_calls.append(msg)
                    original_log_error(msg, error)
                orchestrator.logger.log_error = capture_log_error

                # when
                run_async(orchestrator._extract_and_stage_knowledge(phase=1))

                # then
                assert any("Knowledge extraction failed" in call for call in log_calls)

    def test_stages_only_architecture_when_only_architecture_present(self):
        """When only architecture is returned, only architecture should be staged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                mock_response = """ARCHITECTURE:
- Pipeline Pattern: Services use a pipeline for data processing
"""

                async def mock_query(*args, **kwargs):
                    return mock_response

                orchestrator._extract_text_response = mock_query

                # when
                run_async(orchestrator._extract_and_stage_knowledge(phase=1))

                # then
                assert orchestrator.markers.has_staged_knowledge()
                staged = orchestrator.markers.get_staged_knowledge()
                assert len(staged.architecture) == 1
                assert len(staged.decisions) == 0
                assert len(staged.lessons_learned) == 0

    def test_stages_lessons_learned_with_tags(self):
        """Lessons learned with tags should be staged correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                mock_response = """LESSONS_LEARNED:
- [Kotlin] Use data classes: Data classes provide equals/hashCode automatically
- [Git] Commit often: Small commits are easier to review
"""

                async def mock_query(*args, **kwargs):
                    return mock_response

                orchestrator._extract_text_response = mock_query

                # when
                run_async(orchestrator._extract_and_stage_knowledge(phase=1))

                # then
                assert orchestrator.markers.has_staged_knowledge()
                staged = orchestrator.markers.get_staged_knowledge()
                assert len(staged.lessons_learned) == 2
                assert staged.lessons_learned[0].tag == "Kotlin"
                assert staged.lessons_learned[1].tag == "Git"

    def test_passes_existing_knowledge_context_to_prompt(self):
        """Existing knowledge context should be included in the extraction prompt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                # Set existing knowledge context
                orchestrator._knowledge_context = "# Existing Architecture\nService A talks to B"

                captured_prompts = []

                async def mock_query(prompt, *args, **kwargs):
                    captured_prompts.append(prompt)
                    return "NO_KNOWLEDGE_EXTRACTED"

                orchestrator._extract_text_response = mock_query

                # when
                run_async(orchestrator._extract_and_stage_knowledge(phase=1))

                # then
                assert len(captured_prompts) == 1
                assert "Existing Architecture" in captured_prompts[0]
                assert "Service A talks to B" in captured_prompts[0]

    def test_uses_default_when_no_existing_knowledge(self):
        """When no existing knowledge, prompt should include default text."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                # No existing knowledge (empty string)
                orchestrator._knowledge_context = ""

                captured_prompts = []

                async def mock_query(prompt, *args, **kwargs):
                    captured_prompts.append(prompt)
                    return "NO_KNOWLEDGE_EXTRACTED"

                orchestrator._extract_text_response = mock_query

                # when
                run_async(orchestrator._extract_and_stage_knowledge(phase=1))

                # then
                assert len(captured_prompts) == 1
                assert "No existing knowledge" in captured_prompts[0]

    def test_accumulates_knowledge_across_phases(self):
        """Knowledge from multiple phases should accumulate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                phase1_response = """ARCHITECTURE:
- Pattern A: Description of pattern A
"""
                phase2_response = """DECISIONS:
- Decision B: Rationale for decision B
"""

                call_count = 0

                async def mock_query(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    if call_count == 1:
                        return phase1_response
                    return phase2_response

                orchestrator._extract_text_response = mock_query

                # when - extract from two phases
                run_async(orchestrator._extract_and_stage_knowledge(phase=1))
                run_async(orchestrator._extract_and_stage_knowledge(phase=2))

                # then - both should be staged
                staged = orchestrator.markers.get_staged_knowledge()
                assert len(staged.architecture) == 1
                assert len(staged.decisions) == 1


class TestApplyKnowledgeAtWorkflowEnd:
    """
    Integration tests for _apply_knowledge_at_workflow_end method.

    Tests the orchestrator's integration with markers for applying staged knowledge.
    """

    def test_does_nothing_when_no_staged_knowledge(self):
        """When no knowledge is staged, should return silently."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                # when - should not raise
                orchestrator._apply_knowledge_at_workflow_end()

                # then - nothing staged, nothing applied
                assert not orchestrator.markers.has_staged_knowledge()

    def test_clears_staged_knowledge_after_apply(self):
        """After applying, staged knowledge should be cleared."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                # Stage some knowledge first
                async def mock_query(*args, **kwargs):
                    return """ARCHITECTURE:
- Pattern: Description
"""
                orchestrator._extract_text_response = mock_query
                run_async(orchestrator._extract_and_stage_knowledge(phase=1))
                assert orchestrator.markers.has_staged_knowledge()

                # when
                orchestrator._apply_knowledge_at_workflow_end()

                # then
                assert not orchestrator.markers.has_staged_knowledge()

    def test_clears_staged_knowledge_even_on_error(self):
        """Even if apply fails, staged knowledge should be cleared to prevent retry loops."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                # Stage some knowledge
                async def mock_query(*args, **kwargs):
                    return """ARCHITECTURE:
- Pattern: Description
"""
                orchestrator._extract_text_response = mock_query
                run_async(orchestrator._extract_and_stage_knowledge(phase=1))

                # Make apply fail
                original_apply = orchestrator.markers.apply_staged_knowledge
                def failing_apply(*args, **kwargs):
                    raise IOError("Disk full")
                orchestrator.markers.apply_staged_knowledge = failing_apply

                # when - should not raise
                orchestrator._apply_knowledge_at_workflow_end()

                # then - staged knowledge should still be cleared
                assert not orchestrator.markers.has_staged_knowledge()


class TestFormatStagedKnowledgeForPrompt:
    """
    Unit tests for format_staged_knowledge_for_prompt function.

    Tests the formatting of staged knowledge entries for inclusion
    in the extraction prompt to prevent duplicates.
    """

    def test_returns_none_yet_when_no_staged_knowledge(self):
        """When no knowledge is staged, should return 'None yet'."""
        # given
        from wp_supervisor.templates import format_staged_knowledge_for_prompt
        sys.path.insert(0, 'hooks/lib')
        from wp_knowledge import StagedKnowledge

        staged = StagedKnowledge()

        # when
        result = format_staged_knowledge_for_prompt(staged)

        # then
        assert result == "None yet"

    def test_formats_architecture_entry_with_title_and_first_sentence(self):
        """Architecture entries should show title and first sentence."""
        # given
        from wp_supervisor.templates import format_staged_knowledge_for_prompt
        sys.path.insert(0, 'hooks/lib')
        from wp_knowledge import StagedKnowledge, StagedKnowledgeEntry

        staged = StagedKnowledge(
            architecture=[
                StagedKnowledgeEntry(
                    title="Pipeline Pattern",
                    content="Services use a pipeline for processing. This enables composability. More details here.",
                    phase=1
                )
            ]
        )

        # when
        result = format_staged_knowledge_for_prompt(staged)

        # then
        assert "Pipeline Pattern" in result
        assert "Services use a pipeline for processing" in result

    def test_formats_decisions_entry(self):
        """Decisions entries should show title and first sentence."""
        # given
        from wp_supervisor.templates import format_staged_knowledge_for_prompt
        sys.path.insert(0, 'hooks/lib')
        from wp_knowledge import StagedKnowledge, StagedKnowledgeEntry

        staged = StagedKnowledge(
            decisions=[
                StagedKnowledgeEntry(
                    title="Event-Driven Design",
                    content="Chose events over polling for responsiveness. This reduces latency significantly.",
                    phase=1
                )
            ]
        )

        # when
        result = format_staged_knowledge_for_prompt(staged)

        # then
        assert "Event-Driven Design" in result
        assert "Chose events over polling" in result

    def test_formats_lessons_learned_with_tag(self):
        """Lessons learned should include the technology tag."""
        # given
        from wp_supervisor.templates import format_staged_knowledge_for_prompt
        sys.path.insert(0, 'hooks/lib')
        from wp_knowledge import StagedKnowledge, StagedKnowledgeEntry

        staged = StagedKnowledge(
            lessons_learned=[
                StagedKnowledgeEntry(
                    title="DSL Builder Pattern",
                    content="WoT generator creates top-level functions. Import them directly.",
                    phase=2,
                    tag="Kotlin"
                )
            ]
        )

        # when
        result = format_staged_knowledge_for_prompt(staged)

        # then
        assert "[Kotlin]" in result
        assert "DSL Builder Pattern" in result

    def test_formats_multiple_categories(self):
        """Should format entries from all categories."""
        # given
        from wp_supervisor.templates import format_staged_knowledge_for_prompt
        sys.path.insert(0, 'hooks/lib')
        from wp_knowledge import StagedKnowledge, StagedKnowledgeEntry

        staged = StagedKnowledge(
            architecture=[
                StagedKnowledgeEntry(title="Pattern A", content="Arch content", phase=1)
            ],
            decisions=[
                StagedKnowledgeEntry(title="Decision B", content="Dec content", phase=1)
            ],
            lessons_learned=[
                StagedKnowledgeEntry(title="Lesson C", content="Lesson content", phase=2, tag="Python")
            ]
        )

        # when
        result = format_staged_knowledge_for_prompt(staged)

        # then
        assert "Pattern A" in result
        assert "Decision B" in result
        assert "Lesson C" in result
        assert "[Python]" in result


class TestStagedKnowledgeInPrompt:
    """
    Integration tests for staged knowledge being passed to extraction prompt.
    """

    def test_staged_knowledge_included_in_prompt(self):
        """Staged knowledge from previous phases should be in extraction prompt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator

                orchestrator = WPOrchestrator(working_dir=tmpdir)

                # Stage some knowledge first (simulating phase 1 extraction)
                async def phase1_query(*args, **kwargs):
                    return """ARCHITECTURE:
- Pipeline Pattern: Services use pipeline for composability
"""
                orchestrator._extract_text_response = phase1_query
                run_async(orchestrator._extract_and_stage_knowledge(phase=1))

                # Capture prompt for phase 2
                captured_prompts = []

                async def phase2_query(prompt, *args, **kwargs):
                    captured_prompts.append(prompt)
                    return "NO_KNOWLEDGE_EXTRACTED"

                orchestrator._extract_text_response = phase2_query

                # when - extract for phase 2
                run_async(orchestrator._extract_and_stage_knowledge(phase=2))

                # then - staged knowledge should be in prompt
                assert len(captured_prompts) == 1
                assert "Pipeline Pattern" in captured_prompts[0]

    def test_no_staged_knowledge_shows_none_yet(self):
        """When no staged knowledge, prompt should show 'None yet'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator

                orchestrator = WPOrchestrator(working_dir=tmpdir)

                captured_prompts = []

                async def mock_query(prompt, *args, **kwargs):
                    captured_prompts.append(prompt)
                    return "NO_KNOWLEDGE_EXTRACTED"

                orchestrator._extract_text_response = mock_query

                # when - extract for phase 1 (no prior staged knowledge)
                run_async(orchestrator._extract_and_stage_knowledge(phase=1))

                # then
                assert len(captured_prompts) == 1
                assert "None yet" in captured_prompts[0]


class TestCodebaseContextInRequirements:
    """Tests that REQUIREMENTS_SUMMARY_PROMPT includes Codebase Context section."""

    def test_requirements_prompt_contains_codebase_context_section(self):
        from wp_supervisor.templates import REQUIREMENTS_SUMMARY_PROMPT
        assert "## Codebase Context" in REQUIREMENTS_SUMMARY_PROMPT

    def test_requirements_prompt_contains_tech_stack(self):
        from wp_supervisor.templates import REQUIREMENTS_SUMMARY_PROMPT
        assert "Tech Stack" in REQUIREMENTS_SUMMARY_PROMPT

    def test_requirements_prompt_contains_key_files(self):
        from wp_supervisor.templates import REQUIREMENTS_SUMMARY_PROMPT
        assert "Key Files" in REQUIREMENTS_SUMMARY_PROMPT

    def test_phase2_context_contains_reuse_guidance(self):
        from wp_supervisor.templates import PHASE2_CONTEXT
        assert "Codebase Context" in PHASE2_CONTEXT
        assert "re-exploring" in PHASE2_CONTEXT

    def test_phase3_context_contains_reuse_guidance(self):
        from wp_supervisor.templates import PHASE3_CONTEXT
        assert "Codebase Context" in PHASE3_CONTEXT

    def test_phase4_context_contains_reuse_guidance(self):
        from wp_supervisor.templates import PHASE4_CONTEXT
        assert "Codebase Context" in PHASE4_CONTEXT


class TestIntegrationTaskGuidance:
    """Tests that phase templates include guidance for modifying existing code."""

    def test_phase2_context_contains_integration_guidance(self):
        from wp_supervisor.templates import PHASE2_CONTEXT
        assert "modify" in PHASE2_CONTEXT.lower() or "existing" in PHASE2_CONTEXT.lower()
        assert "call site" in PHASE2_CONTEXT.lower()

    def test_phase3_context_contains_existing_test_guidance(self):
        from wp_supervisor.templates import PHASE3_CONTEXT
        assert "existing test file" in PHASE3_CONTEXT.lower()

    def test_interfaces_summary_prompt_includes_modified(self):
        from wp_supervisor.templates import INTERFACES_SUMMARY_PROMPT
        assert "Modified" in INTERFACES_SUMMARY_PROMPT


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
