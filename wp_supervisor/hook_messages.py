#!/usr/bin/env python3
"""
Waypoints Supervisor - Hook Messages

Templates and strings for hook responses.
Extracted for readability and consistency with CLI mode.
"""

# Phase guard denial messages
PHASE1_BLOCK_REASON = (
    "Waypoints Phase 1: Cannot edit source files during requirements gathering. "
    "Complete requirements first, then advance to Phase 2."
)

PHASE2_BLOCK_REASON = (
    "Waypoints Phase 2: Cannot write tests during interface design. "
    "Design interfaces first, then advance to Phase 3 for test writing."
)

PHASE3_BLOCK_REASON = (
    "Waypoints Phase 3: Cannot edit implementation during test writing. "
    "Write tests first, then advance to Phase 4 for implementation."
)


def get_phase_block_reason(phase: int) -> str:
    """Get the block reason message for a given phase."""
    reasons = {
        1: PHASE1_BLOCK_REASON,
        2: PHASE2_BLOCK_REASON,
        3: PHASE3_BLOCK_REASON,
    }
    return reasons.get(phase, "")


# Log message templates
def log_phase_block(phase: int, file_path: str, reason: str) -> str:
    """Format a phase block log message."""
    return f"Phase {phase}: Blocked edit to {file_path} - {reason}"


LOG_REASONS = {
    1: "requirements gathering",
    2: "no tests during interface design",
    3: "no implementation during test writing",
}


def get_log_reason(phase: int) -> str:
    """Get the log reason for a phase block."""
    return LOG_REASONS.get(phase, "unknown")


# --- Build Verification Templates ---

COMPILE_ERROR_TEMPLATE = """## Compilation FAILED ({profile})

**Command:** `{cmd}`

**Output:**
```
{output}
```

Fix the compilation errors and try again."""


TEST_FAILURE_TEMPLATE = """## Tests FAILED ({profile})

**Output:**
```
{output}
```

Fix the failing tests and try again."""


def format_compile_error(output: str, profile: str, cmd: str) -> str:
    """Format a compile error message."""
    return COMPILE_ERROR_TEMPLATE.format(
        profile=profile,
        cmd=cmd,
        output=output[:2000]
    )


def format_test_failure(output: str, profile: str) -> str:
    """Format a test failure message."""
    return TEST_FAILURE_TEMPLATE.format(
        profile=profile,
        output=output[:2000]
    )
