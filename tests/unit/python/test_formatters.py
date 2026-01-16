#!/usr/bin/env python3
"""
Unit tests for formatters.py

These are pure function tests - no mocking needed.
"""

import sys
from pathlib import Path

# Add hooks/lib to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "hooks" / "lib"))

from formatters import (
    truncate_head,
    truncate_tail,
    format_compile_error,
    format_phase4_compile_error,
    format_phase4_test_failure,
    format_phase1_block,
    format_phase2_compile_error,
    format_phase2_awaiting_approval,
    format_phase3_compile_error,
    format_phase3_awaiting_approval,
    format_phase4_orchestrator_compile_error,
    format_phase4_orchestrator_test_failure,
    format_phase_guard_phase1_block,
    format_phase_guard_phase2_block,
    format_phase_guard_phase3_block,
)


class TestTruncateHead:
    """Tests for truncate_head helper."""

    def test_returns_first_n_lines(self):
        output = "line1\nline2\nline3\nline4\nline5"
        result = truncate_head(output, max_lines=3)
        assert result == "line1\nline2\nline3"

    def test_returns_all_lines_if_less_than_max(self):
        output = "line1\nline2"
        result = truncate_head(output, max_lines=5)
        assert result == "line1\nline2"

    def test_handles_empty_output(self):
        result = truncate_head("", max_lines=5)
        assert result == ""

    def test_strips_whitespace(self):
        output = "  \n  line1  \n  line2  \n  "
        result = truncate_head(output, max_lines=5)
        assert "line1" in result

    def test_default_max_lines_is_20(self):
        output = "\n".join([f"line{i}" for i in range(50)])
        result = truncate_head(output)
        assert result.count("line") == 20


class TestTruncateTail:
    """Tests for truncate_tail helper."""

    def test_returns_last_n_lines(self):
        output = "line1\nline2\nline3\nline4\nline5"
        result = truncate_tail(output, max_lines=3)
        assert result == "line3\nline4\nline5"

    def test_returns_all_lines_if_less_than_max(self):
        output = "line1\nline2"
        result = truncate_tail(output, max_lines=5)
        assert result == "line1\nline2"

    def test_handles_empty_output(self):
        result = truncate_tail("", max_lines=5)
        assert result == ""

    def test_default_max_lines_is_30(self):
        output = "\n".join([f"line{i}" for i in range(50)])
        result = truncate_tail(output)
        assert result.count("line") == 30


class TestFormatCompileError:
    """Tests for format_compile_error (auto-compile)."""

    def test_includes_file_path(self):
        result = format_compile_error("error", "/src/Service.kt", "maven")
        assert "/src/Service.kt" in result

    def test_includes_profile_name(self):
        result = format_compile_error("error", "/file.kt", "gradle")
        assert "gradle" in result

    def test_includes_compilation_failed_header(self):
        result = format_compile_error("error", "/file.kt", "maven")
        assert "COMPILATION FAILED" in result

    def test_truncates_long_output(self):
        long_output = "\n".join([f"error line {i}" for i in range(50)])
        result = format_compile_error(long_output, "/file.kt", "maven", max_lines=20)
        assert "error line 0" in result
        assert "error line 19" in result
        assert "error line 20" not in result

    def test_handles_empty_output(self):
        result = format_compile_error("", "/file.kt", "maven")
        assert "COMPILATION FAILED" in result

    def test_includes_fix_errors_instruction(self):
        result = format_compile_error("error", "/file.kt", "maven")
        assert "Fix" in result


class TestFormatPhase4CompileError:
    """Tests for format_phase4_compile_error (auto-test)."""

    def test_includes_phase_4_header(self):
        result = format_phase4_compile_error("error", "/file.kt", "maven")
        assert "WP Phase 4" in result
        assert "Compilation FAILED" in result

    def test_includes_file_path(self):
        result = format_phase4_compile_error("error", "/src/Main.kt", "maven")
        assert "/src/Main.kt" in result

    def test_includes_continue_implementing_instruction(self):
        result = format_phase4_compile_error("error", "/file.kt", "maven")
        assert "continue implementing" in result


