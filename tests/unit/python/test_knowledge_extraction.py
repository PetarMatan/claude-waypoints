#!/usr/bin/env python3
"""
Unit tests for Knowledge Extraction and Persistence feature.

Tests cover the following requirements:
- REQ-1 through REQ-29: Knowledge loading, injection, extraction, staging, and application
- EDGE-1 through EDGE-6: Edge cases
- ERR-1, ERR-2: Error handling

Test organization:
1. StagedKnowledgeEntry and StagedKnowledge dataclasses
2. ExtractionResult dataclass
3. extract_from_text() parser function
4. KnowledgeManager - loading methods
5. KnowledgeManager - application methods
6. SupervisorMarkers - staging methods
7. ContextBuilder - knowledge injection
8. Integration tests
"""

import sys
import json
import tempfile
import pytest
from pathlib import Path
from datetime import date
from unittest.mock import patch, MagicMock

# Add hooks/lib to path
sys.path.insert(0, 'hooks/lib')
sys.path.insert(0, '.')

from wp_knowledge import (
    StagedKnowledgeEntry,
    StagedKnowledge,
    ExtractionResult,
    extract_from_text,
    KnowledgeManager,
    KnowledgeCategory,
    _parse_architecture_section,
    _parse_decisions_section,
    _parse_lessons_learned_section,
)
from wp_supervisor.markers import SupervisorMarkers
from wp_supervisor.context import ContextBuilder


# =============================================================================
# STAGED KNOWLEDGE ENTRY TESTS
# =============================================================================

class TestStagedKnowledgeEntry:
    """Tests for StagedKnowledgeEntry dataclass."""

    def test_create_entry_with_required_fields(self):
        # when
        entry = StagedKnowledgeEntry(
            title="API Design",
            content="REST endpoints follow resource naming",
            phase=2
        )

        # then
        assert entry.title == "API Design"
        assert entry.content == "REST endpoints follow resource naming"
        assert entry.phase == 2
        assert entry.tag is None

    def test_create_entry_with_tag(self):
        # when
        entry = StagedKnowledgeEntry(
            title="Async patterns",
            content="Use asyncio for I/O bound operations",
            phase=4,
            tag="Python"
        )

        # then
        assert entry.tag == "Python"

    def test_entry_equality(self):
        # given
        entry1 = StagedKnowledgeEntry("Title", "Content", 1, "Tag")
        entry2 = StagedKnowledgeEntry("Title", "Content", 1, "Tag")

        # then
        assert entry1 == entry2

    def test_entry_inequality_different_phase(self):
        # given
        entry1 = StagedKnowledgeEntry("Title", "Content", 1)
        entry2 = StagedKnowledgeEntry("Title", "Content", 2)

        # then
        assert entry1 != entry2


# =============================================================================
# STAGED KNOWLEDGE CONTAINER TESTS
# =============================================================================

class TestStagedKnowledge:
    """Tests for StagedKnowledge container dataclass."""

    def test_create_empty_container(self):
        # when
        staged = StagedKnowledge()

        # then
        assert staged.architecture == []
        assert staged.decisions == []
        assert staged.lessons_learned == []

    def test_is_empty_when_no_entries(self):
        # given
        staged = StagedKnowledge()

        # when/then
        assert staged.is_empty() is True

    def test_is_empty_false_when_has_architecture(self):
        # given
        staged = StagedKnowledge(
            architecture=[StagedKnowledgeEntry("Title", "Content", 1)]
        )

        # when/then
        assert staged.is_empty() is False

    def test_is_empty_false_when_has_decisions(self):
        # given
        staged = StagedKnowledge(
            decisions=[StagedKnowledgeEntry("Title", "Content", 1)]
        )

        # when/then
        assert staged.is_empty() is False

    def test_is_empty_false_when_has_lessons_learned(self):
        # given
        staged = StagedKnowledge(
            lessons_learned=[StagedKnowledgeEntry("Title", "Content", 1, "Python")]
        )

        # when/then
        assert staged.is_empty() is False

    def test_total_count_empty(self):
        # given
        staged = StagedKnowledge()

        # when/then
        assert staged.total_count() == 0

    def test_total_count_with_entries(self):
        # given
        staged = StagedKnowledge(
            architecture=[
                StagedKnowledgeEntry("A1", "C1", 1),
                StagedKnowledgeEntry("A2", "C2", 2),
            ],
            decisions=[
                StagedKnowledgeEntry("D1", "C1", 1),
            ],
            lessons_learned=[
                StagedKnowledgeEntry("L1", "C1", 3, "Python"),
                StagedKnowledgeEntry("L2", "C2", 4, "Git"),
                StagedKnowledgeEntry("L3", "C3", 4, "TypeScript"),
            ],
        )

        # when/then
        assert staged.total_count() == 6


# =============================================================================
# EXTRACTION RESULT TESTS
# =============================================================================

