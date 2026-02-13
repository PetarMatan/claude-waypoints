#!/usr/bin/env python3
"""
Unit tests for wp_supervisor/templates.py - Prompt templates and formatting functions
"""

import sys
import pytest

# Add wp_supervisor to path
sys.path.insert(0, '.')
from wp_supervisor import templates


class TestPhaseContextTemplates:
    """Tests for phase context templates."""

    def test_phase1_supervisor_fallback_context_exists(self):
        assert hasattr(templates, 'PHASE1_SUPERVISOR_FALLBACK_CONTEXT')
        assert len(templates.PHASE1_SUPERVISOR_FALLBACK_CONTEXT) > 0

    def test_phase1_supervisor_fallback_context_has_placeholder(self):
        assert "{task_section}" in templates.PHASE1_SUPERVISOR_FALLBACK_CONTEXT

    def test_phase1_supervisor_fallback_has_phase_complete_signal(self):
        """Supervisor fallback context should have ---PHASE_COMPLETE--- signal."""
        assert "PHASE_COMPLETE" in templates.PHASE1_SUPERVISOR_FALLBACK_CONTEXT

    def test_phase1_supervisor_fallback_has_guardrail(self):
        """Supervisor fallback context should warn against premature PHASE_COMPLETE."""
        assert "CRITICAL" in templates.PHASE1_SUPERVISOR_FALLBACK_CONTEXT
        assert "clarifying questions" in templates.PHASE1_SUPERVISOR_FALLBACK_CONTEXT

    def test_phase1_task_section_exists(self):
        assert hasattr(templates, 'PHASE1_TASK_SECTION')
        assert "{user_task}" in templates.PHASE1_TASK_SECTION

    def test_phase2_context_exists(self):
        assert hasattr(templates, 'PHASE2_CONTEXT')
        assert "{requirements_summary}" in templates.PHASE2_CONTEXT

    def test_phase3_context_exists(self):
        assert hasattr(templates, 'PHASE3_CONTEXT')
        assert "{requirements_summary}" in templates.PHASE3_CONTEXT
        assert "{interfaces_list}" in templates.PHASE3_CONTEXT

    def test_phase4_context_exists(self):
        assert hasattr(templates, 'PHASE4_CONTEXT')
        assert "{requirements_summary}" in templates.PHASE4_CONTEXT
        assert "{interfaces_list}" in templates.PHASE4_CONTEXT
        assert "{tests_list}" in templates.PHASE4_CONTEXT


class TestSummaryPromptTemplates:
    """Tests for summary generation templates."""

    def test_requirements_summary_prompt_exists(self):
        assert hasattr(templates, 'REQUIREMENTS_SUMMARY_PROMPT')
        prompt = templates.REQUIREMENTS_SUMMARY_PROMPT
        assert "Requirements Summary" in prompt
        assert "Purpose" in prompt
        assert "Functional Requirements" in prompt

    def test_interfaces_summary_prompt_exists(self):
        assert hasattr(templates, 'INTERFACES_SUMMARY_PROMPT')
        prompt = templates.INTERFACES_SUMMARY_PROMPT
        assert "Interfaces Created" in prompt
        assert "File" in prompt

    def test_tests_summary_prompt_exists(self):
        assert hasattr(templates, 'TESTS_SUMMARY_PROMPT')
        prompt = templates.TESTS_SUMMARY_PROMPT
        assert "Tests Created" in prompt
        assert "Test Cases" in prompt or "Test Files" in prompt

    def test_requirements_prompt_requests_numbered_items(self):
        """Requirements should be numbered for traceability."""
        prompt = templates.REQUIREMENTS_SUMMARY_PROMPT
        assert "REQ-" in prompt or "number" in prompt.lower()

    def test_interfaces_prompt_requests_file_paths(self):
        """Interfaces prompt should request exact file paths."""
        prompt = templates.INTERFACES_SUMMARY_PROMPT
        assert "path" in prompt.lower() or "Path" in prompt

    def test_tests_prompt_requests_coverage_mapping(self):
        """Tests prompt should request requirement coverage mapping."""
        prompt = templates.TESTS_SUMMARY_PROMPT
        assert "coverage" in prompt.lower() or "Coverage" in prompt


class TestReviewPromptTemplates:
    """Tests for self-review templates."""

    def test_requirements_review_prompt_exists(self):
        assert hasattr(templates, 'REQUIREMENTS_REVIEW_PROMPT')
        prompt = templates.REQUIREMENTS_REVIEW_PROMPT
        assert len(prompt) > 0

    def test_interfaces_review_prompt_exists(self):
        assert hasattr(templates, 'INTERFACES_REVIEW_PROMPT')
        prompt = templates.INTERFACES_REVIEW_PROMPT
        assert len(prompt) > 0

    def test_tests_review_prompt_exists(self):
        assert hasattr(templates, 'TESTS_REVIEW_PROMPT')
        prompt = templates.TESTS_REVIEW_PROMPT
        assert len(prompt) > 0

    def test_review_prompts_contain_checklist(self):
        """All review prompts should have verification checklist."""
        for prompt_name in ['REQUIREMENTS_REVIEW_PROMPT', 'INTERFACES_REVIEW_PROMPT', 'TESTS_REVIEW_PROMPT']:
            prompt = getattr(templates, prompt_name)
            assert "[ ]" in prompt, f"{prompt_name} should contain checklist items"

    def test_review_prompts_contain_gaps_signal(self):
        """All review prompts should mention GAPS_FOUND signal."""
        for prompt_name in ['REQUIREMENTS_REVIEW_PROMPT', 'INTERFACES_REVIEW_PROMPT', 'TESTS_REVIEW_PROMPT']:
            prompt = getattr(templates, prompt_name)
            assert "GAPS_FOUND" in prompt, f"{prompt_name} should mention GAPS_FOUND"

    def test_review_prompts_contain_verified_signal(self):
        """All review prompts should mention SUMMARY_VERIFIED signal."""
        for prompt_name in ['REQUIREMENTS_REVIEW_PROMPT', 'INTERFACES_REVIEW_PROMPT', 'TESTS_REVIEW_PROMPT']:
            prompt = getattr(templates, prompt_name)
            assert "SUMMARY_VERIFIED" in prompt, f"{prompt_name} should mention SUMMARY_VERIFIED"


