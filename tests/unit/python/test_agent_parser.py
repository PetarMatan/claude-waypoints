#!/usr/bin/env python3
"""
Unit tests for agent_parser.py
"""

import json
import os
import sys
import tempfile
import pytest
from pathlib import Path

# Add hooks/lib to path
sys.path.insert(0, 'hooks/lib')
from agent_parser import (
    parse_frontmatter,
    get_content_without_frontmatter,
    get_phases_list,
    get_agent_name,
    get_agent_content,
    list_agents_data,
    get_agents_for_phase,
)


class TestParseFrontmatter:
    """Tests for parse_frontmatter function."""

    def test_parses_name_and_phases(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("""---
name: Test Agent
phases: [1, 2, 3]
---

# Content here
""")
            f.flush()
            result = parse_frontmatter(f.name)
            assert result['name'] == 'Test Agent'
            assert result['phases'] == [1, 2, 3]

    def test_parses_phases_without_spaces(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("""---
name: Compact
phases: [1,2,3]
---

Content
""")
            f.flush()
            result = parse_frontmatter(f.name)
            assert result['phases'] == [1, 2, 3]

    def test_returns_none_without_frontmatter(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Just markdown content")
            f.flush()
            result = parse_frontmatter(f.name)
            assert result is None

    def test_returns_none_without_end_delimiter(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("""---
name: Test
# No end delimiter
""")
            f.flush()
            result = parse_frontmatter(f.name)
            assert result is None

    def test_returns_none_for_empty_frontmatter(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("""---
---

Content
""")
            f.flush()
            result = parse_frontmatter(f.name)
            assert result is None

    def test_returns_none_for_missing_file(self):
        result = parse_frontmatter("/nonexistent/file.md")
        assert result is None

    def test_parses_only_name(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("""---
name: Name Only Agent
---

Content
""")
            f.flush()
            result = parse_frontmatter(f.name)
            assert result == {'name': 'Name Only Agent'}

    def test_parses_only_phases(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("""---
phases: [2, 4]
---

Content
""")
            f.flush()
            result = parse_frontmatter(f.name)
            assert result == {'phases': [2, 4]}


class TestGetContentWithoutFrontmatter:
    """Tests for get_content_without_frontmatter function."""

    def test_removes_frontmatter(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("""---
name: Test
---

# Main Content
Some text here.
""")
            f.flush()
            result = get_content_without_frontmatter(f.name)
            assert "# Main Content" in result
            assert "name: Test" not in result

    def test_returns_full_content_without_frontmatter(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# No frontmatter\nJust content.")
            f.flush()
            result = get_content_without_frontmatter(f.name)
            assert result == "# No frontmatter\nJust content."

    def test_returns_empty_for_missing_file(self):
        result = get_content_without_frontmatter("/nonexistent/file.md")
        assert result == ""


class TestGetPhasesList:
    """Tests for get_phases_list function."""

    def test_returns_phases(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("""---
phases: [1, 3]
---
Content
""")
            f.flush()
            result = get_phases_list(f.name)
            assert result == [1, 3]

    def test_returns_empty_list_without_phases(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("""---
name: No Phases
---
Content
""")
            f.flush()
            result = get_phases_list(f.name)
            assert result == []

    def test_returns_empty_list_for_invalid_file(self):
        result = get_phases_list("/nonexistent/file.md")
        assert result == []


class TestGetAgentName:
    """Tests for get_agent_name function."""

    def test_returns_name_from_frontmatter(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("""---
name: My Custom Agent
---
Content
""")
            f.flush()
            result = get_agent_name(f.name)
            assert result == "My Custom Agent"

    def test_derives_name_from_filename(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "wp-tester.md")
            with open(filepath, 'w') as f:
                f.write("# No frontmatter")
            result = get_agent_name(filepath)
            assert result == "Wp Tester"

    def test_derives_name_without_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "my-agent.md")
            with open(filepath, 'w') as f:
                f.write("""---
phases: [1]
---
Content without name
""")
            result = get_agent_name(filepath)
            assert result == "My Agent"


class TestGetAgentContent:
    """Tests for get_agent_content function."""

    def test_returns_content_without_frontmatter(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("""---
name: Test
---

# Agent Instructions
Do this and that.
""")
            f.flush()
            result = get_agent_content(f.name)
            assert "# Agent Instructions" in result
            assert "name: Test" not in result

    def test_returns_none_for_missing_file(self):
        result = get_agent_content("/nonexistent/file.md")
        assert result is None


class TestListAgentsData:
    """Tests for list_agents_data function."""

    def test_lists_agents_with_phases(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create agent with phases
            with open(os.path.join(tmpdir, "agent1.md"), 'w') as f:
                f.write("""---
name: Agent One
phases: [1, 2]
---
Content
""")
            # Create agent without phases (should be excluded)
            with open(os.path.join(tmpdir, "agent2.md"), 'w') as f:
                f.write("# No phases")

            result = list_agents_data(tmpdir)
            assert len(result) == 1
            assert result[0]['name'] == 'Agent One'
            assert result[0]['phases'] == [1, 2]

    def test_returns_empty_for_nonexistent_dir(self):
        result = list_agents_data("/nonexistent/dir")
        assert result == []

    def test_ignores_non_md_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "agent.md"), 'w') as f:
                f.write("""---
phases: [1]
---
Content
""")
            with open(os.path.join(tmpdir, "readme.txt"), 'w') as f:
                f.write("Not an agent")

            result = list_agents_data(tmpdir)
            assert len(result) == 1


class TestGetAgentsForPhase:
    """Tests for get_agents_for_phase function."""

    def test_returns_agents_matching_phase(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent1 = os.path.join(tmpdir, "phase1.md")
            with open(agent1, 'w') as f:
                f.write("""---
phases: [1]
---
""")
            agent2 = os.path.join(tmpdir, "phase2.md")
            with open(agent2, 'w') as f:
                f.write("""---
phases: [2, 3]
---
""")

            result = get_agents_for_phase(tmpdir, 1)
            assert len(result) == 1
            assert agent1 in result

            result = get_agents_for_phase(tmpdir, 2)
            assert len(result) == 1
            assert agent2 in result

    def test_returns_multiple_matching_agents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ["a.md", "b.md"]:
                with open(os.path.join(tmpdir, name), 'w') as f:
                    f.write("""---
phases: [3]
---
""")

            result = get_agents_for_phase(tmpdir, 3)
            assert len(result) == 2

    def test_returns_empty_for_nonexistent_dir(self):
        result = get_agents_for_phase("/nonexistent/dir", 1)
        assert result == []

    def test_returns_empty_for_unmatched_phase(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "agent.md"), 'w') as f:
                f.write("""---
phases: [1, 2]
---
""")

            result = get_agents_for_phase(tmpdir, 4)
            assert result == []


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
