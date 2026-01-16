#!/usr/bin/env python3
"""
Hook I/O - Input parsing and response generation for Claude Code hooks.

Usage:
    from lib.hook_io import HookInput, approve_with_message
    hook = HookInput.from_stdin()
    print(hook.tool_name, hook.file_path)
"""

import json
import sys
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class HookInput:
    """Parsed hook input data."""
    tool_name: str
    file_path: str
    cwd: str
    session_id: str
    stop_hook_active: bool
    event_type: str
    hook_event_name: str
    raw_data: Dict[str, Any]

    @classmethod
    def from_stdin(cls) -> "HookInput":
        """Parse hook input from stdin."""
        try:
            data = json.load(sys.stdin)
        except json.JSONDecodeError:
            data = {}
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HookInput":
        """Parse hook input from a dictionary."""
        tool_input = data.get('tool_input', {})
        file_path = tool_input.get('file_path', '') if isinstance(tool_input, dict) else ''

        return cls(
            tool_name=data.get('tool_name', ''),
            file_path=file_path,
            cwd=data.get('cwd', ''),
            session_id=data.get('session_id', 'unknown'),
            stop_hook_active=data.get('stop_hook_active', False),
            event_type=data.get('event_type', ''),
            hook_event_name=data.get('hook_event_name', ''),
            raw_data=data,
        )


def approve_with_message(reason: str, hook_event: str, context: str) -> None:
    """
    Generate an approve response with additional context message.
    Used for cases like compile errors where we approve but want to show info.

    Args:
        reason: Short reason for the message
        hook_event: The hook event name (e.g., "PostToolUse")
        context: Detailed context/message to show
    """
    output = {
        "decision": "approve",
        "reason": reason,
        "hookSpecificOutput": {
            "hookEventName": hook_event,
            "additionalContext": context
        }
    }
    print(json.dumps(output, indent=2))


