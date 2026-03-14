# Architecture

## Overview

Claude Waypoints is a hook-based workflow system for Claude Code that implements structured 4-phase development through a state machine. The approach is inspired by Test-Driven Development principles, adapted for AI-assisted development.

This document covers CLI mode architecture. For Supervisor mode (multi-session orchestration), see [supervisor-mode.md](supervisor-mode.md).

## Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        Claude Code                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Hook System                           │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │    │
│  │  │PreToolUse│  │PostToolUse│ │   Stop   │  │SessionEnd│ │    │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘ │    │
│  └───────┼─────────────┼────────────┼──────────────┼───────┘    │
│          │             │            │              │            │
└──────────┼─────────────┼────────────┼──────────────┼────────────┘
           │             │            │              │
           ▼             ▼            ▼              ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
    │  Phase   │  │   Auto   │  │Orchestrator│ │ Cleanup  │
    │  Guard   │  │ Compile  │  │           │  │ Markers  │
    └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
         │             │            │              │
         └─────────────┴────────────┴──────────────┘
                          │
                          ▼
                   ┌──────────────┐
                   │   Markers    │
                   │ (~/.claude/) │
                   │   tmp/       │
                   └──────────────┘
```

## Hook Flow

### PreToolUse (wp-phase-guard.py)

```
Write/Edit Request
        │
        ▼
┌───────────────────┐
│  WP Mode Active?  │──No──► Allow
└────────┬──────────┘
         │Yes
         ▼
┌───────────────────┐
│  Get Current Phase│
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│ Match File Pattern│
└────────┬──────────┘
         │
    ┌────┴────┐
    ▼         ▼
 Phase 1:  Phase 2:  Phase 3:  Phase 4:
 Block    Block     Block     Allow
 All      Tests     Main      All
```

### PostToolUse (wp-auto-compile.py / wp-auto-test.py)

```
Write/Edit Complete
        │
        ▼
┌───────────────────┐
│  Is Source File?  │──No──► Exit
└────────┬──────────┘
         │Yes
         ▼
┌───────────────────┐
│ WP Phase 4?       │──No──► Auto-Compile Only
└────────┬──────────┘
         │Yes
         ▼
┌───────────────────┐
│  Compile + Test   │
└────────┬──────────┘
         │
    ┌────┴────┐
    ▼         ▼
  Pass      Fail
    │         │
    ▼         ▼
 Report    Report
 Success   Errors
```

### Stop (wp-orchestrator.py)

```
Claude Stops Execution
        │
        ▼
┌───────────────────┐
│  WP Mode Active?  │──No──► Exit
└────────┬──────────┘
         │Yes
         ▼
┌───────────────────┐
│  Check Phase      │
└────────┬──────────┘
         │
    ┌────┼────┬────┐
    ▼    ▼    ▼    ▼
   P1   P2   P3   P4
    │    │    │    │
    ▼    ▼    ▼    ▼
Check  Check Check Check
Marker Compile Tests Tests
       +Marker +Marker Pass
    │    │    │    │
    ▼    ▼    ▼    ▼
Block/ Advance Block/ Complete
Advance Phase  Advance +Cleanup
```

## State Machine

```
                    ┌─────────────────────────────────────────┐
                    │                                         │
                    ▼                                         │
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────┴───┐
│ Inactive│──►│ Phase 1 │──►│ Phase 2 │──►│ Phase 3 │──►│ Phase 4 │
└─────────┘   │ Require │   │Interface│   │  Tests  │   │ Implmnt │
 /wp-start    │  ments  │   │ Design  │   │ Writing │   │  Loop   │
              └────┬────┘   └────┬────┘   └────┬────┘   └────┬────┘
                   │             │             │             │
                   ▼             ▼             ▼             ▼
              requirements  interfaces     tests       implementation
               complete      complete     complete       complete
                                                           │
                                                           ▼
                                                       Cleanup
                                                      (return to
                                                       Inactive)
```

## State Management

All workflow state is consolidated in a single `state.json` file in `~/.claude/tmp/wp-<workflow-id>/`:

```json
{
    "version": 1,
    "active": true,
    "phase": 2,
    "mode": "cli",
    "completedPhases": {
        "requirements": true,
        "interfaces": false,
        "tests": false,
        "implementation": false
    },
    "metadata": {
        "startedAt": "2026-01-09T10:30:00Z",
        "workflowId": "20260109-103000"
    }
}
```

Phase summaries are stored as dedicated document files alongside `state.json` (e.g., `phase1-requirements.md`, `phase1-technical-digest.md`) for human readability.

## Configuration

### Profile Detection Priority

1. Override file (`~/.claude/wp-override.json`)
2. Auto-detection based on project files
3. `WP_DEFAULT_PROFILE` environment variable (optional)
4. No fallback - hooks skip if no profile detected

### Model Selection (Supervisor Mode)

The Claude model used for supervisor sessions is configurable:

1. `WP_MODEL` environment variable (one-off override)
2. `model` field in `~/.claude/wp-override.json` (persistent)
3. Default: `sonnet`

Valid values: `haiku`, `sonnet`, `opus`

Example override file:
```json
{
  "activeProfile": "kotlin-maven",
  "model": "opus"
}
```

One-off: `WP_MODEL=opus wp-start`

### Source Pattern Matching

Each profile defines patterns for:
- **Main source** - Production code
- **Test source** - Test code
- **Config files** - Build/config files (always editable)

## Error Handling

### Compilation Failures

- Error output captured and displayed to Claude
- Claude instructed to fix errors
- Loop continues until success

### Test Failures

- Test output captured and displayed
- Failing tests identified
- Claude continues implementing until all pass

### Phase Violations

- File edit blocked with explanation
- Current phase requirements shown
- Instructions for advancing phase provided
