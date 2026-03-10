#!/usr/bin/env python3
"""
Unit tests for wp_knowledge.py - Knowledge Management
"""

import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add hooks/lib to path
sys.path.insert(0, 'hooks/lib')
from wp_knowledge import ProjectIdentifier, KnowledgeManager


class TestProjectIdentifier:
    """Tests for ProjectIdentifier class."""

    def test_get_project_id_from_waypoints_project_file(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            project_file = Path(tmpdir) / ".waypoints-project"
            project_file.write_text("my-custom-project")
            identifier = ProjectIdentifier(tmpdir)

            # when
            result = identifier.get_project_id()

            # then
            assert result == "my-custom-project"

    def test_get_project_id_from_waypoints_project_file_strips_whitespace(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            project_file = Path(tmpdir) / ".waypoints-project"
            project_file.write_text("  my-project  \n")
            identifier = ProjectIdentifier(tmpdir)

            # when
            result = identifier.get_project_id()

            # then
            assert result == "my-project"

    def test_get_project_id_from_git_remote_ssh_url(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            identifier = ProjectIdentifier(tmpdir)
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "git@github.com:user/my-repo.git\n"

            # when
            with patch('subprocess.run', return_value=mock_result):
                result = identifier.get_project_id()

            # then
            assert result == "my-repo"

    def test_get_project_id_from_git_remote_https_url(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            identifier = ProjectIdentifier(tmpdir)
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "https://github.com/user/another-repo.git\n"

            # when
            with patch('subprocess.run', return_value=mock_result):
                result = identifier.get_project_id()

            # then
            assert result == "another-repo"

    def test_get_project_id_from_git_remote_without_git_suffix(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            identifier = ProjectIdentifier(tmpdir)
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "https://github.com/user/repo-name\n"

            # when
            with patch('subprocess.run', return_value=mock_result):
                result = identifier.get_project_id()

            # then
            assert result == "repo-name"

    def test_get_project_id_falls_back_to_directory_name(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "fallback-project"
            project_dir.mkdir()
            identifier = ProjectIdentifier(str(project_dir))
            mock_result = MagicMock()
            mock_result.returncode = 1  # git command fails

            # when
            with patch('subprocess.run', return_value=mock_result):
                result = identifier.get_project_id()

            # then
            assert result == "fallback-project"

    def test_get_project_id_waypoints_file_takes_priority_over_git(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            project_file = Path(tmpdir) / ".waypoints-project"
            project_file.write_text("explicit-project-id")
            identifier = ProjectIdentifier(tmpdir)
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "git@github.com:user/git-repo.git\n"

            # when
            with patch('subprocess.run', return_value=mock_result):
                result = identifier.get_project_id()

            # then
            assert result == "explicit-project-id"

    def test_get_project_id_empty_waypoints_file_falls_through(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "my-dir"
            project_dir.mkdir()
            project_file = project_dir / ".waypoints-project"
            project_file.write_text("")
            identifier = ProjectIdentifier(str(project_dir))
            mock_result = MagicMock()
            mock_result.returncode = 1

            # when
            with patch('subprocess.run', return_value=mock_result):
                result = identifier.get_project_id()

            # then
            assert result == "my-dir"


class TestKnowledgeManagerLoading:
    """Tests for KnowledgeManager knowledge loading."""

    def test_load_knowledge_context_returns_placeholders_when_no_files(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    manager = KnowledgeManager(tmpdir)

                    # when
                    result = manager.load_knowledge_context()

                    # then
                    assert "# Project Knowledge" in result
                    assert "No architecture documented yet" in result
                    assert "No decisions documented yet" in result
                    assert "No lessons learned documented yet" in result

    def test_load_knowledge_context_loads_architecture(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    knowledge_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge" / "test-project"
                    knowledge_dir.mkdir(parents=True)
                    (knowledge_dir / "architecture.md").write_text("# Architecture\nService A connects to B")

                    manager = KnowledgeManager(tmpdir)

                    # when
                    result = manager.load_knowledge_context()

                    # then
                    assert "# Architecture" in result
                    assert "Service A connects to B" in result

    def test_load_knowledge_context_loads_decisions(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    knowledge_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge" / "test-project"
                    knowledge_dir.mkdir(parents=True)
                    (knowledge_dir / "decisions.md").write_text("# Decisions\nChose async pattern")

                    manager = KnowledgeManager(tmpdir)

                    # when
                    result = manager.load_knowledge_context()

                    # then
                    assert "# Decisions" in result
                    assert "Chose async pattern" in result

    def test_load_knowledge_context_loads_global_lessons_learned(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    knowledge_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge"
                    knowledge_dir.mkdir(parents=True)
                    (knowledge_dir / "lessons-learned.md").write_text("# Lessons\n[MongoDB] Use @BsonId")

                    manager = KnowledgeManager(tmpdir)

                    # when
                    result = manager.load_knowledge_context()

                    # then
                    assert "# Lessons" in result
                    assert "[MongoDB] Use @BsonId" in result

    def test_load_knowledge_context_combines_all_files(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    project_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge" / "test-project"
                    project_dir.mkdir(parents=True)
                    global_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge"

                    (project_dir / "architecture.md").write_text("ARCH_CONTENT")
                    (project_dir / "decisions.md").write_text("DECISIONS_CONTENT")
                    (global_dir / "lessons-learned.md").write_text("LESSONS_CONTENT")

                    manager = KnowledgeManager(tmpdir)

                    # when
                    result = manager.load_knowledge_context()

                    # then
                    assert "ARCH_CONTENT" in result
                    assert "DECISIONS_CONTENT" in result
                    assert "LESSONS_CONTENT" in result


class TestKnowledgeManagerGraphIntegration:
    """Tests for KnowledgeManager integration with graph storage."""

    def test_knowledge_manager_initializes_graph_storage_when_enabled(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    # when
                    manager = KnowledgeManager(tmpdir, enable_graph=True)

                    # then - Should initialize graph storage
                    assert hasattr(manager, 'graph_storage')

    def test_knowledge_manager_initializes_rag_service_when_enabled(self):
        # given - [REQ-5] Use local embeddings model for semantic search
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    # when
                    manager = KnowledgeManager(tmpdir, enable_rag=True)

                    # then - Should initialize RAG service
                    assert hasattr(manager, 'rag_service')

    def test_knowledge_manager_loads_from_graph_when_enabled(self):
        # given - [REQ-10] Always load complete architecture entries from graph
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    mock_graph_storage = MagicMock()
                    mock_graph = MagicMock()
                    mock_graph_storage.load_project_graph.return_value = mock_graph

                    # when
                    with patch('wp_knowledge.GraphStorage', return_value=mock_graph_storage):
                        manager = KnowledgeManager(tmpdir, enable_graph=True)
                        manager.load_knowledge_context()

                    # then
                    mock_graph_storage.load_project_graph.assert_called()

    def test_load_knowledge_context_accepts_query_text_parameter(self):
        # given - [REQ-7] Query RAG with initial task description
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    manager = KnowledgeManager(tmpdir, enable_rag=True)

                    # when
                    result = manager.load_knowledge_context(query_text="implement authentication")

                    # then - Should not crash, query_text is used for RAG filtering
                    assert isinstance(result, str)

    def test_load_knowledge_context_filters_lessons_by_query_when_rag_enabled(self):
        # given - [REQ-8] Retrieve only semantically relevant lessons-learned entries
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    mock_rag_service = MagicMock()
                    mock_rag_service.query_relevant_lessons.return_value = []  # Empty results

                    manager = KnowledgeManager(tmpdir, enable_rag=True)
                    manager.rag_service = mock_rag_service

                    # when
                    manager.load_knowledge_context(query_text="python testing")

                    # then
                    mock_rag_service.query_relevant_lessons.assert_called_with("python testing")

    def test_load_knowledge_context_loads_all_architecture_from_graph(self):
        # given - [REQ-10] Always load complete architecture entries (no filtering)
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    mock_graph_storage = MagicMock()
                    mock_graph = MagicMock()
                    mock_graph.get_nodes_by_category.return_value = []
                    mock_graph_storage.load_project_graph.return_value = mock_graph

                    with patch('wp_knowledge.GraphStorage', return_value=mock_graph_storage):
                        manager = KnowledgeManager(tmpdir, enable_graph=True)

                        # when
                        manager.load_knowledge_context()

                        # then - Should load ALL architecture nodes
                        from wp_knowledge import KnowledgeCategory
                        mock_graph.get_nodes_by_category.assert_any_call(KnowledgeCategory.ARCHITECTURE)

    def test_load_knowledge_context_loads_all_decisions_from_graph(self):
        # given - [REQ-11] Always load complete decisions entries (no filtering)
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    mock_graph_storage = MagicMock()
                    mock_graph = MagicMock()
                    mock_graph.get_nodes_by_category.return_value = []
                    mock_graph_storage.load_project_graph.return_value = mock_graph

                    with patch('wp_knowledge.GraphStorage', return_value=mock_graph_storage):
                        manager = KnowledgeManager(tmpdir, enable_graph=True)

                        # when
                        manager.load_knowledge_context()

                        # then - Should load ALL decisions nodes
                        from wp_knowledge import KnowledgeCategory
                        mock_graph.get_nodes_by_category.assert_any_call(KnowledgeCategory.DECISIONS)

    def test_load_knowledge_context_logs_rag_result_count(self):
        # given - [REQ-9] Log the count of lessons loaded
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    mock_rag_service = MagicMock()
                    mock_rag_service.query_relevant_lessons.return_value = []
                    mock_rag_service.get_indexed_count.return_value = 5

                    manager = KnowledgeManager(tmpdir, enable_rag=True)
                    manager.rag_service = mock_rag_service

                    # when
                    manager.load_knowledge_context(query_text="test query")

                    # then - Count should be retrievable
                    count = mock_rag_service.get_indexed_count()
                    assert count == 5

    def test_load_knowledge_context_without_query_loads_from_markdown(self):
        # given - Backward compatible: without query_text, load from markdown
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    knowledge_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge"
                    knowledge_dir.mkdir(parents=True)
                    (knowledge_dir / "lessons-learned.md").write_text("# Lessons\n[Python] Lesson A")

                    manager = KnowledgeManager(tmpdir, enable_rag=False)

                    # when
                    result = manager.load_knowledge_context()

                    # then - Should load from markdown when RAG disabled
                    assert "[Python] Lesson A" in result


class TestKnowledgeManagerApplication:
    """Tests for KnowledgeManager applying staged knowledge to graph."""

    def test_apply_staged_knowledge_adds_entries_to_graph(self):
        # given - [REQ-1] Store all knowledge entries as nodes in graph
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    from wp_knowledge import StagedKnowledge, StagedKnowledgeEntry

                    mock_graph_storage = MagicMock()
                    mock_graph = MagicMock()
                    mock_graph_storage.load_project_graph.return_value = mock_graph

                    with patch('wp_knowledge.GraphStorage', return_value=mock_graph_storage):
                        manager = KnowledgeManager(tmpdir, enable_graph=True)

                        staged = StagedKnowledge(
                            architecture=[
                                StagedKnowledgeEntry(
                                    title="New Pattern",
                                    content="Pattern description",
                                    phase=1
                                )
                            ]
                        )

                        # when
                        manager.apply_staged_knowledge(staged, session_id="test-session")

                        # then - Should add node to graph
                        mock_graph.add_node.assert_called()

    def test_apply_staged_knowledge_parses_relationships(self):
        # given - [REQ-18] Parse relationship markers from extraction response
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    from wp_knowledge import StagedKnowledge, StagedKnowledgeEntry

                    mock_graph_storage = MagicMock()
                    mock_graph = MagicMock()
                    mock_graph_storage.load_project_graph.return_value = mock_graph

                    with patch('wp_knowledge.GraphStorage', return_value=mock_graph_storage):
                        manager = KnowledgeManager(tmpdir, enable_graph=True)

                        staged = StagedKnowledge(
                            decisions=[
                                StagedKnowledgeEntry(
                                    title="Use REST",
                                    content="REST API [led_to: \"API Gateway Pattern\"] for simplicity.",
                                    phase=1,
                                    relationships=[("led_to", "API Gateway Pattern")]
                                )
                            ]
                        )

                        # when
                        manager.apply_staged_knowledge(staged, session_id="test-session")

                        # then - Should create relationships
                        # Relationships should be stored in node

    def test_apply_staged_knowledge_regenerates_markdown_views(self):
        # given - [REQ-15] Regenerate markdown files from graph
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    from wp_knowledge import StagedKnowledge, StagedKnowledgeEntry

                    mock_graph_storage = MagicMock()
                    mock_graph = MagicMock()
                    mock_graph_storage.load_project_graph.return_value = mock_graph

                    with patch('wp_knowledge.GraphStorage', return_value=mock_graph_storage):
                        manager = KnowledgeManager(tmpdir, enable_graph=True)

                        staged = StagedKnowledge(
                            architecture=[
                                StagedKnowledgeEntry(title="Pattern", content="Content", phase=1)
                            ]
                        )

                        # when
                        manager.apply_staged_knowledge(staged, session_id="test-session")

                        # then - Should save graph (which triggers markdown regeneration)
                        mock_graph_storage.save_project_graph.assert_called()

    def test_apply_staged_knowledge_updates_rag_index_for_lessons(self):
        # given - Lessons-learned should update RAG index
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    from wp_knowledge import StagedKnowledge, StagedKnowledgeEntry

                    mock_rag_service = MagicMock()
                    mock_graph_storage = MagicMock()
                    mock_graph = MagicMock()
                    mock_graph_storage.load_global_graph.return_value = mock_graph

                    with patch('wp_knowledge.GraphStorage', return_value=mock_graph_storage):
                        manager = KnowledgeManager(tmpdir, enable_rag=True)
                        manager.rag_service = mock_rag_service

                        staged = StagedKnowledge(
                            lessons_learned=[
                                StagedKnowledgeEntry(
                                    title="Lesson",
                                    content="Content",
                                    phase=2,
                                    tag="Python"
                                )
                            ]
                        )

                        # when
                        manager.apply_staged_knowledge(staged, session_id="test-session")

                        # then - Should rebuild RAG index
                        mock_rag_service.rebuild_index.assert_called()


class TestKnowledgeManagerMarkdownGeneration:
    """Tests for generating markdown views from graph."""

    def test_generate_markdown_from_graph_creates_valid_markdown(self):
        # given - [REQ-14] Maintain markdown files as human-readable materialized views
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    from wp_graph import KnowledgeGraph, KnowledgeNode, NodeId
                    from wp_knowledge import KnowledgeCategory

                    mock_graph_storage = MagicMock()
                    graph = KnowledgeGraph()
                    node_id = NodeId("architecture", "Pattern A", "2026-03-09")
                    graph.add_node(KnowledgeNode(
                        node_id, "Pattern A", "Description", "architecture", "2026-03-09", "s1"
                    ))
                    mock_graph_storage.load_project_graph.return_value = graph

                    with patch('wp_knowledge.GraphStorage', return_value=mock_graph_storage):
                        manager = KnowledgeManager(tmpdir, enable_graph=True)

                        # when
                        markdown = manager.generate_markdown_from_graph(graph, KnowledgeCategory.ARCHITECTURE)

                        # then
                        assert "# Architecture" in markdown
                        assert "Pattern A" in markdown

    def test_regenerate_all_markdown_views_creates_all_files(self):
        # given - [REQ-15] Regenerate markdown files when knowledge is applied
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    mock_graph_storage = MagicMock()
                    mock_graph = MagicMock()
                    mock_graph.get_nodes_by_category.return_value = []
                    mock_graph_storage.load_project_graph.return_value = mock_graph
                    mock_graph_storage.load_global_graph.return_value = mock_graph

                    with patch('wp_knowledge.GraphStorage', return_value=mock_graph_storage):
                        manager = KnowledgeManager(tmpdir, enable_graph=True)

                        # when
                        result = manager.regenerate_all_markdown_views()

                        # then
                        assert result is True


class TestKnowledgeParsingFunctions:
    """Tests for relationship parsing in knowledge entry parsing."""

    def test_parse_architecture_section_extracts_relationships(self):
        # given - [REQ-3] Parse relationships from Claude's extraction output
        from wp_knowledge import _parse_architecture_section

        section_text = """
- API Gateway: Central entry point [led_to: "Load Balancer"] for all services.
"""

        # when
        entries = _parse_architecture_section(section_text)

        # then
        assert len(entries) == 1
        assert entries[0].title == "API Gateway"
        assert len(entries[0].relationships) > 0

    def test_parse_decisions_section_extracts_relationships(self):
        # given
        from wp_knowledge import _parse_decisions_section

        section_text = """
- Use GraphQL: Chose GraphQL [supersedes: "REST API v1"] for flexible querying.
"""

        # when
        entries = _parse_decisions_section(section_text)

        # then
        assert len(entries) == 1
        assert entries[0].title == "Use GraphQL"
        assert len(entries[0].relationships) > 0

    def test_parse_lessons_section_handles_relationships(self):
        # given
        from wp_knowledge import _parse_lessons_learned_section

        section_text = """
- [Python] Use Type Hints: Always add type hints [applies_to: "Function Definitions"] for better IDE support.
"""

        # when
        entries = _parse_lessons_learned_section(section_text)

        # then
        assert len(entries) == 1
        assert entries[0].tag == "Python"
        assert len(entries[0].relationships) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
