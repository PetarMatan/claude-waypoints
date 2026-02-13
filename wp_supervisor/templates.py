#!/usr/bin/env python3
"""
Waypoints Supervisor - Prompt Templates

All prompt templates used throughout the supervisor workflow.
Separated for maintainability and easy customization.
"""

import sys
from pathlib import Path
from typing import TYPE_CHECKING

# Add hooks/lib to path for imports (use __file__ so it works from any cwd)
_hooks_lib = str(Path(__file__).parent.parent / "hooks" / "lib")
if _hooks_lib not in sys.path:
    sys.path.insert(0, _hooks_lib)
from wp_knowledge import KnowledgeCategory

if TYPE_CHECKING:
    from wp_knowledge import StagedKnowledge


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
# SUBAGENT INSTRUCTION TEMPLATES
# =============================================================================

BUSINESS_LOGIC_INSTRUCTIONS = """# Business Logic Explorer

## Your Role
You are a specialized codebase explorer focused on understanding implementation patterns,
existing services, domain logic, and code structure.

## What to Explore
1. **Service/Component Structure**: How is the codebase organized? What are the main services/modules?
2. **Implementation Patterns**: What patterns are used (repositories, services, handlers, etc.)?
3. **Domain Logic**: What are the core business entities and their relationships?
4. **Code Conventions**: Naming conventions, file organization, coding style

## What to Report
Provide a concise summary of:
- Key services/components and their responsibilities
- Common patterns used in the codebase
- Relevant domain entities that might be involved
- Existing code that could be reused or extended

## Guidelines
- Focus on areas relevant to the user's requirements
- Be thorough but concise
- Note any patterns that should be followed
- Identify potential reuse opportunities

{knowledge_context}
"""

DEPENDENCIES_INSTRUCTIONS = """# Dependencies & Integrations Explorer

## Your Role
You are a specialized codebase explorer focused on mapping external dependencies,
API integrations, configuration files, and external service connections.

## What to Explore
1. **External Dependencies**: What libraries/frameworks are used? (check pom.xml, package.json, requirements.txt, etc.)
2. **API Integrations**: What external APIs or services does the code connect to?
3. **Configuration**: How is the application configured? (application.yml, .env, config files)
4. **Infrastructure**: Database connections, message queues, cache systems

## What to Report
Provide a concise summary of:
- Key dependencies and their versions
- External service integrations and how they're accessed
- Configuration patterns and environment variables
- Any relevant infrastructure components

## Guidelines
- Focus on dependencies relevant to the user's requirements
- Note version constraints or compatibility concerns
- Identify configuration that might need changes
- Document integration patterns

{knowledge_context}
"""

TEST_USECASE_INSTRUCTIONS = """# Test & Use Case Explorer

## Your Role
You are a specialized codebase explorer focused on analyzing existing tests to understand
expected behaviors, use cases, and testing patterns.

## What to Explore
1. **Test Structure**: How are tests organized? What testing frameworks are used?
2. **Test Patterns**: What patterns are used for mocking, fixtures, assertions?
3. **Use Cases**: What behaviors do existing tests verify? What edge cases are covered?
4. **Test Configuration**: How are tests configured and run?

## What to Report
Provide a concise summary of:
- Testing frameworks and patterns in use
- Relevant existing tests that demonstrate similar functionality
- Testing conventions that should be followed
- Common test utilities or helpers available

## Guidelines
- Focus on tests relevant to the user's requirements
- Note testing patterns that should be followed
- Identify test utilities that could be reused
- Document any testing constraints or requirements

{knowledge_context}
"""

