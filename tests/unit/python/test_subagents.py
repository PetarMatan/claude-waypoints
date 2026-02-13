#!/usr/bin/env python3
"""
Unit tests for wp_supervisor/subagents.py - Subagent definitions and builder

Tests cover:
- [REQ-1] Three specialized subagents for Phase 1 parallel exploration
- [REQ-2] Subagents built as AgentDefinition for SDK's agents parameter
- [REQ-3] Subagents have full tool access (not restricted)
- [REQ-7] Subagent instructions are hybrid: static base + dynamic knowledge context
- [REQ-8] Each subagent has clear instructions about its specific concern
- [REQ-9] Subagents receive full project knowledge context
- [REQ-10] Parent session context instructs delegation to subagents
"""

import sys
import pytest

# Mock claude_agent_sdk before importing subagents
from dataclasses import dataclass
from typing import Optional, List
from unittest.mock import MagicMock

@dataclass
class MockAgentDefinition:
    """Mock AgentDefinition for testing."""
    description: str
    prompt: str
    tools: Optional[list] = None
    model: Optional[str] = None

mock_sdk = MagicMock()
mock_sdk.AgentDefinition = MockAgentDefinition
sys.modules['claude_agent_sdk'] = mock_sdk

# Add wp_supervisor to path
sys.path.insert(0, '.')
from wp_supervisor.subagents import (
    SubagentBuilder,
    BUSINESS_LOGIC_EXPLORER,
    DEPENDENCIES_EXPLORER,
    TEST_USECASE_EXPLORER,
    BUSINESS_LOGIC_DESCRIPTION,
    DEPENDENCIES_DESCRIPTION,
    TEST_USECASE_DESCRIPTION,
    EXPLORATION_TOOLS,
)
from wp_supervisor.templates import (
    BUSINESS_LOGIC_INSTRUCTIONS,
    DEPENDENCIES_INSTRUCTIONS,
    TEST_USECASE_INSTRUCTIONS,
    PHASE1_SUPERVISOR_INSTRUCTIONS,
)


class TestSubagentNames:
    """Tests for subagent name constants."""

    def test_business_logic_explorer_name_defined(self):
        """Business logic explorer name constant should be defined."""
        assert BUSINESS_LOGIC_EXPLORER == "business-logic-explorer"

    def test_dependencies_explorer_name_defined(self):
        """Dependencies explorer name constant should be defined."""
        assert DEPENDENCIES_EXPLORER == "dependencies-explorer"

    def test_test_usecase_explorer_name_defined(self):
        """Test/use case explorer name constant should be defined."""
        assert TEST_USECASE_EXPLORER == "test-usecase-explorer"

    def test_all_three_subagent_names_unique(self):
        """All three subagent names should be unique."""
        names = [BUSINESS_LOGIC_EXPLORER, DEPENDENCIES_EXPLORER, TEST_USECASE_EXPLORER]
        assert len(names) == len(set(names))


class TestSubagentInstructions:
    """Tests for subagent instruction templates."""

    def test_business_logic_instructions_defined(self):
        """Business logic instructions should be defined."""
        assert len(BUSINESS_LOGIC_INSTRUCTIONS) > 0

    def test_dependencies_instructions_defined(self):
        """Dependencies instructions should be defined."""
        assert len(DEPENDENCIES_INSTRUCTIONS) > 0

    def test_test_usecase_instructions_defined(self):
        """Test/use case instructions should be defined."""
        assert len(TEST_USECASE_INSTRUCTIONS) > 0

    def test_business_logic_instructions_has_knowledge_placeholder(self):
        """Business logic instructions should have knowledge context placeholder."""
        assert "{knowledge_context}" in BUSINESS_LOGIC_INSTRUCTIONS

    def test_dependencies_instructions_has_knowledge_placeholder(self):
        """Dependencies instructions should have knowledge context placeholder."""
        assert "{knowledge_context}" in DEPENDENCIES_INSTRUCTIONS

    def test_test_usecase_instructions_has_knowledge_placeholder(self):
        """Test/use case instructions should have knowledge context placeholder."""
        assert "{knowledge_context}" in TEST_USECASE_INSTRUCTIONS

    def test_business_logic_instructions_describes_role(self):
        """Business logic instructions should describe the explorer's role."""
        assert "implementation pattern" in BUSINESS_LOGIC_INSTRUCTIONS.lower()
        assert "domain logic" in BUSINESS_LOGIC_INSTRUCTIONS.lower()

    def test_dependencies_instructions_describes_role(self):
        """Dependencies instructions should describe the explorer's role."""
        assert "external" in DEPENDENCIES_INSTRUCTIONS.lower() or "dependencies" in DEPENDENCIES_INSTRUCTIONS.lower()
        assert "configuration" in DEPENDENCIES_INSTRUCTIONS.lower() or "api" in DEPENDENCIES_INSTRUCTIONS.lower()

    def test_test_usecase_instructions_describes_role(self):
        """Test/use case instructions should describe the explorer's role."""
        assert "test" in TEST_USECASE_INSTRUCTIONS.lower()
        assert "pattern" in TEST_USECASE_INSTRUCTIONS.lower() or "behavior" in TEST_USECASE_INSTRUCTIONS.lower()


