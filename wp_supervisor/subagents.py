#!/usr/bin/env python3
"""
Waypoints Supervisor - Subagent Definitions

Defines specialized exploration subagents for Phase 1 parallel codebase exploration.
Uses SDK's AgentDefinition with the `agents` parameter in ClaudeAgentOptions.
"""

from dataclasses import dataclass
from typing import Dict, Optional

from .templates import (
    BUSINESS_LOGIC_INSTRUCTIONS,
    DEPENDENCIES_INSTRUCTIONS,
    TEST_USECASE_INSTRUCTIONS,
)

try:
    from claude_agent_sdk import AgentDefinition
except ImportError:
    @dataclass
    class AgentDefinition:  # type: ignore[no-redef]
        description: str
        prompt: str
        tools: Optional[list] = None
        model: Optional[str] = None


# Subagent names
BUSINESS_LOGIC_EXPLORER = "business-logic-explorer"
DEPENDENCIES_EXPLORER = "dependencies-explorer"
TEST_USECASE_EXPLORER = "test-usecase-explorer"

# Exploration tools for subagents. Bash is included for commands like
# git log or directory listing; write prevention is instruction-based, not tool-enforced.
EXPLORATION_TOOLS = ["Read", "Grep", "Glob", "Bash"]


# =============================================================================
# SUBAGENT DESCRIPTIONS (for Claude's tool selection)
# =============================================================================

BUSINESS_LOGIC_DESCRIPTION = (
    "Explores implementation patterns, services, domain logic, and code structure. "
    "Use for understanding how existing code is organized and what patterns to follow."
)

DEPENDENCIES_DESCRIPTION = (
    "Maps external dependencies, API integrations, configuration, and infrastructure. "
    "Use for understanding what libraries and services the codebase uses."
)

TEST_USECASE_DESCRIPTION = (
    "Analyzes existing tests to understand behaviors, use cases, and testing patterns. "
    "Use for understanding how similar functionality is tested."
)


# =============================================================================
# SUBAGENT BUILDER
# =============================================================================

class SubagentBuilder:
    """Builds AgentDefinition instances for Phase 1 parallel exploration."""

    @staticmethod
    def _format_knowledge_section(knowledge_context: str) -> str:
        """Format knowledge context into a prompt section."""
        if knowledge_context:
            return f"## Project Knowledge\n{knowledge_context}"
        return ""

    @staticmethod
    def build_exploration_agents(
        knowledge_context: str = ""
    ) -> Dict[str, AgentDefinition]:
        """Build all three exploration subagents with injected context."""
        return {
            BUSINESS_LOGIC_EXPLORER: SubagentBuilder.build_business_logic_agent(
                knowledge_context=knowledge_context
            ),
            DEPENDENCIES_EXPLORER: SubagentBuilder.build_dependencies_agent(
                knowledge_context=knowledge_context
            ),
            TEST_USECASE_EXPLORER: SubagentBuilder.build_test_usecase_agent(
                knowledge_context=knowledge_context
            ),
        }

    @staticmethod
    def build_business_logic_agent(
        knowledge_context: str = ""
    ) -> AgentDefinition:
        """Build the Business Logic Explorer subagent."""
        prompt = BUSINESS_LOGIC_INSTRUCTIONS.format(
            knowledge_context=SubagentBuilder._format_knowledge_section(knowledge_context)
        )

        return AgentDefinition(
            description=BUSINESS_LOGIC_DESCRIPTION,
            prompt=prompt,
            tools=EXPLORATION_TOOLS
        )

    @staticmethod
    def build_dependencies_agent(
        knowledge_context: str = ""
    ) -> AgentDefinition:
        """Build the Dependencies/Integrations Explorer subagent."""
        prompt = DEPENDENCIES_INSTRUCTIONS.format(
            knowledge_context=SubagentBuilder._format_knowledge_section(knowledge_context)
        )

        return AgentDefinition(
            description=DEPENDENCIES_DESCRIPTION,
            prompt=prompt,
            tools=EXPLORATION_TOOLS
        )

    @staticmethod
    def build_test_usecase_agent(
        knowledge_context: str = ""
    ) -> AgentDefinition:
        """Build the Test/Use Case Explorer subagent."""
        prompt = TEST_USECASE_INSTRUCTIONS.format(
            knowledge_context=SubagentBuilder._format_knowledge_section(knowledge_context)
        )

        return AgentDefinition(
            description=TEST_USECASE_DESCRIPTION,
            prompt=prompt,
            tools=EXPLORATION_TOOLS
        )