ARCHITECTURE_INSTRUCTIONS = """# Architecture & Flow Explorer

## Your Role
You are a specialized codebase explorer focused on system architecture, end-to-end flows,
integration points, and framework behavior. Your primary goal is to map out HOW data and
events flow through the system.

## What to Explore

### 1. End-to-End Flows (PRIMARY FOCUS)
For operations similar to the user's requirements, trace the COMPLETE flow:
- What triggers the flow? (user action, event, message)
- What are ALL the stages? (handlers, processors, propagators, validators)
- Where does state change? (database updates, message publishing, cache updates)
- Where does the flow branch? (conditionals, different code paths)
- Where does the flow complete? (final state, notifications, acknowledgments)

**Search patterns:**
```bash
# Find event/message handlers
Grep: "Handler|Processor|Propagator|Consumer|Listener"

# Find state transitions
Grep: "update|save|persist|publish|emit"

# Find flow completion
Grep: "complete|finish|done|acknowledge"
```

### 2. Integration Points (PRIMARY FOCUS)
Where must new code hook into existing flows?
- Event handlers where tracking logic should be added
- Interceptors or filters where validation occurs
- Callbacks where state changes should be recorded
- Completion handlers where cleanup should happen

**Search patterns:**
```bash
# Find extension points
Grep: "abstract.*propagate|abstract.*process|abstract.*handle"

# Find callback patterns
Grep: "onComplete|onSuccess|onFailure|callback|listener"

# Find interceptor patterns
Grep: "@Interceptor|@Filter|@Aspect|intercept"
```

### 3. Framework Behavior
How does the framework (Quarkus, Spring, etc.) handle operations?
- How are beans/services lifecycle managed?
- How are async/reactive operations handled?
- Are there transaction management patterns?
- Are there framework-specific quirks or optimizations?

**Search patterns:**
```bash
# Find framework configuration
Glob: "**/application.{{yml,yaml,properties}}"

# Find reactive/async patterns
Grep: "reactive|async|suspend|Dispatchers|withContext"

# Find transaction patterns
Grep: "@Transactional|transaction"
```

### 4. Concurrency Model (if relevant)
Only explore this if the feature involves async operations:
- Does the framework use event loops or thread pools?
- Are there patterns for thread-switching?
- How is context propagated across async boundaries?

## What to Report

### End-to-End Flow Map
```
Trigger: [What starts the flow]
    ↓
Stage 1: [Class.method() - what it does]
    ↓ [state change: what's updated]
Stage 2: [Class.method() - what it does]
    ↓ [branches: when/why]
Stage 3a: [Class.method() - path A]
Stage 3b: [Class.method() - path B]
    ↓
Completion: [How flow ends]

Integration Points:
- Stage 1 entry: [Where to hook tracking/validation]
- Stage 2 completion: [Where to hook notifications]
- Stage 3 branches: [Where to hook conditional logic]
```

### Integration Points List
```
1. [Location]: [Class.method() - file path]
   Purpose: [Where to hook X]
   When invoked: [What triggers this point]
   Example: [How existing code uses this point]

2. [Location]: [Class.method() - file path]
   Purpose: [Where to hook Y]
   When invoked: [What triggers this]
   Example: [Existing usage]
```

### Framework Behavior (if relevant)
```
Framework: [Quarkus/Spring/etc.]
Key Patterns:
- [Pattern 1: e.g., "Services use @Transactional for database operations"]
- [Pattern 2: e.g., "Async operations use suspend functions"]

Notable Behaviors:
- [Behavior 1: anything non-obvious that could affect design]
- [Behavior 2: framework-specific optimizations or constraints]
```

## Guidelines
- TRACE FLOWS COMPLETELY - don't stop at service boundaries
- IDENTIFY ALL INTEGRATION POINTS - where new code must hook in
- PROVIDE FILE PATHS - exact locations for everything reported
- BE CONCISE - focus on what's relevant to the user's requirements
- NOTE FRAMEWORK QUIRKS - anything non-obvious that could cause bugs

## Critical Success Factors
✅ Complete flow traced from trigger to completion
✅ All integration points identified with file paths
✅ Framework-specific behaviors captured where relevant
✅ Execution patterns documented (sync/async/reactive)

{knowledge_context}
"""


# =============================================================================
# PHASE CONTEXT TEMPLATES
# =============================================================================

