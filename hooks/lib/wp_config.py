#!/usr/bin/env python3
"""
Claude Waypoints - Configuration Library

Handles technology profile detection and configuration loading.
Wraps config_reader.py and profile_detector.py for easy use.
"""

import os
from pathlib import Path
from typing import Optional

# Import sibling modules (absolute imports for subprocess compatibility)
import config_reader
import profile_detector
import pattern_matcher


class WPConfig:
    """Configuration manager for Waypoints workflow."""

    def __init__(self, project_dir: str = "."):
        """Initialize config manager."""
        self.project_dir = os.path.abspath(project_dir)

        install_dir = os.environ.get(
            "WP_INSTALL_DIR",
            str(Path.home() / ".claude" / "waypoints")
        )
        self.config_file = os.environ.get(
            "WP_CONFIG_FILE",
            os.path.join(install_dir, "config", "wp-config.json")
        )
        self.override_file = os.environ.get(
            "WP_OVERRIDE_FILE",
            str(Path.home() / ".claude" / "wp-override.json")
        )

        self._detected_profile: Optional[str] = None

    def detect_profile(self) -> Optional[str]:
        """Detect technology profile based on project files."""
        if self._detected_profile is not None:
            return self._detected_profile

        # Check for override file first
        if os.path.exists(self.override_file):
            override = profile_detector.get_override(self.override_file)
            if override:
                self._detected_profile = override
                return override

        # Auto-detect based on project files
        detected = profile_detector.detect_profile(self.project_dir, self.config_file)
        if detected:
            self._detected_profile = detected
            return detected

        # Check for environment variable default
        default_profile = os.environ.get("WP_DEFAULT_PROFILE")
        if default_profile:
            self._detected_profile = default_profile
            return default_profile

        return None

    def get_profile_name(self) -> str:
        """Get human-readable profile name."""
        profile = self.detect_profile()
        if not profile:
            return "Unknown"

        name = config_reader.get_config_value(
            f"profiles.{profile}.name",
            self.config_file
        )
        return name or profile

    def get_command(self, command_name: str) -> Optional[str]:
        """Get command for current profile (compile, test, testCompile)."""
        profile = self.detect_profile()
        if not profile:
            return None

        return config_reader.get_config_value(
            f"profiles.{profile}.commands.{command_name}",
            self.config_file
        )

    def get_source_pattern(self, pattern_type: str) -> Optional[str]:
        """Get source pattern for current profile (main, test, config)."""
        profile = self.detect_profile()
        if not profile:
            return None

        return config_reader.get_config_value(
            f"profiles.{profile}.sourcePatterns.{pattern_type}",
            self.config_file
        )

    def is_main_source(self, file_path: str) -> bool:
        """Check if file matches main source pattern."""
        patterns = self.get_source_pattern("main")
        if not patterns:
            return False
        return pattern_matcher.matches_any(file_path, patterns)

    def is_test_source(self, file_path: str) -> bool:
        """Check if file matches test source pattern."""
        patterns = self.get_source_pattern("test")
        if not patterns:
            return False
        return pattern_matcher.matches_any(file_path, patterns)

    def is_config_file(self, file_path: str) -> bool:
        """Check if file matches config pattern."""
        patterns = self.get_source_pattern("config")
        if not patterns:
            return False
        return pattern_matcher.matches_any(file_path, patterns)

    def get_todo_placeholder(self) -> Optional[str]:
        """Get TODO placeholder for current profile."""
        profile = self.detect_profile()
        if not profile:
            return None

        return config_reader.get_config_value(
            f"profiles.{profile}.todoPlaceholder",
            self.config_file
        )
