#!/usr/bin/env python3
"""
Unit tests for pattern_matcher.py
"""

import sys
import pytest

# Add hooks/lib to path
sys.path.insert(0, 'hooks/lib')
from pattern_matcher import glob_to_regex, matches_pattern, matches_any


class TestGlobToRegex:
    """Tests for glob_to_regex function."""

    def test_simple_extension(self):
        regex = glob_to_regex("*.py")
        assert regex == r'^(?:.*/)?[^/]*\.py$'

    def test_double_star_directory(self):
        regex = glob_to_regex("src/**/*.ts")
        assert "(?:.*/)?" in regex

    def test_question_mark_single_char(self):
        regex = glob_to_regex("test?.py")
        assert "[^/]" in regex

    def test_escapes_special_chars(self):
        regex = glob_to_regex("file[1].txt")
        assert r"\[1\]" in regex

    def test_double_star_at_end(self):
        regex = glob_to_regex("src/**")
        assert ".*" in regex


class TestMatchesPattern:
    """Tests for matches_pattern function."""

    def test_matches_extension(self):
        assert matches_pattern("src/main.py", "*.py") is True

    def test_does_not_match_wrong_extension(self):
        assert matches_pattern("src/main.ts", "*.py") is False

    def test_matches_nested_path(self):
        assert matches_pattern("src/components/Button.tsx", "**/*.tsx") is True

    def test_matches_directory_pattern(self):
        assert matches_pattern("src/test/Main.java", "src/test/*.java") is True

    def test_matches_question_mark(self):
        assert matches_pattern("test1.py", "test?.py") is True
        assert matches_pattern("test12.py", "test?.py") is False

    def test_matches_specific_filename(self):
        assert matches_pattern("package.json", "package.json") is True
        assert matches_pattern("other.json", "package.json") is False


class TestMatchesAny:
    """Tests for matches_any function."""

    def test_matches_string_pattern(self):
        assert matches_any("main.py", "*.py") is True

    def test_matches_json_array_pattern(self):
        assert matches_any("main.py", '["*.py", "*.ts"]') is True
        assert matches_any("main.ts", '["*.py", "*.ts"]') is True
        assert matches_any("main.js", '["*.py", "*.ts"]') is False

    def test_matches_list_pattern(self):
        assert matches_any("main.py", ["*.py", "*.ts"]) is True
        assert matches_any("main.ts", ["*.py", "*.ts"]) is True

    def test_no_match_returns_false(self):
        assert matches_any("main.rb", ["*.py", "*.ts"]) is False

    def test_empty_patterns_list(self):
        assert matches_any("main.py", []) is False

    def test_matches_first_pattern(self):
        assert matches_any("test.py", ["*.py", "*.ts"]) is True

    def test_matches_second_pattern(self):
        assert matches_any("test.ts", ["*.py", "*.ts"]) is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