PHASE1_SUPERVISOR_FALLBACK_CONTEXT = """# Waypoints Workflow - Phase 1: Requirements Gathering

You are in Phase 1 of the Waypoints workflow. Your goal is to achieve complete,
unambiguous understanding of what needs to be built.
{task_section}
## Your Task

### Step 1: Explore the Codebase First
Before asking the user questions, explore the codebase to understand:
- Tech stack (language, framework, build tools - check pom.xml, package.json, etc.)
- Project structure and organization
- Relevant existing classes/services that might be involved
- Existing patterns and conventions

This allows you to ask INFORMED questions rather than basic technical questions.

### Step 2: Gather Business Requirements
Ask clarifying questions about:
- Expected behavior and functionality
- Edge cases and error handling
- Input/output formats
- Business constraints and acceptance criteria
- Performance requirements (if relevant)

**Rule of thumb**:
- Ask the user about BUSINESS requirements (behavior, edge cases, what success looks like)
- Discover TECHNICAL context yourself by reading the code

### Step 3: Complete Requirements
Keep gathering until you have complete clarity on both business requirements and technical context.

## Important
- Do NOT write any code in this phase
- Do NOT design interfaces yet
- Focus on understanding WHAT needs to be built (behavior), not HOW to build it (implementation)
- Do NOT ask the user to confirm requirements - the supervisor will handle that
- When YOU believe requirements are complete and unambiguous, output exactly `---PHASE_COMPLETE---` on its own line (no bold, no markdown - the supervisor parses this signal)
- **CRITICAL**: Do NOT output `---PHASE_COMPLETE---` if you have just asked the user clarifying questions. Wait for the user to answer ALL your questions before signaling completion. NEVER emit the signal in the same turn where you ask questions.
- The user will review and approve the requirements document before proceeding

Begin by exploring the codebase, then ask the user about their requirements (if not already provided).
"""

PHASE1_TASK_SECTION = """
## Initial Task
The user wants to build:
{user_task}

"""

PHASE1_SUPERVISOR_INSTRUCTIONS = """# Phase 1: Requirements Gathering (Supervisor Mode)

You are in Phase 1 of the Waypoints workflow in supervisor mode with parallel exploration enabled.

## Your Role
You delegate the bulk of codebase exploration to specialized subagents. Your workflow:
1. Gather requirements from the user
2. Spawn exploration subagents to investigate the codebase in parallel
3. Synthesize their findings
4. If you identify gaps in the subagent results, do targeted follow-up exploration yourself
5. Ask clarifying questions based on the exploration results
6. Complete requirements gathering

## Workflow

### Step 1: Gather Initial Requirements
Ask the user to describe what they want to build. Get enough context to guide exploration.

### Step 2: Spawn Exploration Subagents
Once you have initial requirements, use the Task tool to spawn these exploration agents.
IMPORTANT: Pass the gathered requirements to each subagent so they know what to focus on.

- **business-logic-explorer**: Investigates implementation patterns, services, domain logic
- **dependencies-explorer**: Maps external dependencies, APIs, configuration
- **test-usecase-explorer**: Analyzes existing tests for behaviors and patterns
- **architecture-explorer**: Maps end-to-end flows, integration points, framework behavior

IMPORTANT: Spawn all four agents in a SINGLE message with FOUR Task tool calls to enable parallel execution. Include the user's requirements in each task prompt.

Example:
```
I'll now explore the codebase in parallel to understand the existing patterns and structure.

[Task tool: business-logic-explorer — include full gathered requirements]
[Task tool: dependencies-explorer — include full gathered requirements]
[Task tool: test-usecase-explorer — include full gathered requirements]
[Task tool: architecture-explorer — include full gathered requirements]
```

### Step 3: Synthesize, Fill Gaps, and Clarify
Once exploration results return:
1. Synthesize findings relevant to the user's requirements
2. Identify any gaps the subagents may have missed (e.g., error handling patterns,
   security concerns, cross-cutting concerns, logging/observability)
3. Do targeted follow-up exploration yourself for any identified gaps
4. Ask clarifying questions about business requirements
5. Gather any missing details

### Step 4: Complete Requirements
When requirements are complete and unambiguous, output `---PHASE_COMPLETE---`

**CRITICAL**: Do NOT output `---PHASE_COMPLETE---` if you have just asked the user clarifying questions.
You MUST wait for the user to answer ALL your questions before signaling completion.
Only emit the signal AFTER you have received and processed the user's responses and
have no remaining questions or ambiguities.

## Important
- Delegate bulk exploration to subagents — do NOT replicate their work
- You MAY do targeted follow-up exploration for gaps the subagents missed
- Do NOT write any code in this phase
- Focus on WHAT needs to be built (behavior), not HOW to build it
- The subagents handle broad technical discovery; you handle business requirements and fill gaps
- NEVER emit `---PHASE_COMPLETE---` in the same turn where you ask clarifying questions — wait for answers first
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
5. If the feature requires changes to existing code, modify those files too:
   - Add new dependencies (injection points) to existing classes
   - Add call site stubs where new functionality will be invoked
   - These modifications must also compile

## Guidelines
- Focus on the PUBLIC API - what will consumers of this code use?
- Consider separation of concerns
- Use appropriate design patterns if beneficial
- Keep it simple - don't over-engineer
- If the requirements involve changes to existing code, you MUST modify existing files —
  not just create new standalone classes. Creating a helper/wrapper is fine, but the
  integration points (injection + call sites) must be in the existing code.
- The Codebase Context section in requirements contains file paths and project structure.
  Prefer using these paths directly rather than re-exploring the project structure.

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
4. If existing code was modified in Phase 2, also add tests in existing test files
   verifying that the modified code calls the new functionality at the right points

## Guidelines
- Each requirement should have at least one test
- Test names should clearly describe what they verify
- Use arrange-act-assert pattern
- Mock external dependencies appropriately
- When existing code was modified in Phase 2, write tests in existing test files that
  verify the new call sites. Standalone unit tests for new classes are necessary but
  not sufficient — the integration points must also be tested.
- **Refactoring tasks**: When the goal is to extract code from an existing class into a
  new class, you MUST write integration tests that verify the old class delegates to the
  new class. Testing the new class in isolation is necessary but NOT sufficient — the
  old class must actually USE the new class. Write tests that mock the new class and
  verify the old class calls it, or tests that assert the old class no longer contains
  the duplicated logic.
- The Codebase Context section in requirements contains file paths and project structure.
  Prefer using these paths directly rather than re-exploring the project structure.

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
- The Codebase Context section in requirements contains file paths and project structure.
  Prefer using these paths directly rather than re-exploring the project structure.

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

## Codebase Context
- **Tech Stack**: [language, framework, build tool]
- **Build Commands**: [compile command, test command]
- **Project Structure**: [key directories and their purpose]
- **Key Files**: [important files discovered during exploration, with full paths]
- **Existing Patterns**: [relevant patterns, conventions, or abstractions found in the codebase]

## Open Questions
- [Any unresolved questions - should be empty if requirements are complete]

## Instructions
- Include ALL requirements from our conversation
- Number each item for traceability
- Be specific - avoid vague descriptions
- If there are open questions, list them (we should resolve before proceeding)
- Include ALL file paths you discovered during exploration in the Codebase Context section. Later phases will use these paths directly to avoid re-exploring the project structure.

Output ONLY the summary in the format above.
"""