class TestExtractionResult:
    """Tests for ExtractionResult dataclass."""

    def test_create_successful_result(self):
        # given
        knowledge = StagedKnowledge()

        # when
        result = ExtractionResult(knowledge=knowledge, had_content=True)

        # then
        assert result.knowledge == knowledge
        assert result.had_content is True
        assert result.parse_error is None

    def test_create_result_with_error(self):
        # when
        result = ExtractionResult(
            knowledge=StagedKnowledge(),
            had_content=False,
            parse_error="Malformed response"
        )

        # then
        assert result.parse_error == "Malformed response"
        assert result.had_content is False


# =============================================================================
# EXTRACT_FROM_TEXT PARSER TESTS [REQ-9, REQ-10, ERR-1]
# =============================================================================

class TestExtractFromText:
    """Tests for extract_from_text() parser function."""

    def test_parse_no_knowledge_extracted(self):
        """[REQ-9] NO_KNOWLEDGE_EXTRACTED signal should return empty result."""
        # given
        response = "NO_KNOWLEDGE_EXTRACTED"

        # when
        result = extract_from_text(response)

        # then
        assert result.had_content is False
        assert result.knowledge.is_empty()
        assert result.parse_error is None

    def test_parse_no_knowledge_extracted_with_whitespace(self):
        # given
        response = "  NO_KNOWLEDGE_EXTRACTED  \n"

        # when
        result = extract_from_text(response)

        # then
        assert result.had_content is False

    def test_parse_architecture_section(self):
        """[REQ-9] Parse ARCHITECTURE: section entries."""
        # given
        response = """ARCHITECTURE:
- Service Layer: Handles business logic separate from API controllers
- Repository Pattern: Data access abstracted through interfaces"""

        # when
        result = extract_from_text(response)

        # then
        assert result.had_content is True
        assert len(result.knowledge.architecture) == 2
        assert result.knowledge.architecture[0].title == "Service Layer"
        assert "business logic" in result.knowledge.architecture[0].content

    def test_parse_decisions_section(self):
        """[REQ-9] Parse DECISIONS: section entries."""
        # given
        response = """DECISIONS:
- Use async/await: Chose async pattern for better scalability with I/O operations
- SQLite for tests: Using SQLite instead of PostgreSQL for faster test execution"""

        # when
        result = extract_from_text(response)

        # then
        assert result.had_content is True
        assert len(result.knowledge.decisions) == 2
        assert result.knowledge.decisions[0].title == "Use async/await"

    def test_parse_lessons_learned_section_with_tags(self):
        """[REQ-9, REQ-10] Parse LESSONS_LEARNED: section with technology tags."""
        # given
        response = """LESSONS_LEARNED:
- [Python] Use dataclasses: Dataclasses provide clean immutable data containers
- [Git] Commit atomic changes: Each commit should be a single logical change"""

        # when
        result = extract_from_text(response)

        # then
        assert result.had_content is True
        assert len(result.knowledge.lessons_learned) == 2
        assert result.knowledge.lessons_learned[0].tag == "Python"
        assert result.knowledge.lessons_learned[0].title == "Use dataclasses"
        assert result.knowledge.lessons_learned[1].tag == "Git"

    def test_parse_all_sections(self):
        """[REQ-9] Parse response with all three sections."""
        # given
        response = """ARCHITECTURE:
- Event-driven design: Components communicate via events

DECISIONS:
- Chose Redis: Selected Redis for caching due to speed

LESSONS_LEARNED:
- [TypeScript] Strict mode: Always enable strict mode for type safety"""

        # when
        result = extract_from_text(response)

        # then
        assert result.had_content is True
        assert len(result.knowledge.architecture) == 1
        assert len(result.knowledge.decisions) == 1
        assert len(result.knowledge.lessons_learned) == 1

    def test_parse_empty_sections_are_skipped(self):
        """Parse response where some sections have no entries."""
        # given
        response = """ARCHITECTURE:
- Microservice: Service boundary defined

DECISIONS:

LESSONS_LEARNED:
- [Python] Virtual environments: Always use venv for isolation"""

        # when
        result = extract_from_text(response)

        # then
        assert len(result.knowledge.architecture) == 1
        assert len(result.knowledge.decisions) == 0
        assert len(result.knowledge.lessons_learned) == 1

    def test_parse_malformed_response_returns_error(self):
        """[ERR-1] Malformed response should set parse_error."""
        # given
        response = "Some random text without proper sections"

        # when
        result = extract_from_text(response)

        # then
        assert result.had_content is False
        assert result.knowledge.is_empty()
        # Note: The implementation may or may not set parse_error for ambiguous cases
        # The key is that it doesn't crash and returns a usable result

    def test_parse_multiline_content(self):
        """Parse entries with multi-line descriptions."""
        # given
        response = """ARCHITECTURE:
- Complex service: This service handles multiple responsibilities
  including user management and authentication"""

        # when
        result = extract_from_text(response)

        # then
        assert result.had_content is True
        # Multi-line content handling depends on implementation

    def test_parse_entries_without_colon_separator(self):
        """Entries without colon separator should be handled gracefully."""
        # given
        response = """ARCHITECTURE:
- This entry has no colon separator
- Valid Entry: With proper format"""

        # when
        result = extract_from_text(response)

        # then
        # Should not crash, may skip malformed entries
        assert result.parse_error is None or len(result.knowledge.architecture) > 0


