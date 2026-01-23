#!/usr/bin/env python3
"""
Waypoints Supervisor - Prompt Templates

All prompt templates used throughout the supervisor workflow.
Separated for maintainability and easy customization.
"""


# =============================================================================
# PHASE METADATA
# =============================================================================

PHASE_NAMES = {
    1: "Requirements Gathering",
    2: "Interface Design",
    3: "Test Writing",
    4: "Implementation",
}


# =============================================================================
# PHASE CONTEXT TEMPLATES
# =============================================================================

PHASE1_CONTEXT = """# Waypoints Workflow - Phase 1: Requirements Gathering

You are in Phase 1 of the Waypoints workflow. Your goal is to achieve complete,
unambiguous understanding of what needs to be built.
{task_section}
## Your Task
1. Understand what the user wants to build
2. Ask clarifying questions about:
   - Expected behavior and functionality
   - Edge cases and error handling
   - Input/output formats
   - Dependencies and constraints
   - Performance requirements (if relevant)
3. Keep gathering until you have complete clarity

## Important
- Do NOT write any code in this phase
- Do NOT design interfaces yet
- Focus entirely on understanding WHAT, not HOW
- Do NOT ask the user to confirm requirements - the supervisor will handle that
- When YOU believe requirements are complete and unambiguous, output exactly `---PHASE_COMPLETE---` on its own line (no bold, no markdown - the supervisor parses this signal)
- The user will review and approve the requirements document before proceeding

Begin by asking the user what they want to build (if not already provided).
"""

PHASE1_TASK_SECTION = """
## Initial Task
The user wants to build:
{user_task}

"""

PHASE2_CONTEXT = """# Waypoints Workflow - Phase 2: Interface Design

You are in Phase 2 of the Waypoints workflow. Your goal is to design the
structural skeleton of the solution WITHOUT implementing business logic.

## Requirements from Phase 1
{requirements_summary}

## Your Task
1. Design class/interface signatures
2. Design method signatures with parameter and return types
3. Create the structural skeleton with:
   - Method stubs that throw NotImplementedError or return TODO markers
   - No actual business logic
4. Ensure the code compiles/type-checks successfully

## Guidelines
- Focus on the PUBLIC API - what will consumers of this code use?
- Consider separation of concerns
- Use appropriate design patterns if beneficial
- Keep it simple - don't over-engineer

## Important
- Do NOT implement business logic
- Method bodies should be stubs only
- Code MUST compile successfully
- Do NOT ask the user to approve interfaces - the supervisor will handle that
- When YOU believe interfaces are complete and compile successfully, output exactly `---PHASE_COMPLETE---` on its own line (no bold, no markdown - the supervisor parses this signal)
- The user will review and approve the interfaces document before proceeding
"""

PHASE3_CONTEXT = """# Waypoints Workflow - Phase 3: Test Writing

You are in Phase 3 of the Waypoints workflow. Your goal is to write tests
that define the expected behavior.

## Requirements from Phase 1
{requirements_summary}

## Interfaces from Phase 2
{interfaces_list}

## Your Task
1. Write unit tests based on the requirements
2. Cover:
   - Happy path scenarios
   - Edge cases identified in requirements
   - Error scenarios and exception handling
   - Boundary conditions
3. Tests should compile but FAIL when run (Red phase)

## Guidelines
- Each requirement should have at least one test
- Test names should clearly describe what they verify
- Use arrange-act-assert pattern
- Mock external dependencies appropriately

## Important
- Do NOT implement the actual code yet
- Tests MUST compile
- Tests SHOULD fail (they test unimplemented code)
- Do NOT ask the user to approve tests - the supervisor will handle that
- When YOU believe test coverage is complete, output exactly `---PHASE_COMPLETE---` on its own line (no bold, no markdown - the supervisor parses this signal)
- The user will review and approve the tests document before proceeding
"""

PHASE4_CONTEXT = """# Waypoints Workflow - Phase 4: Implementation

You are in Phase 4 of the Waypoints workflow. Your goal is to implement
the business logic to make all tests pass.

## Requirements Summary
{requirements_summary}

## Interfaces Created
{interfaces_list}

## Tests to Pass
{tests_list}

## Your Task
1. Read the test files to understand expected behavior
2. Implement business logic method by method
3. Run tests frequently to verify progress
4. Continue until ALL tests pass

## Guidelines
- The tests are your specification - make them pass
- Implement the simplest solution that passes tests
- If a test seems wrong, discuss with user before changing it
- Refactor for clarity after tests pass (if needed)

## Important
- Focus on making tests pass, not on perfect code
- Run tests after each significant change
- When ALL tests pass, output exactly `---PHASE_COMPLETE---` on its own line to signal completion (no bold, no markdown - the supervisor parses this signal)
"""


