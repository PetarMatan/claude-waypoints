#!/usr/bin/env python3
"""
Claude Waypoints - Agent Discovery Library

Discovers and loads agents based on Waypoints phase configuration.
Wraps agent_parser.py for easy use.
"""

import os
from pathlib import Path
from typing import List, Optional

# Absolute import for subprocess compatibility
import agent_parser


class AgentLoader:
    """Loads and manages phase-bound agents."""

    def __init__(self, agents_dir: Optional[str] = None):
        """Initialize agent loader."""
        if agents_dir:
            self.agents_dir = agents_dir
        else:
            install_dir = os.environ.get(
                "WP_INSTALL_DIR",
                str(Path.home() / ".claude" / "waypoints")
            )
            self.agents_dir = os.path.join(install_dir, "agents")

    def get_agents_for_phase(self, phase: int) -> List[str]:
        """Get list of agent file paths configured for a specific phase."""
        if not os.path.isdir(self.agents_dir):
            return []

        return agent_parser.get_agents_for_phase(self.agents_dir, phase)

    def get_agent_name(self, agent_file: str) -> str:
        """Get agent name from frontmatter or filename."""
        return agent_parser.get_agent_name(agent_file)

    def get_agent_content(self, agent_file: str) -> Optional[str]:
        """Get agent content (markdown without frontmatter)."""
        return agent_parser.get_agent_content(agent_file)

    def get_new_agents_for_phase(self, phase: int) -> List[str]:
        """
        Get agents that are NEW in this phase (not in any previous phase).

        Used by CLI mode where context persists - agents loaded in earlier
        phases don't need to be loaded again.

        Args:
            phase: The Waypoints phase number (1-4)

        Returns:
            List of agent file paths that are new in this phase
        """
        current_agents = set(self.get_agents_for_phase(phase))
        if not current_agents:
            return []

        # Get agents from all previous phases
        previous_agents = set()
        for prev_phase in range(1, phase):
            previous_agents.update(self.get_agents_for_phase(prev_phase))

        # Return only agents that weren't in previous phases
        new_agents = current_agents - previous_agents
        return list(new_agents)

    def load_phase_agents(self, phase: int, logger=None, skip_already_loaded: bool = False) -> str:
        """
        Load agents configured for a phase and return combined content.

        Args:
            phase: The Waypoints phase number (1-4)
            logger: Optional WPLogger for logging agent loads
            skip_already_loaded: If True, only load agents new to this phase
                                (for CLI mode where context persists)

        Returns:
            Combined agent content string for injection into context
        """
        if skip_already_loaded:
            agent_files = self.get_new_agents_for_phase(phase)
        else:
            agent_files = self.get_agents_for_phase(phase)

        if not agent_files:
            return ""

        agent_content = ""
        for agent_file in agent_files:
            agent_name = self.get_agent_name(agent_file)
            if logger:
                logger.log_wp(f"Loading agent '{agent_name}' for phase {phase}")
            print(f">>> Waypoints: Loaded agent: {agent_name}", file=__import__('sys').stderr)

            content = self.get_agent_content(agent_file)
            if content:
                agent_content += f"\n\n---\n\n## Agent: {agent_name}\n\n{content}"

        return agent_content

    def list_agents(self) -> str:
        """List all agents with their phase bindings (JSON)."""
        if not os.path.isdir(self.agents_dir):
            return "[]"
        return agent_parser.list_agents(self.agents_dir)
