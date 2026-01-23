#!/usr/bin/env python3
"""
Waypoints Activation Hook - PreToolUse Hook

Intercepts wp: marker commands and handles state management.
This ensures state.json is created in the correct session-specific directory.

The hook has access to session_id (from Claude Code via stdin JSON), which
skills/prompts don't have. This solves the session-specific state problem.

Commands intercepted (as comments in bash commands):
  true # wp:init              - Initialize workflow
  true # wp:status            - Get status
  true # wp:reset             - Reset workflow state
  true # wp:reset --full      - Full reset including session
  true # wp:mark-complete requirements  - Mark requirements done
  true # wp:mark-complete interfaces    - Mark interfaces done
  true # wp:mark-complete tests         - Mark tests done
  true # wp:mark-complete implementation - Mark implementation done
  true # wp:set-phase N       - Set phase to N

Note: Knowledge staging (wp:stage) has been removed from CLI mode [DEC-1].
Knowledge extraction is now supervisor-exclusive.
"""

import os
import sys
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

from hook_io import HookInput, approve_with_message
from markers import MarkerManager
from wp_logging import WPLogger
from wp_agents import AgentLoader
from wp_knowledge import KnowledgeManager


def respond(message: str, additional: str = ""):
    """Provide feedback to Claude via approve with additional context."""
    full_message = message + additional if additional else message
    approve_with_message("Waypoints", "PreToolUse", full_message)


def format_knowledge_summary(summary: dict) -> str:
    """Format knowledge update summary for display."""
    if not summary:
        return ""

    parts = []
    for category, count in summary.items():
        entry_word = "entry" if count == 1 else "entries"
        parts.append(f"   {category}.md (+{count} {entry_word})")

    return "\n\n📚 Knowledge updated:\n" + "\n".join(parts)


def main():
    hook = HookInput.from_stdin()

    # Only handle Bash tool
    if hook.tool_name != "Bash":
        return

    # Get command from tool input
    tool_input = hook.raw_data.get('tool_input', {})
    if isinstance(tool_input, dict):
        command = tool_input.get('command', '')
    else:
        command = str(tool_input) if tool_input else ''

    if not command:
        return

    # Check for wp: marker commands (e.g., "true # wp:init")
    if 'wp:' not in command:
        return

    markers = MarkerManager(hook.session_id)
    logger = WPLogger(hook.session_id)
    agents = AgentLoader()

    # Handle: wp:init
    if 'wp:init' in command:
        knowledge = KnowledgeManager(hook.cwd)
        knowledge_context = knowledge.load_knowledge_context()
        knowledge_section = f"\n\n## Project Knowledge\n\n{knowledge_context}" if knowledge_context else ""

        if not markers.is_wp_active():
            markers._state.initialize()
            logger.log_wp(f"Activation hook: Initialized WP state for session {hook.session_id}")
            phase_agents = agents.load_phase_agents(1, logger, skip_already_loaded=True)
            respond("Waypoints workflow initialized. You are now in Phase 1: Requirements Gathering.", phase_agents + knowledge_section)
        else:
            current_phase = markers.get_phase()
            phase_agents = agents.load_phase_agents(current_phase, logger, skip_already_loaded=True)
            respond(f"Waypoints workflow already active (Phase {current_phase}).", phase_agents + knowledge_section)
        return

    # Handle: wp:mark-complete <phase>
    # skip_already_loaded=True: CLI mode has persistent context, skip agents from previous phases
    if 'wp:mark-complete' in command:
        if 'requirements' in command:
            markers.mark_requirements_complete()
            markers.set_phase(2)
            logger.log_wp("Activation hook: Marked requirements complete, advancing to phase 2")
            phase_agents = agents.load_phase_agents(2, logger, skip_already_loaded=True)
            respond("Requirements phase marked complete. Advancing to Phase 2: Interface Design.", phase_agents)
        elif 'interfaces' in command:
            markers.mark_interfaces_complete()
            markers.set_phase(3)
            logger.log_wp("Activation hook: Marked interfaces complete, advancing to phase 3")
            phase_agents = agents.load_phase_agents(3, logger, skip_already_loaded=True)
            respond("Interfaces phase marked complete. Advancing to Phase 3: Test Writing.", phase_agents)
        elif 'tests' in command:
            markers.mark_tests_complete()
            markers.set_phase(4)
            logger.log_wp("Activation hook: Marked tests complete, advancing to phase 4")
            phase_agents = agents.load_phase_agents(4, logger, skip_already_loaded=True)
            respond("Tests phase marked complete. Advancing to Phase 4: Implementation.", phase_agents)
        elif 'implementation' in command:
            markers.mark_implementation_complete()
            logger.log_wp("Activation hook: Marked implementation complete")

            # Apply staged learnings and cleanup
            knowledge = KnowledgeManager(hook.session_id, hook.cwd)
            summary = knowledge.apply_staged_learnings()
            knowledge.cleanup_staging()
            summary_msg = format_knowledge_summary(summary)

            respond("Implementation complete. Waypoints workflow finished!" + summary_msg)
        return

    # Handle: wp:set-phase <n>
    if 'wp:set-phase' in command:
        match = re.search(r'wp:set-phase\s+(\d+)', command)
        if match:
            phase = int(match.group(1))
            markers.set_phase(phase)
            logger.log_wp(f"Activation hook: Set phase to {phase}")
            respond(f"Phase set to {phase}.")
        return

    # Handle: wp:reset
    if 'wp:reset' in command:
        if '--full' in command:
            markers.cleanup_session()
            logger.log_wp("Activation hook: Full reset")
            respond("Waypoints workflow fully reset. Run /wp-start to begin again.")
        else:
            markers.cleanup_workflow_state()
            logger.log_wp("Activation hook: Workflow state reset")
            respond("Waypoints workflow state reset.")
        return

    # Handle: wp:status
    if 'wp:status' in command:
        phase = markers.get_phase()
        active = markers.is_wp_active()
        status_msg = f"Waypoints Status: {'Active' if active else 'Inactive'}, Phase: {phase}"
        if active:
            phase_agents = agents.load_phase_agents(phase, logger, skip_already_loaded=True)
            respond(status_msg, phase_agents)
        else:
            respond(status_msg)
        return

    # Note: wp:stage command has been removed [REQ-26, DEC-1]
    # Knowledge extraction is now supervisor-exclusive


if __name__ == '__main__':
    main()
