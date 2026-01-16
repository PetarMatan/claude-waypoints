#!/usr/bin/env python3
"""
WP Workflow - Output Formatters

Pure functions for formatting hook output messages.
These are easily unit-testable without mocking.
"""


def truncate_head(output: str, max_lines: int = 20) -> str:
    """Get first N lines of output."""
    lines = output.strip().split('\n')[:max_lines]
    return '\n'.join(lines)


def truncate_tail(output: str, max_lines: int = 30) -> str:
    """Get last N lines of output."""
    lines = output.strip().split('\n')[-max_lines:]
    return '\n'.join(lines)


# =============================================================================
# Auto-Compile Formatters
# =============================================================================

def format_compile_error(
    output: str,
    file_path: str,
    profile_name: str,
    max_lines: int = 20
) -> str:
    """Format compilation error for PostToolUse context injection."""
    error_summary = truncate_head(output, max_lines)

    return f"""## COMPILATION FAILED ({profile_name})

**File:** {file_path}

**Errors:**
```
{error_summary}
```

Fix the compilation errors before proceeding."""


# =============================================================================
# Auto-Test Formatters (Phase 4)
# =============================================================================

def format_phase4_compile_error(
    output: str,
    file_path: str,
    profile_name: str,
    max_lines: int = 20
) -> str:
    """Format Phase 4 compilation error for PostToolUse context injection."""
    error_summary = truncate_head(output, max_lines)

    return f"""## WP Phase 4: Compilation FAILED ({profile_name})

**File:** {file_path}

**Errors:**
```
{error_summary}
```

Fix these compilation errors and continue implementing."""


def format_phase4_test_failure(
    output: str,
    file_path: str,
    profile_name: str,
    max_lines: int = 30
) -> str:
    """Format Phase 4 test failure for PostToolUse context injection."""
    test_summary = truncate_tail(output, max_lines)

    return f"""## WP Phase 4: Compilation PASSED, Tests FAILED ({profile_name})

**File:** {file_path}

**Test Results:**
```
{test_summary}
```

Review the failing tests and continue implementing the business logic."""


# =============================================================================
# Phase Guard Formatters (PreToolUse Blocks)
# =============================================================================

def format_phase_guard_phase1_block(file_path: str, profile_name: str, marker_dir: str = "") -> str:
    """Format Phase 1 block message for source file edit attempt."""
    mark_cmd = "true # wp:mark-complete requirements"

    return f"""## WP Phase 1: Requirements Gathering ({profile_name})

**Blocked:** Cannot edit `{file_path}`

You are in **Phase 1 (Requirements)**. No source code changes are allowed yet.

**Complete Phase 1 first:**
1. Gather all requirements from user
2. Ask clarifying questions
3. Get user confirmation
4. Mark requirements complete:
   ```bash
   {mark_cmd}
   ```

Then you can proceed to Phase 2 (Interface Design)."""


def format_phase_guard_phase2_block(file_path: str, profile_name: str, marker_dir: str = "") -> str:
    """Format Phase 2 block message for test file edit attempt."""
    mark_cmd = "true # wp:mark-complete interfaces"

    return f"""## WP Phase 2: Interface Design ({profile_name})

**Blocked:** Cannot edit `{file_path}`

You are in **Phase 2 (Interfaces)**. Test files cannot be edited yet.

**In Phase 2, you should:**
1. Create class skeletons in main source
2. Define method signatures with TODO bodies
3. Ensure code compiles
4. Present interfaces to user for approval
5. Mark interfaces complete:
   ```bash
   {mark_cmd}
   ```

**After marking complete**, you'll advance to Phase 3 (Tests)."""


def format_phase_guard_phase3_block(file_path: str, profile_name: str, marker_dir: str = "") -> str:
    """Format Phase 3 block message for implementation file edit attempt."""
    mark_cmd = "true # wp:mark-complete tests"

    return f"""## WP Phase 3: Test Writing ({profile_name})

**Blocked:** Cannot edit `{file_path}`

You are in **Phase 3 (Tests)**. Implementation files cannot be edited yet.

**In Phase 3, you should:**
1. Write tests in test source directories
2. Tests WILL fail (Red phase) - that's expected
3. Present tests to user for approval
4. Mark tests complete:
   ```bash
   {mark_cmd}
   ```

**After marking complete**, you'll advance to Phase 4 (Implementation)."""


# =============================================================================
# Orchestrator Formatters (Phase Blocks)
# =============================================================================

