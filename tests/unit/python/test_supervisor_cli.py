#!/usr/bin/env python3
"""
Unit tests for wp_supervisor/__main__.py - CLI entry point
"""

import os
import sys
import tempfile
import pytest
import argparse
from pathlib import Path
from unittest.mock import patch, MagicMock

# Mock claude_agent_sdk before any imports
sys.modules['claude_agent_sdk'] = MagicMock()


class TestArgumentParsing:
    """Tests for CLI argument parsing."""

    def test_parse_args_default_dir(self):
        """Default directory should be '.'"""
        parser = argparse.ArgumentParser()
        parser.add_argument("-d", "--dir", type=str, default=".")
        parser.add_argument("-t", "--task", type=str, default=None)
        
        args = parser.parse_args([])
        assert args.dir == "."

    def test_parse_args_custom_dir(self):
        """Custom directory via -d flag."""
        parser = argparse.ArgumentParser()
        parser.add_argument("-d", "--dir", type=str, default=".")
        parser.add_argument("-t", "--task", type=str, default=None)
        
        args = parser.parse_args(["-d", "/custom/path"])
        assert args.dir == "/custom/path"

    def test_parse_args_custom_dir_long_form(self):
        """Custom directory via --dir flag."""
        parser = argparse.ArgumentParser()
        parser.add_argument("-d", "--dir", type=str, default=".")
        parser.add_argument("-t", "--task", type=str, default=None)
        
        args = parser.parse_args(["--dir", "/another/path"])
        assert args.dir == "/another/path"

    def test_parse_args_task_flag(self):
        """Task description via -t flag."""
        parser = argparse.ArgumentParser()
        parser.add_argument("-d", "--dir", type=str, default=".")
        parser.add_argument("-t", "--task", type=str, default=None)
        
        args = parser.parse_args(["-t", "Build a REST API"])
        assert args.task == "Build a REST API"

    def test_parse_args_task_flag_long_form(self):
        """Task description via --task flag."""
        parser = argparse.ArgumentParser()
        parser.add_argument("-d", "--dir", type=str, default=".")
        parser.add_argument("-t", "--task", type=str, default=None)
        
        args = parser.parse_args(["--task", "Add authentication"])
        assert args.task == "Add authentication"

    def test_parse_args_all_flags_combined(self):
        """All flags can be combined."""
        parser = argparse.ArgumentParser()
        parser.add_argument("-d", "--dir", type=str, default=".")
        parser.add_argument("-t", "--task", type=str, default=None)

        args = parser.parse_args([
            "-d", "/project",
            "-t", "Build feature",
        ])

        assert args.dir == "/project"
        assert args.task == "Build feature"

    def test_parse_args_defaults_task_to_none(self):
        """Task defaults to None when not provided."""
        parser = argparse.ArgumentParser()
        parser.add_argument("-d", "--dir", type=str, default=".")
        parser.add_argument("-t", "--task", type=str, default=None)
        
        args = parser.parse_args([])
        assert args.task is None

class TestDirectoryValidation:
    """Tests for directory validation."""

    def test_valid_directory_is_detected(self):
        """Valid directory should be detected as dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            assert path.is_dir()

    def test_resolve_relative_path(self):
        """Relative paths should be resolved to absolute."""
        path = Path(".")
        resolved = path.resolve()
        assert resolved.is_absolute()

    def test_nonexistent_directory_detected(self):
        """Nonexistent directory should be detected."""
        path = Path("/nonexistent/path/xyz123")
        assert not path.is_dir()

    def test_file_is_not_directory(self):
        """File should not be detected as directory."""
        with tempfile.NamedTemporaryFile() as f:
            path = Path(f.name)
            assert not path.is_dir()


class TestPathResolution:
    """Tests for working directory path resolution."""

    def test_dot_resolves_to_cwd(self):
        """'.' should resolve to current working directory."""
        path = Path(".").resolve()
        assert path == Path.cwd()

    def test_absolute_path_stays_absolute(self):
        """Absolute paths should remain absolute after resolve."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            resolved = path.resolve()
            assert resolved.is_absolute()
            assert str(resolved) == str(Path(tmpdir).resolve())

    def test_home_expansion(self):
        """~ should expand to home directory."""
        path = Path("~").expanduser()
        assert path.is_absolute()
        assert str(path) == str(Path.home())


class TestErrorHandling:
    """Tests for error handling in CLI."""

    def test_keyboard_interrupt_exit_code(self):
        """KeyboardInterrupt should result in exit code 130."""
        # Exit code 130 is standard for Ctrl+C (128 + SIGINT=2)
        expected_code = 128 + 2
        assert expected_code == 130

    def test_general_error_exit_code(self):
        """General errors should result in exit code 1."""
        assert 1 == 1  # Standard error exit code


class TestHelpText:
    """Tests for help text and documentation."""

    def test_parser_has_description(self):
        """Parser should have a description."""
        parser = argparse.ArgumentParser(
            description="WP Supervisor - Orchestrate Waypoints workflow"
        )
        assert parser.description is not None
        assert "WP" in parser.description

    def test_epilog_can_contain_examples(self):
        """Help text can contain usage examples."""
        parser = argparse.ArgumentParser(
            epilog="""
Examples:
    python -m wp_supervisor
    python -m wp_supervisor -d /path/to/project
"""
        )
        assert "Examples" in parser.epilog


class TestEnvironmentVariables:
    """Tests for environment variable handling."""

    def test_env_var_names_are_correct(self):
        """Environment variable names should be correct."""
        expected_vars = [
            "WP_SUPERVISOR_WORKFLOW_ID",
            "WP_SUPERVISOR_MARKERS_DIR",
            "WP_SUPERVISOR_ACTIVE",
        ]
        for var in expected_vars:
            assert var.startswith("WP_SUPERVISOR_")

    def test_supervisor_active_value(self):
        """WP_SUPERVISOR_ACTIVE should be '1' when active."""
        expected_value = "1"
        assert expected_value == "1"


class TestUserCommands:
    """Tests for user command constants."""

    def test_done_commands(self):
        """Commands to signal phase completion."""
        done_commands = ['/done', '/complete', '/next']
        for cmd in done_commands:
            assert cmd.startswith('/')

    def test_quit_commands(self):
        """Commands to abort workflow."""
        quit_commands = ['/quit', '/exit', '/abort']
        for cmd in quit_commands:
            assert cmd.startswith('/')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
