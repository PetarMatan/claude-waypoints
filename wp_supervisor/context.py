#!/usr/bin/env python3
"""
Waypoints Supervisor - Context Builder

Builds context prompts for each Waypoints phase, including summaries
from previous phases and project knowledge context [REQ-5, REQ-6].
"""

from typing import Optional

from .templates import (
    PHASE1_CONTEXT,
    PHASE1_TASK_SECTION,
    PHASE2_CONTEXT,
    PHASE3_CONTEXT,
    PHASE4_CONTEXT,
    REQUIREMENTS_SUMMARY_PROMPT,
    INTERFACES_SUMMARY_PROMPT,
    TESTS_SUMMARY_PROMPT,
    REQUIREMENTS_REVIEW_PROMPT,
    INTERFACES_REVIEW_PROMPT,
    TESTS_REVIEW_PROMPT,
    KNOWLEDGE_EXTRACTION_PROMPT,
)


class ContextBuilder:
    """
    Builds context/prompts for each Waypoints phase.

    All phases receive identical knowledge context [REQ-6], which is loaded
    once at workflow start and passed to each build_phase*_context() method.
    """

    @staticmethod
    def build_phase1_context(
        user_task: Optional[str] = None,
        knowledge_context: str = ""
    ) -> str:
        """
        Build context for Phase 1: Requirements Gathering.

        Args:
            user_task: Optional initial task description from user
            knowledge_context: Project knowledge section to inject [REQ-5]
        """
        # Build task section if user provided task
        task_section = ""
        if user_task:
            task_section = PHASE1_TASK_SECTION.format(user_task=user_task)

        # Build base context
        context = PHASE1_CONTEXT.format(task_section=task_section)

        # Inject knowledge context if provided [REQ-5]
        if knowledge_context:
            context = f"{context}\n\n{knowledge_context}"

        return context

    @staticmethod
    def build_phase2_context(
        requirements_summary: str,
        knowledge_context: str = ""
    ) -> str:
        """
        Build context for Phase 2: Interface Design.

        Args:
            requirements_summary: Summary from Phase 1
            knowledge_context: Project knowledge section to inject [REQ-5]
        """
        context = PHASE2_CONTEXT.format(requirements_summary=requirements_summary)

        # Inject knowledge context if provided [REQ-5]
        if knowledge_context:
            context = f"{context}\n\n{knowledge_context}"

        return context

    @staticmethod
    def build_phase3_context(
        requirements_summary: str,
        interfaces_list: str,
        knowledge_context: str = ""
    ) -> str:
        """
        Build context for Phase 3: Test Writing.

        Args:
            requirements_summary: Summary from Phase 1
            interfaces_list: Interfaces created in Phase 2
            knowledge_context: Project knowledge section to inject [REQ-5]
        """
        context = PHASE3_CONTEXT.format(
            requirements_summary=requirements_summary,
            interfaces_list=interfaces_list
        )

        # Inject knowledge context if provided [REQ-5]
        if knowledge_context:
            context = f"{context}\n\n{knowledge_context}"

        return context

    @staticmethod
    def build_phase4_context(
        requirements_summary: str,
        interfaces_list: str,
        tests_list: str,
        knowledge_context: str = ""
    ) -> str:
        """
        Build context for Phase 4: Implementation.

        Args:
            requirements_summary: Summary from Phase 1
            interfaces_list: Interfaces created in Phase 2
            tests_list: Tests created in Phase 3
            knowledge_context: Project knowledge section to inject [REQ-5]
        """
        context = PHASE4_CONTEXT.format(
            requirements_summary=requirements_summary,
            interfaces_list=interfaces_list,
            tests_list=tests_list
        )

        # Inject knowledge context if provided [REQ-5]
        if knowledge_context:
            context = f"{context}\n\n{knowledge_context}"

        return context

    @staticmethod
    def get_summary_prompt(phase: int) -> str:
        """Get the summary generation prompt for a phase."""
        prompts = {
            1: REQUIREMENTS_SUMMARY_PROMPT,
            2: INTERFACES_SUMMARY_PROMPT,
            3: TESTS_SUMMARY_PROMPT,
        }
        return prompts.get(phase, "")

    @staticmethod
    def get_review_prompt(phase: int) -> str:
        """Get the self-review prompt for a phase summary."""
        prompts = {
            1: REQUIREMENTS_REVIEW_PROMPT,
            2: INTERFACES_REVIEW_PROMPT,
            3: TESTS_REVIEW_PROMPT,
        }
        return prompts.get(phase, "")

    @staticmethod
    def get_knowledge_extraction_prompt(
        phase: int,
        existing_knowledge: str = ""
    ) -> str:
        """
        Get the knowledge extraction prompt for a phase [REQ-7, REQ-8, REQ-9, REQ-11].

        Args:
            phase: Phase number (1-4)
            existing_knowledge: Current project knowledge to avoid duplicates [REQ-11]

        Returns:
            Extraction prompt instructing Claude to output in exact format:
            ARCHITECTURE:, DECISIONS:, LESSONS_LEARNED: sections with entries,
            or NO_KNOWLEDGE_EXTRACTED if nothing notable.
        """
        # Format the extraction prompt with existing knowledge [REQ-11]
        existing = existing_knowledge if existing_knowledge else "(No existing project knowledge)"
        return KNOWLEDGE_EXTRACTION_PROMPT.format(existing_knowledge=existing)
