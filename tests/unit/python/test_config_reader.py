#!/usr/bin/env python3
"""
Unit tests for config_reader.py
"""

import json
import sys
import tempfile
import pytest

# Add hooks/lib to path
sys.path.insert(0, 'hooks/lib')
from config_reader import get_config_value


class TestGetConfigValue:
    """Tests for get_config_value function."""

    def test_reads_simple_value(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"name": "test"}, f)
            f.flush()
            result = get_config_value("name", f.name)
            assert result == "test"

    def test_reads_nested_value(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"profiles": {"kotlin": {"name": "Kotlin"}}}, f)
            f.flush()
            result = get_config_value("profiles.kotlin.name", f.name)
            assert result == "Kotlin"

    def test_reads_deeply_nested_value(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "profiles": {
                    "typescript-npm": {
                        "commands": {
                            "compile": "npm run build"
                        }
                    }
                }
            }, f)
            f.flush()
            result = get_config_value("profiles.typescript-npm.commands.compile", f.name)
            assert result == "npm run build"

    def test_returns_dict_for_object_path(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"profiles": {"kotlin": {"name": "Kotlin", "version": "1.9"}}}, f)
            f.flush()
            result = get_config_value("profiles.kotlin", f.name)
            assert result == {"name": "Kotlin", "version": "1.9"}

    def test_returns_list_for_array_path(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"patterns": ["*.py", "*.ts"]}, f)
            f.flush()
            result = get_config_value("patterns", f.name)
            assert result == ["*.py", "*.ts"]

    def test_returns_none_for_missing_path(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"name": "test"}, f)
            f.flush()
            result = get_config_value("nonexistent.path", f.name)
            assert result is None

    def test_returns_none_for_partial_path(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"profiles": {"kotlin": {"name": "Kotlin"}}}, f)
            f.flush()
            result = get_config_value("profiles.kotlin.commands.compile", f.name)
            assert result is None

    def test_returns_none_for_missing_file(self):
        result = get_config_value("name", "/nonexistent/file.json")
        assert result is None

    def test_returns_none_for_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json {")
            f.flush()
            result = get_config_value("name", f.name)
            assert result is None

    def test_returns_none_when_traversing_non_dict(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"name": "test"}, f)
            f.flush()
            result = get_config_value("name.subkey", f.name)
            assert result is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
