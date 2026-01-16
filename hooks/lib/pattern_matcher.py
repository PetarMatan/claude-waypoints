#!/usr/bin/env python3
"""
Pattern Matcher Library for Waypoints Workflow
Provides glob-to-regex conversion and file pattern matching.

Usage:
    from pattern_matcher import matches_any, matches_pattern, glob_to_regex
    if matches_any(file_path, ["*.py", "*.ts"]):
        print("Match found")
"""

import re
import json


def glob_to_regex(pattern):
    """
    Convert a glob pattern to a regex pattern.

    Supports:
    - ** matches zero or more directories
    - * matches anything except /
    - ? matches single character except /
    """
    # Escape special regex chars except * and ?
    regex = re.escape(pattern)

    # Unescape the glob special chars we want to handle
    regex = regex.replace(r'\*\*', '__DOUBLE_STAR__')
    regex = regex.replace(r'\*', '__SINGLE_STAR__')
    regex = regex.replace(r'\?', '__QUESTION__')

    # Convert glob patterns to regex
    regex = regex.replace('__DOUBLE_STAR__/', '(?:.*/)?')  # **/ matches zero or more directories
    regex = regex.replace('__DOUBLE_STAR__', '.*')         # ** at end matches anything
    regex = regex.replace('__SINGLE_STAR__', '[^/]*')      # * matches anything except /
    regex = regex.replace('__QUESTION__', '[^/]')          # ? matches single char except /

    # Pattern should match the end of the path (with optional leading directories)
    return f'^(?:.*/)?{regex}$'


def matches_pattern(file_path, pattern):
    """Check if a file path matches a single glob pattern."""
    regex = glob_to_regex(pattern)
    return bool(re.match(regex, file_path))


def matches_any(file_path, patterns):
    """
    Check if a file path matches any of the given patterns.

    Args:
        file_path: The file path to check
        patterns: A single pattern string, JSON array string, or list of patterns

    Returns:
        True if file matches any pattern, False otherwise
    """
    # Handle different input formats
    if isinstance(patterns, str):
        if patterns.startswith('['):
            patterns = json.loads(patterns)
        else:
            patterns = [patterns]

    for pattern in patterns:
        if matches_pattern(file_path, pattern):
            return True
    return False