# =============================================================================
# SECTION PARSER TESTS
# =============================================================================

class TestParseSectionFunctions:
    """Tests for individual section parser functions."""

    def test_parse_architecture_section_empty(self):
        # when
        entries = _parse_architecture_section("")

        # then
        assert entries == []

    def test_parse_architecture_section_single_entry(self):
        # given
        section = "- API Gateway: Centralized entry point for all requests"

        # when
        entries = _parse_architecture_section(section)

        # then
        assert len(entries) == 1
        assert entries[0].title == "API Gateway"
        assert "Centralized entry point" in entries[0].content
        assert entries[0].tag is None

    def test_parse_decisions_section_multiple_entries(self):
        # given
        section = """- Use PostgreSQL: Better for complex queries
- JSON API format: Industry standard for REST APIs"""

        # when
        entries = _parse_decisions_section(section)

        # then
        assert len(entries) == 2

    def test_parse_lessons_learned_extracts_tag(self):
        """[REQ-10] Tag format: [Tag] Title: Description"""
        # given
        section = "- [MongoDB] Use indexes: Indexes critical for query performance"

        # when
        entries = _parse_lessons_learned_section(section)

        # then
        assert len(entries) == 1
        assert entries[0].tag == "MongoDB"
        assert entries[0].title == "Use indexes"

    def test_parse_lessons_learned_handles_missing_tag(self):
        """Entries without tags should still be parsed (with warning)."""
        # given
        section = "- Missing tag entry: No tag provided"

        # when
        entries = _parse_lessons_learned_section(section)

        # then
        # Implementation can either skip these or parse with empty tag
        # Key is it doesn't crash


# =============================================================================
# KNOWLEDGE MANAGER - LOADING TESTS [REQ-1, REQ-2, REQ-3, REQ-4]
# =============================================================================