class TestSubagentDescriptions:
    """Tests for subagent descriptions (used by Claude for tool selection)."""

    def test_business_logic_description_defined(self):
        """Business logic description should be defined."""
        assert len(BUSINESS_LOGIC_DESCRIPTION) > 0

    def test_dependencies_description_defined(self):
        """Dependencies description should be defined."""
        assert len(DEPENDENCIES_DESCRIPTION) > 0

    def test_test_usecase_description_defined(self):
        """Test/use case description should be defined."""
        assert len(TEST_USECASE_DESCRIPTION) > 0

    def test_business_logic_description_mentions_patterns(self):
        """Business logic description should mention patterns or implementation."""
        desc = BUSINESS_LOGIC_DESCRIPTION.lower()
        assert "pattern" in desc or "implementation" in desc or "logic" in desc

    def test_dependencies_description_mentions_dependencies(self):
        """Dependencies description should mention dependencies or integrations."""
        desc = DEPENDENCIES_DESCRIPTION.lower()
        assert "dependencies" in desc or "integration" in desc

    def test_test_usecase_description_mentions_tests(self):
        """Test/use case description should mention tests or use cases."""
        desc = TEST_USECASE_DESCRIPTION.lower()
        assert "test" in desc


class TestSubagentBuilderBuildExplorationAgents:
    """Tests for SubagentBuilder.build_exploration_agents method."""

    def test_build_exploration_agents_returns_four_agents(self):
        """Should return exactly four exploration agents."""
        # when
        agents = SubagentBuilder.build_exploration_agents(
            knowledge_context="# Architecture\nService-based"
        )

        # then
        assert len(agents) == 4

    def test_build_exploration_agents_returns_dict(self):
        """Should return a dictionary mapping names to AgentDefinition."""
        # when
        agents = SubagentBuilder.build_exploration_agents()

        # then
        assert isinstance(agents, dict)

    def test_build_exploration_agents_contains_business_logic_key(self):
        """Should contain business-logic-explorer key."""
        # when
        agents = SubagentBuilder.build_exploration_agents()

        # then
        assert BUSINESS_LOGIC_EXPLORER in agents

    def test_build_exploration_agents_contains_dependencies_key(self):
        """Should contain dependencies-explorer key."""
        # when
        agents = SubagentBuilder.build_exploration_agents()

        # then
        assert DEPENDENCIES_EXPLORER in agents

    def test_build_exploration_agents_contains_test_usecase_key(self):
        """Should contain test-usecase-explorer key."""
        # when
        agents = SubagentBuilder.build_exploration_agents()

        # then
        assert TEST_USECASE_EXPLORER in agents

    def test_build_exploration_agents_injects_knowledge_context(self):
        """Should inject knowledge context into all agent prompts."""
        # given
        knowledge = "# Architecture\nMicroservices pattern with Kafka"

        # when
        agents = SubagentBuilder.build_exploration_agents(
            knowledge_context=knowledge
        )

        # then
        for name, agent in agents.items():
            assert knowledge in agent.prompt, f"{name} should have knowledge context in prompt"

    def test_build_exploration_agents_with_empty_knowledge_context(self):
        """Should work with empty knowledge context."""
        # when
        agents = SubagentBuilder.build_exploration_agents(
            knowledge_context=""
        )

        # then
        assert len(agents) == 4
        # Should not have the literal placeholder in prompts
        for agent in agents.values():
            assert "{knowledge_context}" not in agent.prompt

    def test_build_exploration_agents_read_only_tools(self):
        """Subagents should have read-only tool access to prevent file writes."""
        # when
        agents = SubagentBuilder.build_exploration_agents()

        # then
        for name, agent in agents.items():
            assert agent.tools == EXPLORATION_TOOLS, f"{name} should have read-only tools"
            assert "Write" not in agent.tools, f"{name} should not have Write tool"
            assert "Edit" not in agent.tools, f"{name} should not have Edit tool"

    def test_build_exploration_agents_have_descriptions(self):
        """All agents should have descriptions for Claude's tool selection."""
        # when
        agents = SubagentBuilder.build_exploration_agents()

        # then
        for name, agent in agents.items():
            assert agent.description is not None, f"{name} should have description"
            assert len(agent.description) > 0, f"{name} should have non-empty description"