# =============================================================================
# SUMMARY GENERATION TEMPLATES
# =============================================================================

REQUIREMENTS_SUMMARY_PROMPT = """
Create a comprehensive requirements summary based on our discussion.

## Required Format

# Requirements Summary

## Purpose
[One clear sentence describing what this feature/component does]

## Functional Requirements
- [REQ-1] [Requirement description]
- [REQ-2] [Requirement description]
[Add all requirements discussed]

## Edge Cases & Error Handling
- [EDGE-1] [Edge case and how it should be handled]
- [ERR-1] [Error scenario and expected behavior]
[Include ALL edge cases we discussed]

## Constraints & Decisions
- [Decision/constraint and rationale]
[Include technical constraints, assumptions, and key decisions made]

## Open Questions
- [Any unresolved questions - should be empty if requirements are complete]

## Instructions
- Include ALL requirements from our conversation
- Number each item for traceability
- Be specific - avoid vague descriptions
- If there are open questions, list them (we should resolve before proceeding)

Output ONLY the summary in the format above.
"""

INTERFACES_SUMMARY_PROMPT = """
Document ALL interfaces you created with concrete details.

## Required Format

# Interfaces Created

## Files Created
| File Path | Purpose |
|-----------|---------|
| `path/to/file.ext` | Brief description |
[List ALL files you created or modified]

## Classes/Modules
### `ClassName`
- Purpose: [what this class does]
- File: `path/to/file.ext`

### `ClassName2`
- Purpose: [what this class does]
- File: `path/to/file.ext`

## Key Method Signatures
```
[language]
class ClassName:
    def method_name(param: Type) -> ReturnType:
        '''Brief description'''

    def another_method(param: Type) -> ReturnType:
        '''Brief description'''
```
[Include actual signatures - copy from the code you wrote]

## Data Types/Models
- `TypeName` - [purpose and key fields]

## Dependencies
- [Any external dependencies introduced]

## Instructions
- Include EXACT file paths you created
- Copy ACTUAL method signatures from your code
- This will be used to verify files exist in the next phase

Output ONLY the summary in the format above.
"""

TESTS_SUMMARY_PROMPT = """
Document ALL tests you created with concrete details.

## Required Format

# Tests Created

## Test Files
| File Path | Test Count | Purpose |
|-----------|------------|---------|
| `path/to/test_file.ext` | N tests | What it tests |
[List ALL test files created]

## Test Cases by Category

### Happy Path Tests
- `test_name` - [what it verifies]
- `test_name2` - [what it verifies]

### Edge Case Tests
- `test_edge_case_name` - [which edge case from requirements: EDGE-X]
- `test_another_edge` - [which edge case]

### Error Handling Tests
- `test_error_scenario` - [which error from requirements: ERR-X]
- `test_another_error` - [which error]

## Requirements Coverage
| Requirement | Test(s) |
|-------------|---------|
| REQ-1 | test_name, test_name2 |
| REQ-2 | test_another |
[Map requirements to tests that verify them]

## Test Commands
```bash
[Command to run these tests, e.g., pytest path/to/tests/]
```

## Instructions
- Include EXACT file paths
- Reference requirement IDs from Phase 1 (REQ-X, EDGE-X, ERR-X)
- Ensure every requirement has at least one test mapped
- Include the actual command to run tests

Output ONLY the summary in the format above.
"""


# =============================================================================
# SELF-REVIEW TEMPLATES
# =============================================================================

REQUIREMENTS_REVIEW_PROMPT = """
Review the requirements summary you just created for completeness.

## Checklist - Verify each item:
1. [ ] ALL functional requirements from our discussion are included
2. [ ] ALL edge cases we talked about are listed
3. [ ] ALL error scenarios are documented
4. [ ] ALL constraints and decisions are captured
5. [ ] No open questions remain (or they're explicitly listed)
6. [ ] Each item is specific enough to implement against

## Your Task
Go through our conversation and verify nothing was missed.

If anything is MISSING:
- Output "GAPS_FOUND" on the first line
- Then output the COMPLETE UPDATED summary with additions marked as [ADDED]

If everything is complete:
- Output "SUMMARY_VERIFIED" on the first line
- Then output the original summary unchanged
"""

