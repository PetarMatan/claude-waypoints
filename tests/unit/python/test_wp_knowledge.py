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
from wp_knowledge import ProjectIdentifier, KnowledgeManager, StagedLearning


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

    def test_load_knowledge_context_returns_empty_when_no_files(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    manager = KnowledgeManager("session-123", tmpdir)

                    # when
                    result = manager.load_knowledge_context()

                    # then
                    assert result == ""

    def test_load_knowledge_context_loads_architecture(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    knowledge_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge" / "test-project"
                    knowledge_dir.mkdir(parents=True)
                    (knowledge_dir / "architecture.md").write_text("# Architecture\nService A connects to B")

                    manager = KnowledgeManager("session-123", tmpdir)

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

                    manager = KnowledgeManager("session-123", tmpdir)

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

                    manager = KnowledgeManager("session-123", tmpdir)

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

                    manager = KnowledgeManager("session-123", tmpdir)

                    # when
                    result = manager.load_knowledge_context()

                    # then
                    assert "ARCH_CONTENT" in result
                    assert "DECISIONS_CONTENT" in result
                    assert "LESSONS_CONTENT" in result


class TestKnowledgeManagerStaging:
    """Tests for KnowledgeManager staging functionality."""

    def test_stage_learning_creates_staging_file(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    manager = KnowledgeManager("session-123", tmpdir)
                    learning = StagedLearning(
                        category="architecture",
                        title="Service topology",
                        content="Service A calls Service B via REST",
                        source_phase=2
                    )

                    # when
                    manager.stage_learning(learning)

                    # then
                    staging_dir = Path(tmpdir) / ".claude" / "waypoints" / "staging" / "session-123"
                    assert staging_dir.exists()

    def test_get_staged_learnings_returns_staged_items(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    manager = KnowledgeManager("session-123", tmpdir)
                    learning1 = StagedLearning("architecture", "Title1", "Content1", 2)
                    learning2 = StagedLearning("decisions", "Title2", "Content2", 2)

                    # when
                    manager.stage_learning(learning1)
                    manager.stage_learning(learning2)
                    result = manager.get_staged_learnings()

                    # then
                    assert len(result) == 2
                    assert result[0].title == "Title1"
                    assert result[1].title == "Title2"

    def test_has_staged_learnings_returns_false_when_empty(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    manager = KnowledgeManager("session-123", tmpdir)

                    # when
                    result = manager.has_staged_learnings()

                    # then
                    assert result is False

    def test_has_staged_learnings_returns_true_when_has_items(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    manager = KnowledgeManager("session-123", tmpdir)
                    manager.stage_learning(StagedLearning("architecture", "Title", "Content", 2))

                    # when
                    result = manager.has_staged_learnings()

                    # then
                    assert result is True


class TestKnowledgeManagerMerging:
    """Tests for KnowledgeManager merging functionality."""

    def test_apply_staged_learnings_creates_architecture_file(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    manager = KnowledgeManager("session-123", tmpdir)
                    manager.stage_learning(StagedLearning(
                        "architecture", "Service A", "Handles user requests", 2
                    ))

                    # when
                    result = manager.apply_staged_learnings()

                    # then
                    arch_file = Path(tmpdir) / ".claude" / "waypoints" / "knowledge" / "test-project" / "architecture.md"
                    assert arch_file.exists()
                    content = arch_file.read_text()
                    assert "Service A" in content
                    assert result["architecture"] == 1

    def test_apply_staged_learnings_creates_decisions_file(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    manager = KnowledgeManager("session-123", tmpdir)
                    manager.stage_learning(StagedLearning(
                        "decisions", "Use async", "For better scalability", 1
                    ))

                    # when
                    result = manager.apply_staged_learnings()

                    # then
                    decisions_file = Path(tmpdir) / ".claude" / "waypoints" / "knowledge" / "test-project" / "decisions.md"
                    assert decisions_file.exists()
                    assert result["decisions"] == 1

    def test_apply_staged_learnings_creates_global_lessons_file(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    manager = KnowledgeManager("session-123", tmpdir)
                    manager.stage_learning(StagedLearning(
                        "lessons-learned", "[Kotlin] Coroutines", "Use structured concurrency", 4
                    ))

                    # when
                    result = manager.apply_staged_learnings()

                    # then
                    lessons_file = Path(tmpdir) / ".claude" / "waypoints" / "knowledge" / "lessons-learned.md"
                    assert lessons_file.exists()
                    content = lessons_file.read_text()
                    assert "[Kotlin] Coroutines" in content
                    assert result["lessons-learned"] == 1

    def test_apply_staged_learnings_appends_to_existing_file(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    knowledge_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge" / "test-project"
                    knowledge_dir.mkdir(parents=True)
                    arch_file = knowledge_dir / "architecture.md"
                    arch_file.write_text("# Architecture\n\n- Existing entry\n")

                    manager = KnowledgeManager("session-123", tmpdir)
                    manager.stage_learning(StagedLearning(
                        "architecture", "New service", "Does something new", 2
                    ))

                    # when
                    manager.apply_staged_learnings()

                    # then
                    content = arch_file.read_text()
                    assert "Existing entry" in content
                    assert "New service" in content

    def test_apply_staged_learnings_returns_correct_counts(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    manager = KnowledgeManager("session-123", tmpdir)
                    manager.stage_learning(StagedLearning("architecture", "T1", "C1", 2))
                    manager.stage_learning(StagedLearning("architecture", "T2", "C2", 2))
                    manager.stage_learning(StagedLearning("decisions", "T3", "C3", 1))
                    manager.stage_learning(StagedLearning("lessons-learned", "T4", "C4", 4))
                    manager.stage_learning(StagedLearning("lessons-learned", "T5", "C5", 4))
                    manager.stage_learning(StagedLearning("lessons-learned", "T6", "C6", 4))

                    # when
                    result = manager.apply_staged_learnings()

                    # then
                    assert result == {"architecture": 2, "decisions": 1, "lessons-learned": 3}

    def test_apply_staged_learnings_returns_empty_when_nothing_staged(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    manager = KnowledgeManager("session-123", tmpdir)

                    # when
                    result = manager.apply_staged_learnings()

                    # then
                    assert result == {}


class TestKnowledgeManagerCleanup:
    """Tests for KnowledgeManager cleanup functionality."""

    def test_cleanup_staging_removes_staging_directory(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    manager = KnowledgeManager("session-123", tmpdir)
                    manager.stage_learning(StagedLearning("architecture", "Title", "Content", 2))
                    staging_dir = Path(tmpdir) / ".claude" / "waypoints" / "staging" / "session-123"
                    assert staging_dir.exists()

                    # when
                    manager.cleanup_staging()

                    # then
                    assert not staging_dir.exists()

    def test_cleanup_staging_handles_nonexistent_directory(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    manager = KnowledgeManager("session-123", tmpdir)

                    # when/then - should not raise
                    manager.cleanup_staging()

    def test_cleanup_staging_does_not_affect_knowledge_files(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'home', return_value=Path(tmpdir)):
                with patch.object(ProjectIdentifier, 'get_project_id', return_value='test-project'):
                    knowledge_dir = Path(tmpdir) / ".claude" / "waypoints" / "knowledge" / "test-project"
                    knowledge_dir.mkdir(parents=True)
                    arch_file = knowledge_dir / "architecture.md"
                    arch_file.write_text("Important content")

                    manager = KnowledgeManager("session-123", tmpdir)
                    manager.stage_learning(StagedLearning("architecture", "Title", "Content", 2))

                    # when
                    manager.cleanup_staging()

                    # then
                    assert arch_file.exists()
                    assert arch_file.read_text() == "Important content"


class TestStagedLearning:
    """Tests for StagedLearning dataclass."""

    def test_staged_learning_creation(self):
        # when
        learning = StagedLearning(
            category="architecture",
            title="My Title",
            content="My Content",
            source_phase=2
        )

        # then
        assert learning.category == "architecture"
        assert learning.title == "My Title"
        assert learning.content == "My Content"
        assert learning.source_phase == 2

    def test_staged_learning_equality(self):
        # given
        learning1 = StagedLearning("architecture", "Title", "Content", 2)
        learning2 = StagedLearning("architecture", "Title", "Content", 2)

        # then
        assert learning1 == learning2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