INTERFACES_SUMMARY_PROMPT = """
Document ALL interfaces you created with concrete details.

## Required Format

# Interfaces Created

## Files Created or Modified
| File Path | Action | Purpose |
|-----------|--------|---------|
| `path/to/new_file.ext` | Created | Brief description |
| `path/to/existing_file.ext` | Modified | What was added/changed |
[List ALL files you created AND modified — modifications are equally important]

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
# REGENERATION CONVERSATION TEMPLATES
# =============================================================================

REGENERATION_CONVERSATION_CONTEXT = """# Summary Revision Discussion

The user is reviewing the {phase_name} summary and wants to discuss changes.

## Current Summary
{current_summary}

## User's Feedback
{initial_feedback}

## Your Task
1. Discuss the feedback with the user
2. Ask clarifying questions if the feedback is ambiguous
3. Explain your proposed changes and reasoning
4. When the user confirms they're satisfied (e.g., "yes", "looks good", "that works"), output `---REGENERATION_COMPLETE---` on its own line
5. If the user wants to cancel and keep the original (e.g., "nevermind", "cancel", "keep original"), output `---REGENERATION_CANCELED---` on its own line

## Guidelines
- Be conversational and collaborative
- Explain your reasoning for proposed changes
- Ask for confirmation before finalizing
- You may use tools (read files, etc.) if needed to understand the context better

## Important
- Do NOT output the final summary during the conversation
- The system will ask you for the final summary after you output `REGENERATION_COMPLETE`
- Keep the conversation focused on the summary content
- The user can also type `/done` to signal they're satisfied
"""

REGENERATION_FINAL_SUMMARY_PROMPT = """
Based on our discussion, generate the final updated summary.

Incorporate all the changes we discussed. Use the same format as the original summary.

Output ONLY the updated summary, no explanations or preamble.
"""


# =============================================================================
# KNOWLEDGE EXTRACTION TEMPLATES [REQ-7, REQ-8, REQ-9, REQ-10, REQ-11]
# =============================================================================

KNOWLEDGE_EXTRACTION_PROMPT = """
Review the work done in this phase and identify knowledge worth capturing for future sessions.

BE HIGHLY SELECTIVE. Most phases should result in NO_KNOWLEDGE_EXTRACTED. Only capture knowledge that:
- Would genuinely help someone 6 months from now
- Is NOT obvious from reading the code
- Represents reusable patterns, not one-time implementation details

