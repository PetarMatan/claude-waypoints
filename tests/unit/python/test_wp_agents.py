#!/usr/bin/env python3
"""
Unit tests for wp_agents.py
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add hooks/lib to path
sys.path.insert(0, 'hooks/lib')
from wp_agents import AgentLoader


class TestAgentLoader:
    """Tests for AgentLoader class."""

    def test_init_uses_provided_dir(self):
        loader = AgentLoader("/custom/agents/dir")
        assert loader.agents_dir == "/custom/agents/dir"

    def test_init_uses_env_var(self):
        with patch.dict(os.environ, {"WP_INSTALL_DIR": "/from/env"}):
            loader = AgentLoader()
            assert loader.agents_dir == "/from/env/agents"

    def test_init_uses_default_path(self):
        with patch.dict(os.environ, {}, clear=True):
            # Clear WP_INSTALL_DIR if set
            os.environ.pop("WP_INSTALL_DIR", None)
            loader = AgentLoader()
            assert "waypoints/agents" in loader.agents_dir

    def test_get_agents_for_phase(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create agent for phase 2
            with open(os.path.join(tmpdir, "tester.md"), 'w') as f:
                f.write("""---
name: Tester
phases: [2, 3]
---
Test content
""")
            loader = AgentLoader(tmpdir)
            result = loader.get_agents_for_phase(2)
            assert len(result) == 1
            assert "tester.md" in result[0]

    def test_get_agents_for_phase_empty_dir(self):
        loader = AgentLoader("/nonexistent/dir")
        result = loader.get_agents_for_phase(1)
        assert result == []

    def test_get_agent_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_file = os.path.join(tmpdir, "my-agent.md")
            with open(agent_file, 'w') as f:
                f.write("""---
name: Custom Agent Name
---
Content
""")
            loader = AgentLoader(tmpdir)
            result = loader.get_agent_name(agent_file)
            assert result == "Custom Agent Name"

    def test_get_agent_name_from_filename(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_file = os.path.join(tmpdir, "wp-tester.md")
            with open(agent_file, 'w') as f:
                f.write("# No frontmatter")
            loader = AgentLoader(tmpdir)
            result = loader.get_agent_name(agent_file)
            assert result == "Wp Tester"

    def test_get_agent_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_file = os.path.join(tmpdir, "agent.md")
            with open(agent_file, 'w') as f:
                f.write("""---
name: Test
---

# Instructions
Do these things.
""")
            loader = AgentLoader(tmpdir)
            result = loader.get_agent_content(agent_file)
            assert "# Instructions" in result
            assert "name: Test" not in result

    def test_get_agent_content_returns_none_for_missing(self):
        loader = AgentLoader("/tmp")
        result = loader.get_agent_content("/nonexistent/agent.md")
        assert result is None

    def test_load_phase_agents_returns_combined_content(self, capsys):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "agent1.md"), 'w') as f:
                f.write("""---
name: Agent One
phases: [1]
---

First agent content.
""")
            with open(os.path.join(tmpdir, "agent2.md"), 'w') as f:
                f.write("""---
name: Agent Two
phases: [1]
---

Second agent content.
""")
            loader = AgentLoader(tmpdir)
            result = loader.load_phase_agents(1)

            assert "## Agent: Agent One" in result
            assert "First agent content" in result
            assert "## Agent: Agent Two" in result
            assert "Second agent content" in result

    def test_load_phase_agents_returns_empty_for_no_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "agent.md"), 'w') as f:
                f.write("""---
phases: [3]
---
Content
""")
            loader = AgentLoader(tmpdir)
            result = loader.load_phase_agents(1)
            assert result == ""

    def test_load_phase_agents_with_logger(self, capsys):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "agent.md"), 'w') as f:
                f.write("""---