class TestFormatPhase4TestFailure:
    """Tests for format_phase4_test_failure (auto-test)."""

    def test_includes_compilation_passed_tests_failed(self):
        result = format_phase4_test_failure("test output", "/file.kt", "maven")
        assert "Compilation PASSED" in result
        assert "Tests FAILED" in result

    def test_uses_tail_truncation(self):
        # Test output should show last 30 lines (tail), not first 20
        long_output = "\n".join([f"test line {i}" for i in range(50)])
        result = format_phase4_test_failure(long_output, "/file.kt", "maven", max_lines=30)
        assert "test line 49" in result  # Should include last line
        assert "test line 20" in result  # Should include line 20
        assert "test line 0" not in result  # Should NOT include first line

    def test_includes_test_results_header(self):
        result = format_phase4_test_failure("test output", "/file.kt", "maven")
        assert "Test Results" in result


class TestFormatPhase1Block:
    """Tests for format_phase1_block (orchestrator)."""

    def test_includes_requirements_gathering_header(self):
        result = format_phase1_block("/path/markers")
        assert "Phase 1" in result
        assert "Requirements" in result

    def test_includes_cli_command(self):
        result = format_phase1_block("/path/to/markers")
        assert "true # wp:mark-complete requirements" in result

    def test_includes_ask_user_question_instruction(self):
        result = format_phase1_block("/path/markers")
        assert "AskUserQuestion" in result


class TestFormatPhase2CompileError:
    """Tests for format_phase2_compile_error (orchestrator)."""

    def test_includes_phase_2_header(self):
        result = format_phase2_compile_error("error", "maven", "mvn compile")
        assert "Phase 2" in result
        assert "Interface Design" in result

    def test_includes_compilation_failed(self):
        result = format_phase2_compile_error("error", "maven", "mvn compile")
        assert "Compilation FAILED" in result

    def test_includes_compile_command(self):
        result = format_phase2_compile_error("error", "maven", "mvn compile")
        assert "mvn compile" in result

    def test_truncates_errors(self):
        long_output = "\n".join([f"error {i}" for i in range(50)])
        result = format_phase2_compile_error(long_output, "maven", "mvn compile", max_lines=20)
        assert "error 0" in result
        assert "error 19" in result
        assert "error 20" not in result


class TestFormatPhase2AwaitingApproval:
    """Tests for format_phase2_awaiting_approval (orchestrator)."""

    def test_includes_compilation_passed(self):
        result = format_phase2_awaiting_approval("/markers", "maven")
        assert "Compilation PASSED" in result

    def test_includes_cli_command(self):
        result = format_phase2_awaiting_approval("/markers", "maven")
        assert "true # wp:mark-complete interfaces" in result

    def test_includes_ask_user_question(self):
        result = format_phase2_awaiting_approval("/markers", "maven")
        assert "AskUserQuestion" in result


class TestFormatPhase3CompileError:
    """Tests for format_phase3_compile_error (orchestrator)."""

    def test_includes_phase_3_header(self):
        result = format_phase3_compile_error("error", "maven", "mvn test-compile")
        assert "Phase 3" in result
        assert "Test Writing" in result

    def test_includes_test_compilation_failed(self):
        result = format_phase3_compile_error("error", "maven", "mvn test-compile")
        assert "Test Compilation FAILED" in result

    def test_includes_compile_command(self):
        result = format_phase3_compile_error("error", "maven", "mvn test-compile")
        assert "mvn test-compile" in result


class TestFormatPhase3AwaitingApproval:
    """Tests for format_phase3_awaiting_approval (orchestrator)."""

    def test_includes_tests_compile_successfully(self):
        result = format_phase3_awaiting_approval("/markers", "maven")
        assert "Tests compile successfully" in result

    def test_includes_cli_command(self):
        result = format_phase3_awaiting_approval("/markers", "maven")
        assert "true # wp:mark-complete tests" in result

    def test_mentions_tests_will_fail(self):
        result = format_phase3_awaiting_approval("/markers", "maven")
        assert "Tests WILL FAIL" in result


