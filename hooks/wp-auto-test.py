#!/usr/bin/env python3
"""
Waypoints Auto-Test Hook - PostToolUse

Runs compile + test cycle after file changes in Phase 4.
"""

import json
import os
import subprocess
import sys

# Add lib directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

from hook_io import HookInput
from markers import MarkerManager
from wp_logging import WPLogger
from wp_config import WPConfig
from formatters import format_phase4_compile_error, format_phase4_test_failure


def approve_with_message(reason: str, context: str) -> None:
    """Output an approve response with additional context message."""
    output = {
        "decision": "approve",
        "reason": reason,
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context
        }
    }
    print(json.dumps(output, indent=2))


def run_command(cmd: str, timeout: int = 300) -> tuple:
    """Run a shell command and return (exit_code, output)."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return 1, f"Command timed out after {timeout} seconds"
    except Exception as e:
        return 1, f"Command error: {e}"


def main():
    # Parse hook input
    hook = HookInput.from_stdin()

    # Initialize components
    markers = MarkerManager(hook.session_id)
    logger = WPLogger(hook.session_id)

    # Only process Write|Edit operations
    if hook.tool_name not in ("Write", "Edit"):
        return

    # Check if Waypoints mode is active
    if not markers.is_wp_active():
        return

    # Check if we're in Phase 4
    current_phase = markers.get_phase()
    if current_phase != 4:
        return

    # Change to project directory
    if not hook.cwd or not os.path.isdir(hook.cwd):
        return

    os.chdir(hook.cwd)

    # Initialize config
    config = WPConfig(hook.cwd)
    profile_name = config.get_profile_name()

    # Check if file is a source file
    is_source = config.is_main_source(hook.file_path) or config.is_test_source(hook.file_path)
    if not is_source:
        return

    # Get commands
    compile_cmd = config.get_command("compile")
    test_cmd = config.get_command("test")

    if not compile_cmd or not test_cmd:
        return

    # Substitute placeholders in commands
    compile_cmd = compile_cmd.replace("{file}", hook.file_path)
    test_cmd = test_cmd.replace("{file}", hook.file_path)

    logger.log_wp(f"Phase 4: Running compile + test cycle for {hook.file_path}")
    print(f">>> Waypoints Phase 4 ({profile_name}): Running compile + test cycle...", file=sys.stderr)

    # Run compilation
    compile_exit_code, compile_output = run_command(compile_cmd, timeout=120)

    if compile_exit_code != 0:
        logger.log_build("FAILED", "Waypoints Phase 4 compilation failed")
        print(">>> Waypoints: Compilation failed", file=sys.stderr)

        context = format_phase4_compile_error(compile_output, hook.file_path, profile_name)

        approve_with_message(
            f"Waypoints Phase 4 ({profile_name}): Compilation failed, fix immediately",
            context
        )
        return

    logger.log_build("SUCCESS", "Waypoints Phase 4 compilation passed")
    print(">>> Waypoints: Compilation passed, running tests...", file=sys.stderr)

    # Run tests
    test_exit_code, test_output = run_command(test_cmd, timeout=300)

    if test_exit_code != 0:
        logger.log_wp("Phase 4: Tests failed - continuing implementation")
        print(">>> Waypoints: Tests failed", file=sys.stderr)

        context = format_phase4_test_failure(test_output, hook.file_path, profile_name)

        approve_with_message(
            f"Waypoints Phase 4 ({profile_name}): Tests failing, continue implementing",
            context
        )
        return

    # Both passed!
    logger.log_wp("Phase 4: All tests passing!")
    print(">>> Waypoints: All tests passing!", file=sys.stderr)


if __name__ == '__main__':
    main()
