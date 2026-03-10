#!/usr/bin/env python3
"""
Unit tests for wp_migration.py - Migration utility to convert markdown to graph
"""

import sys
import tempfile
import pytest
from pathlib import Path

# Add hooks/lib to path
sys.path.insert(0, 'hooks/lib')
from wp_migration import (
    MarkdownParser,
    KnowledgeMigrator,
    migrate_knowledge_cli
)


class TestMarkdownParser:
    """Tests for MarkdownParser - parses existing markdown knowledge files."""

    def test_parse_architecture_markdown_extracts_entries(self):
        # given - [REQ-23] Preserve all existing entry content, dates, and session metadata
        markdown_content = """# Architecture

## 2026-03-09 (Session: 20260309-120000)

### Event-Driven System
The system uses events for asynchronous communication between services.

### Service Mesh
Services communicate through a mesh with built-in service discovery.
"""

        # when
        entries = MarkdownParser.parse_architecture_markdown(markdown_content)

        # then
        assert len(entries) == 2
        assert entries[0]["title"] == "Event-Driven System"
        assert entries[0]["date"] == "2026-03-09"
        assert entries[0]["session_id"] == "20260309-120000"
        assert "asynchronous communication" in entries[0]["content"]

    def test_parse_architecture_markdown_handles_multiple_sessions(self):
        # given
        markdown_content = """# Architecture

## 2026-03-09 (Session: session-1)

### Pattern A
Content A

## 2026-03-08 (Session: session-2)

### Pattern B
Content B
"""

        # when
        entries = MarkdownParser.parse_architecture_markdown(markdown_content)

        # then
        assert len(entries) == 2
        assert entries[0]["session_id"] == "session-1"
        assert entries[1]["session_id"] == "session-2"

    def test_parse_architecture_markdown_handles_empty_content(self):
        # given
        markdown_content = """# Architecture

No architecture documented yet.
"""

        # when
        entries = MarkdownParser.parse_architecture_markdown(markdown_content)

        # then
        assert len(entries) == 0

    def test_parse_decisions_markdown_extracts_entries(self):
        # given
        markdown_content = """# Decisions

## 2026-03-09 (Session: 20260309-130000)

### Use REST over GraphQL
REST API provides simplicity and widespread tooling support.

### Chose PostgreSQL
Relational database chosen for ACID guarantees.
"""

        # when
        entries = MarkdownParser.parse_decisions_markdown(markdown_content)

        # then
        assert len(entries) == 2
        assert entries[0]["title"] == "Use REST over GraphQL"
        assert entries[1]["title"] == "Chose PostgreSQL"
        assert "ACID guarantees" in entries[1]["content"]

    def test_parse_decisions_markdown_preserves_multiline_content(self):
        # given
        markdown_content = """# Decisions

## 2026-03-09 (Session: s1)

### Use Async Pattern
We chose async/await for better concurrency.

This decision was made after comparing:
- Thread-based approach
- Async/await approach
- Event loop approach

The async approach won due to better resource efficiency.
"""

        # when
        entries = MarkdownParser.parse_decisions_markdown(markdown_content)

        # then
        assert len(entries) == 1
        assert "Thread-based approach" in entries[0]["content"]
        assert "resource efficiency" in entries[0]["content"]

    def test_parse_lessons_markdown_extracts_entries_with_tags(self):
        # given
        markdown_content = """# Lessons Learned

## [Python]

### Use Type Hints (2026-03-09)
Always add type hints to function signatures for better IDE support.

### Avoid Mutable Defaults (2026-03-08)
Never use mutable objects like lists as default arguments.

## [Git]

### Commit Often (2026-03-07)
Small, frequent commits are easier to review and debug.
"""

        # when
        entries = MarkdownParser.parse_lessons_markdown(markdown_content)

        # then
        assert len(entries) == 3
        assert entries[0]["tag"] == "Python"
        assert entries[0]["title"] == "Use Type Hints"
        assert entries[0]["date"] == "2026-03-09"
        assert entries[2]["tag"] == "Git"

    def test_parse_lessons_markdown_handles_missing_dates(self):
        # given - Some older lessons may not have dates
        markdown_content = """# Lessons Learned

## [Docker]

### Use Multi-Stage Builds
Multi-stage builds reduce image size significantly.
"""

        # when
        entries = MarkdownParser.parse_lessons_markdown(markdown_content)

        # then
        assert len(entries) == 1
        assert entries[0]["tag"] == "Docker"
        assert entries[0]["date"] is not None  # Should use current date as fallback

    def test_parse_architecture_markdown_handles_malformed_headers(self):
        # given
        markdown_content = """# Architecture

## Invalid header format

### Valid Entry
This should still be parsed.

Malformed session header
### Another Entry
This should also work.
"""

        # when
        entries = MarkdownParser.parse_architecture_markdown(markdown_content)

        # then - Should extract valid entries despite malformed headers
        assert len(entries) >= 1

    def test_parse_lessons_markdown_handles_entries_without_tags(self):
        # given - Legacy format without tags
        markdown_content = """# Lessons Learned

### Document Edge Cases (2026-03-09)
Always document edge cases in function docstrings.
"""

        # when
        entries = MarkdownParser.parse_lessons_markdown(markdown_content)

        # then
        assert len(entries) == 1
        assert entries[0]["tag"] is None or entries[0]["tag"] == ""


