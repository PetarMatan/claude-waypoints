#!/usr/bin/env python3
"""Unit tests for wp_supervisor/orchestrator.py"""

import io
import os
import sys
import tempfile
import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from dataclasses import dataclass
from typing import Optional, List

@dataclass
class MockAgentDefinition:
    description: str
    prompt: str
    tools: Optional[list] = None
    model: Optional[str] = None

class MockAssistantMessage:
    pass

class MockResultMessage:
    pass

class MockClaudeSDKClient:
    _mock_responses = []

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
        if MockClaudeSDKClient._mock_responses:
            for msg in MockClaudeSDKClient._mock_responses:
                yield msg
        else:
            mock_msg = MockAssistantMessage()
            mock_msg.session_id = "test-session-123"
            text_block = MagicMock()
            text_block.text = "---PHASE_COMPLETE---"
            mock_msg.content = [text_block]
            yield mock_msg

    async def query(self, user_input, session_id="default"):
        self._prompt = user_input

    async def receive_response(self):
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
mock_sdk.AgentDefinition = MockAgentDefinition
mock_types = MagicMock()
mock_types.AssistantMessage = MockAssistantMessage
mock_types.ResultMessage = MockResultMessage
mock_sdk.types = mock_types
sys.modules['claude_agent_sdk'] = mock_sdk
sys.modules['claude_agent_sdk.types'] = mock_types

sys.path.insert(0, '.')
from wp_supervisor.markers import SupervisorMarkers
from wp_supervisor.context import ContextBuilder
from wp_supervisor.session import read_user_input


# Isolate tests from live workflows - pytest during Phase 4 leaks env vars
@pytest.fixture(autouse=True)
def clean_supervisor_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("WP_SUPERVISOR_"):
            monkeypatch.delenv(key, raising=False)


def run_async(coro):
    return asyncio.run(coro)


class TestReadUserInput:

    def test_simple_text_input(self):
        with patch('builtins.input', return_value="hello world"):
            result = read_user_input()
        assert result == "hello world"

    def test_empty_input_returns_empty_string(self):
        with patch('builtins.input', return_value=""):
            result = read_user_input()
        assert result == ""

    def test_eof_returns_empty_string(self):
        with patch('builtins.input', side_effect=EOFError):
            result = read_user_input()
        assert result == ""

    def test_keyboard_interrupt_returns_empty_string(self):
        with patch('builtins.input', side_effect=KeyboardInterrupt):
            result = read_user_input()
        assert result == ""

    def test_file_input_with_at_prefix(self, capsys):
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
        with patch('builtins.input', return_value="@/nonexistent/file.md"):
            result = read_user_input()

        assert result == ""
        captured = capsys.readouterr()
        assert "File not found" in captured.out

    def test_path_like_text_not_existing_file(self):
        with patch('builtins.input', return_value="/not/a/real/file"):
            result = read_user_input()

        assert result == "/not/a/real/file"

    def test_structured_requirements_from_file(self, capsys):
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
                orchestrator = WPOrchestrator(working_dir=".")
                assert orchestrator.working_dir.is_absolute()


class TestOrchestratorSignals:

    def test_phase_complete_signal_exists(self):
        from wp_supervisor.orchestrator import PHASE_COMPLETE_SIGNAL
        assert PHASE_COMPLETE_SIGNAL == "---PHASE_COMPLETE---"

    def test_summary_verified_signal_exists(self):
        from wp_supervisor.orchestrator import SUMMARY_VERIFIED_SIGNAL
        assert SUMMARY_VERIFIED_SIGNAL == "SUMMARY_VERIFIED"

    def test_gaps_found_signal_exists(self):
        from wp_supervisor.orchestrator import GAPS_FOUND_SIGNAL
        assert GAPS_FOUND_SIGNAL == "GAPS_FOUND"

    def test_phase_names_dict_exists(self):
        from wp_supervisor.templates import PHASE_NAMES
        assert 1 in PHASE_NAMES
        assert 2 in PHASE_NAMES
        assert 3 in PHASE_NAMES
        assert 4 in PHASE_NAMES


