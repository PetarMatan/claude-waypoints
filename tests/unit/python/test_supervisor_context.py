#!/usr/bin/env python3
"""
Unit tests for wp_supervisor/context.py - ContextBuilder class
"""

import sys
import pytest

# Add wp_supervisor to path
sys.path.insert(0, '.')
from wp_supervisor.context import ContextBuilder


class TestBuildPhase1Context:
    """Tests for build_phase1_context method."""

    def test_build_phase1_context_without_task(self):
        context = ContextBuilder.build_phase1_context()
        assert "Phase 1" in context
        assert "Requirements Gathering" in context
        assert "Initial Task" not in context

    def test_build_phase1_context_with_task(self):
        task = "Build a user authentication system"
        context = ContextBuilder.build_phase1_context(task)
        assert "Initial Task" in context
        assert task in context

    def test_build_phase1_context_contains_phase_instructions(self):
        context = ContextBuilder.build_phase1_context()
        assert "clarifying questions" in context.lower()
        assert "Do NOT write any code" in context
        assert "PHASE_COMPLETE" in context

    def test_build_phase1_context_mentions_edge_cases(self):
        context = ContextBuilder.build_phase1_context()
        assert "edge case" in context.lower() or "Edge case" in context

    def test_build_phase1_context_emphasizes_what_not_how(self):
        context = ContextBuilder.build_phase1_context()
        assert "WHAT" in context
        assert "HOW" in context or "how" in context.lower()

    def test_build_phase1_context_with_empty_task(self):
        context = ContextBuilder.build_phase1_context("")
        # Empty string is falsy, so no task section
        assert "Initial Task" not in context

    def test_build_phase1_context_with_none_task(self):
        context = ContextBuilder.build_phase1_context(None)
        assert "Initial Task" not in context


class TestBuildPhase2Context:
    """Tests for build_phase2_context method."""

    def test_build_phase2_context_includes_requirements(self):
        requirements = "# Requirements\n- User login\n- Password reset"
        context = ContextBuilder.build_phase2_context(requirements)
        assert requirements in context

    def test_build_phase2_context_contains_interface_instructions(self):
        context = ContextBuilder.build_phase2_context("requirements")
        assert "Phase 2" in context
        assert "Interface Design" in context
        assert "class" in context.lower() or "interface" in context.lower()

    def test_build_phase2_context_mentions_stubs(self):
        context = ContextBuilder.build_phase2_context("requirements")
        assert "stub" in context.lower() or "NotImplementedError" in context

    def test_build_phase2_context_mentions_no_business_logic(self):
        context = ContextBuilder.build_phase2_context("requirements")
        assert "Do NOT implement business logic" in context

    def test_build_phase2_context_contains_phase_complete_signal(self):
        context = ContextBuilder.build_phase2_context("requirements")
        assert "PHASE_COMPLETE" in context

    def test_build_phase2_context_mentions_compilation(self):
        context = ContextBuilder.build_phase2_context("requirements")
        assert "compile" in context.lower()


class TestBuildPhase3Context:
    """Tests for build_phase3_context method."""

    def test_build_phase3_context_includes_requirements(self):
        requirements = "# Requirements\n- Feature A"
        interfaces = "# Interfaces\n- ServiceA"
        context = ContextBuilder.build_phase3_context(requirements, interfaces)
        assert requirements in context

    def test_build_phase3_context_includes_interfaces(self):
        requirements = "# Requirements\n- Feature A"
        interfaces = "# Interfaces\n- ServiceA"
        context = ContextBuilder.build_phase3_context(requirements, interfaces)
        assert interfaces in context

    def test_build_phase3_context_contains_test_instructions(self):
        context = ContextBuilder.build_phase3_context("req", "interfaces")
        assert "Phase 3" in context
        assert "Test Writing" in context
        assert "unit test" in context.lower()

    def test_build_phase3_context_mentions_red_phase(self):
        context = ContextBuilder.build_phase3_context("req", "interfaces")
        assert "Red" in context or "fail" in context.lower()

    def test_build_phase3_context_mentions_coverage(self):
        context = ContextBuilder.build_phase3_context("req", "interfaces")
        assert "Happy path" in context or "happy path" in context
        assert "Edge case" in context or "edge case" in context

    def test_build_phase3_context_contains_phase_complete_signal(self):
        context = ContextBuilder.build_phase3_context("req", "interfaces")
        assert "PHASE_COMPLETE" in context

    def test_build_phase3_context_mentions_no_implementation(self):
        context = ContextBuilder.build_phase3_context("req", "interfaces")
        assert "Do NOT implement" in context


