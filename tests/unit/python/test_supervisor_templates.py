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
        assert "ABSOLUTE RULE" in templates.PHASE1_SUPERVISOR_FALLBACK_CONTEXT
        assert "questions" in templates.PHASE1_SUPERVISOR_FALLBACK_CONTEXT

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

    def test_requirements_prompt_instructs_build_tool_verification(self):
        """Requirements prompt should instruct model to verify build tool from filesystem."""
        prompt = templates.REQUIREMENTS_SUMMARY_PROMPT
        assert "verify" in prompt.lower() or "Verify" in prompt
        assert "build wrapper" in prompt.lower() or "build tool" in prompt.lower()
        assert "subagent" in prompt.lower()

    def test_interfaces_prompt_requests_file_paths(self):
        """Interfaces prompt should request exact file paths."""
        prompt = templates.INTERFACES_SUMMARY_PROMPT
        assert "path" in prompt.lower() or "Path" in prompt

    def test_tests_prompt_requests_coverage_mapping(self):
        """Tests prompt should request requirement coverage mapping."""
        prompt = templates.TESTS_SUMMARY_PROMPT
        assert "coverage" in prompt.lower() or "Coverage" in prompt


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


class TestTechnicalDigestPrompt:
    """Tests for TECHNICAL_DIGEST_PROMPT template."""

    def test_technical_digest_prompt_exists(self):
        assert hasattr(templates, 'TECHNICAL_DIGEST_PROMPT')
        assert len(templates.TECHNICAL_DIGEST_PROMPT) > 0

    def test_technical_digest_prompt_has_type_definitions_section(self):
        prompt = templates.TECHNICAL_DIGEST_PROMPT
        assert "Type Definitions" in prompt

    def test_technical_digest_prompt_has_method_signatures_section(self):
        prompt = templates.TECHNICAL_DIGEST_PROMPT
        assert "Method Signatures" in prompt

    def test_technical_digest_prompt_has_integration_points_section(self):
        prompt = templates.TECHNICAL_DIGEST_PROMPT
        assert "Integration Points" in prompt

    def test_technical_digest_prompt_has_test_boilerplate_section(self):
        prompt = templates.TECHNICAL_DIGEST_PROMPT
        assert "Test Boilerplate" in prompt

    def test_technical_digest_prompt_requires_file_paths(self):
        prompt = templates.TECHNICAL_DIGEST_PROMPT
        assert "file path" in prompt.lower() or "EXACT file path" in prompt

    def test_technical_digest_prompt_discourages_full_file_dumps(self):
        prompt = templates.TECHNICAL_DIGEST_PROMPT
        assert "NOT" in prompt or "full file" in prompt.lower()

    def test_technical_digest_prompt_requests_actual_code(self):
        prompt = templates.TECHNICAL_DIGEST_PROMPT
        assert "ACTUAL" in prompt or "Copy" in prompt


class TestKnowledgeExtractionPrompt:
    """Tests for knowledge extraction prompt with relationship notation."""

    def test_extraction_prompt_exists(self):
        # given - [REQ-17] Modify extraction prompt to instruct Claude
        assert hasattr(templates, 'KNOWLEDGE_EXTRACTION_PROMPT')

    def test_extraction_prompt_mentions_relationships(self):
        # given - [REQ-17] Instruct Claude to mark relationships using bracket notation
        prompt = templates.KNOWLEDGE_EXTRACTION_PROMPT

        # then
        assert "relationship" in prompt.lower()

    def test_extraction_prompt_documents_bracket_notation(self):
        # given - [REQ-3] Parse relationships using inline bracket notation
        prompt = templates.KNOWLEDGE_EXTRACTION_PROMPT

        # then - Should document the bracket syntax
        assert "[led_to:" in prompt or "led_to:" in prompt

    def test_extraction_prompt_lists_all_relationship_types(self):
        # given - [REQ-2] Support all relationship types
        prompt = templates.KNOWLEDGE_EXTRACTION_PROMPT

        # then - Should document all 5 relationship types
        relationship_types = ["led_to", "contradicts", "supersedes", "related_to", "applies_to"]
        for rel_type in relationship_types:
            assert rel_type in prompt

    def test_extraction_prompt_provides_examples(self):
        # given - Examples help Claude understand the format
        prompt = templates.KNOWLEDGE_EXTRACTION_PROMPT

        # then
        assert "example" in prompt.lower() or "[" in prompt  # Bracket notation example

    def test_extraction_prompt_mentions_optional_relationships(self):
        # given - [REQ-20] Continue supporting entries without relationships
        prompt = templates.KNOWLEDGE_EXTRACTION_PROMPT

        # then
        assert "optional" in prompt.lower() or "not required" in prompt.lower()


class TestStagedKnowledgeFormatting:
    """Tests for format_staged_knowledge_for_prompt function."""

    def test_format_staged_knowledge_function_exists(self):
        # given
        assert hasattr(templates, 'format_staged_knowledge_for_prompt')
        assert callable(templates.format_staged_knowledge_for_prompt)

    def test_format_staged_knowledge_with_empty_returns_none_yet(self):
        # given
        sys.path.insert(0, 'hooks/lib')
        from wp_knowledge import StagedKnowledge

        staged = StagedKnowledge()

        # when
        result = templates.format_staged_knowledge_for_prompt(staged)

        # then
        assert result == "None yet"

    def test_format_staged_knowledge_with_entries_returns_summary(self):
        # given
        sys.path.insert(0, 'hooks/lib')
        from wp_knowledge import StagedKnowledge, StagedKnowledgeEntry

        staged = StagedKnowledge(
            architecture=[
                StagedKnowledgeEntry(
                    title="Service Mesh",
                    content="Services communicate through a mesh.",
                    phase=1
                )
            ]
        )

        # when
        result = templates.format_staged_knowledge_for_prompt(staged)

        # then
        assert "Service Mesh" in result
        assert result != "None yet"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