name: Test Agent
phases: [2]
---
Content
""")
            mock_logger = MagicMock()
            loader = AgentLoader(tmpdir)
            loader.load_phase_agents(2, logger=mock_logger)

            mock_logger.log_wp.assert_called_once()
            call_args = mock_logger.log_wp.call_args[0][0]
            assert "Test Agent" in call_args
            assert "phase 2" in call_args

    def test_load_phase_agents_prints_to_stderr(self, capsys):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "agent.md"), 'w') as f:
                f.write("""---
name: Visible Agent
phases: [1]
---
Content
""")
            loader = AgentLoader(tmpdir)
            loader.load_phase_agents(1)

            captured = capsys.readouterr()
            assert "Loaded agent: Visible Agent" in captured.err

    def test_list_agents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "agent1.md"), 'w') as f:
                f.write("""---
name: First
phases: [1, 2]
---
""")
            with open(os.path.join(tmpdir, "agent2.md"), 'w') as f:
                f.write("""---
name: Second
phases: [3]
---
""")
            loader = AgentLoader(tmpdir)
            result = loader.list_agents()

            import json
            data = json.loads(result)
            assert len(data) == 2
            names = [a['name'] for a in data]
            assert "First" in names
            assert "Second" in names

    def test_list_agents_empty_dir(self):
        loader = AgentLoader("/nonexistent/dir")
        result = loader.list_agents()
        assert result == "[]"

    def test_get_new_agents_for_phase_returns_only_new(self):
        """Should return only agents not present in previous phases."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Agent for phases 1, 2, 3, 4 (like Uncle Bob)
            with open(os.path.join(tmpdir, "uncle-bob.md"), 'w') as f:
                f.write("""---
name: Uncle Bob
phases: [1, 2, 3, 4]
---
Content
""")
            # Agent for phases 2, 4 only (like Developer)
            with open(os.path.join(tmpdir, "developer.md"), 'w') as f:
                f.write("""---
name: Developer
phases: [2, 4]
---
Content
""")
            # Agent for phase 3 only (like Tester)
            with open(os.path.join(tmpdir, "tester.md"), 'w') as f:
                f.write("""---
name: Tester
phases: [3]
---
Content
""")

            loader = AgentLoader(tmpdir)

            # Phase 1: Uncle Bob is new
            new_phase1 = loader.get_new_agents_for_phase(1)
            assert len(new_phase1) == 1
            assert any("uncle-bob.md" in f for f in new_phase1)

            # Phase 2: Developer is new (Uncle Bob was in phase 1)
            new_phase2 = loader.get_new_agents_for_phase(2)
            assert len(new_phase2) == 1
            assert any("developer.md" in f for f in new_phase2)

            # Phase 3: Tester is new (Uncle Bob was in phase 1)
            new_phase3 = loader.get_new_agents_for_phase(3)
            assert len(new_phase3) == 1
            assert any("tester.md" in f for f in new_phase3)

            # Phase 4: No new agents (all were in previous phases)
            new_phase4 = loader.get_new_agents_for_phase(4)
            assert len(new_phase4) == 0

    def test_load_phase_agents_skip_already_loaded(self, capsys):
        """Should skip agents from previous phases when skip_already_loaded=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Agent for all phases
            with open(os.path.join(tmpdir, "common.md"), 'w') as f:
                f.write("""---
name: Common Agent
phases: [1, 2, 3]
---
Common content
""")
            # Agent for phase 2 only
            with open(os.path.join(tmpdir, "phase2-only.md"), 'w') as f:
                f.write("""---
name: Phase 2 Only
phases: [2]
---
Phase 2 content
""")

            loader = AgentLoader(tmpdir)

            # Phase 2 with skip: should only load Phase 2 Only (Common was in phase 1)
            result = loader.load_phase_agents(2, skip_already_loaded=True)
            assert "Phase 2 Only" in result
            assert "Common Agent" not in result

            # Phase 2 without skip: should load both
            result = loader.load_phase_agents(2, skip_already_loaded=False)
            assert "Phase 2 Only" in result
            assert "Common Agent" in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
