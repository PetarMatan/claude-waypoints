#!/usr/bin/env python3
"""
Waypoints Supervisor - Context Builder

Builds context prompts for each Waypoints phase, including summaries
from previous phases and project knowledge context.
"""

from typing import Optional

from .templates import (
    PHASE1_CONTEXT,
    PHASE1_TASK_SECTION,
    PHASE2_CONTEXT,
    PHASE3_CONTEXT,
    PHASE4_CONTEXT,
    PHASE_NAMES,
    REQUIREMENTS_SUMMARY_PROMPT,
    INTERFACES_SUMMARY_PROMPT,
    TESTS_SUMMARY_PROMPT,
    REQUIREMENTS_REVIEW_PROMPT,
    INTERFACES_REVIEW_PROMPT,
    TESTS_REVIEW_PROMPT,
    REGENERATION_CONVERSATION_CONTEXT,
    REGENERATION_FINAL_SUMMARY_PROMPT,
    KNOWLEDGE_EXTRACTION_PROMPT,
)
from .subagents import PHASE1_SUPERVISOR_INSTRUCTIONS


class ContextBuilder:
    """
    Builds context/prompts for each Waypoints phase.

    All phases receive identical knowledge context, which is loaded
    once at workflow start and passed to each build_phase*_context() method.
    """

    @staticmethod
    def build_phase1_context(
        user_task: Optional[str] = None,
        knowledge_context: str = "",
        supervisor_mode: bool = True
    ) -> str:
        """
        Build context for Phase 1: Requirements Gathering.

        In supervisor mode, uses special instructions that delegate exploration
        to subagents rather than exploring directly.

        Args:
            user_task: Optional initial task description from user
            knowledge_context: Project knowledge section to inject
            supervisor_mode: If True, use supervisor instructions with subagent
                           delegation. Default True since this is the supervisor
                           module.

        Returns:
            Context string for Phase 1 session
        """
        # Build task section if user provided task
        task_section = ""
        if user_task:
            task_section = PHASE1_TASK_SECTION.format(user_task=user_task)

        # Use supervisor instructions in supervisor mode
        # These instructions tell Claude to delegate exploration to subagents
        if supervisor_mode:
            context = PHASE1_SUPERVISOR_INSTRUCTIONS
            if task_section:
                context = f"{context}\n\n## Initial Task\n{user_task}\n"
        else:
            # Fallback to standard Phase 1 context (CLI mode behavior)
            context = PHASE1_CONTEXT.format(task_section=task_section)

        # Inject knowledge context if provided
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
            knowledge_context: Project knowledge section to inject
        """
        context = PHASE2_CONTEXT.format(requirements_summary=requirements_summary)

        # Inject knowledge context if provided
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
            knowledge_context: Project knowledge section to inject
        """
        context = PHASE3_CONTEXT.format(
            requirements_summary=requirements_summary,
            interfaces_list=interfaces_list
        )

        # Inject knowledge context if provided
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
            knowledge_context: Project knowledge section to inject
        """
        context = PHASE4_CONTEXT.format(
            requirements_summary=requirements_summary,
            interfaces_list=interfaces_list,
            tests_list=tests_list
        )

        # Inject knowledge context if provided
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
    def build_regeneration_context(
        phase: int,
        current_summary: str,
        initial_feedback: str
    ) -> str:
        """
        Build context for summary regeneration conversation.

        Args:
            phase: Phase number (1-3)
            current_summary: The current summary being reviewed
            initial_feedback: User's initial feedback

        Returns:
            Context prompt for the regeneration conversation
        """
        phase_name = PHASE_NAMES.get(phase, f"Phase {phase}")
        return REGENERATION_CONVERSATION_CONTEXT.format(
            phase_name=phase_name,
            current_summary=current_summary,
            initial_feedback=initial_feedback
        )

    @staticmethod
    def get_regeneration_summary_prompt() -> str:
        """
        Get the prompt for generating final summary after regeneration conversation.

        Returns:
            Prompt string for final summary generation
        """
        return REGENERATION_FINAL_SUMMARY_PROMPT

    @staticmethod
    def get_knowledge_extraction_prompt(
        phase: int,
        existing_knowledge: str = "",
        staged_this_session: str = ""
    ) -> str:
        """
        Get the knowledge extraction prompt for a phase.

        Args:
            phase: Phase number (1-4)
            existing_knowledge: Current project knowledge to avoid duplicates
            staged_this_session: Already staged knowledge from this session to avoid duplicates

        Returns:
            Extraction prompt instructing Claude to output in exact format:
            ARCHITECTURE:, DECISIONS:, LESSONS_LEARNED: sections with entries,
            or NO_KNOWLEDGE_EXTRACTED if nothing notable.
        """
        # Format the extraction prompt with existing knowledge
        existing = existing_knowledge if existing_knowledge else "(No existing project knowledge)"
        staged = staged_this_session if staged_this_session else "None yet"
        return KNOWLEDGE_EXTRACTION_PROMPT.format(
            existing_knowledge=existing,
            staged_this_session=staged
        )