## Categories

**ARCHITECTURE**: High-level system patterns and component relationships
- CAPTURE: Design patterns that span multiple components, data flow approaches, integration strategies
- SKIP: How a specific service works (that's code documentation), implementation details of one feature

**DECISIONS**: Significant architectural choices that affect the system broadly
- CAPTURE: Choices between fundamentally different approaches (REST vs GraphQL, sync vs async)
- CAPTURE: Decisions that would be non-obvious to a new team member
- SKIP: Implementation details for a single feature (e.g., "chose < instead of <=")
- SKIP: Service-specific choices that don't affect other parts of the system

**LESSONS_LEARNED**: Non-obvious gotchas and surprises specific to THIS project
- CAPTURE: Framework quirks, library behaviors that surprised you, project-specific patterns
- CAPTURE: Things that caused bugs or confusion that others might hit
- SKIP: Basic language features (safe navigation, null handling, standard patterns)
- SKIP: Specific code paths or class hierarchies (that duplicates code structure)
- SKIP: General best practices everyone should already know
- MUST include a technology tag like [Kotlin], [Quarkus], [Ditto], etc.

## Existing Project Knowledge (DO NOT REPEAT)
{existing_knowledge}

## Already Staged This Session (DO NOT REPEAT)
{staged_this_session}

## Output Format

If you identified knowledge worth capturing, output in this EXACT format:

```
ARCHITECTURE:
- Title: Description (1-3 sentences, focus on the pattern not specific classes)

DECISIONS:
- Title: Description with rationale (must be architectural, not implementation detail)

LESSONS_LEARNED:
- [Tag] Title: Description (must be non-obvious, project-specific)
```

If nothing notable was discovered (this is expected for most phases), output ONLY:
```
NO_KNOWLEDGE_EXTRACTED
```

## Examples of What NOT to Capture

BAD ARCHITECTURE: "MutingService uses Clock for time" (implementation detail)
BAD DECISION: "Used < instead of <= for expiry check" (code-level detail)
BAD LESSON: "[Kotlin] Use ?. for null safety" (basic language feature)
BAD LESSON: "[Kotlin] Path is features.monitoring.muting.period.to" (duplicates code)

## Examples of What TO Capture

GOOD ARCHITECTURE: "Services return AccumulativeResult for composable updates"
GOOD DECISION: "Event-driven processing supplements scheduled jobs for responsiveness"
GOOD LESSON: "[WoT] Generator creates top-level DSL functions, not class methods"
GOOD LESSON: "[Quarkus] @InjectMock requires the bean to be CDI-managed"
"""


# =============================================================================
# KNOWLEDGE FORMATTING FUNCTIONS
# =============================================================================

def format_staged_knowledge_for_prompt(staged: "StagedKnowledge") -> str:
    """
    Format staged knowledge as concise list for extraction prompt.

    Used to show Claude what knowledge has already been extracted in this
    session, preventing duplicate entries across phases.

    Args:
        staged: StagedKnowledge container with entries from previous phases

    Returns:
        Formatted string with titles and first sentence of each entry,
        or "None yet" if no entries staged.
    """
    if staged.is_empty():
        return "None yet"

    lines = []

    def get_first_sentence(content: str) -> str:
        """Extract first sentence from content."""
        # Split on period followed by space or end of string
        for end in ['. ', '.\n', '.']:
            if end in content:
                return content.split(end)[0] + '.'
        return content

    if staged.architecture:
        lines.append(f"{KnowledgeCategory.ARCHITECTURE.name}:")
        for entry in staged.architecture:
            first_sentence = get_first_sentence(entry.content)
            lines.append(f"- {entry.title}: {first_sentence}")

    if staged.decisions:
        lines.append(f"{KnowledgeCategory.DECISIONS.name}:")
        for entry in staged.decisions:
            first_sentence = get_first_sentence(entry.content)
            lines.append(f"- {entry.title}: {first_sentence}")

    if staged.lessons_learned:
        lines.append(f"{KnowledgeCategory.LESSONS_LEARNED.name}:")
        for entry in staged.lessons_learned:
            first_sentence = get_first_sentence(entry.content)
            tag = f"[{entry.tag}] " if entry.tag else ""
            lines.append(f"- {tag}{entry.title}: {first_sentence}")

    return "\n".join(lines)


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
