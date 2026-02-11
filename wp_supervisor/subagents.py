#!/usr/bin/env python3
"""
Waypoints Supervisor - Subagent Definitions

Defines specialized exploration subagents for Phase 1 parallel codebase exploration.
Uses SDK's AgentDefinition with the `agents` parameter in ClaudeAgentOptions.

Three subagents for concurrent exploration:
  - Business Logic Explorer
  - Dependencies/Integrations Explorer
  - Test/Use Case Explorer

Subagent instructions are hybrid: static base + dynamic task context
        Static part: AgentDefinition.prompt (instructions + knowledge)
        Dynamic part: provided by parent session when invoking via Task tool
Each subagent has clear instructions about its specific exploration concern
Subagents receive full project knowledge context
"""

from dataclasses import dataclass
from typing import Dict, Optional

try:
    from claude_agent_sdk import AgentDefinition
except ImportError:
    # For type-checking when SDK not installed
    @dataclass
    class AgentDefinition:  # type: ignore[no-redef]
        description: str
        prompt: str
        tools: Optional[list] = None
        model: Optional[str] = None


# =============================================================================
# SUBAGENT NAMES
# =============================================================================

BUSINESS_LOGIC_EXPLORER = "business-logic-explorer"
DEPENDENCIES_EXPLORER = "dependencies-explorer"
TEST_USECASE_EXPLORER = "test-usecase-explorer"

# Read-only tools for exploration subagents.
# Subagents must NOT write files during Phase 1 — phase guards on the parent
# session may not propagate to subagents, so we enforce read-only access here.
EXPLORATION_TOOLS = ["Read", "Grep", "Glob", "Bash"]


# =============================================================================
# SUBAGENT BASE INSTRUCTIONS
# =============================================================================

BUSINESS_LOGIC_INSTRUCTIONS = """# Business Logic Explorer

## Your Role
You are a specialized codebase explorer focused on understanding implementation patterns,
existing services, domain logic, and code structure.

## What to Explore
1. **Service/Component Structure**: How is the codebase organized? What are the main services/modules?
2. **Implementation Patterns**: What patterns are used (repositories, services, handlers, etc.)?
3. **Domain Logic**: What are the core business entities and their relationships?
4. **Code Conventions**: Naming conventions, file organization, coding style

## What to Report
Provide a concise summary of:
- Key services/components and their responsibilities
- Common patterns used in the codebase
- Relevant domain entities that might be involved
- Existing code that could be reused or extended

## Guidelines
- Focus on areas relevant to the user's requirements
- Be thorough but concise
- Note any patterns that should be followed
- Identify potential reuse opportunities

{knowledge_context}

## User Requirements Context
{task_context}
"""

DEPENDENCIES_INSTRUCTIONS = """# Dependencies & Integrations Explorer

## Your Role
You are a specialized codebase explorer focused on mapping external dependencies,
API integrations, configuration files, and external service connections.

## What to Explore
1. **External Dependencies**: What libraries/frameworks are used? (check pom.xml, package.json, requirements.txt, etc.)
2. **API Integrations**: What external APIs or services does the code connect to?
3. **Configuration**: How is the application configured? (application.yml, .env, config files)
4. **Infrastructure**: Database connections, message queues, cache systems

## What to Report
Provide a concise summary of:
- Key dependencies and their versions
- External service integrations and how they're accessed
- Configuration patterns and environment variables
- Any relevant infrastructure components

## Guidelines
- Focus on dependencies relevant to the user's requirements
- Note version constraints or compatibility concerns
- Identify configuration that might need changes
- Document integration patterns

{knowledge_context}

## User Requirements Context
{task_context}
"""

