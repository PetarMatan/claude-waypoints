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
              requirements  interfaces    tests         tests
              -confirmed    -designed    -approved     -passing
                                                           │
                                                           ▼
                                                       Cleanup
                                                      (return to
                                                       Inactive)
```

## Marker Files

Located in `~/.claude/tmp/`:

| File | Purpose | Created By |
|------|---------|------------|
| `wp-mode` | Indicates Waypoints mode is active | `/wp-start` skill |
| `wp-phase` | Contains current phase (1-4) | Orchestrator |
| `wp-requirements-confirmed` | Phase 1 complete | User via Claude |
| `wp-interfaces-designed` | Phase 2 complete | User via Claude |
| `wp-tests-approved` | Phase 3 complete | User via Claude |
| `wp-tests-passing` | Phase 4 complete | Orchestrator |

## Configuration

### Profile Detection Priority

1. Override file (`~/.claude/wp-override.json`)
2. Auto-detection based on project files
3. `WP_DEFAULT_PROFILE` environment variable (optional)
4. No fallback - hooks skip if no profile detected

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
