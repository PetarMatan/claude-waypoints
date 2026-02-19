#!/usr/bin/env python3
"""
Unit tests for wp_supervisor/display.py - SupervisorDisplay class

Tests for:
- Constructor: NO_COLOR detection, TTY detection, HAS_RICH fallback
- stream_text: prefix appears once per message, resets after stream_text_end()
- supervisor_message/success/error/warning: correct prefix symbols
- start_tool_spinner / stop_tool_spinner: task lifecycle
- spinner context manager: works with async, fallback when no rich
- usage_summary: plain-text fallback output
- Graceful degradation: all methods produce output when HAS_RICH=False
"""

import asyncio
import io
import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Mock claude_agent_sdk before importing display module
from dataclasses import dataclass
from typing import Optional

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

sys.path.insert(0, '.')
from wp_supervisor.display import SupervisorDisplay, HAS_RICH


@pytest.fixture(autouse=True)
def clean_supervisor_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("WP_SUPERVISOR_"):
            monkeypatch.delenv(key, raising=False)


def run_async(coro):
    return asyncio.run(coro)


class TestSupervisorDisplayInit:
    """Tests for constructor behavior."""

    def test_display_class_exists(self):
        assert SupervisorDisplay is not None

    def test_creates_instance(self):
        display = SupervisorDisplay()
        assert display is not None

    def test_no_color_env_disables_rich(self):
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            display = SupervisorDisplay()
            assert display._use_rich is False

    def test_non_tty_disables_rich(self):
        with patch('sys.stdout') as mock_stdout:
            mock_stdout.isatty.return_value = False
            display = SupervisorDisplay()
            assert display._use_rich is False

    def test_no_rich_module_disables_rich(self):
        with patch('wp_supervisor.display.HAS_RICH', False):
            display = SupervisorDisplay()
            assert display._use_rich is False

    def test_stream_prefix_initially_false(self):
        display = SupervisorDisplay()
        assert display._stream_prefix_shown is False

    def test_tool_spinner_task_initially_none(self):
        display = SupervisorDisplay()
        assert display._tool_spinner_task is None


class TestStreamText:
    """Tests for stream_text and stream_text_end."""

    def test_stream_text_outputs_to_stdout(self):
        display = SupervisorDisplay()
        display._use_rich = False

        captured = io.StringIO()
        with patch('sys.stdout', captured):
            display.stream_text("hello")

        output = captured.getvalue()
        assert "hello" in output

    def test_stream_text_shows_prefix_once(self):
        display = SupervisorDisplay()
        display._use_rich = False

        captured = io.StringIO()
        captured.isatty = lambda: False
        with patch('sys.stdout', captured):
            display.stream_text("first")
            display.stream_text("second")

        output = captured.getvalue()
        assert output.count("Claude") == 1

    def test_stream_text_end_resets_prefix(self):
        display = SupervisorDisplay()
        display._use_rich = False

        captured = io.StringIO()
        captured.isatty = lambda: False
        with patch('sys.stdout', captured):
            display.stream_text("msg1")
            display.stream_text_end()
            display.stream_text("msg2")

        output = captured.getvalue()
        assert output.count("Claude") == 2

    def test_stream_text_end_sets_flag(self):
        display = SupervisorDisplay()
        display._stream_prefix_shown = True
        display.stream_text_end()
        assert display._stream_prefix_shown is False


class TestStatusMessages:
    """Tests for supervisor status message methods."""

    def test_supervisor_message_outputs(self, capsys):
        display = SupervisorDisplay()
        display._use_rich = False
        display.supervisor_message("test message")
        captured = capsys.readouterr()
        assert "test message" in captured.out

    def test_supervisor_success_outputs(self, capsys):
        display = SupervisorDisplay()
        display._use_rich = False
        display.supervisor_success("success text")
        captured = capsys.readouterr()
        assert "success text" in captured.out

    def test_supervisor_error_outputs(self, capsys):
        display = SupervisorDisplay()
        display._use_rich = False
        display.supervisor_error("error text")
        captured = capsys.readouterr()
        assert "error text" in captured.err

    def test_supervisor_warning_outputs(self, capsys):
        display = SupervisorDisplay()
        display._use_rich = False
        display.supervisor_warning("warning text")
        captured = capsys.readouterr()
        assert "warning text" in captured.out

    def test_tip_outputs(self, capsys):
        display = SupervisorDisplay()
        display._use_rich = False
        display.tip("helpful tip")
        captured = capsys.readouterr()
        assert "helpful tip" in captured.out

    def test_print_outputs(self, capsys):
        display = SupervisorDisplay()
        display.print("generic text")
        captured = capsys.readouterr()
        assert "generic text" in captured.out


