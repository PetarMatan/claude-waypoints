#!/usr/bin/env python3
"""
Waypoints Orchestrator - Stop Hook

Build verification hook: runs compile/test commands and blocks on failures.
Phase transitions and agent loading are handled by wp-activation.py.
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


def block_with_error(reason: str) -> None:
    """Output a block response for build errors.

    For Stop hooks, decision: "block" means Claude cannot stop and must continue.
    This should only be used for actual errors (compile/test failures).
    """
    output = {
        "decision": "block",
        "reason": reason
    }
    print(json.dumps(output, indent=2))


def run_command(cmd: str, timeout: int = 120) -> tuple:
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


def format_compile_error(output: str, profile: str, cmd: str) -> str:
    """Format a compile error message."""
    return f"""## Compilation FAILED ({profile})

**Command:** `{cmd}`

**Output:**
```
{output[:2000]}
```

Fix the compilation errors and try again."""


def format_test_failure(output: str, profile: str) -> str:
    """Format a test failure message."""
    return f"""## Tests FAILED ({profile})

**Output:**
```
{output[:2000]}
```

Fix the failing tests and try again."""


def main():
    # Parse hook input
    hook = HookInput.from_stdin()

    # Initialize components
    markers = MarkerManager(hook.session_id)
    logger = WPLogger(hook.session_id)

    # Prevent infinite loops
    if hook.stop_hook_active:
        return

    # Check if Waypoints mode is active
    if not markers.is_wp_active():
        return

    # Get current phase
    current_phase = markers.get_phase()

    # Phase 1: No build verification needed
    if current_phase == 1:
        return

    # Change to project directory for running commands
    if not hook.cwd or not os.path.isdir(hook.cwd):
        return

    os.chdir(hook.cwd)

    # Initialize config
    config = WPConfig(hook.cwd)
    profile_name = config.get_profile_name()

    # Get commands
    compile_cmd = config.get_command("compile")
    test_compile_cmd = config.get_command("testCompile")
    test_cmd = config.get_command("test")

    logger.log_build(f"Phase {current_phase} stop hook triggered", f"profile: {profile_name}")

    # Helper to check if command has unreplaced placeholders
    def has_placeholder(cmd: str) -> bool:
        return "{file}" in cmd or "{testClass}" in cmd or "{testName}" in cmd or "{testFile}" in cmd

    # Phase 2: Verify interfaces compile
    if current_phase == 2:
        if compile_cmd and not has_placeholder(compile_cmd):
            logger.log_build(f"Running: {compile_cmd}")
            exit_code, output = run_command(compile_cmd)
            if exit_code != 0:
                logger.log_wp("Phase 2: Compile FAILED")
                block_with_error(format_compile_error(output, profile_name, compile_cmd))
                return
            logger.log_wp("Phase 2: Compile OK")
        return

    # Phase 3: Verify tests compile
    if current_phase == 3:
        test_compile = test_compile_cmd or compile_cmd
        if test_compile and not has_placeholder(test_compile):
            logger.log_build(f"Running: {test_compile}")
            exit_code, output = run_command(test_compile)
            if exit_code != 0:
                logger.log_wp("Phase 3: Test compile FAILED")
                block_with_error(format_compile_error(output, profile_name, test_compile))
                return
            logger.log_wp("Phase 3: Test compile OK")
        return

    # Phase 4: Verify compile passes and tests pass
    if current_phase == 4:
        # Check compile (skip if command requires a specific file)
        if compile_cmd and not has_placeholder(compile_cmd):
            logger.log_build(f"Running: {compile_cmd}")
            exit_code, output = run_command(compile_cmd)
            if exit_code != 0:
                logger.log_wp("Phase 4: Compile FAILED")
                block_with_error(format_compile_error(output, profile_name, compile_cmd))
                return
            logger.log_wp("Phase 4: Compile OK")

        # Check tests
        if test_cmd and not has_placeholder(test_cmd):
            logger.log_build(f"Running: {test_cmd}")
            exit_code, output = run_command(test_cmd, timeout=300)
            if exit_code != 0:
                logger.log_wp("Phase 4: Tests FAILED")
                block_with_error(format_test_failure(output, profile_name))
                return
            logger.log_wp("Phase 4: Tests OK")

        # Both compile and tests pass - Waypoints complete!
        logger.log_wp("Phase 4 COMPLETE: All builds and tests passing")
        print(">>> Waypoints: All tests passing! Workflow complete.", file=sys.stderr)

        # Mark implementation complete and cleanup
        markers.mark_implementation_complete()
        markers.cleanup_workflow_state()
        return


if __name__ == '__main__':
    main()