TEST_USECASE_INSTRUCTIONS = """# Test & Use Case Explorer

## Your Role
You are a specialized codebase explorer focused on analyzing existing tests to understand
expected behaviors, use cases, and testing patterns.

## What to Explore
1. **Test Structure**: How are tests organized? What testing frameworks are used?
2. **Test Patterns**: What patterns are used for mocking, fixtures, assertions?
3. **Use Cases**: What behaviors do existing tests verify? What edge cases are covered?
4. **Test Configuration**: How are tests configured and run?

## What to Report
Provide a concise summary of:
- Testing frameworks and patterns in use
- Relevant existing tests that demonstrate similar functionality
- Testing conventions that should be followed
- Common test utilities or helpers available

## Guidelines
- Focus on tests relevant to the user's requirements
- Note testing patterns that should be followed
- Identify test utilities that could be reused
- Document any testing constraints or requirements

{knowledge_context}

## User Requirements Context
{task_context}
"""


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
    """
    Builds subagent definitions for Phase 1 parallel exploration.

    Creates AgentDefinition instances with:
    - Static base instructions per exploration concern
    - Project knowledge context
    - Read-only tool access (Read, Grep, Glob, Bash)

    Dynamic task context (user requirements) is provided by the parent session
    when it invokes subagents via Task tool after gathering requirements.
    """

    @staticmethod
    def build_exploration_agents(
        task_context: str,
        knowledge_context: str = ""
    ) -> Dict[str, AgentDefinition]:
        """
        Build all three exploration subagents with injected context.

        Args:
            task_context: User's requirements/task description to inject
            knowledge_context: Project knowledge (architecture.md, decisions.md,
                             lessons-learned.md) to inject

        Returns:
            Dictionary mapping subagent names to AgentDefinition instances,
            ready to be passed to ClaudeAgentOptions.agents

        Note:
            Subagents have read-only tool access to prevent file writes
            during Phase 1 exploration. Phase guards may not propagate to subagents.
        """
        return {
            BUSINESS_LOGIC_EXPLORER: SubagentBuilder.build_business_logic_agent(
                task_context=task_context,
                knowledge_context=knowledge_context
            ),
            DEPENDENCIES_EXPLORER: SubagentBuilder.build_dependencies_agent(
                task_context=task_context,
                knowledge_context=knowledge_context
            ),
            TEST_USECASE_EXPLORER: SubagentBuilder.build_test_usecase_agent(
                task_context=task_context,
                knowledge_context=knowledge_context
            ),
        }

    @staticmethod
    def build_business_logic_agent(
        task_context: str,
        knowledge_context: str = ""
    ) -> AgentDefinition:
        """
        Build the Business Logic Explorer subagent.

        Investigates implementation patterns, existing services,
        domain logic, and code structure.

        Args:
            task_context: User's requirements to focus exploration
            knowledge_context: Project knowledge to include

        Returns:
            AgentDefinition for business logic exploration
        """
        # Build knowledge section
        knowledge_section = ""
        if knowledge_context:
            knowledge_section = f"## Project Knowledge\n{knowledge_context}"

        # Inject placeholders
        prompt = BUSINESS_LOGIC_INSTRUCTIONS.format(
            task_context=task_context,
            knowledge_context=knowledge_section
        )

        return AgentDefinition(
            description=BUSINESS_LOGIC_DESCRIPTION,
            prompt=prompt,
            tools=EXPLORATION_TOOLS
        )

    @staticmethod
    def build_dependencies_agent(
        task_context: str,
        knowledge_context: str = ""
    ) -> AgentDefinition:
        """
        Build the Dependencies/Integrations Explorer subagent.

        Maps external dependencies, API integrations, configuration files,
        and external service connections.

        Args:
            task_context: User's requirements to focus exploration
            knowledge_context: Project knowledge to include

        Returns:
            AgentDefinition for dependencies exploration
        """
        # Build knowledge section
        knowledge_section = ""
        if knowledge_context:
            knowledge_section = f"## Project Knowledge\n{knowledge_context}"

        # Inject placeholders
        prompt = DEPENDENCIES_INSTRUCTIONS.format(
            task_context=task_context,
            knowledge_context=knowledge_section
        )

        return AgentDefinition(
            description=DEPENDENCIES_DESCRIPTION,
            prompt=prompt,
            tools=EXPLORATION_TOOLS
        )

    @staticmethod
    def build_test_usecase_agent(
        task_context: str,
        knowledge_context: str = ""
    ) -> AgentDefinition:
        """
        Build the Test/Use Case Explorer subagent.

        Analyzes existing tests to understand expected behaviors,
        use cases, and testing patterns.

        Args:
            task_context: User's requirements to focus exploration
            knowledge_context: Project knowledge to include

        Returns:
            AgentDefinition for test/use case exploration
        """
        # Build knowledge section
        knowledge_section = ""
        if knowledge_context:
            knowledge_section = f"## Project Knowledge\n{knowledge_context}"

        # Inject placeholders
        prompt = TEST_USECASE_INSTRUCTIONS.format(
            task_context=task_context,
            knowledge_context=knowledge_section
        )

        return AgentDefinition(
            description=TEST_USECASE_DESCRIPTION,
            prompt=prompt,
            tools=EXPLORATION_TOOLS
        )


# =============================================================================
# PARENT SESSION INSTRUCTIONS
# =============================================================================

PHASE1_SUPERVISOR_INSTRUCTIONS = """# Phase 1: Requirements Gathering (Supervisor Mode)

You are in Phase 1 of the Waypoints workflow in supervisor mode with parallel exploration enabled.

## Your Role
You delegate the bulk of codebase exploration to specialized subagents. Your workflow:
1. Gather requirements from the user
2. Spawn exploration subagents to investigate the codebase in parallel
3. Synthesize their findings
4. If you identify gaps in the subagent results, do targeted follow-up exploration yourself
5. Ask clarifying questions based on the exploration results
6. Complete requirements gathering

## Workflow

### Step 1: Gather Initial Requirements
Ask the user to describe what they want to build. Get enough context to guide exploration.

### Step 2: Spawn Exploration Subagents
Once you have initial requirements, use the Task tool to spawn these exploration agents.
IMPORTANT: Pass the gathered requirements to each subagent so they know what to focus on.

- **business-logic-explorer**: Investigates implementation patterns, services, domain logic
- **dependencies-explorer**: Maps external dependencies, APIs, configuration
- **test-usecase-explorer**: Analyzes existing tests for behaviors and patterns

IMPORTANT: Spawn all three agents in a SINGLE message with THREE Task tool calls to enable parallel execution. Include the user's requirements in each task prompt.

Example:
```
I'll now explore the codebase in parallel to understand the existing patterns and structure.

[Task tool: business-logic-explorer — include full gathered requirements]
[Task tool: dependencies-explorer — include full gathered requirements]
[Task tool: test-usecase-explorer — include full gathered requirements]
```

### Step 3: Synthesize, Fill Gaps, and Clarify
Once exploration results return:
1. Synthesize findings relevant to the user's requirements
2. Identify any gaps the subagents may have missed (e.g., error handling patterns,
   security concerns, cross-cutting concerns, logging/observability)
3. Do targeted follow-up exploration yourself for any identified gaps
4. Ask clarifying questions about business requirements
5. Gather any missing details

### Step 4: Complete Requirements
When requirements are complete and unambiguous, output `---PHASE_COMPLETE---`

## Important
- Delegate bulk exploration to subagents — do NOT replicate their work
- You MAY do targeted follow-up exploration for gaps the subagents missed
- Do NOT write any code in this phase
- Focus on WHAT needs to be built (behavior), not HOW to build it
- The subagents handle broad technical discovery; you handle business requirements and fill gaps
"""