INTERFACES_REVIEW_PROMPT = """
Review the interfaces summary you just created for completeness.

## Checklist - Verify each item:
1. [ ] ALL files created are listed with correct paths
2. [ ] ALL classes/modules are documented
3. [ ] ALL public method signatures are included
4. [ ] ALL data types/models are listed
5. [ ] Signatures match EXACTLY what's in the code
6. [ ] File paths are correct and would be found in the project

## Your Task
Compare your summary against the actual code you wrote.

If anything is MISSING or INCORRECT:
- Output "GAPS_FOUND" on the first line
- Then output the COMPLETE UPDATED summary with corrections marked as [FIXED] or [ADDED]

If everything is complete and accurate:
- Output "SUMMARY_VERIFIED" on the first line
- Then output the original summary unchanged
"""

TESTS_REVIEW_PROMPT = """
Review the tests summary you just created for completeness.

## Checklist - Verify each item:
1. [ ] ALL test files are listed with correct paths
2. [ ] ALL test cases are documented
3. [ ] Every requirement (REQ-X) has at least one mapped test
4. [ ] Every edge case (EDGE-X) has a corresponding test
5. [ ] Every error scenario (ERR-X) has a corresponding test
6. [ ] Test command is correct for this project

## Your Task
Compare your summary against the actual tests you wrote and the requirements from Phase 1.

If anything is MISSING or requirements lack test coverage:
- Output "GAPS_FOUND" on the first line
- List what's missing
- Then output the COMPLETE UPDATED summary

If everything is complete with full coverage:
- Output "SUMMARY_VERIFIED" on the first line
- Then output the original summary unchanged
"""


# =============================================================================
# KNOWLEDGE EXTRACTION TEMPLATES [REQ-7, REQ-8, REQ-9, REQ-10, REQ-11]
# =============================================================================

KNOWLEDGE_EXTRACTION_PROMPT = """
Review the work done in this phase and identify any learnings worth capturing.

## Categories to Consider

**ARCHITECTURE**: System structure, service responsibilities, data flow, component interactions
- Worth capturing: Design patterns used, architectural decisions, integration approaches

**DECISIONS**: Why choices were made, trade-offs considered, constraints discovered
- Worth capturing: Technical decisions with rationale, rejected alternatives and why

**LESSONS_LEARNED**: Technology-specific gotchas, patterns, corrections
- Worth capturing: Things that surprised you, workarounds discovered, best practices learned
- MUST include a technology tag like [Python], [Git], [TypeScript], etc.

## Existing Project Knowledge (DO NOT REPEAT)
{existing_knowledge}

## Output Format

If you identified knowledge worth capturing, output in this EXACT format:

```
ARCHITECTURE:
- Title: Description (1-3 sentences with context)
- Another Title: Another description

DECISIONS:
- Title: Description with rationale

LESSONS_LEARNED:
- [Tag] Title: Description
- [AnotherTag] Title: Description
```

If nothing notable was discovered in this phase, output ONLY:
```
NO_KNOWLEDGE_EXTRACTED
```

## Guidelines
- Only capture things that would help someone working on this project 6 months from now
- Do NOT repeat information already in project knowledge
- Be specific and include context
- Lessons learned MUST have a technology tag in [brackets]
- Empty sections can be omitted
"""


# =============================================================================
# CONSOLE OUTPUT FUNCTIONS
# =============================================================================

def format_phase_header(phase: int, name: str) -> str:
    """Format a phase header for console output."""
    separator = '=' * 60
    return f"\n{separator}\nPHASE {phase}: {name.upper()}\n{separator}\n"


def format_workflow_header(working_dir: str, workflow_id: str, markers_dir: str) -> str:
    """Format the workflow start header."""
    separator = '=' * 60
    return f"""
{separator}
Waypoints Supervisor - Starting Workflow
{separator}
Working directory: {working_dir}
Workflow ID: {workflow_id}
Markers directory: {markers_dir}
{separator}
"""


def format_phase_complete_banner(phase: int, name: str, doc_path: str = "") -> str:
    """Format the phase completion banner with review options."""
    separator = '=' * 60
    lines = [
        f"\n{separator}",
        f"  Phase {phase} ({name}) Complete",
        separator,
    ]

    if doc_path:
        lines.append("")
        lines.append(f"Review: {doc_path}")
        lines.append("        (You can open this file in your editor)")

    lines.append("")
    lines.append("Options:")
    lines.append("  y - Proceed to next phase")
    lines.append("  e - Edit document manually, then reload")
    lines.append("  r - Provide feedback to regenerate")
    lines.append("  Ctrl+C - Abort workflow")

    return '\n'.join(lines)


def format_workflow_complete() -> str:
    """Format the workflow completion message."""
    separator = '=' * 60
    return f"\n{separator}\nWaypoints Workflow Complete!\n{separator}\n"
