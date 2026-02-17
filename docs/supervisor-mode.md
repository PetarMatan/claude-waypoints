# Supervisor Mode

Supervisor mode runs each phase in a fresh Claude session, preventing context accumulation that can degrade AI performance on large features.

## The Context Problem

When working on large features, a single Claude session accumulates context from all your interactions: requirements discussions, interface iterations, test debugging, implementation attempts. This context buildup has real consequences:

- **Response quality degrades** as the model juggles more information
- **Focus drifts** from the current task to past conversations
- **Token limits** eventually force session restarts, losing context anyway

For a normal feature that takes 30-60 minutes, this isn't noticeable. But for a feature that spans hours or involves complex multi-file changes, context accumulation becomes the bottleneck.

## How Supervisor Mode Solves This

Supervisor mode runs each phase in a **fresh Claude session**. Instead of carrying the full conversation history, each phase starts clean with only what it needs:

```
Phase 1 (Requirements)
    │
    └─► Generates requirements summary
            │
            ▼
Phase 2 (Interfaces) ◄─── Receives only the summary
    │
    └─► Generates interfaces list
            │
            ▼
Phase 3 (Tests) ◄─── Receives requirements + interfaces
    │
    └─► Generates tests list
            │
            ▼
Phase 4 (Implementation) ◄─── Receives all summaries
```

Each session gets distilled context (what was decided) rather than full history (how it was decided). The AI focuses entirely on the current phase's goals.

## When to Use Each Mode

| Scenario | Recommended Mode | Why |
|----------|-----------------|-----|
| Quick bug fix | CLI (`/wp-start`) | Overhead not worth it |
| Single-file feature | CLI (`/wp-start`) | Context stays manageable |
| Multi-file feature | Either | Depends on complexity |
| Large feature (2+ hours) | Supervisor (`wp-supervisor`) | Prevents context degradation |
| Multi-day project | Supervisor (`wp-supervisor`) | Essential for quality |
| Learning/experimenting | CLI (`/wp-start`) | Faster iteration |

**Rule of thumb**: If you'd normally take breaks or restart sessions due to AI getting "confused", use Supervisor mode.

## Prerequisites

Supervisor mode requires the Claude Agent SDK:

```bash
pip install claude-agent-sdk
```

The installer checks for this and will warn you if it's not installed.

## Usage

### Starting a Workflow

```bash
# From your project directory
wp-supervisor

# Specify a different directory
wp-supervisor -d ./my-project

# With an initial task description
wp-supervisor -t "Build a REST API for user management"
```

### During the Session

Each phase runs interactively. You converse with Claude normally as it works through the phase goals.

**File-based input (recommended for complex requirements):**

For structured requirements with multiple sections, formatting, or detailed specifications, write them in a file and provide the path:

```bash
You: @/path/to/requirements.md       # Explicit file reference
You: ./requirements.md               # Relative path (auto-detected)
You: ~/Desktop/feature-spec.md       # Home path (auto-detected)
```

This is especially useful for:
- Pasting Jira tickets or specs
- Multi-section requirements with headers
- Code snippets or examples
- Any content with newlines and formatting

**Quick text input:**

For short responses and follow-ups, just type normally:
```bash
You: yes, that looks correct
You: add error handling for the edge case
```

**Phase completion signals:**
- Type `/done`, `/complete`, or `/next` to signal you're ready for the next phase
- Claude will also detect when phase goals are met

**Abort signals:**
- Type `/quit`, `/exit`, or `/abort` to stop the workflow
- Press `Ctrl+C` to interrupt

**Phase transitions:**
At the end of each phase, you'll be asked to confirm:
```
Proceed to next phase? [y to continue, Ctrl+C to abort]
```

### Command Reference

| Command | Description |
|---------|-------------|
| `wp-supervisor` | Start new workflow in current directory |
| `wp-supervisor -d PATH` | Start in specified directory |
| `wp-supervisor -t "TASK"` | Start with initial task description |
| `wp-supervisor -h` | Show help |

## Differences from CLI Mode

| Aspect | CLI Mode | Supervisor Mode |
|--------|----------|-----------------|
| Sessions | Single | One per phase |
| Context | Accumulates | Fresh each phase |
| Best for | Small features | Large features |
| Startup | `/wp-start` in Claude Code | `wp-supervisor` in terminal |
| Hooks | Via settings.json | Built-in SDK hooks |

## Built-in Hooks

Supervisor mode includes the same safety hooks as CLI mode, implemented via the Claude Agent SDK:

| Hook | Type | Description |
|------|------|-------------|
| **Phase Guard** | PreToolUse | Blocks file edits that violate current phase rules |
| **Tool Logger** | PreToolUse | Logs all tool usage to workflow.log |
| **Build Verify** | Stop | Runs compile/test before phase completion |
| **File Change Tracker** | PostToolUse | Records Write/Edit events for reviewer (Phase 4 only) |