class TestSubagentBuilderBuildBusinessLogicAgent:
    """Tests for SubagentBuilder.build_business_logic_agent method."""

    def test_returns_agent_definition(self):
        """Should return an AgentDefinition instance."""
        # when
        agent = SubagentBuilder.build_business_logic_agent()

        # then
        assert hasattr(agent, 'description')
        assert hasattr(agent, 'prompt')

    def test_has_description(self):
        """Should have a description for Claude's tool selection."""
        # when
        agent = SubagentBuilder.build_business_logic_agent()

        # then
        assert len(agent.description) > 0

    def test_description_mentions_patterns_or_logic(self):
        """Description should mention patterns, implementation, or logic."""
        # when
        agent = SubagentBuilder.build_business_logic_agent()

        # then
        desc = agent.description.lower()
        assert "pattern" in desc or "implementation" in desc or "logic" in desc

    def test_injects_knowledge_context(self):
        """Should inject knowledge context into prompt."""
        # given
        knowledge = "# Decisions\nUsing middleware pattern"

        # when
        agent = SubagentBuilder.build_business_logic_agent(
            knowledge_context=knowledge
        )

        # then
        assert knowledge in agent.prompt

    def test_has_read_only_tools(self):
        """Should have read-only tools to prevent file writes during exploration."""
        # when
        agent = SubagentBuilder.build_business_logic_agent()

        # then
        assert agent.tools == EXPLORATION_TOOLS


class TestSubagentBuilderBuildDependenciesAgent:
    """Tests for SubagentBuilder.build_dependencies_agent method."""

    def test_returns_agent_definition(self):
        """Should return an AgentDefinition instance."""
        # when
        agent = SubagentBuilder.build_dependencies_agent()

        # then
        assert hasattr(agent, 'description')
        assert hasattr(agent, 'prompt')

    def test_has_description(self):
        """Should have a description for Claude's tool selection."""
        # when
        agent = SubagentBuilder.build_dependencies_agent()

        # then
        assert len(agent.description) > 0

    def test_description_mentions_dependencies_or_integration(self):
        """Description should mention dependencies or integrations."""
        # when
        agent = SubagentBuilder.build_dependencies_agent()

        # then
        desc = agent.description.lower()
        assert "dependencies" in desc or "integration" in desc

    def test_injects_knowledge_context(self):
        """Should inject knowledge context into prompt."""
        # given
        knowledge = "# Lessons Learned\n[Stripe] Use webhooks for async events"

        # when
        agent = SubagentBuilder.build_dependencies_agent(
            knowledge_context=knowledge
        )

        # then
        assert knowledge in agent.prompt

    def test_has_read_only_tools(self):
        """Should have read-only tools to prevent file writes during exploration."""
        # when
        agent = SubagentBuilder.build_dependencies_agent()

        # then
        assert agent.tools == EXPLORATION_TOOLS


class TestSubagentBuilderBuildTestUsecaseAgent:
    """Tests for SubagentBuilder.build_test_usecase_agent method."""

    def test_returns_agent_definition(self):
        """Should return an AgentDefinition instance."""
        # when
        agent = SubagentBuilder.build_test_usecase_agent()

        # then
        assert hasattr(agent, 'description')
        assert hasattr(agent, 'prompt')

    def test_has_description(self):
        """Should have a description for Claude's tool selection."""
        # when
        agent = SubagentBuilder.build_test_usecase_agent()

        # then
        assert len(agent.description) > 0

    def test_description_mentions_tests(self):
        """Description should mention tests."""
        # when
        agent = SubagentBuilder.build_test_usecase_agent()

        # then
        desc = agent.description.lower()
        assert "test" in desc

    def test_injects_knowledge_context(self):
        """Should inject knowledge context into prompt."""
        # given
        knowledge = "# Lessons Learned\n[Testing] Use fixtures for database tests"

        # when
        agent = SubagentBuilder.build_test_usecase_agent(
            knowledge_context=knowledge
        )

        # then
        assert knowledge in agent.prompt

    def test_has_read_only_tools(self):
        """Should have read-only tools to prevent file writes during exploration."""
        # when
        agent = SubagentBuilder.build_test_usecase_agent()

        # then
        assert agent.tools == EXPLORATION_TOOLS