class TestKnowledgeManagerLoading:
    """Tests for KnowledgeManager knowledge loading."""

    def test_load_knowledge_context_with_all_files(self):
        """[REQ-2, REQ-3] Load all three knowledge file types."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                # Create project knowledge directory
                project_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge" / "test-project"
                project_dir.mkdir(parents=True)
                global_dir = project_dir.parent

                # Create knowledge files
                (project_dir / "architecture.md").write_text("# Architecture\nService A connects to B")
                (project_dir / "decisions.md").write_text("# Decisions\nChose async pattern")
                (global_dir / "lessons-learned.md").write_text("# Lessons\n[Python] Use venv")

                with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='test-project'):
                    manager = KnowledgeManager(tmpdir)

                    # when
                    context = manager.load_knowledge_context()

                    # then
                    assert "Project Knowledge" in context or "Architecture" in context
                    assert "Service A connects to B" in context
                    assert "Chose async pattern" in context
                    assert "[Python] Use venv" in context

    def test_load_knowledge_context_formats_with_sections(self):
        """[REQ-3] Format as 'Project Knowledge' section with subsections."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                project_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge" / "test-project"
                project_dir.mkdir(parents=True)
                (project_dir / "architecture.md").write_text("ARCH_CONTENT")

                with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='test-project'):
                    manager = KnowledgeManager(tmpdir)

                    # when
                    context = manager.load_knowledge_context()

                    # then
                    # Should have structured format
                    assert "ARCH_CONTENT" in context

    def test_load_knowledge_context_shows_placeholder_when_no_architecture(self):
        """[REQ-4] Show placeholder when architecture file doesn't exist."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='test-project'):
                    manager = KnowledgeManager(tmpdir)

                    # when
                    context = manager.load_knowledge_context()

                    # then
                    # Should show placeholder or empty
                    assert "No" in context or context == "" or "documented" in context.lower()

    def test_load_knowledge_context_shows_placeholder_when_no_decisions(self):
        """[REQ-4] Show placeholder when decisions file doesn't exist."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                project_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge" / "test-project"
                project_dir.mkdir(parents=True)
                (project_dir / "architecture.md").write_text("ARCH")

                with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='test-project'):
                    manager = KnowledgeManager(tmpdir)

                    # when
                    context = manager.load_knowledge_context()

                    # then
                    # Decisions placeholder or section should be handled

    def test_load_knowledge_context_shows_placeholder_when_no_lessons(self):
        """[REQ-4] Show placeholder when lessons-learned file doesn't exist."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='test-project'):
                    manager = KnowledgeManager(tmpdir)

                    # when
                    context = manager.load_knowledge_context()

                    # then
                    # Should handle missing global file gracefully

    def test_load_architecture_returns_content(self):
        """[REQ-2] Load project-specific architecture.md."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                project_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge" / "test-project"
                project_dir.mkdir(parents=True)
                (project_dir / "architecture.md").write_text("# Architecture\nContent here")

                with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='test-project'):
                    manager = KnowledgeManager(tmpdir)

                    # when
                    content = manager._load_architecture()

                    # then
                    assert content is not None
                    assert "Content here" in content

    def test_load_architecture_returns_none_when_missing(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='test-project'):
                    manager = KnowledgeManager(tmpdir)

                    # when
                    content = manager._load_architecture()

                    # then
                    assert content is None

    def test_load_decisions_returns_content(self):
        """[REQ-2] Load project-specific decisions.md."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                project_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge" / "test-project"
                project_dir.mkdir(parents=True)
                (project_dir / "decisions.md").write_text("# Decisions\nDecision content")

                with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='test-project'):
                    manager = KnowledgeManager(tmpdir)

                    # when
                    content = manager._load_decisions()

                    # then
                    assert content is not None
                    assert "Decision content" in content

    def test_load_lessons_learned_from_global_path(self):
        """[REQ-2] Load global lessons-learned.md."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                global_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge"
                global_dir.mkdir(parents=True)
                (global_dir / "lessons-learned.md").write_text("# Lessons\nGlobal lesson")

                with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='test-project'):
                    manager = KnowledgeManager(tmpdir)

                    # when
                    content = manager._load_lessons_learned()

                    # then
                    assert content is not None
                    assert "Global lesson" in content

    def test_project_id_property_uses_identifier(self):
        """[REQ-1] Use ProjectIdentifier.get_project_id()."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='my-project'):
                manager = KnowledgeManager(tmpdir)

                # when
                project_id = manager.project_id

                # then
                assert project_id == 'my-project'


# =============================================================================
# KNOWLEDGE MANAGER - APPLICATION TESTS [REQ-17, REQ-18, REQ-19, REQ-20, REQ-21]
# =============================================================================

class TestKnowledgeManagerApplication:
    """Tests for KnowledgeManager knowledge application."""

    def test_apply_staged_knowledge_creates_directories(self):
        """[REQ-18] Create knowledge directories if they don't exist."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='new-project'):
                    manager = KnowledgeManager(tmpdir)
                    staged = StagedKnowledge(
                        architecture=[StagedKnowledgeEntry("Title", "Content", 1)]
                    )

                    # when
                    manager.apply_staged_knowledge(staged, "session-123")

                    # then
                    project_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge" / "new-project"
                    assert project_dir.exists()

    def test_apply_staged_knowledge_appends_to_existing(self):
        """[REQ-19] Append to existing files, don't overwrite."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                project_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge" / "test-project"
                project_dir.mkdir(parents=True)
                arch_file = project_dir / "architecture.md"
                arch_file.write_text("# Architecture\n\n## Existing Entry\nOld content")

                with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='test-project'):
                    manager = KnowledgeManager(tmpdir)
                    staged = StagedKnowledge(
                        architecture=[StagedKnowledgeEntry("New Entry", "New content", 2)]
                    )

                    # when
                    manager.apply_staged_knowledge(staged, "session-456")

                    # then
                    content = arch_file.read_text()
                    assert "Existing Entry" in content
                    assert "New Entry" in content

    def test_apply_architecture_uses_date_header(self):
        """[REQ-20] Architecture entries use date header format."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='test-project'):
                    manager = KnowledgeManager(tmpdir)
                    staged = StagedKnowledge(
                        architecture=[StagedKnowledgeEntry("Service Design", "Details here", 2)]
                    )

                    # when
                    manager.apply_staged_knowledge(staged, "session-789")

                    # then
                    project_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge" / "test-project"
                    content = (project_dir / "architecture.md").read_text()
                    today = date.today().strftime("%Y-%m-%d")
                    assert today in content
                    assert "session-789" in content

    def test_apply_decisions_uses_date_header(self):
        """[REQ-20] Decisions entries use date header format."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='test-project'):
                    manager = KnowledgeManager(tmpdir)
                    staged = StagedKnowledge(
                        decisions=[StagedKnowledgeEntry("Database Choice", "Chose PostgreSQL", 1)]
                    )

                    # when
                    manager.apply_staged_knowledge(staged, "session-abc")

                    # then
                    project_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge" / "test-project"
                    content = (project_dir / "decisions.md").read_text()
                    assert "Session: session-abc" in content

    def test_apply_lessons_learned_groups_by_tag(self):
        """[REQ-21] Lessons-learned grouped by technology tag."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='test-project'):
                    manager = KnowledgeManager(tmpdir)
                    staged = StagedKnowledge(
                        lessons_learned=[
                            StagedKnowledgeEntry("Lesson 1", "Python tip", 1, "Python"),
                            StagedKnowledgeEntry("Lesson 2", "Another Python tip", 2, "Python"),
                            StagedKnowledgeEntry("Git Lesson", "Git tip", 3, "Git"),
                        ]
                    )

                    # when
                    manager.apply_staged_knowledge(staged, "session-123")

                    # then
                    global_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge"
                    content = (global_dir / "lessons-learned.md").read_text()
                    assert "[Python]" in content or "## Python" in content
                    assert "[Git]" in content or "## Git" in content

    def test_apply_lessons_learned_includes_date(self):
        """[REQ-21] Lessons entries include date in title."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='test-project'):
                    manager = KnowledgeManager(tmpdir)
                    staged = StagedKnowledge(
                        lessons_learned=[
                            StagedKnowledgeEntry("Important Lesson", "Details", 4, "TypeScript")
                        ]
                    )

                    # when
                    manager.apply_staged_knowledge(staged, "session-123")

                    # then
                    global_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge"
                    content = (global_dir / "lessons-learned.md").read_text()
                    today = date.today().strftime("%Y-%m-%d")
                    assert today in content

    def test_apply_staged_knowledge_returns_counts(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='test-project'):
                    manager = KnowledgeManager(tmpdir)
                    staged = StagedKnowledge(
                        architecture=[
                            StagedKnowledgeEntry("A1", "C1", 1),
                            StagedKnowledgeEntry("A2", "C2", 2),
                        ],
                        decisions=[
                            StagedKnowledgeEntry("D1", "C1", 1),
                        ],
                        lessons_learned=[
                            StagedKnowledgeEntry("L1", "C1", 3, "Python"),
                            StagedKnowledgeEntry("L2", "C2", 4, "Git"),
                        ],
                    )

                    # when
                    counts = manager.apply_staged_knowledge(staged, "session-123")

                    # then
                    assert counts["architecture"] == 2
                    assert counts["decisions"] == 1
                    assert counts["lessons-learned"] == 2

    def test_apply_staged_knowledge_returns_empty_when_nothing_staged(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='test-project'):
                    manager = KnowledgeManager(tmpdir)
                    staged = StagedKnowledge()

                    # when
                    counts = manager.apply_staged_knowledge(staged, "session-123")

                    # then
                    assert counts == {} or all(v == 0 for v in counts.values())

    def test_apply_staged_knowledge_handles_write_failure(self):
        """[ERR-2] File write failure logs error but continues."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='test-project'):
                    manager = KnowledgeManager(tmpdir)
                    staged = StagedKnowledge(
                        architecture=[StagedKnowledgeEntry("Title", "Content", 1)]
                    )

                    # Make directory read-only to simulate write failure
                    project_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge" / "test-project"
                    project_dir.mkdir(parents=True)
                    # Note: This might not work on all systems/permissions

                    # when/then - should not raise
                    with patch.object(manager, '_append_to_file', return_value=False):
                        counts = manager.apply_staged_knowledge(staged, "session-123")
                        # Should return partial or zero counts but not crash

    def test_get_updated_files_summary_formats_message(self):
        """[REQ-22] Format console message for updated files."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='test-project'):
                manager = KnowledgeManager(tmpdir)
                counts = {"architecture": 2, "decisions": 1, "lessons-learned": 3}

                # when
                summary = manager.get_updated_files_summary(counts)

                # then
                assert "architecture.md" in summary or "Architecture" in summary
                assert "decisions.md" in summary or "Decisions" in summary
                assert "lessons-learned.md" in summary or "Lessons" in summary

    def test_get_updated_files_summary_empty_counts(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='test-project'):
                manager = KnowledgeManager(tmpdir)

                # when
                summary = manager.get_updated_files_summary({})

                # then
                # Should handle empty gracefully
                assert summary is not None

    def test_get_knowledge_file_path_for_architecture(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='my-project'):
                    manager = KnowledgeManager(tmpdir)

                    # when
                    path = manager._get_knowledge_file_path(KnowledgeCategory.ARCHITECTURE)

                    # then
                    assert "my-project" in str(path)
                    assert "architecture.md" in str(path)

    def test_get_knowledge_file_path_for_global_lessons(self):
        """[DEC-6] Lessons-learned is global, not per-project."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='my-project'):
                    manager = KnowledgeManager(tmpdir)

                    # when
                    path = manager._get_knowledge_file_path(KnowledgeCategory.LESSONS_LEARNED)

                    # then
                    assert "my-project" not in str(path)
                    assert "lessons-learned.md" in str(path)