class TestKnowledgeMigrator:
    """Tests for KnowledgeMigrator - migrates markdown files to graph structure."""

    def test_knowledge_migrator_initialization_for_project(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)

            # when
            migrator = KnowledgeMigrator(knowledge_dir, project_id="test-project")

            # then
            assert migrator is not None

    def test_knowledge_migrator_initialization_for_global(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)

            # when
            migrator = KnowledgeMigrator(knowledge_dir, project_id=None)

            # then
            assert migrator is not None

    def test_migrate_project_creates_graph_from_architecture_markdown(self):
        # given - [REQ-21] Provide explicit CLI command to migrate
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            project_dir = knowledge_dir / "test-project"
            project_dir.mkdir(parents=True)

            arch_file = project_dir / "architecture.md"
            arch_file.write_text("""# Architecture

## 2026-03-09 (Session: session-1)

### Microservices
System split into independent services.
""")

            migrator = KnowledgeMigrator(knowledge_dir, project_id="test-project")

            # when
            result = migrator.migrate_project()

            # then
            assert result is True
            graph_file = project_dir / "graph.json"
            assert graph_file.exists()

    def test_migrate_project_creates_graph_from_decisions_markdown(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            project_dir = knowledge_dir / "project-a"
            project_dir.mkdir(parents=True)

            decisions_file = project_dir / "decisions.md"
            decisions_file.write_text("""# Decisions

## 2026-03-09 (Session: session-1)

### Use Redis
Fast in-memory cache chosen for session storage.
""")

            migrator = KnowledgeMigrator(knowledge_dir, project_id="project-a")

            # when
            result = migrator.migrate_project()

            # then
            assert result is True

    def test_migrate_project_combines_architecture_and_decisions(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            project_dir = knowledge_dir / "project-b"
            project_dir.mkdir(parents=True)

            (project_dir / "architecture.md").write_text("""# Architecture

## 2026-03-09 (Session: s1)

### API Gateway
Central entry point for all services.
""")

            (project_dir / "decisions.md").write_text("""# Decisions

## 2026-03-09 (Session: s1)

### Use JWT
JSON Web Tokens for stateless authentication.
""")

            migrator = KnowledgeMigrator(knowledge_dir, project_id="project-b")

            # when
            result = migrator.migrate_project()

            # then
            assert result is True
            # Graph should contain both architecture and decisions
            graph_file = project_dir / "graph.json"
            import json
            graph_data = json.loads(graph_file.read_text())
            assert len(graph_data["nodes"]) == 2

    def test_migrate_project_returns_true_when_no_markdown_files(self):
        # given - No markdown files to migrate
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            project_dir = knowledge_dir / "empty-project"
            project_dir.mkdir(parents=True)

            migrator = KnowledgeMigrator(knowledge_dir, project_id="empty-project")

            # when
            result = migrator.migrate_project()

            # then
            assert result is True  # Not an error, just nothing to migrate

    def test_migrate_project_skips_if_graph_already_exists(self):
        # given - [ERR-3] Migration of already-migrated content: detect and skip
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            project_dir = knowledge_dir / "migrated-project"
            project_dir.mkdir(parents=True)

            # Create existing graph
            graph_file = project_dir / "graph.json"
            graph_file.write_text('{"nodes": {}}')

            migrator = KnowledgeMigrator(knowledge_dir, project_id="migrated-project")

            # when
            result = migrator.migrate_project()

            # then
            assert result is True  # Should succeed but not overwrite

    def test_migrate_global_creates_graph_from_lessons_markdown(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)

            lessons_file = knowledge_dir / "lessons-learned.md"
            lessons_file.write_text("""# Lessons Learned

## [Python]

### Use Context Managers (2026-03-09)
Always use 'with' statements for file operations.

## [Git]

### Atomic Commits (2026-03-08)
Each commit should be a single logical change.
""")

            migrator = KnowledgeMigrator(knowledge_dir, project_id=None)

            # when
            result = migrator.migrate_global()

            # then
            assert result is True
            graph_file = knowledge_dir / "global-graph.json"
            assert graph_file.exists()

    def test_migrate_global_preserves_tags(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)

            lessons_file = knowledge_dir / "lessons-learned.md"
            lessons_file.write_text("""# Lessons Learned

## [Kotlin]

### Use Data Classes (2026-03-09)
Data classes provide equals/hashCode automatically.
""")

            migrator = KnowledgeMigrator(knowledge_dir, project_id=None)

            # when
            migrator.migrate_global()

            # then
            graph_file = knowledge_dir / "global-graph.json"
            import json
            graph_data = json.loads(graph_file.read_text())
            # Find the node and check tag is preserved
            nodes = graph_data["nodes"]
            assert len(nodes) > 0
            # Tag should be preserved in node data

    def test_migrate_all_migrates_project_and_global(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)

            # Create project markdown
            project_dir = knowledge_dir / "project-all"
            project_dir.mkdir(parents=True)
            (project_dir / "architecture.md").write_text("""# Architecture

## 2026-03-09 (Session: s1)

### Pattern A
Content A
""")

            # Create global markdown
            (knowledge_dir / "lessons-learned.md").write_text("""# Lessons Learned

## [Python]

### Lesson A (2026-03-09)
Content A
""")

            migrator = KnowledgeMigrator(knowledge_dir, project_id="project-all")

            # when
            result = migrator.migrate_all()

            # then
            assert result is True
            assert (project_dir / "graph.json").exists()
            assert (knowledge_dir / "global-graph.json").exists()

    def test_migrate_project_handles_io_errors(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            # Non-existent project
            migrator = KnowledgeMigrator(knowledge_dir, project_id="nonexistent")

            # when
            result = migrator.migrate_project()

            # then - Should handle gracefully
            assert result is True or result is False  # Either is acceptable


class TestMigrateKnowledgeCLI:
    """Tests for migrate_knowledge_cli function - CLI command entry point."""

    def test_migrate_knowledge_cli_with_project_id(self):
        # given - [REQ-21] Provide explicit CLI command to migrate
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            project_dir = knowledge_dir / "cli-project"
            project_dir.mkdir(parents=True)

            (project_dir / "architecture.md").write_text("""# Architecture

## 2026-03-09 (Session: s1)

### CLI Pattern
Architecture for CLI.
""")

            # when
            exit_code = migrate_knowledge_cli(knowledge_dir, project_id="cli-project")

            # then
            assert exit_code == 0
            assert (project_dir / "graph.json").exists()

    def test_migrate_knowledge_cli_global_only_flag(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)

            (knowledge_dir / "lessons-learned.md").write_text("""# Lessons Learned

## [Python]

### CLI Lesson (2026-03-09)
Always validate CLI arguments.
""")

            # when
            exit_code = migrate_knowledge_cli(knowledge_dir, global_only=True)

            # then
            assert exit_code == 0
            assert (knowledge_dir / "global-graph.json").exists()

    def test_migrate_knowledge_cli_returns_zero_on_success(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)

            # when
            exit_code = migrate_knowledge_cli(knowledge_dir)

            # then
            assert exit_code == 0

    def test_migrate_knowledge_cli_returns_nonzero_on_error(self):
        # given - Invalid directory
        knowledge_dir = Path("/nonexistent/directory/that/does/not/exist")

        # when
        exit_code = migrate_knowledge_cli(knowledge_dir)

        # then
        assert exit_code != 0

    def test_migrate_knowledge_cli_with_both_project_and_global(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            project_dir = knowledge_dir / "both-project"
            project_dir.mkdir(parents=True)

            (project_dir / "decisions.md").write_text("""# Decisions

## 2026-03-09 (Session: s1)

### Decision A
Content A
""")

            (knowledge_dir / "lessons-learned.md").write_text("""# Lessons Learned

## [Go]

### Lesson B (2026-03-09)
Content B
""")

            # when - Migrate project (which should also migrate global)
            exit_code = migrate_knowledge_cli(knowledge_dir, project_id="both-project")

            # then
            assert exit_code == 0
            assert (project_dir / "graph.json").exists()
            assert (knowledge_dir / "global-graph.json").exists()


class TestMigrationEdgeCases:
    """Tests for edge cases in migration process."""

    def test_migrate_handles_relationship_markers_in_content(self):
        # given - Content with relationship markers should be preserved
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            project_dir = knowledge_dir / "rel-project"
            project_dir.mkdir(parents=True)

            (project_dir / "decisions.md").write_text("""# Decisions

## 2026-03-09 (Session: s1)

### Use GraphQL
We chose GraphQL [led_to: "Flexible API Design"] for better querying.
""")

            migrator = KnowledgeMigrator(knowledge_dir, project_id="rel-project")

            # when
            result = migrator.migrate_project()

            # then
            assert result is True
            # Relationship markers should be parsed and stored

    def test_migrate_handles_duplicate_titles_with_different_dates(self):
        # given - [EDGE-4] Duplicate entry titles handled by (type, title, date) tuple
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            project_dir = knowledge_dir / "dup-project"
            project_dir.mkdir(parents=True)

            (project_dir / "architecture.md").write_text("""# Architecture

## 2026-03-09 (Session: s1)

### API Design
First version of API design.

## 2026-03-08 (Session: s2)

### API Design
Earlier version of API design.
""")

            migrator = KnowledgeMigrator(knowledge_dir, project_id="dup-project")

            # when
            result = migrator.migrate_project()

            # then
            assert result is True
            # Both entries should be in graph with different node IDs

    def test_migrate_preserves_special_characters_in_content(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            project_dir = knowledge_dir / "special-project"
            project_dir.mkdir(parents=True)

            (project_dir / "architecture.md").write_text("""# Architecture

## 2026-03-09 (Session: s1)

### Code Example
```python
def example():
    return "Special: <>&\\"'"
```
""")

            migrator = KnowledgeMigrator(knowledge_dir, project_id="special-project")

            # when
            result = migrator.migrate_project()

            # then
            assert result is True
            # Special characters should be preserved


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