class TestPhase1SupervisorInstructions:
    """Tests for PHASE1_SUPERVISOR_INSTRUCTIONS constant."""

    def test_instructions_defined(self):
        """Supervisor instructions should be defined."""
        assert len(PHASE1_SUPERVISOR_INSTRUCTIONS) > 0

    def test_instructions_mention_subagents(self):
        """Instructions should mention spawning subagents."""
        assert "subagent" in PHASE1_SUPERVISOR_INSTRUCTIONS.lower()

    def test_instructions_mention_parallel(self):
        """Instructions should mention parallel exploration."""
        lower = PHASE1_SUPERVISOR_INSTRUCTIONS.lower()
        assert "parallel" in lower or "concurrent" in lower

    def test_instructions_mention_delegation(self):
        """Instructions should say parent delegates bulk exploration to subagents."""
        lower = PHASE1_SUPERVISOR_INSTRUCTIONS.lower()
        assert "delegate" in lower

    def test_instructions_mention_all_three_explorers(self):
        """Instructions should mention all three explorer types."""
        lower = PHASE1_SUPERVISOR_INSTRUCTIONS.lower()
        assert "business" in lower or "logic" in lower
        assert "dependencies" in lower or "integration" in lower
        assert "test" in lower

    def test_instructions_mention_requirements_gathering(self):
        """Instructions should mention gathering requirements first."""
        lower = PHASE1_SUPERVISOR_INSTRUCTIONS.lower()
        assert "requirements" in lower

    def test_instructions_mention_phase_complete(self):
        """Instructions should mention PHASE_COMPLETE signal."""
        assert "PHASE_COMPLETE" in PHASE1_SUPERVISOR_INSTRUCTIONS

    def test_instructions_mention_task_tool(self):
        """Instructions should mention using Task tool for subagents."""
        assert "Task" in PHASE1_SUPERVISOR_INSTRUCTIONS


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_knowledge_context_handled(self):
        """Should handle empty knowledge context gracefully."""
        # when
        agents = SubagentBuilder.build_exploration_agents(
            knowledge_context=""
        )

        # then
        assert len(agents) == 4
        # Should still have valid prompts
        for agent in agents.values():
            assert len(agent.prompt) > 0
            assert "{knowledge_context}" not in agent.prompt


class TestSubagentBuilderConsistency:
    """Tests for consistency between individual builders and bulk builder."""

    def test_individual_and_bulk_builders_produce_same_business_logic_agent(self):
        """Individual and bulk builders should produce equivalent business logic agent."""
        # given
        knowledge = "# Architecture\nTest"

        # when
        bulk_agents = SubagentBuilder.build_exploration_agents(
            knowledge_context=knowledge
        )
        individual_agent = SubagentBuilder.build_business_logic_agent(
            knowledge_context=knowledge
        )

        # then
        bulk_agent = bulk_agents[BUSINESS_LOGIC_EXPLORER]
        assert bulk_agent.prompt == individual_agent.prompt
        assert bulk_agent.description == individual_agent.description
        assert bulk_agent.tools == individual_agent.tools

    def test_individual_and_bulk_builders_produce_same_dependencies_agent(self):
        """Individual and bulk builders should produce equivalent dependencies agent."""
        # given
        knowledge = "# Architecture\nTest"

        # when
        bulk_agents = SubagentBuilder.build_exploration_agents(
            knowledge_context=knowledge
        )
        individual_agent = SubagentBuilder.build_dependencies_agent(
            knowledge_context=knowledge
        )

        # then
        bulk_agent = bulk_agents[DEPENDENCIES_EXPLORER]
        assert bulk_agent.prompt == individual_agent.prompt
        assert bulk_agent.description == individual_agent.description
        assert bulk_agent.tools == individual_agent.tools

    def test_individual_and_bulk_builders_produce_same_test_usecase_agent(self):
        """Individual and bulk builders should produce equivalent test/usecase agent."""
        # given
        knowledge = "# Architecture\nTest"

        # when
        bulk_agents = SubagentBuilder.build_exploration_agents(
            knowledge_context=knowledge
        )
        individual_agent = SubagentBuilder.build_test_usecase_agent(
            knowledge_context=knowledge
        )

        # then
        bulk_agent = bulk_agents[TEST_USECASE_EXPLORER]
        assert bulk_agent.prompt == individual_agent.prompt
        assert bulk_agent.description == individual_agent.description
        assert bulk_agent.tools == individual_agent.tools


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