class TestBuildPhase4Context:
    """Tests for build_phase4_context method."""

    def test_build_phase4_context_includes_requirements(self):
        requirements = "# Requirements Summary"
        interfaces = "# Interfaces"
        tests = "# Tests"
        context = ContextBuilder.build_phase4_context(requirements, interfaces, tests)
        assert requirements in context

    def test_build_phase4_context_includes_interfaces(self):
        requirements = "# Requirements"
        interfaces = "# Interfaces Created"
        tests = "# Tests"
        context = ContextBuilder.build_phase4_context(requirements, interfaces, tests)
        assert interfaces in context

    def test_build_phase4_context_includes_tests(self):
        requirements = "# Requirements"
        interfaces = "# Interfaces"
        tests = "# Tests to Pass"
        context = ContextBuilder.build_phase4_context(requirements, interfaces, tests)
        assert tests in context

    def test_build_phase4_context_contains_implementation_instructions(self):
        context = ContextBuilder.build_phase4_context("req", "interfaces", "tests")
        assert "Phase 4" in context
        assert "Implementation" in context

    def test_build_phase4_context_mentions_green_phase(self):
        context = ContextBuilder.build_phase4_context("req", "interfaces", "tests")
        assert "Green" in context or "pass" in context.lower()

    def test_build_phase4_context_mentions_running_tests(self):
        context = ContextBuilder.build_phase4_context("req", "interfaces", "tests")
        assert "Run test" in context or "run test" in context.lower()

    def test_build_phase4_context_no_phase_complete_signal(self):
        # Phase 4 completes when tests pass, not via signal
        context = ContextBuilder.build_phase4_context("req", "interfaces", "tests")
        # PHASE_COMPLETE may or may not be present in phase 4
        # The key is tests passing, which is mentioned
        assert "ALL tests pass" in context or "all tests pass" in context.lower()


class TestGetSummaryPrompt:
    """Tests for get_summary_prompt method."""

    def test_get_summary_prompt_phase1(self):
        prompt = ContextBuilder.get_summary_prompt(1)
        assert "Requirements Summary" in prompt
        assert "Purpose" in prompt
        assert "Functional Requirements" in prompt

    def test_get_summary_prompt_phase2(self):
        prompt = ContextBuilder.get_summary_prompt(2)
        assert "Interfaces Created" in prompt
        assert "Classes" in prompt or "Methods" in prompt

    def test_get_summary_prompt_phase3(self):
        prompt = ContextBuilder.get_summary_prompt(3)
        assert "Tests Created" in prompt
        assert "Test Cases" in prompt or "Test Files" in prompt

    def test_get_summary_prompt_phase4_returns_empty(self):
        prompt = ContextBuilder.get_summary_prompt(4)
        assert prompt == ""

    def test_get_summary_prompt_invalid_phase_returns_empty(self):
        assert ContextBuilder.get_summary_prompt(5) == ""
        assert ContextBuilder.get_summary_prompt(-1) == ""

    def test_get_summary_prompt_phase1_mentions_specific(self):
        """Phase 1 summary should request specific/detailed requirements."""
        prompt = ContextBuilder.get_summary_prompt(1)
        assert "specific" in prompt.lower() or "comprehensive" in prompt.lower()

    def test_get_summary_prompt_phase2_file_paths(self):
        """Phase 2 summary should request file paths."""
        prompt = ContextBuilder.get_summary_prompt(2)
        assert "File" in prompt or "file" in prompt
        assert "path" in prompt.lower()

    def test_get_summary_prompt_phase3_mentions_coverage(self):
        prompt = ContextBuilder.get_summary_prompt(3)
        assert "coverage" in prompt.lower() or "Coverage" in prompt


