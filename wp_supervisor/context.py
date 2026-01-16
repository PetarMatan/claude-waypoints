#!/usr/bin/env python3
"""
Waypoints Supervisor - Context Builder

Builds context prompts for each Waypoints phase, including summaries
from previous phases.
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
)


class ContextBuilder:
    """Builds context/prompts for each Waypoints phase."""

    @staticmethod
    def build_phase1_context(user_task: Optional[str] = None) -> str:
        """
        Build context for Phase 1: Requirements Gathering.

        Args:
            user_task: Optional initial task description from user
        """
        task_section = ""
        if user_task:
            task_section = PHASE1_TASK_SECTION.format(user_task=user_task)

        return PHASE1_CONTEXT.format(task_section=task_section)

    @staticmethod
    def build_phase2_context(requirements_summary: str) -> str:
        """
        Build context for Phase 2: Interface Design.

        Args:
            requirements_summary: Summary from Phase 1
        """
        return PHASE2_CONTEXT.format(requirements_summary=requirements_summary)

    @staticmethod
    def build_phase3_context(requirements_summary: str, interfaces_list: str) -> str:
        """
        Build context for Phase 3: Test Writing.

        Args:
            requirements_summary: Summary from Phase 1
            interfaces_list: Interfaces created in Phase 2
        """
        return PHASE3_CONTEXT.format(
            requirements_summary=requirements_summary,
            interfaces_list=interfaces_list
        )

    @staticmethod
    def build_phase4_context(
        requirements_summary: str,
        interfaces_list: str,
        tests_list: str
    ) -> str:
        """
        Build context for Phase 4: Implementation.

        Args:
            requirements_summary: Summary from Phase 1
            interfaces_list: Interfaces created in Phase 2
            tests_list: Tests created in Phase 3
        """
        return PHASE4_CONTEXT.format(
            requirements_summary=requirements_summary,
            interfaces_list=interfaces_list,
            tests_list=tests_list
        )

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
