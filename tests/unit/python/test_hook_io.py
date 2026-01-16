#!/usr/bin/env python3
"""
Unit tests for hook_io.py

Tests the hook input parsing and response generation functions.
"""

import json
import sys
import io
import pytest
from unittest.mock import patch

# Add the hooks/lib directory to the path
sys.path.insert(0, 'hooks/lib')
from hook_io import approve_with_message


class TestApproveWithMessage:
    """Tests for approve_with_message function."""

    def test_approve_with_context(self, capsys):
        approve_with_message(
            "Compilation failed",
            "PostToolUse",
            "## Error Details\n\nFix the errors."
        )

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output['decision'] == 'approve'
        assert output['reason'] == 'Compilation failed'
        assert output['hookSpecificOutput']['hookEventName'] == 'PostToolUse'
        assert '## Error Details' in output['hookSpecificOutput']['additionalContext']

    def test_approve_with_empty_context(self, capsys):
        approve_with_message("Info", "PreToolUse", "")

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output['decision'] == 'approve'
        assert output['hookSpecificOutput']['additionalContext'] == ''

    def test_output_structure(self, capsys):
        approve_with_message("reason", "event", "context")

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        # Verify complete structure
        assert set(output.keys()) == {'decision', 'reason', 'hookSpecificOutput'}
        assert set(output['hookSpecificOutput'].keys()) == {'hookEventName', 'additionalContext'}


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