class TestToolSpinner:
    """Tests for start_tool_spinner / stop_tool_spinner."""

    def test_start_tool_spinner_creates_task(self):
        display = SupervisorDisplay()
        display._use_rich = False

        async def test():
            await display.start_tool_spinner("Write")
            assert display._tool_spinner_task is not None
            await display.stop_tool_spinner()

        run_async(test())

    def test_stop_tool_spinner_clears_task(self):
        display = SupervisorDisplay()
        display._use_rich = False

        async def test():
            await display.start_tool_spinner("Read")
            await display.stop_tool_spinner()
            assert display._tool_spinner_task is None

        run_async(test())

    def test_stop_tool_spinner_noop_when_no_task(self):
        display = SupervisorDisplay()

        async def test():
            await display.stop_tool_spinner()
            assert display._tool_spinner_task is None

        run_async(test())

    def test_start_tool_spinner_stops_previous(self):
        display = SupervisorDisplay()
        display._use_rich = False

        async def test():
            await display.start_tool_spinner("Write")
            first_task = display._tool_spinner_task
            await display.start_tool_spinner("Edit")
            assert display._tool_spinner_task is not first_task
            await display.stop_tool_spinner()

        run_async(test())


class TestSpinnerContextManager:
    """Tests for the spinner async context manager."""

    def test_spinner_works_as_context_manager(self):
        display = SupervisorDisplay()
        display._use_rich = False

        async def test():
            async with display.spinner("Loading"):
                pass

        run_async(test())

    def test_spinner_outputs_label(self):
        display = SupervisorDisplay()
        display._use_rich = False

        captured = io.StringIO()
        captured.isatty = lambda: False
        with patch('sys.stdout', captured):
            async def test():
                async with display.spinner("Processing data"):
                    pass
            run_async(test())

        output = captured.getvalue()
        assert "Processing data" in output

    def test_spinner_fallback_shows_done(self):
        display = SupervisorDisplay()
        display._use_rich = False

        captured = io.StringIO()
        captured.isatty = lambda: False
        with patch('sys.stdout', captured):
            async def test():
                async with display.spinner("Working"):
                    pass
            run_async(test())

        output = captured.getvalue()
        assert "done" in output


class TestStructuredOutput:
    """Tests for structured output methods (panels, tables)."""

    def test_workflow_header_outputs(self, capsys):
        display = SupervisorDisplay()
        display._use_rich = False
        display.workflow_header("/tmp/project", "wf-123", "/tmp/markers")
        captured = capsys.readouterr()
        assert "Waypoints Supervisor" in captured.out
        assert "/tmp/project" in captured.out
        assert "wf-123" in captured.out

    def test_phase_header_outputs(self, capsys):
        display = SupervisorDisplay()
        display._use_rich = False
        display.phase_header(1, "Requirements Gathering")
        captured = capsys.readouterr()
        assert "PHASE 1" in captured.out
        assert "REQUIREMENTS GATHERING" in captured.out

    def test_phase_complete_banner_outputs(self, capsys):
        display = SupervisorDisplay()
        display._use_rich = False
        display.phase_complete_banner(2, "Interface Design", "/tmp/doc.md")
        captured = capsys.readouterr()
        assert "Phase 2" in captured.out
        assert "Interface Design" in captured.out
        assert "/tmp/doc.md" in captured.out

    def test_workflow_complete_outputs(self, capsys):
        display = SupervisorDisplay()
        display._use_rich = False
        display.workflow_complete()
        captured = capsys.readouterr()
        assert "Complete" in captured.out

    def test_feedback_injection_outputs(self, capsys):
        display = SupervisorDisplay()
        display._use_rich = False
        display.feedback_injection("- Fix the bug in line 42")
        captured = capsys.readouterr()
        assert "Fix the bug" in captured.out

    def test_document_preview_outputs(self, capsys):
        display = SupervisorDisplay()
        display._use_rich = False
        display.document_preview("# Summary\n- item 1")
        captured = capsys.readouterr()
        assert "Summary" in captured.out
        assert "item 1" in captured.out

    def test_knowledge_summary_outputs(self, capsys):
        display = SupervisorDisplay()
        display._use_rich = False
        display.knowledge_summary("Updated 3 knowledge files")
        captured = capsys.readouterr()
        assert "Updated 3 knowledge files" in captured.out