class TestGetReviewPrompt:
    """Tests for get_review_prompt method."""

    def test_get_review_prompt_phase1(self):
        prompt = ContextBuilder.get_review_prompt(1)
        assert len(prompt) > 0
        assert "review" in prompt.lower() or "verify" in prompt.lower()

    def test_get_review_prompt_phase2(self):
        prompt = ContextBuilder.get_review_prompt(2)
        assert len(prompt) > 0
        assert "review" in prompt.lower() or "verify" in prompt.lower()

    def test_get_review_prompt_phase3(self):
        prompt = ContextBuilder.get_review_prompt(3)
        assert len(prompt) > 0
        assert "review" in prompt.lower() or "verify" in prompt.lower()

    def test_get_review_prompt_phase4_returns_empty(self):
        prompt = ContextBuilder.get_review_prompt(4)
        assert prompt == ""

    def test_get_review_prompt_invalid_phase_returns_empty(self):
        assert ContextBuilder.get_review_prompt(5) == ""
        assert ContextBuilder.get_review_prompt(-1) == ""

    def test_get_review_prompt_contains_checklist(self):
        """Review prompts should contain verification checklist."""
        for phase in [1, 2, 3]:
            prompt = ContextBuilder.get_review_prompt(phase)
            assert "[ ]" in prompt or "checklist" in prompt.lower()

    def test_get_review_prompt_contains_gaps_signal(self):
        """Review prompts should mention GAPS_FOUND signal."""
        for phase in [1, 2, 3]:
            prompt = ContextBuilder.get_review_prompt(phase)
            assert "GAPS_FOUND" in prompt

    def test_get_review_prompt_contains_verified_signal(self):
        """Review prompts should mention SUMMARY_VERIFIED signal."""
        for phase in [1, 2, 3]:
            prompt = ContextBuilder.get_review_prompt(phase)
            assert "SUMMARY_VERIFIED" in prompt


class TestContextBuilderStaticMethods:
    """Tests verifying methods are static."""

    def test_build_phase1_context_is_static(self):
        # Should be callable without instance
        result = ContextBuilder.build_phase1_context()
        assert isinstance(result, str)

    def test_build_phase2_context_is_static(self):
        result = ContextBuilder.build_phase2_context("req")
        assert isinstance(result, str)

    def test_build_phase3_context_is_static(self):
        result = ContextBuilder.build_phase3_context("req", "interfaces")
        assert isinstance(result, str)

    def test_build_phase4_context_is_static(self):
        result = ContextBuilder.build_phase4_context("req", "interfaces", "tests")
        assert isinstance(result, str)

    def test_get_summary_prompt_is_static(self):
        result = ContextBuilder.get_summary_prompt(1)
        assert isinstance(result, str)

    def test_get_review_prompt_is_static(self):
        result = ContextBuilder.get_review_prompt(1)
        assert isinstance(result, str)


class TestContextIntegration:
    """Integration tests for context building across phases."""

    def test_phase1_output_fits_phase2_input(self):
        # Phase 1 produces requirements summary
        phase1_output = "# Requirements\n- User auth\n- Password reset"
        # Phase 2 should accept it
        context = ContextBuilder.build_phase2_context(phase1_output)
        assert phase1_output in context
        assert "Phase 2" in context

    def test_phase2_output_fits_phase3_input(self):
        requirements = "# Requirements\n- Feature"
        interfaces = "# Interfaces\n- AuthService\n- UserRepository"
        context = ContextBuilder.build_phase3_context(requirements, interfaces)
        assert requirements in context
        assert interfaces in context

    def test_all_phases_context_fits_phase4(self):
        requirements = "# Requirements\n- Feature A"
        interfaces = "# Interfaces\n- ServiceA"
        tests = "# Tests\n- test_feature_a"
        context = ContextBuilder.build_phase4_context(requirements, interfaces, tests)
        assert requirements in context
        assert interfaces in context
        assert tests in context


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