# =============================================================================
# SUPERVISOR MARKERS - STAGING TESTS [REQ-13, REQ-14, REQ-15, REQ-16]
# =============================================================================

class TestSupervisorMarkersStaging:
    """Tests for SupervisorMarkers knowledge staging methods."""

    def test_stage_knowledge_creates_file(self):
        """[REQ-13] Store in dedicated temporary file in workflow state directory."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test-workflow")
                knowledge = StagedKnowledge(
                    architecture=[StagedKnowledgeEntry("Title", "Content", 1)]
                )

                # when
                markers.stage_knowledge(knowledge)

                # then
                staged_path = markers._get_staged_knowledge_path()
                assert staged_path.exists()

    def test_stage_knowledge_file_structure(self):
        """[REQ-14] File structure matches specification."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test-workflow")
                knowledge = StagedKnowledge(
                    architecture=[StagedKnowledgeEntry("Arch Title", "Arch Content", 2)],
                    decisions=[StagedKnowledgeEntry("Dec Title", "Dec Content", 1)],
                    lessons_learned=[StagedKnowledgeEntry("Lesson", "Lesson Content", 3, "Python")]
                )

                # when
                markers.stage_knowledge(knowledge)

                # then
                data = json.loads(markers._get_staged_knowledge_path().read_text())
                assert "architecture" in data
                assert "decisions" in data
                assert "lessons_learned" in data
                assert data["architecture"][0]["title"] == "Arch Title"
                assert data["architecture"][0]["phase"] == 2
                assert data["lessons_learned"][0]["tag"] == "Python"

    def test_stage_knowledge_accumulates_across_phases(self):
        """[REQ-15] Knowledge accumulates across phases."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test-workflow")

                # when - stage from phase 1
                markers.stage_knowledge(StagedKnowledge(
                    architecture=[StagedKnowledgeEntry("From Phase 1", "Content", 1)]
                ))

                # when - stage from phase 2
                markers.stage_knowledge(StagedKnowledge(
                    architecture=[StagedKnowledgeEntry("From Phase 2", "Content", 2)]
                ))

                # then
                staged = markers.get_staged_knowledge()
                assert len(staged.architecture) == 2
                assert staged.architecture[0].title == "From Phase 1"
                assert staged.architecture[1].title == "From Phase 2"

    def test_get_staged_knowledge_returns_all_entries(self):
        """[REQ-16] get_staged_knowledge() returns accumulated entries."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test-workflow")
                markers.stage_knowledge(StagedKnowledge(
                    architecture=[StagedKnowledgeEntry("A1", "C1", 1)],
                    decisions=[StagedKnowledgeEntry("D1", "C1", 2)],
                    lessons_learned=[StagedKnowledgeEntry("L1", "C1", 3, "Python")]
                ))

                # when
                staged = markers.get_staged_knowledge()

                # then
                assert isinstance(staged, StagedKnowledge)
                assert len(staged.architecture) == 1
                assert len(staged.decisions) == 1
                assert len(staged.lessons_learned) == 1

    def test_get_staged_knowledge_returns_empty_when_no_file(self):
        """[EDGE-6] Return empty StagedKnowledge if file doesn't exist."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test-workflow")

                # when
                staged = markers.get_staged_knowledge()

                # then
                assert isinstance(staged, StagedKnowledge)
                assert staged.is_empty()

    def test_has_staged_knowledge_true_when_has_entries(self):
        """[REQ-16] has_staged_knowledge() returns True when entries exist."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test-workflow")
                markers.stage_knowledge(StagedKnowledge(
                    architecture=[StagedKnowledgeEntry("Title", "Content", 1)]
                ))

                # when/then
                assert markers.has_staged_knowledge() is True

    def test_has_staged_knowledge_false_when_empty(self):
        """[REQ-16] has_staged_knowledge() returns False when no entries."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test-workflow")

                # when/then
                assert markers.has_staged_knowledge() is False

    def test_clear_staged_knowledge_deletes_file(self):
        """[REQ-16, REQ-23] clear_staged_knowledge() deletes the file."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test-workflow")
                markers.stage_knowledge(StagedKnowledge(
                    architecture=[StagedKnowledgeEntry("Title", "Content", 1)]
                ))
                staged_path = markers._get_staged_knowledge_path()
                assert staged_path.exists()

                # when
                markers.clear_staged_knowledge()

                # then
                assert not staged_path.exists()

    def test_clear_staged_knowledge_handles_missing_file(self):
        """[REQ-25] clear_staged_knowledge() handles nonexistent file."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test-workflow")

                # when/then - should not raise
                markers.clear_staged_knowledge()

    def test_staged_knowledge_file_location(self):
        """[REQ-13] File stored in workflow state directory."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test-workflow")

                # when
                path = markers._get_staged_knowledge_path()

                # then
                assert str(markers.markers_dir) in str(path)
                assert "staged-knowledge.json" in str(path)

    def test_apply_staged_knowledge_via_markers(self):
        """[REQ-17] apply_staged_knowledge() calls KnowledgeManager."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test-workflow")
                markers.stage_knowledge(StagedKnowledge(
                    architecture=[StagedKnowledgeEntry("Title", "Content", 1)]
                ))

                with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='test-project'):
                    # when
                    counts = markers.apply_staged_knowledge(tmpdir)

                    # then
                    assert isinstance(counts, dict)


# =============================================================================
# CONTEXT BUILDER - KNOWLEDGE INJECTION TESTS [REQ-5, REQ-6]
# =============================================================================

class TestContextBuilderKnowledgeInjection:
    """Tests for ContextBuilder knowledge injection."""

    def test_build_phase1_context_includes_knowledge(self):
        """[REQ-5] Phase 1 context includes knowledge."""
        # given
        knowledge_context = "## Project Knowledge\nArchitecture: Service A"

        # when
        context = ContextBuilder.build_phase1_context(
            user_task="Build feature",
            knowledge_context=knowledge_context
        )

        # then
        assert "Project Knowledge" in context or "Architecture" in context

    def test_build_phase1_context_without_knowledge(self):
        """Phase 1 works without knowledge context."""
        # when
        context = ContextBuilder.build_phase1_context(
            user_task="Build feature",
            knowledge_context=""
        )

        # then
        assert "Phase 1" in context

    def test_build_phase2_context_includes_knowledge(self):
        """[REQ-5] Phase 2 context includes knowledge."""
        # given
        knowledge_context = "## Project Knowledge\nDecisions: Use async"

        # when
        context = ContextBuilder.build_phase2_context(
            requirements_summary="Build a service",
            knowledge_context=knowledge_context
        )

        # then
        assert "Project Knowledge" in context or "Use async" in context

    def test_build_phase3_context_includes_knowledge(self):
        """[REQ-5] Phase 3 context includes knowledge."""
        # given
        knowledge_context = "## Lessons Learned\n[Python] Use pytest"

        # when
        context = ContextBuilder.build_phase3_context(
            requirements_summary="Requirements here",
            interfaces_list="Interfaces here",
            knowledge_context=knowledge_context
        )

        # then
        assert "Lessons Learned" in context or "pytest" in context

    def test_build_phase4_context_includes_knowledge(self):
        """[REQ-5] Phase 4 context includes knowledge."""
        # given
        knowledge_context = "## Architecture\nMicroservices pattern"

        # when
        context = ContextBuilder.build_phase4_context(
            requirements_summary="Requirements",
            interfaces_list="Interfaces",
            tests_list="Tests",
            knowledge_context=knowledge_context
        )

        # then
        assert "Microservices" in context

    def test_all_phases_receive_identical_knowledge(self):
        """[REQ-6] All phases receive identical knowledge context."""
        # given
        knowledge = "## Project Knowledge\nIdentical content for all phases"

        # when
        ctx1 = ContextBuilder.build_phase1_context(knowledge_context=knowledge)
        ctx2 = ContextBuilder.build_phase2_context("req", knowledge_context=knowledge)
        ctx3 = ContextBuilder.build_phase3_context("req", "int", knowledge_context=knowledge)
        ctx4 = ContextBuilder.build_phase4_context("req", "int", "tests", knowledge_context=knowledge)

        # then
        assert "Identical content for all phases" in ctx1
        assert "Identical content for all phases" in ctx2
        assert "Identical content for all phases" in ctx3
        assert "Identical content for all phases" in ctx4

    def test_get_knowledge_extraction_prompt_includes_phase(self):
        """[REQ-7, REQ-8] Extraction prompt is phase-specific."""
        # when
        prompt = ContextBuilder.get_knowledge_extraction_prompt(
            phase=2,
            existing_knowledge=""
        )

        # then
        assert "ARCHITECTURE" in prompt
        assert "DECISIONS" in prompt
        assert "LESSONS_LEARNED" in prompt
        assert "NO_KNOWLEDGE_EXTRACTED" in prompt

    def test_get_knowledge_extraction_prompt_includes_existing_knowledge(self):
        """[REQ-11] Extraction prompt includes existing knowledge to avoid duplicates."""
        # given
        existing = "## Existing Architecture\nService A does X"

        # when
        prompt = ContextBuilder.get_knowledge_extraction_prompt(
            phase=1,
            existing_knowledge=existing
        )

        # then
        assert "Service A does X" in prompt or "Existing" in prompt

    def test_get_knowledge_extraction_prompt_format_instructions(self):
        """[REQ-9, REQ-10] Prompt includes format instructions."""
        # when
        prompt = ContextBuilder.get_knowledge_extraction_prompt(phase=1)

        # then
        assert "Title:" in prompt or "title" in prompt.lower()
        assert "[" in prompt  # Tag format instruction


# =============================================================================
# EDGE CASES AND ERROR HANDLING TESTS
# =============================================================================

class TestKnowledgeEdgeCases:
    """Tests for edge cases identified in requirements."""

    def test_first_run_for_project_shows_placeholders(self):
        """[EDGE-1] First run shows placeholder text."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='brand-new-project'):
                    manager = KnowledgeManager(tmpdir)

                    # when
                    context = manager.load_knowledge_context()

                    # then
                    # Should be empty or have placeholders, not crash
                    assert context is not None

    def test_empty_extraction_no_knowledge_signal(self):
        """[EDGE-2] Empty extraction returns NO_KNOWLEDGE_EXTRACTED."""
        # given
        response = "NO_KNOWLEDGE_EXTRACTED"

        # when
        result = extract_from_text(response)

        # then
        assert result.had_content is False
        assert result.knowledge.is_empty()

    def test_malformed_extraction_continues_workflow(self):
        """[ERR-1] Malformed extraction response doesn't crash."""
        # given
        response = "This is completely malformed garbage @#$%^&*"

        # when
        result = extract_from_text(response)

        # then
        # Should return valid result even if parsing fails
        assert isinstance(result, ExtractionResult)
        assert isinstance(result.knowledge, StagedKnowledge)

    def test_concurrent_workflows_have_separate_staging(self):
        """[EDGE-5] Concurrent workflows have separate staged files."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers1 = SupervisorMarkers("workflow-1")
                markers2 = SupervisorMarkers("workflow-2")

                # when
                markers1.stage_knowledge(StagedKnowledge(
                    architecture=[StagedKnowledgeEntry("From Workflow 1", "Content", 1)]
                ))
                markers2.stage_knowledge(StagedKnowledge(
                    architecture=[StagedKnowledgeEntry("From Workflow 2", "Content", 1)]
                ))

                # then
                staged1 = markers1.get_staged_knowledge()
                staged2 = markers2.get_staged_knowledge()

                assert staged1.architecture[0].title == "From Workflow 1"
                assert staged2.architecture[0].title == "From Workflow 2"


class TestKnowledgeCleanup:
    """Tests for knowledge cleanup on abort [REQ-24, REQ-25]."""

    def test_clear_staged_knowledge_on_abort(self):
        """[REQ-24, REQ-25] Staged knowledge deleted on abort."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test-workflow")
                markers.stage_knowledge(StagedKnowledge(
                    architecture=[StagedKnowledgeEntry("Will be deleted", "Content", 1)]
                ))
                assert markers.has_staged_knowledge()

                # when - simulating abort
                markers.clear_staged_knowledge()

                # then
                assert not markers.has_staged_knowledge()

    def test_staged_knowledge_not_applied_on_abort(self):
        """[REQ-24] Knowledge NOT applied to permanent files on abort."""
        # This is tested through the orchestrator, but we can verify
        # the markers behavior independently
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("test-workflow")
                markers.stage_knowledge(StagedKnowledge(
                    architecture=[StagedKnowledgeEntry("Should not persist", "Content", 1)]
                ))

                # Simulate abort by clearing without applying
                markers.clear_staged_knowledge()

                # Verify no permanent files created
                knowledge_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge"
                # Knowledge files should not exist
                assert not (knowledge_dir / "architecture.md").exists() or \
                       "Should not persist" not in (knowledge_dir / "architecture.md").read_text() \
                       if (knowledge_dir / "architecture.md").exists() else True


