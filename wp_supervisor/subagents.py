#!/usr/bin/env python3
"""
Waypoints Supervisor - Subagent Definitions

Defines specialized subagents for:
- Phase 1: Parallel codebase exploration
- Phase 4: Implementation subagents (Claude-orchestrated via Task tool)

Uses SDK's AgentDefinition with the `agents` parameter in ClaudeAgentOptions.
"""

from dataclasses import dataclass
from typing import Dict, Optional

from .templates import (
    BUSINESS_LOGIC_INSTRUCTIONS,
    DEPENDENCIES_INSTRUCTIONS,
    TEST_USECASE_INSTRUCTIONS,
    ARCHITECTURE_INSTRUCTIONS,
    TECH_CAPABILITY_INSTRUCTIONS,
    IMPLEMENTATION_SUBAGENT_INSTRUCTIONS,
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
ARCHITECTURE_EXPLORER = "architecture-explorer"
TECH_CAPABILITY_EXPLORER = "tech-capability-explorer"

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

ARCHITECTURE_DESCRIPTION = (
    "Maps system architecture, end-to-end flows, integration points, and framework behavior. "
    "Use for understanding how data/events flow through the system and where to hook in new code."
)

TECH_CAPABILITY_DESCRIPTION = (
    "Maps capabilities of load-bearing runtimes, SDKs, and frameworks — especially "
    "primitives the codebase is NOT yet using. Use for surfacing built-in platform "
    "capabilities before the design reinvents them."
)


# =============================================================================
# SUBAGENT BUILDER
# =============================================================================

class SubagentBuilder:
    """Builds AgentDefinition instances for Phase 1 exploration and Phase 4 implementation."""

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
        """Build all four exploration subagents with injected context."""
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
            ARCHITECTURE_EXPLORER: SubagentBuilder.build_architecture_agent(
                knowledge_context=knowledge_context
            ),
            TECH_CAPABILITY_EXPLORER: SubagentBuilder.build_tech_capability_agent(
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
            tools=EXPLORATION_TOOLS,
            model="sonnet"
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
            tools=EXPLORATION_TOOLS,
            model="sonnet"
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
            tools=EXPLORATION_TOOLS,
            model="sonnet"
        )

    @staticmethod
    def build_architecture_agent(
        knowledge_context: str = ""
    ) -> AgentDefinition:
        """Build the Architecture & Flow Explorer subagent."""
        prompt = ARCHITECTURE_INSTRUCTIONS.format(
            knowledge_context=SubagentBuilder._format_knowledge_section(knowledge_context)
        )

        return AgentDefinition(
            description=ARCHITECTURE_DESCRIPTION,
            prompt=prompt,
            tools=EXPLORATION_TOOLS,
            model="sonnet"
        )

    @staticmethod
    def build_tech_capability_agent(
        knowledge_context: str = ""
    ) -> AgentDefinition:
        """Build the Tech Capability Explorer subagent."""
        prompt = TECH_CAPABILITY_INSTRUCTIONS.format(
            knowledge_context=SubagentBuilder._format_knowledge_section(knowledge_context)
        )

        return AgentDefinition(
            description=TECH_CAPABILITY_DESCRIPTION,
            prompt=prompt,
            tools=EXPLORATION_TOOLS,
            model="sonnet"
        )

    @staticmethod
    def build_implementation_agents(
        knowledge_context: str = "",
        requirements_summary: str = ""
    ) -> Dict[str, AgentDefinition]:
        """Build implementation subagents for Phase 4 Claude-orchestrated delegation."""
        agents: Dict[str, AgentDefinition] = {}

        for i in range(1, MAX_IMPLEMENTATION_SUBAGENTS + 1):
            name = f"implementer-{i}"
            prompt = IMPLEMENTATION_SUBAGENT_INSTRUCTIONS.format(
                knowledge_context=SubagentBuilder._format_knowledge_section(knowledge_context),
                requirements_summary=requirements_summary or "(Will be provided by parent session)"
            )
            agents[name] = AgentDefinition(
                description=IMPLEMENTATION_SUBAGENT_DESCRIPTION,
                prompt=prompt,
                tools=IMPLEMENTATION_TOOLS,
                model="sonnet"
            )

        return agents


# =============================================================================
# PHASE 4 IMPLEMENTATION SUBAGENTS
# =============================================================================

# Implementation tools for subagents - includes write capabilities
IMPLEMENTATION_TOOLS = ["Read", "Grep", "Glob", "Bash", "Write", "Edit"]

MAX_IMPLEMENTATION_SUBAGENTS = 4

IMPLEMENTATION_SUBAGENT_DESCRIPTION = (
    "Implements a specific scope of work assigned by the parent session. "
    "Has write access to implement business logic and run tests."
)