class TestFormatPhase4OrchestratorCompileError:
    """Tests for format_phase4_orchestrator_compile_error (orchestrator)."""

    def test_includes_phase_4_header(self):
        result = format_phase4_orchestrator_compile_error("error", "maven")
        assert "Phase 4" in result
        assert "Implementation Loop" in result

    def test_includes_compilation_failed(self):
        result = format_phase4_orchestrator_compile_error("error", "maven")
        assert "Compilation FAILED" in result

    def test_includes_continue_loop_instruction(self):
        result = format_phase4_orchestrator_compile_error("error", "maven")
        assert "Continue the loop" in result


class TestFormatPhase4OrchestratorTestFailure:
    """Tests for format_phase4_orchestrator_test_failure (orchestrator)."""

    def test_includes_compilation_passed_tests_failed(self):
        result = format_phase4_orchestrator_test_failure("output", "maven")
        assert "Compilation PASSED" in result
        assert "Tests FAILED" in result

    def test_includes_continue_loop_instruction(self):
        result = format_phase4_orchestrator_test_failure("output", "maven")
        assert "Continue the loop" in result

    def test_uses_tail_truncation(self):
        long_output = "\n".join([f"line {i}" for i in range(50)])
        result = format_phase4_orchestrator_test_failure(long_output, "maven", max_lines=30)
        assert "line 49" in result
        assert "line 0" not in result


# =============================================================================
# Phase Guard Formatter Tests
# =============================================================================

class TestFormatPhaseGuardPhase1Block:
    """Tests for format_phase_guard_phase1_block (phase-guard)."""

    def test_includes_phase_1_header(self):
        result = format_phase_guard_phase1_block("/src/Service.kt", "maven")
        assert "Phase 1" in result
        assert "Requirements" in result

    def test_includes_file_path(self):
        result = format_phase_guard_phase1_block("/src/Main.kt", "maven")
        assert "/src/Main.kt" in result

    def test_includes_profile_name(self):
        result = format_phase_guard_phase1_block("/src/Service.kt", "gradle")
        assert "gradle" in result

    def test_includes_blocked_message(self):
        result = format_phase_guard_phase1_block("/src/Service.kt", "maven")
        assert "Blocked" in result

    def test_includes_cli_instruction(self):
        result = format_phase_guard_phase1_block("/src/Service.kt", "maven")
        assert "true # wp:mark-complete requirements" in result


class TestFormatPhaseGuardPhase2Block:
    """Tests for format_phase_guard_phase2_block (phase-guard)."""

    def test_includes_phase_2_header(self):
        result = format_phase_guard_phase2_block("/src/ServiceTest.kt", "maven")
        assert "Phase 2" in result
        assert "Interface" in result

    def test_includes_file_path(self):
        result = format_phase_guard_phase2_block("/src/ServiceTest.kt", "maven")
        assert "/src/ServiceTest.kt" in result

    def test_includes_profile_name(self):
        result = format_phase_guard_phase2_block("/src/ServiceTest.kt", "npm")
        assert "npm" in result

    def test_includes_blocked_message(self):
        result = format_phase_guard_phase2_block("/src/ServiceTest.kt", "maven")
        assert "Blocked" in result

    def test_includes_cli_instruction(self):
        result = format_phase_guard_phase2_block("/src/ServiceTest.kt", "maven")
        assert "true # wp:mark-complete interfaces" in result


class TestFormatPhaseGuardPhase3Block:
    """Tests for format_phase_guard_phase3_block (phase-guard)."""

    def test_includes_phase_3_header(self):
        result = format_phase_guard_phase3_block("/src/Service.kt", "maven")
        assert "Phase 3" in result
        assert "Test" in result

    def test_includes_file_path(self):
        result = format_phase_guard_phase3_block("/src/Service.kt", "maven")
        assert "/src/Service.kt" in result

    def test_includes_profile_name(self):
        result = format_phase_guard_phase3_block("/src/Service.kt", "gradle")
        assert "gradle" in result

    def test_includes_blocked_message(self):
        result = format_phase_guard_phase3_block("/src/Service.kt", "maven")
        assert "Blocked" in result

    def test_includes_cli_instruction(self):
        result = format_phase_guard_phase3_block("/src/Service.kt", "maven")
        assert "true # wp:mark-complete tests" in result
