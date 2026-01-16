#!/usr/bin/env python3
"""
Settings Manager - Manages Claude Code settings.json for Waypoints workflow.

Usage from bash:
    # Add Waypoints hooks and permissions
    python3 settings_manager.py add /path/to/settings.json /path/to/install/dir

    # Remove Waypoints hooks and permissions
    python3 settings_manager.py remove /path/to/settings.json

    # Validate settings.json
    python3 settings_manager.py validate /path/to/settings.json
"""

import json
import os
import sys
import tempfile
from typing import Any, Dict, List


# Waypoints permissions to add/remove
WP_PERMISSIONS = [
    "Bash(mkdir -p ~/.claude/tmp:*)",
    "Bash(mkdir -p ~/.claude/tmp &&:*)",
    "Bash(touch ~/.claude/tmp/:*)",
    "Bash(echo:*)",
    "Bash(rm -f ~/.claude/tmp/wp-*:*)",
    "Bash(cat ~/.claude/tmp/:*)",
    "Bash(python3 $WP_INSTALL_DIR/hooks/lib/wp_cli.py:*)",
]


def get_wp_hooks(install_dir: str) -> Dict[str, List[Dict[str, Any]]]:
    """Generate Waypoints hook configurations for the given install directory."""
    return {
        "PreToolUse": [
            {
                "matcher": "Bash",
                "hooks": [{
                    "type": "command",
                    "command": f"python3 {install_dir}/hooks/wp-activation.py",
                    "timeout": 5000
                }]
            },
            {
                "matcher": "Write|Edit",
                "hooks": [{
                    "type": "command",
                    "command": f"python3 {install_dir}/hooks/wp-phase-guard.py",
                    "timeout": 5000
                }]
            }
        ],
        "PostToolUse": [
            {
                "matcher": "Write|Edit",
                "hooks": [{
                    "type": "command",
                    "command": f"python3 {install_dir}/hooks/wp-auto-compile.py",
                    "timeout": 120000
                }]
            },
            {
                "matcher": "Write|Edit",
                "hooks": [{
                    "type": "command",
                    "command": f"python3 {install_dir}/hooks/wp-auto-test.py",
                    "timeout": 300000
                }]
            }
        ],
        "Stop": [
            {
                "hooks": [{
                    "type": "command",
                    "command": f"python3 {install_dir}/hooks/wp-orchestrator.py",
                    "timeout": 120000
                }]
            }
        ],
        "SessionEnd": [
            {
                "hooks": [{
                    "type": "command",
                    "command": f"python3 {install_dir}/hooks/wp-cleanup-markers.py",
                    "timeout": 5000
                }]
            }
        ]
    }


def atomic_write(filepath: str, data: Dict[str, Any]) -> None:
    """Write JSON data to file atomically to prevent corruption."""
    settings_dir = os.path.dirname(filepath)
    with tempfile.NamedTemporaryFile(
        mode='w',
        dir=settings_dir,
        suffix='.json',
        delete=False
    ) as f:
        temp_file = f.name
        json.dump(data, f, indent=2)

    os.replace(temp_file, filepath)


def validate_settings(settings_file: str) -> bool:
    """Validate that a settings file is valid JSON."""
    try:
        with open(settings_file, 'r') as f:
            json.load(f)
        return True
    except (json.JSONDecodeError, FileNotFoundError):
        return False


def add_wp_settings(settings_file: str, install_dir: str) -> None:
    """
    Add Waypoints hooks and permissions to settings.json.

    Args:
        settings_file: Path to settings.json
        install_dir: Path to Waypoints workflow installation directory
    """
    with open(settings_file, 'r') as f:
        settings = json.load(f)

    # Ensure permissions structure exists
    if 'permissions' not in settings:
        settings['permissions'] = {}
    if 'allow' not in settings['permissions']:
        settings['permissions']['allow'] = []

    # Add Waypoints permissions if not present
    for perm in WP_PERMISSIONS:
        if perm not in settings['permissions']['allow']:
            settings['permissions']['allow'].append(perm)

    # Ensure hooks structure exists
    if 'hooks' not in settings:
        settings['hooks'] = {}

    # Get Waypoints hooks configuration
    wp_hooks = get_wp_hooks(install_dir)

    # Merge hooks (add Waypoints hooks, don't replace existing)
    for event, hooks in wp_hooks.items():
        if event not in settings['hooks']:
            settings['hooks'][event] = []

        # Collect existing commands to avoid duplicates
        existing_commands = set()
        for hook_config in settings['hooks'][event]:
            for h in hook_config.get('hooks', []):
                existing_commands.add(h.get('command', ''))

        # Add new hooks if not already present
        for hook in hooks:
            hook_cmd = hook['hooks'][0]['command']
            if hook_cmd not in existing_commands:
                settings['hooks'][event].append(hook)

    # Write atomically
    atomic_write(settings_file, settings)
    print("Settings updated successfully.")


def remove_wp_settings(settings_file: str) -> None:
    """
    Remove Waypoints hooks and permissions from settings.json.

    Args:
        settings_file: Path to settings.json
    """
    with open(settings_file, 'r') as f:
        settings = json.load(f)

    # Remove Waypoints-related permissions
    if 'permissions' in settings and 'allow' in settings['permissions']:
        settings['permissions']['allow'] = [
            p for p in settings['permissions']['allow']
            if p not in WP_PERMISSIONS
        ]

    # Remove Waypoints hooks
    if 'hooks' in settings:
        for event in list(settings['hooks'].keys()):
            if event in settings['hooks']:
                settings['hooks'][event] = [
                    hook_config for hook_config in settings['hooks'][event]
                    if not any(
                        'wp-' in h.get('command', '')
                        for h in hook_config.get('hooks', [])
                    )
                ]
                # Remove empty event lists
                if not settings['hooks'][event]:
                    del settings['hooks'][event]

    # Write atomically
    atomic_write(settings_file, settings)
    print("Waypoints hooks removed from settings.")


def main():
    if len(sys.argv) < 3:
        print("Usage: settings_manager.py <command> <settings_file> [install_dir]", file=sys.stderr)
        print("Commands: add, remove, validate", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    settings_file = sys.argv[2]

    if command == 'validate':
        if validate_settings(settings_file):
            print("Settings file is valid JSON.")
            sys.exit(0)
        else:
            print("Settings file is not valid JSON.", file=sys.stderr)
            sys.exit(1)

    elif command == 'add':
        if len(sys.argv) < 4:
            print("Usage: settings_manager.py add <settings_file> <install_dir>", file=sys.stderr)
            sys.exit(1)
        install_dir = sys.argv[3]
        add_wp_settings(settings_file, install_dir)

    elif command == 'remove':
        remove_wp_settings(settings_file)

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
