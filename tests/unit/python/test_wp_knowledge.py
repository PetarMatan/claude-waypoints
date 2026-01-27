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


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