class TestFormatPhaseHeader:
    """Tests for format_phase_header function."""

    def test_format_phase_header_exists(self):
        assert hasattr(templates, 'format_phase_header')
        assert callable(templates.format_phase_header)

    def test_format_phase_header_includes_phase_number(self):
        result = templates.format_phase_header(1, "Requirements")
        assert "PHASE 1" in result

    def test_format_phase_header_includes_phase_name(self):
        result = templates.format_phase_header(2, "Interface Design")
        assert "INTERFACE DESIGN" in result

    def test_format_phase_header_has_separators(self):
        result = templates.format_phase_header(3, "Test Writing")
        assert "=" in result

    def test_format_phase_header_all_phases(self):
        phases = [
            (1, "Requirements"),
            (2, "Interface Design"),
            (3, "Test Writing"),
            (4, "Implementation"),
        ]
        for phase_num, phase_name in phases:
            result = templates.format_phase_header(phase_num, phase_name)
            assert f"PHASE {phase_num}" in result
            assert phase_name.upper() in result


class TestFormatWorkflowHeader:
    """Tests for format_workflow_header function."""

    def test_format_workflow_header_exists(self):
        assert hasattr(templates, 'format_workflow_header')
        assert callable(templates.format_workflow_header)

    def test_format_workflow_header_includes_working_dir(self):
        result = templates.format_workflow_header(
            working_dir="/path/to/project",
            workflow_id="abc123",
            markers_dir="/path/to/markers"
        )
        assert "/path/to/project" in result

    def test_format_workflow_header_includes_workflow_id(self):
        result = templates.format_workflow_header(
            working_dir="/path",
            workflow_id="workflow-123",
            markers_dir="/markers"
        )
        assert "workflow-123" in result

    def test_format_workflow_header_includes_markers_dir(self):
        result = templates.format_workflow_header(
            working_dir="/path",
            workflow_id="id",
            markers_dir="/path/to/markers"
        )
        assert "/path/to/markers" in result

    def test_format_workflow_header_has_title(self):
        result = templates.format_workflow_header(
            working_dir="/path",
            workflow_id="id",
            markers_dir="/markers"
        )
        assert "Waypoints Supervisor" in result


class TestFormatPhaseCompleteBanner:
    """Tests for format_phase_complete_banner function."""

    def test_format_phase_complete_banner_exists(self):
        assert hasattr(templates, 'format_phase_complete_banner')
        assert callable(templates.format_phase_complete_banner)

    def test_format_phase_complete_banner_includes_phase(self):
        result = templates.format_phase_complete_banner(1, "Requirements")
        assert "Phase 1" in result
        assert "Requirements" in result

    def test_format_phase_complete_banner_mentions_complete(self):
        result = templates.format_phase_complete_banner(2, "Interface Design")
        assert "complete" in result.lower()


class TestFormatWorkflowComplete:
    """Tests for format_workflow_complete function."""

    def test_format_workflow_complete_exists(self):
        assert hasattr(templates, 'format_workflow_complete')
        assert callable(templates.format_workflow_complete)

    def test_format_workflow_complete_mentions_complete(self):
        result = templates.format_workflow_complete()
        assert "Complete" in result or "complete" in result

    def test_format_workflow_complete_has_separators(self):
        result = templates.format_workflow_complete()
        assert "=" in result


class TestTemplateConsistency:
    """Tests for template consistency across phases."""

    def test_all_summary_prompts_request_format(self):
        """All summary prompts should request specific output format."""
        prompts = [
            templates.REQUIREMENTS_SUMMARY_PROMPT,
            templates.INTERFACES_SUMMARY_PROMPT,
            templates.TESTS_SUMMARY_PROMPT,
        ]
        for prompt in prompts:
            assert "format" in prompt.lower() or "Format" in prompt

    def test_all_supervisor_phase_contexts_mention_phase_complete(self):
        """All supervisor phase contexts should mention PHASE_COMPLETE signal."""
        contexts = [
            templates.PHASE1_SUPERVISOR_FALLBACK_CONTEXT,
            templates.PHASE2_CONTEXT,
            templates.PHASE3_CONTEXT,
            templates.PHASE4_CONTEXT,
        ]
        for context in contexts:
            assert "PHASE_COMPLETE" in context

    def test_all_phase_contexts_have_your_task_section(self):
        """All phase contexts should have 'Your Task' section."""
        contexts = [
            templates.PHASE1_SUPERVISOR_FALLBACK_CONTEXT,
            templates.PHASE2_CONTEXT,
            templates.PHASE3_CONTEXT,
            templates.PHASE4_CONTEXT,
        ]
        for context in contexts:
            assert "Your Task" in context or "## Your Task" in context


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