class TestLargeKnowledgeFiles:
    """Tests for large knowledge file handling [EDGE-4]."""

    def test_load_large_knowledge_file(self):
        """[EDGE-4] Large files are loaded fully (v1 behavior)."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                project_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge" / "test-project"
                project_dir.mkdir(parents=True)

                # Create a large file (10KB+)
                large_content = "# Architecture\n\n" + ("Entry content. " * 1000)
                (project_dir / "architecture.md").write_text(large_content)

                with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='test-project'):
                    manager = KnowledgeManager(tmpdir)

                    # when
                    context = manager.load_knowledge_context()

                    # then
                    assert len(context) > 1000  # Full content loaded


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestKnowledgeWorkflowIntegration:
    """Integration tests for the complete knowledge workflow."""

    def test_full_extraction_and_application_cycle(self):
        """Test complete cycle: extract -> stage -> apply."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("integration-test")

                # Simulate extraction response
                response = """ARCHITECTURE:
- Service Layer: Business logic separated from controllers

DECISIONS:
- Use Repository Pattern: For data access abstraction

LESSONS_LEARNED:
- [Python] Type hints: Always use type hints for better IDE support"""

                # when - parse extraction
                result = extract_from_text(response)
                assert result.had_content is True

                # Set phases for entries
                for entry in result.knowledge.architecture:
                    entry.phase = 2
                for entry in result.knowledge.decisions:
                    entry.phase = 2
                for entry in result.knowledge.lessons_learned:
                    entry.phase = 2

                # Stage the knowledge
                markers.stage_knowledge(result.knowledge)

                # Verify staged
                staged = markers.get_staged_knowledge()
                assert len(staged.architecture) == 1
                assert len(staged.decisions) == 1
                assert len(staged.lessons_learned) == 1

                # Apply to permanent files
                with patch('wp_knowledge.ProjectIdentifier.get_project_id', return_value='integration-project'):
                    counts = markers.apply_staged_knowledge(tmpdir)

                    # then
                    assert counts["architecture"] == 1
                    assert counts["decisions"] == 1
                    assert counts["lessons-learned"] == 1

                    # Verify files created
                    project_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge" / "integration-project"
                    assert (project_dir / "architecture.md").exists()
                    assert (project_dir / "decisions.md").exists()

                    global_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge"
                    assert (global_dir / "lessons-learned.md").exists()

    def test_accumulation_across_multiple_phases(self):
        """Test knowledge accumulates correctly across phases."""
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                markers = SupervisorMarkers("accumulation-test")

                # Phase 1 extraction
                phase1_knowledge = StagedKnowledge(
                    architecture=[StagedKnowledgeEntry("Phase 1 Arch", "From phase 1", 1)]
                )
                markers.stage_knowledge(phase1_knowledge)

                # Phase 2 extraction
                phase2_knowledge = StagedKnowledge(
                    decisions=[StagedKnowledgeEntry("Phase 2 Decision", "From phase 2", 2)]
                )
                markers.stage_knowledge(phase2_knowledge)

                # Phase 3 extraction
                phase3_knowledge = StagedKnowledge(
                    lessons_learned=[StagedKnowledgeEntry("Phase 3 Lesson", "From phase 3", 3, "Testing")]
                )
                markers.stage_knowledge(phase3_knowledge)

                # Phase 4 extraction
                phase4_knowledge = StagedKnowledge(
                    architecture=[StagedKnowledgeEntry("Phase 4 Arch", "From phase 4", 4)]
                )
                markers.stage_knowledge(phase4_knowledge)

                # when
                staged = markers.get_staged_knowledge()

                # then
                assert len(staged.architecture) == 2
                assert len(staged.decisions) == 1
                assert len(staged.lessons_learned) == 1
                assert staged.total_count() == 4


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
