#!/usr/bin/env python3
"""
Unit tests for profile_detector.py
"""

import json
import sys
import tempfile
import pytest
from pathlib import Path

# Add hooks/lib to path
sys.path.insert(0, 'hooks/lib')
from profile_detector import get_override, detect_profile


class TestGetOverride:
    """Tests for get_override function."""

    def test_reads_active_profile(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"activeProfile": "kotlin-maven"}, f)
            f.flush()
            result = get_override(f.name)
            assert result == "kotlin-maven"

    def test_returns_empty_for_missing_profile(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"otherKey": "value"}, f)
            f.flush()
            result = get_override(f.name)
            assert result == ""

    def test_returns_empty_for_null_profile(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"activeProfile": None}, f)
            f.flush()
            result = get_override(f.name)
            assert result == ""

    def test_returns_empty_for_empty_string_profile(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"activeProfile": ""}, f)
            f.flush()
            result = get_override(f.name)
            assert result == ""

    def test_returns_empty_for_missing_file(self):
        result = get_override("/nonexistent/file.json")
        assert result == ""

    def test_returns_empty_for_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("not valid json {")
            f.flush()
            result = get_override(f.name)
            assert result == ""


class TestDetectProfile:
    """Tests for detect_profile function."""

    def test_detects_based_on_files(self):
        with tempfile.TemporaryDirectory() as project_dir:
            # Create detection file
            Path(project_dir, "package.json").touch()

            # Create config file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump({
                    "profiles": {
                        "typescript-npm": {
                            "detection": {
                                "files": ["package.json"],
                                "patterns": []
                            }
                        }
                    }
                }, f)
                f.flush()
                result = detect_profile(project_dir, f.name)
                assert result == "typescript-npm"

    def test_detects_based_on_patterns(self):
        with tempfile.TemporaryDirectory() as project_dir:
            # Create source file matching pattern
            src_dir = Path(project_dir, "src")
            src_dir.mkdir()
            (src_dir / "main.py").touch()

            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump({
                    "profiles": {
                        "python-pytest": {
                            "detection": {
                                "files": [],
                                "patterns": ["*.py"]
                            }
                        }
                    }
                }, f)
                f.flush()
                result = detect_profile(project_dir, f.name)
                assert result == "python-pytest"

    def test_returns_highest_scoring_profile(self):
        with tempfile.TemporaryDirectory() as project_dir:
            # Create files that match both profiles
            Path(project_dir, "package.json").touch()
            Path(project_dir, "pom.xml").touch()
            Path(project_dir, "build.gradle").touch()  # Extra point for kotlin

            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump({
                    "profiles": {
                        "typescript-npm": {
                            "detection": {
                                "files": ["package.json"],
                                "patterns": []
                            }
                        },
                        "kotlin-maven": {
                            "detection": {
                                "files": ["pom.xml", "build.gradle"],
                                "patterns": []
                            }
                        }
                    }
                }, f)
                f.flush()
                result = detect_profile(project_dir, f.name)
                # Kotlin should win with 2 files (20 points) vs TypeScript 1 file (10 points)
                assert result == "kotlin-maven"

    def test_returns_empty_for_no_match(self):
        with tempfile.TemporaryDirectory() as project_dir:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump({
                    "profiles": {
                        "typescript-npm": {
                            "detection": {
                                "files": ["package.json"],
                                "patterns": []
                            }
                        }
                    }
                }, f)
                f.flush()
                result = detect_profile(project_dir, f.name)
                assert result == ""

    def test_returns_empty_for_missing_config(self):
        with tempfile.TemporaryDirectory() as project_dir:
            result = detect_profile(project_dir, "/nonexistent/config.json")
            assert result == ""

    def test_returns_empty_for_invalid_config(self):
        with tempfile.TemporaryDirectory() as project_dir:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                f.write("invalid json")
                f.flush()
                result = detect_profile(project_dir, f.name)
                assert result == ""

    def test_handles_empty_profiles(self):
        with tempfile.TemporaryDirectory() as project_dir:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump({"profiles": {}}, f)
                f.flush()
                result = detect_profile(project_dir, f.name)
                assert result == ""


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