### Build Verification by Phase

| Phase | Verification |
|-------|-------------|
| Phase 1 | None (requirements gathering) |
| Phase 2 | Compile command must pass |
| Phase 3 | Test compile command must pass |
| Phase 4 | Compile + full test suite must pass |

Build failures block phase completion and return errors to Claude for fixing.

## Concurrent Reviewer (Phase 4)

During Phase 4, a Sonnet-based reviewer agent runs concurrently with the implementer. It validates code changes against the requirements gathered in Phase 1.

### How It Works

```
Implementer (Opus)              Reviewer (Sonnet)
    │                               │
    ├── Edits file ─────────────────► Triggered (threshold=1)
    ├── Edits another file          │ Reviewing...
    ├── Edits third file            │ (debounced into one review)
    │                               │
    ├── Signals PHASE_COMPLETE      │
    │   ┌───────────────────────────┤
    │   │  Review gate activates    │
    │   │  Waits for review...      ◄── Review complete
    │   │                           │
    │   │  Feedback found?          │
    │   │  ├── No  → Gate passes    │
    │   │  └── Yes → Inject feedback│
    │   │      └── Implementer      │
    │   │         addresses issues  │
    │   │         re-signals done   │
    │   └───────────────────────────┘
    │
    ▼ Phase complete
```

### Key Behaviors

- **Triggers on every file edit** with debounce — multiple rapid edits merge into a single review
- **Review gate** blocks phase completion until pending reviews finish and any feedback is addressed
- **Feedback injection** sends issues directly into the implementer session with instructions to fix or explain each point
- **Repeat detection** escalates issues that persist after 2 feedback cycles
- **Degraded mode** — if the reviewer fails to start, Phase 4 continues normally without review

## Troubleshooting

### "claude-agent-sdk not installed"

```bash
pip install claude-agent-sdk
```

Or if using a virtual environment:
```bash
source your-venv/bin/activate
pip install claude-agent-sdk
```

### Session interrupted

If you interrupt a session (`Ctrl+C`), markers are automatically cleaned up. Simply start a new session when ready.

### Phase not advancing

If a phase isn't advancing, use the manual completion commands:
- `/done`, `/complete`, or `/next`

You'll then be prompted to confirm before proceeding to the next phase.

## Living Project Documents

Supervisor mode automatically extracts and preserves knowledge across sessions. This feature is **only available in Supervisor mode** - CLI mode does not have knowledge extraction.

### How It Works

At each phase transition, the supervisor prompts Claude to identify learnings worth preserving:

```
Phase 1 complete → Extract architectural decisions discovered
Phase 2 complete → Extract interface design rationale
Phase 3 complete → Extract testing constraints and edge cases
Phase 4 complete → Extract implementation gotchas and lessons
```

### Knowledge Categories

| Category | Scope | What Gets Captured |
|----------|-------|-------------------|
| **Architecture** | Per-project | Services, dependencies, data flow, system structure |
| **Decisions** | Per-project | Why choices were made (ADRs), trade-offs considered |
| **Lessons Learned** | Global | Technology gotchas, patterns, corrections (organized by tech tag) |

### Storage Location

Knowledge is stored in your Claude config directory:

```
~/.claude/waypoints/knowledge/
├── {project-id}/
│   ├── architecture.md    # Per-project architecture
│   └── decisions.md       # Per-project decisions
└── lessons-learned.md     # Global lessons (shared across projects)
```

Project identification uses (in order): `.waypoints-project` file, git remote URL hash, or directory name.

### Session Flow

1. **Session Start**: Existing knowledge is loaded into Claude's context
2. **During Work**: Knowledge informs Claude's decisions (e.g., "use Result type per project patterns")
3. **Phase Transitions**: New knowledge is staged for review
4. **Session End**: Staged knowledge is applied to permanent files

### Example Extracted Knowledge

**Architecture:**
```markdown
## PostProcessor Service Topology
Consumes from `device-events` topic, produces to `device-commands`.
Uses schema-registry for Avro serialization.
```

**Decisions:**
```markdown
## Async Exports for Large Datasets (2026-01-21)
Chose async job pattern for exports >1000 records because
synchronous processing caused gateway timeouts in load testing.
```

**Lessons Learned:**
```markdown
## [MongoDB] @BsonId required for updates (2026-01-21)
Update operations require @BsonId annotation on the ID field.
Without it, updates silently fail with no error.
```

### Knowledge Extraction Behavior

Knowledge extraction happens automatically at phase transitions. The supervisor prompts Claude to identify learnings, parses the response, and stages them without user intervention. Staged knowledge is applied to permanent files when the workflow completes.