def format_phase1_block(marker_dir: str) -> str:
    """Format Phase 1 requirements gathering block message."""
    return f"""## WP Phase 1: Requirements Gathering

You cannot proceed until requirements are fully gathered and confirmed.

**Required Actions:**

1. **Review the user's feature request** - understand what they want
2. **Identify any gaps or ambiguities** in the requirements
3. **Ask clarifying questions** using AskUserQuestion tool:
   - Edge cases to handle
   - Error scenarios
   - Expected behavior details
4. **When requirements are complete**, ask user to confirm:
   - Use AskUserQuestion: "Are these requirements complete and accurate?"
   - Options: "Yes, requirements are complete" / "No, I have more details"

5. **When user confirms**, mark requirements complete:
   ```bash
   true # wp:mark-complete requirements
   ```

**Only after marking complete can you proceed to Phase 2 (Interface Design).**"""


def format_phase2_compile_error(
    output: str,
    profile_name: str,
    compile_cmd: str,
    max_lines: int = 20
) -> str:
    """Format Phase 2 compile error block message."""
    compile_errors = truncate_head(output, max_lines)

    return f"""## WP Phase 2: Interface Design ({profile_name})

**Compilation FAILED** - fix errors before proceeding.

**Compilation Errors:**
```
{compile_errors}
```

**Required Actions:**

1. **Design class structure** based on requirements from Phase 1
2. **Create empty classes** with proper package organization
3. **Define method signatures** (parameters, return types)
4. **Method bodies should throw** NOT_IMPLEMENTED or TODO

5. **Ensure code compiles**: `{compile_cmd}`

**After code compiles, present interfaces to user for approval.**"""


def format_phase2_awaiting_approval(marker_dir: str, profile_name: str) -> str:
    """Format Phase 2 awaiting interface approval block message."""
    return f"""## WP Phase 2: Interface Design ({profile_name})

**Compilation PASSED** - now get user approval for interfaces.

**Required Actions:**

1. **Present interfaces to user for review**:
   - Use AskUserQuestion: "I've designed the following interfaces. Please review and approve."
   - List the classes/methods you created
   - Options: "Interfaces look good, approved" / "Need changes"

2. **When user approves**, mark interfaces complete:
   ```bash
   true # wp:mark-complete interfaces
   ```

**Only after marking complete can you proceed to Phase 3 (Test Writing).**"""


def format_phase3_compile_error(
    output: str,
    profile_name: str,
    compile_cmd: str,
    max_lines: int = 20
) -> str:
    """Format Phase 3 test compile error block message."""
    compile_errors = truncate_head(output, max_lines)

    return f"""## WP Phase 3: Test Writing ({profile_name})

**Test Compilation FAILED** - fix errors before proceeding.

**Compilation Errors:**
```
{compile_errors}
```

**Required Actions:**

1. **Write tests** that compile correctly
2. **Tests WILL FAIL** when run - that's expected (Red phase of TDD)
3. **Ensure tests compile**: `{compile_cmd}`

**After tests compile, present them to user for approval.**"""


def format_phase3_awaiting_approval(marker_dir: str, profile_name: str) -> str:
    """Format Phase 3 awaiting test approval block message."""
    return f"""## WP Phase 3: Test Writing ({profile_name})

**Tests compile successfully** - now get user approval.

**Required Actions:**

1. **Write unit/integration tests** based on requirements:
   - Happy path tests (main success scenarios)
   - Edge case tests
   - Error handling tests

2. **Tests WILL FAIL** - that's expected (Red phase of TDD)

3. **Present tests to user for review**:
   - Use AskUserQuestion: "I've written the following tests. Please review and approve."
   - List the test cases you've written
   - Options: "Tests look good, approved" / "Need changes"

4. **When user approves**, mark tests complete:
   ```bash
   true # wp:mark-complete tests
   ```

**Only after marking complete can you proceed to Phase 4 (Implementation).**"""


def format_phase4_orchestrator_compile_error(
    output: str,
    profile_name: str,
    max_lines: int = 20
) -> str:
    """Format Phase 4 orchestrator compile error block message."""
    compile_errors = truncate_head(output, max_lines)

    return f"""## WP Phase 4: Implementation Loop ({profile_name})

**Compilation FAILED** - fix errors and continue.

**Compilation Errors:**
```
{compile_errors}
```

**Continue the loop:** Implement -> Compile -> Test -> Fix -> Repeat

Fix the compilation errors, then try again."""


def format_phase4_orchestrator_test_failure(
    output: str,
    profile_name: str,
    max_lines: int = 30
) -> str:
    """Format Phase 4 orchestrator test failure block message."""
    test_summary = truncate_tail(output, max_lines)

    return f"""## WP Phase 4: Implementation Loop ({profile_name})

**Compilation PASSED** but **Tests FAILED** - continue implementing.

**Test Results:**
```
{test_summary}
```

**Continue the loop:** Implement -> Compile -> Test -> Fix -> Repeat

Review the failing tests, implement the missing logic, and try again."""