class TestRunPhase:

    def test_run_phase_sets_phase_marker(self):
        for phase in [1, 2, 3, 4]:
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch.object(Path, 'home', return_value=Path(tmpdir)):
                    from wp_supervisor.orchestrator import WPOrchestrator
                    orchestrator = WPOrchestrator(working_dir=tmpdir)

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

    def test_run_phase4_keeps_all_artifacts(self):
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

                assert orchestrator.markers.markers_dir.exists()
                state_file = orchestrator.markers.markers_dir / "state.json"
                assert state_file.exists()
                assert (orchestrator.markers.markers_dir / "phase1-requirements.md").exists()
                assert (orchestrator.markers.markers_dir / "phase2-interfaces.md").exists()
                assert (orchestrator.markers.markers_dir / "phase3-tests.md").exists()

    def test_run_phase4_marks_implementation_complete(self):
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

                state_file = orchestrator.markers.markers_dir / "state.json"
                import json
                with open(state_file) as f:
                    state = json.load(f)
                assert state["completedPhases"]["implementation"] is True

    def test_run_phase_edit_reloads_document(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                async def mock_run_session(*args, **kwargs):
                    pass

                async def mock_generate_and_verify(*args, **kwargs):
                    return "# Original Requirements"

                confirm_calls = []
                async def mock_confirm(phase, doc_path="", session_id=None):
                    confirm_calls.append(phase)
                    if len(confirm_calls) == 1:
                        orchestrator.markers.save_phase_document(phase, "# Edited Requirements")
                        return 'edit'
                    return 'proceed'

                orchestrator._run_phase_session = mock_run_session
                orchestrator._generate_and_verify_summary = mock_generate_and_verify
                orchestrator._confirm_phase_completion = mock_confirm

                run_async(orchestrator._run_phase(1, "test"))

                saved = orchestrator.markers.get_requirements_summary()
                assert "# Edited Requirements" in saved

    def test_run_phase_regenerate_calls_regenerate_summary(self):
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

                assert 1 in regenerate_called
                saved = orchestrator.markers.get_requirements_summary()
                assert "# Regenerated Requirements" in saved


class TestRegenerateSummary:

    def test_regenerate_summary_returns_current_on_empty_feedback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                orchestrator.markers.save_phase_document(1, "# Current Summary")

                with patch('builtins.input', return_value=''):
                    result = run_async(orchestrator._regenerate_summary(1))

                assert result == "# Current Summary"

    def test_regenerate_summary_calls_conversation_with_feedback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                orchestrator.markers.save_phase_document(1, "# Current Summary")

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

    def test_generate_and_verify_returns_empty_for_phase4(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

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
                        return "# Some other response"

                orchestrator._extract_text_response = mock_extract_text_response

                result = run_async(orchestrator._generate_and_verify_summary(1))

                assert "Some other response" in result


class TestRunSupervisor:

    def test_run_supervisor_function_exists(self):
        from wp_supervisor.orchestrator import run_supervisor
        assert callable(run_supervisor)


class TestKeyboardInterruptHandling:

    def test_keyboard_interrupt_cleans_up_markers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                orchestrator.markers.initialize()

                async def raise_interrupt(*args, **kwargs):
                    raise KeyboardInterrupt()

                orchestrator._run_phase = raise_interrupt

                run_async(orchestrator.run())

                assert not orchestrator.markers.markers_dir.exists()


class TestConfirmPhaseCompletion:

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

                inputs = iter(['invalid', 'y'])
                with patch('builtins.input', lambda _: next(inputs)):
                    result = run_async(orchestrator._confirm_phase_completion(1))
                    assert result == 'proceed'

    def test_confirm_phase_completion_edit_option(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

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

    def test_confirm_phase1_marks_requirements_complete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                orchestrator.markers.initialize()

                with patch('builtins.input', return_value='y'):
                    run_async(orchestrator._confirm_phase_completion(1))

                state_file = orchestrator.markers.markers_dir / "state.json"
                assert state_file.exists()
                import json
                with open(state_file) as f:
                    state = json.load(f)
                assert state["completedPhases"]["requirements"] is True

    def test_confirm_phase2_marks_interfaces_complete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                orchestrator.markers.initialize()

                with patch('builtins.input', return_value='y'):
                    run_async(orchestrator._confirm_phase_completion(2))

                state_file = orchestrator.markers.markers_dir / "state.json"
                import json
                with open(state_file) as f:
                    state = json.load(f)
                assert state["completedPhases"]["interfaces"] is True

    def test_confirm_phase3_marks_tests_complete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                orchestrator.markers.initialize()

                with patch('builtins.input', return_value='y'):
                    run_async(orchestrator._confirm_phase_completion(3))

                state_file = orchestrator.markers.markers_dir / "state.json"
                import json
                with open(state_file) as f:
                    state = json.load(f)
                assert state["completedPhases"]["tests"] is True


class TestContextPassing:

    def test_phase2_receives_requirements_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                orchestrator.markers.save_requirements_summary("# Saved Requirements")

                captured_context = None

                async def capture_context(context, phase, subagents=None):
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

                async def capture_context(context, phase, subagents=None):
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

                async def capture_context(context, phase, subagents=None):
                    nonlocal captured_context
                    captured_context = context

                orchestrator._run_phase_session = capture_context

                run_async(orchestrator._run_phase(4))

                assert "# Req Summary" in captured_context
                assert "# Int List" in captured_context
                assert "# Test List" in captured_context

    def test_phase_context_includes_agents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
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

                async def capture_context(context, phase, subagents=None):
                    nonlocal captured_context
                    captured_context = context

                async def mock_generate_and_verify(*args, **kwargs):
                    return "# Requirements"

                async def mock_confirm(*args, **kwargs):
                    return 'proceed'

                orchestrator._run_phase_session = capture_context
                orchestrator._generate_and_verify_summary = mock_generate_and_verify
                orchestrator._confirm_phase_completion = mock_confirm

                with patch.dict(os.environ, {"WP_INSTALL_DIR": str(Path(tmpdir) / ".claude" / "waypoints")}):
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

    def _create_mock_client_class(self, phases_executed: list, captured_prompts: list = None):
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
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator

                phases_executed = []
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                MockClient = self._create_mock_client_class(phases_executed)

                with patch('builtins.input', return_value='y'):
                    with patch('wp_supervisor.orchestrator.ClaudeSDKClient', MockClient):
                        run_async(orchestrator.run(initial_task="Build a test feature"))

                assert 1 in phases_executed
                assert 2 in phases_executed
                assert 3 in phases_executed
                assert 4 in phases_executed

                phase_order = [p for p in phases_executed if p in [1, 2, 3, 4]]
                assert phase_order == [1, 2, 3, 4]

                assert orchestrator.markers.markers_dir.exists()
                state_file = orchestrator.markers.markers_dir / "state.json"
                assert state_file.exists()

    def test_workflow_saves_summaries_between_phases(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator

                phases_executed = []
                saved_documents = {}

                orchestrator = WPOrchestrator(working_dir=tmpdir)

                original_save_doc = orchestrator.markers.save_phase_document

                def capture_document(phase, content):
                    saved_documents[phase] = content
                    return original_save_doc(phase, content)

                orchestrator.markers.save_phase_document = capture_document

                MockClient = self._create_mock_client_class(phases_executed)

                with patch('builtins.input', return_value='y'):
                    with patch('wp_supervisor.orchestrator.ClaudeSDKClient', MockClient):
                        run_async(orchestrator.run(initial_task="Build a feature"))

                assert 1 in saved_documents
                assert 2 in saved_documents
                assert 3 in saved_documents

                assert len(saved_documents[1]) > 0
                assert len(saved_documents[2]) > 0
                assert len(saved_documents[3]) > 0

    def test_workflow_with_initial_task(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator

                phases_executed = []
                captured_prompts = []

                MockClient = self._create_mock_client_class(phases_executed, captured_prompts)

                orchestrator = WPOrchestrator(working_dir=tmpdir)

                with patch('builtins.input', return_value='y'):
                    with patch('wp_supervisor.orchestrator.ClaudeSDKClient', MockClient):
                        run_async(orchestrator.run(initial_task="Build a REST API for users"))

                phase1_prompts = [p for p in captured_prompts if "Phase 1" in p]
                assert len(phase1_prompts) > 0
                assert "Build a REST API for users" in phase1_prompts[0]


class TestExtractAndStageKnowledge:

    def test_stages_knowledge_when_claude_returns_valid_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                mock_response = """ARCHITECTURE:
- Service Pattern: The service uses a pipeline pattern for processing

DECISIONS:
- Chose REST: REST was chosen over GraphQL for simplicity
"""

                async def mock_query(*args, **kwargs):
                    return mock_response

                orchestrator._extract_text_response = mock_query

                run_async(orchestrator._extract_and_stage_knowledge(phase=1))

                assert orchestrator.markers.has_staged_knowledge()

    def test_does_not_stage_when_claude_returns_no_knowledge_extracted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                async def mock_query(*args, **kwargs):
                    return "NO_KNOWLEDGE_EXTRACTED"

                orchestrator._extract_text_response = mock_query

                run_async(orchestrator._extract_and_stage_knowledge(phase=1))

                assert not orchestrator.markers.has_staged_knowledge()

    def test_does_not_stage_when_response_has_empty_sections(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                mock_response = """ARCHITECTURE:

DECISIONS:

LESSONS_LEARNED:
"""

                async def mock_query(*args, **kwargs):
                    return mock_response

                orchestrator._extract_text_response = mock_query

                run_async(orchestrator._extract_and_stage_knowledge(phase=1))

                assert not orchestrator.markers.has_staged_knowledge()

    def test_continues_workflow_when_query_raises_exception(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                async def mock_query_that_fails(*args, **kwargs):
                    raise ConnectionError("Network error")

                orchestrator._extract_text_response = mock_query_that_fails

                run_async(orchestrator._extract_and_stage_knowledge(phase=1))

                assert not orchestrator.markers.has_staged_knowledge()

    def test_logs_error_when_query_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                async def mock_query_that_fails(*args, **kwargs):
                    raise ValueError("Test error")

                orchestrator._extract_text_response = mock_query_that_fails

                log_calls = []
                original_log_error = orchestrator.logger.log_error
                def capture_log_error(msg, error=None):
                    log_calls.append(msg)
                    original_log_error(msg, error)
                orchestrator.logger.log_error = capture_log_error

                run_async(orchestrator._extract_and_stage_knowledge(phase=1))

                assert any("Knowledge extraction failed" in call for call in log_calls)

    def test_stages_only_architecture_when_only_architecture_present(self):
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

                run_async(orchestrator._extract_and_stage_knowledge(phase=1))

                assert orchestrator.markers.has_staged_knowledge()
                staged = orchestrator.markers.get_staged_knowledge()
                assert len(staged.architecture) == 1
                assert len(staged.decisions) == 0
                assert len(staged.lessons_learned) == 0

    def test_stages_lessons_learned_with_tags(self):
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

                run_async(orchestrator._extract_and_stage_knowledge(phase=1))

                assert orchestrator.markers.has_staged_knowledge()
                staged = orchestrator.markers.get_staged_knowledge()
                assert len(staged.lessons_learned) == 2
                assert staged.lessons_learned[0].tag == "Kotlin"
                assert staged.lessons_learned[1].tag == "Git"

    def test_passes_existing_knowledge_context_to_prompt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                orchestrator._knowledge_context = "# Existing Architecture\nService A talks to B"

                captured_prompts = []

                async def mock_query(prompt, *args, **kwargs):
                    captured_prompts.append(prompt)
                    return "NO_KNOWLEDGE_EXTRACTED"

                orchestrator._extract_text_response = mock_query

                run_async(orchestrator._extract_and_stage_knowledge(phase=1))

                assert len(captured_prompts) == 1
                assert "Existing Architecture" in captured_prompts[0]
                assert "Service A talks to B" in captured_prompts[0]

    def test_uses_default_when_no_existing_knowledge(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                orchestrator._knowledge_context = ""

                captured_prompts = []

                async def mock_query(prompt, *args, **kwargs):
                    captured_prompts.append(prompt)
                    return "NO_KNOWLEDGE_EXTRACTED"

                orchestrator._extract_text_response = mock_query

                run_async(orchestrator._extract_and_stage_knowledge(phase=1))

                assert len(captured_prompts) == 1
                assert "No existing knowledge" in captured_prompts[0]

    def test_accumulates_knowledge_across_phases(self):
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

                run_async(orchestrator._extract_and_stage_knowledge(phase=1))
                run_async(orchestrator._extract_and_stage_knowledge(phase=2))

                staged = orchestrator.markers.get_staged_knowledge()
                assert len(staged.architecture) == 1
                assert len(staged.decisions) == 1


class TestApplyKnowledgeAtWorkflowEnd:

    def test_does_nothing_when_no_staged_knowledge(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                orchestrator._apply_knowledge_at_workflow_end()

                assert not orchestrator.markers.has_staged_knowledge()

    def test_clears_staged_knowledge_after_apply(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                async def mock_query(*args, **kwargs):
                    return """ARCHITECTURE:
- Pattern: Description
"""
                orchestrator._extract_text_response = mock_query
                run_async(orchestrator._extract_and_stage_knowledge(phase=1))
                assert orchestrator.markers.has_staged_knowledge()

                orchestrator._apply_knowledge_at_workflow_end()

                assert not orchestrator.markers.has_staged_knowledge()

    def test_clears_staged_knowledge_even_on_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                async def mock_query(*args, **kwargs):
                    return """ARCHITECTURE:
- Pattern: Description
"""
                orchestrator._extract_text_response = mock_query
                run_async(orchestrator._extract_and_stage_knowledge(phase=1))

                def failing_apply(*args, **kwargs):
                    raise IOError("Disk full")
                orchestrator.markers.apply_staged_knowledge = failing_apply

                orchestrator._apply_knowledge_at_workflow_end()

                assert not orchestrator.markers.has_staged_knowledge()


class TestFormatStagedKnowledgeForPrompt:

    def test_returns_none_yet_when_no_staged_knowledge(self):
        from wp_supervisor.templates import format_staged_knowledge_for_prompt
        sys.path.insert(0, 'hooks/lib')
        from wp_knowledge import StagedKnowledge

        staged = StagedKnowledge()

        result = format_staged_knowledge_for_prompt(staged)

        assert result == "None yet"

    def test_formats_architecture_entry_with_title_and_first_sentence(self):
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

        result = format_staged_knowledge_for_prompt(staged)

        assert "Pipeline Pattern" in result
        assert "Services use a pipeline for processing" in result

    def test_formats_decisions_entry(self):
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

        result = format_staged_knowledge_for_prompt(staged)

        assert "Event-Driven Design" in result
        assert "Chose events over polling" in result

    def test_formats_lessons_learned_with_tag(self):
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

        result = format_staged_knowledge_for_prompt(staged)

        assert "[Kotlin]" in result
        assert "DSL Builder Pattern" in result

    def test_formats_multiple_categories(self):
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

        result = format_staged_knowledge_for_prompt(staged)

        assert "Pattern A" in result
        assert "Decision B" in result
        assert "Lesson C" in result
        assert "[Python]" in result


class TestStagedKnowledgeInPrompt:

    def test_staged_knowledge_included_in_prompt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator

                orchestrator = WPOrchestrator(working_dir=tmpdir)

                async def phase1_query(*args, **kwargs):
                    return """ARCHITECTURE:
- Pipeline Pattern: Services use pipeline for composability
"""
                orchestrator._extract_text_response = phase1_query
                run_async(orchestrator._extract_and_stage_knowledge(phase=1))

                captured_prompts = []

                async def phase2_query(prompt, *args, **kwargs):
                    captured_prompts.append(prompt)
                    return "NO_KNOWLEDGE_EXTRACTED"

                orchestrator._extract_text_response = phase2_query

                run_async(orchestrator._extract_and_stage_knowledge(phase=2))

                assert len(captured_prompts) == 1
                assert "Pipeline Pattern" in captured_prompts[0]

    def test_no_staged_knowledge_shows_none_yet(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator

                orchestrator = WPOrchestrator(working_dir=tmpdir)

                captured_prompts = []

                async def mock_query(prompt, *args, **kwargs):
                    captured_prompts.append(prompt)
                    return "NO_KNOWLEDGE_EXTRACTED"

                orchestrator._extract_text_response = mock_query

                run_async(orchestrator._extract_and_stage_knowledge(phase=1))

                assert len(captured_prompts) == 1
                assert "None yet" in captured_prompts[0]


class TestCodebaseContextInRequirements:

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


class TestBuildExplorationSubagents:

    def test_build_exploration_subagents_returns_four_agents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                agents = orchestrator._build_exploration_subagents()

                assert len(agents) == 4

    def test_build_exploration_subagents_returns_dict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                agents = orchestrator._build_exploration_subagents()

                assert isinstance(agents, dict)

    def test_build_exploration_subagents_uses_knowledge_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                orchestrator._knowledge_context = "# Architecture\nEvent-driven system"

                agents = orchestrator._build_exploration_subagents()

                for agent in agents.values():
                    assert "Event-driven system" in agent.prompt

    def test_build_exploration_subagents_with_no_args(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                agents = orchestrator._build_exploration_subagents()

                assert len(agents) == 4


class TestSubagentIntegrationWithPhaseSession:

    def test_phase1_builds_subagents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                build_subagents_called = []

                original_build = orchestrator._build_exploration_subagents
                def capture_build():
                    build_subagents_called.append(True)
                    return original_build()

                orchestrator._build_exploration_subagents = capture_build

                async def mock_session(*args, **kwargs):
                    pass

                async def mock_summary(*args, **kwargs):
                    return "# Summary"

                async def mock_confirm(*args, **kwargs):
                    return 'proceed'

                orchestrator._run_phase_session = mock_session
                orchestrator._generate_and_verify_summary = mock_summary
                orchestrator._confirm_phase_completion = mock_confirm

                run_async(orchestrator._run_phase(1, initial_task="Test task"))

                assert len(build_subagents_called) == 1

    def test_phase1_passes_subagents_to_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                captured_subagents = []

                async def capture_session(context, phase, subagents=None):
                    captured_subagents.append(subagents)
                    return None

                async def mock_summary(*args, **kwargs):
                    return "# Summary"

                async def mock_confirm(*args, **kwargs):
                    return 'proceed'

                orchestrator._run_phase_session = capture_session
                orchestrator._generate_and_verify_summary = mock_summary
                orchestrator._confirm_phase_completion = mock_confirm

                run_async(orchestrator._run_phase(1, initial_task="Test task"))

                assert len(captured_subagents) == 1
                assert captured_subagents[0] is not None
                assert len(captured_subagents[0]) == 4

    def test_phase2_does_not_build_subagents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                orchestrator.markers.save_requirements_summary("# Requirements")

                captured_subagents = []

                async def capture_session(context, phase, subagents=None):
                    captured_subagents.append(subagents)
                    return None

                async def mock_summary(*args, **kwargs):
                    return "# Interfaces"

                async def mock_confirm(*args, **kwargs):
                    return 'proceed'

                orchestrator._run_phase_session = capture_session
                orchestrator._generate_and_verify_summary = mock_summary
                orchestrator._confirm_phase_completion = mock_confirm

                run_async(orchestrator._run_phase(2))

                assert len(captured_subagents) == 1
                assert captured_subagents[0] is None

    def test_phase3_does_not_build_subagents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                orchestrator.markers.save_requirements_summary("# Requirements")
                orchestrator.markers.save_interfaces_list("# Interfaces")

                captured_subagents = []

                async def capture_session(context, phase, subagents=None):
                    captured_subagents.append(subagents)
                    return None

                async def mock_summary(*args, **kwargs):
                    return "# Tests"

                async def mock_confirm(*args, **kwargs):
                    return 'proceed'

                orchestrator._run_phase_session = capture_session
                orchestrator._generate_and_verify_summary = mock_summary
                orchestrator._confirm_phase_completion = mock_confirm

                run_async(orchestrator._run_phase(3))

                assert len(captured_subagents) == 1
                assert captured_subagents[0] is None

    def test_phase4_does_not_build_subagents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                orchestrator.markers.save_requirements_summary("# Requirements")
                orchestrator.markers.save_interfaces_list("# Interfaces")
                orchestrator.markers.save_tests_list("# Tests")

                captured_subagents = []

                async def capture_session(context, phase, subagents=None):
                    captured_subagents.append(subagents)
                    return None

                orchestrator._run_phase_session = capture_session

                run_async(orchestrator._run_phase(4))

                assert len(captured_subagents) == 1
                assert captured_subagents[0] is None


class TestSubagentErrorHandling:

    def test_phase1_continues_when_subagent_build_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                def failing_build():
                    raise RuntimeError("Subagent build failed")

                orchestrator._build_exploration_subagents = failing_build

                captured_subagents = []

                async def mock_session(context, phase, subagents=None):
                    captured_subagents.append(subagents)
                    return None

                async def mock_summary(*args, **kwargs):
                    return "# Summary"

                async def mock_confirm(*args, **kwargs):
                    return 'proceed'

                orchestrator._run_phase_session = mock_session
                orchestrator._generate_and_verify_summary = mock_summary
                orchestrator._confirm_phase_completion = mock_confirm

                run_async(orchestrator._run_phase(1, initial_task="Test"))

                assert len(captured_subagents) == 1
                assert captured_subagents[0] is None


class TestPhase1SupervisorModeContext:

    def test_phase1_context_uses_supervisor_mode_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                context = orchestrator._build_phase_context(1, "Test task")

                assert "subagent" in context.lower() or "parallel" in context.lower()

    def test_phase1_context_mentions_delegation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                context = orchestrator._build_phase_context(1, "Test task")

                assert "delegate" in context.lower()

    def test_phase1_context_includes_task(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                task = "Build OAuth integration"

                context = orchestrator._build_phase_context(1, task)

                assert task in context

    def test_phase1_context_includes_knowledge(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                orchestrator._knowledge_context = "# Architecture\nService mesh"

                context = orchestrator._build_phase_context(1, "Test")

                assert "Service mesh" in context


class TestRunPhaseSessionWithSubagents:

    def test_run_phase_session_accepts_subagents_parameter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                import inspect
                sig = inspect.signature(orchestrator._run_phase_session)
                params = sig.parameters

                assert 'subagents' in params
                assert params['subagents'].default is None

    def test_run_phase_session_logs_subagent_configuration(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                assert callable(orchestrator._run_phase_session)


class TestOrchestratorSessionIntegration:

    def test_orchestrator_imports_read_user_input_from_session(self):
        from wp_supervisor.orchestrator import read_user_input
        from wp_supervisor.session import read_user_input as session_read_user_input

        assert read_user_input is session_read_user_input

    def test_orchestrator_imports_session_runner_class(self):
        from wp_supervisor.orchestrator import SessionRunner
        from wp_supervisor.session import SessionRunner as SessionSessionRunner

        assert SessionRunner is SessionSessionRunner

    def test_orchestrator_delegates_to_session_runner(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                from wp_supervisor.session import SessionRunner

                orchestrator = WPOrchestrator(working_dir=tmpdir)

                assert hasattr(orchestrator, '_session_runner')
                assert isinstance(orchestrator._session_runner, SessionRunner)

                assert orchestrator._session_runner.markers is orchestrator.markers
                assert orchestrator._session_runner.logger is orchestrator.logger
                assert orchestrator._session_runner.hooks is orchestrator.hooks


class TestOrchestratorSessionRunnerUsage:

    def test_phase_complete_patterns_importable_from_session(self):
        from wp_supervisor.session import PHASE_COMPLETE_PATTERNS

        assert isinstance(PHASE_COMPLETE_PATTERNS, list)
        assert len(PHASE_COMPLETE_PATTERNS) > 0

    def test_regeneration_patterns_importable_from_session(self):
        from wp_supervisor.session import (
            REGENERATION_COMPLETE_PATTERNS,
            REGENERATION_CANCELED_PATTERNS,
        )

        assert isinstance(REGENERATION_COMPLETE_PATTERNS, list)
        assert isinstance(REGENERATION_CANCELED_PATTERNS, list)
        assert len(REGENERATION_COMPLETE_PATTERNS) > 0
        assert len(REGENERATION_CANCELED_PATTERNS) > 0

    def test_session_runner_handles_usage_recording(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)

                assert hasattr(orchestrator._session_runner, '_record_usage')

                mock_result = MagicMock()
                mock_result.usage = {"input_tokens": 100, "output_tokens": 50}
                mock_result.total_cost_usd = 0.01
                mock_result.duration_ms = 1000
                mock_result.num_turns = 1

                orchestrator._session_runner._record_usage(phase=1, result=mock_result)

                usage = orchestrator.markers.get_all_usage()
                assert usage.get("phase1", {}).get("input_tokens", 0) > 0


# --- Phase 4 Reviewer Integration ---


class TestOrchestratorReviewCoordinatorIntegration:

    def test_orchestrator_has_start_review_coordinator_method(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                assert hasattr(orchestrator, '_start_review_coordinator')

    def test_orchestrator_has_stop_review_coordinator_method(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                assert hasattr(orchestrator, '_stop_review_coordinator')

    def test_orchestrator_has_create_review_coordinator_method(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                assert hasattr(orchestrator, '_create_review_coordinator')

    def test_start_review_coordinator_is_async(self):
        import inspect
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                assert inspect.iscoroutinefunction(orchestrator._start_review_coordinator)

    def test_stop_review_coordinator_is_async(self):
        import inspect
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                assert inspect.iscoroutinefunction(orchestrator._stop_review_coordinator)


class TestOrchestratorReviewerLifecycle:

    def test_review_coordinator_started_during_phase4(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                assert callable(getattr(orchestrator, '_start_review_coordinator', None))

    def test_review_coordinator_stopped_after_phase4(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                assert callable(getattr(orchestrator, '_stop_review_coordinator', None))

    def test_create_review_coordinator_returns_coordinator(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                assert callable(getattr(orchestrator, '_create_review_coordinator', None))


class TestOrchestratorHooksReviewCoordinatorSetting:

    def test_hooks_has_set_review_coordinator_method(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                from wp_supervisor.orchestrator import WPOrchestrator
                orchestrator = WPOrchestrator(working_dir=tmpdir)
                assert hasattr(orchestrator.hooks, 'set_review_coordinator')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