class TestUsageSummary:
    """Tests for usage_summary method."""

    def test_usage_summary_plain_text(self, capsys):
        display = SupervisorDisplay()
        display._use_rich = False

        usage = {
            "phase1": {
                "input_tokens": 1000,
                "output_tokens": 500,
                "cost_usd": 0.05,
                "duration_ms": 10000,
                "turns": 3,
            },
            "phase2": {},
            "phase3": {},
            "phase4": {},
            "total": {
                "input_tokens": 1000,
                "output_tokens": 500,
                "cost_usd": 0.05,
                "duration_ms": 10000,
                "turns": 3,
            },
        }
        phase_names = {1: "Requirements", 2: "Interfaces", 3: "Tests", 4: "Implementation"}

        display.usage_summary(usage, phase_names)
        captured = capsys.readouterr()

        assert "TOKEN USAGE SUMMARY" in captured.out
        assert "1,000" in captured.out
        assert "500" in captured.out
        assert "$0.0500" in captured.out
        assert "TOTAL" in captured.out

    def test_usage_summary_skips_empty_phases(self, capsys):
        display = SupervisorDisplay()
        display._use_rich = False

        usage = {
            "phase1": {"input_tokens": 100, "output_tokens": 50, "cost_usd": 0.01, "duration_ms": 1000, "turns": 1},
            "phase2": {},
            "phase3": {},
            "phase4": {},
            "total": {"input_tokens": 100, "output_tokens": 50, "cost_usd": 0.01, "duration_ms": 1000, "turns": 1},
        }
        phase_names = {1: "Requirements", 2: "Interfaces", 3: "Tests", 4: "Implementation"}

        display.usage_summary(usage, phase_names)
        captured = capsys.readouterr()

        assert "Requirements" in captured.out
        assert "Interfaces" not in captured.out


class TestGracefulDegradation:
    """Tests that all methods work when rich is unavailable."""

    def _create_plain_display(self):
        display = SupervisorDisplay()
        display._use_rich = False
        display._console = None
        return display

    def test_all_methods_work_without_rich(self, capsys):
        display = self._create_plain_display()

        display.workflow_header("/tmp", "id", "/tmp/m")
        display.phase_header(1, "Test")
        display.phase_complete_banner(1, "Test", "/tmp/doc.md")
        display.workflow_complete()
        display.supervisor_message("msg")
        display.supervisor_success("ok")
        display.supervisor_warning("warn")
        display.tip("hint")
        display.feedback_injection("feedback")
        display.document_preview("preview")
        display.knowledge_summary("summary")
        display.print("text")

        captured = capsys.readouterr()
        assert len(captured.out) > 0

    def test_error_works_without_rich(self, capsys):
        display = self._create_plain_display()
        display.supervisor_error("err")
        captured = capsys.readouterr()
        assert "err" in captured.err

    def test_spinner_works_without_rich(self):
        display = self._create_plain_display()

        async def test():
            async with display.spinner("Loading"):
                pass

        run_async(test())

    def test_tool_spinner_works_without_rich(self):
        display = self._create_plain_display()

        async def test():
            await display.start_tool_spinner("Write")
            await display.stop_tool_spinner()

        run_async(test())

    def test_stream_text_works_without_rich(self):
        display = self._create_plain_display()

        captured = io.StringIO()
        captured.isatty = lambda: False
        with patch('sys.stdout', captured):
            display.stream_text("hello")
            display.stream_text_end()

        assert "hello" in captured.getvalue()

    def test_usage_summary_works_without_rich(self, capsys):
        display = self._create_plain_display()
        usage = {"total": {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0, "duration_ms": 0, "turns": 0}}
        display.usage_summary(usage, {1: "Req", 2: "Int", 3: "Test", 4: "Impl"})
        captured = capsys.readouterr()
        assert "TOTAL" in captured.out


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
