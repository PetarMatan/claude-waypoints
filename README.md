# Claude Waypoints

**4-phase workflow for Claude Code.** Set waypoints before AI navigates: requirements, interfaces, tests, then implementation. Each checkpoint ensures you're on course. You define the destination, Claude handles the journey.

## The Problem

You give an AI a prompt, it starts coding. There's no pause to clarify, no checkpoint to course-correct, no feedback loop to catch mistakes early. By the time you see the result, you might realize the approach was wrong from the start.

## The Solution

Four phases that structure the journey from idea to implementation:

1. **Requirements** - What are we actually building?
2. **Interfaces** - What's the shape of the solution?
3. **Tests** - How will we know it works?
4. **Implementation** - Now write the code.

Each phase needs your approval before moving on. You stay in control of the destination.

## Why This Works

The interesting thing isn't the methodology itself - it's what happens when you use structured checkpoints consistently with AI. You start spending less time on implementation details and more time on product questions: What should this do? What are the edge cases? How should errors behave?

The tests become your specification. Claude fulfills the contract.

## Custom Agents

The default setup works fine for general development. But the real power comes when you add custom agents that auto-load at specific phases.

Think of agents as specialists you bring in at the right moment:
- A **domain expert** joins Phase 1 to ensure requirements capture business rules correctly
- An **API architect** joins Phase 2 to enforce REST conventions and consistency
- A **testing specialist** joins Phase 3 to ensure edge cases aren't missed
- A **performance expert** joins Phase 4 to catch inefficient patterns during implementation

Each agent is a markdown file with guidelines, checklists, and domain knowledge. When a phase starts, matching agents automatically load into Claude's context, shaping how it approaches your specific problem space.

Use `/wp-create-agent` to create one interactively, or see the [Custom Agents Guide](docs/custom-agents.md) for examples and detailed instructions.

## Two Modes: CLI and Supervisor

The workflow supports two modes of operation, designed for different scales of work:

### CLI Mode (Single Session)

Best for: **Normal-sized features** that can be completed in one sitting. No extra dependencies required.

```bash
# Inside Claude Code
/wp-start
```

Everything happens in one Claude session. The hooks manage phase transitions, and context accumulates naturally as you work.

### Supervisor Mode (Multi-Session)

Best for: **Large features or projects** where context accumulation becomes a problem. Requires [additional setup](#supervisor-mode).

```bash
# From terminal
wp-supervisor
```

Each phase runs in a **fresh Claude session** with clean context. Summaries are automatically generated and passed between phases.

## Features

- **Multi-language Support** - Pre-configured profiles for Kotlin, TypeScript, JavaScript, Python, Go, Rust, and Java (with npm/pnpm variants)
- **Auto-detection** - Automatically detects project technology stack
- **Phase Guards** - Prevents editing wrong file types per phase
- **Auto Compile/Test** - Runs compile and test commands automatically
- **User Approval Gates** - Human confirms each phase transition
- **Clean Cleanup** - Session end automatically removes markers
- **Supervisor Mode** - Multi-session orchestration for large features (prevents context bloat)
- **Concurrent Code Review** - Sonnet reviewer validates Phase 4 implementation against requirements in real-time (Supervisor mode only)
- **Living Project Documents** - Persistent knowledge that accumulates across sessions (architecture decisions, lessons learned) - *Supervisor mode only*
- **Property-Based Testing** - Optional PBT support in Phase 3 for finding edge cases automatically

## Quick Start

### Prerequisites

- **Python 3.6+** - Required for hook scripts
- **Claude Code** - The CLI tool this integrates with

### Installation

**Quick install (recommended - latest stable):**
```bash
curl -fsSL https://raw.githubusercontent.com/PetarMatan/claude-waypoints/main/install.sh | bash
```

**Install specific version (for stability):**
```bash
# Example: Install v1.3.1
curl -fsSL https://raw.githubusercontent.com/PetarMatan/claude-waypoints/v1.3.1/install.sh | bash
```

**Or clone and install manually:**
```bash
git clone https://github.com/PetarMatan/claude-waypoints.git
cd claude-waypoints
./install.sh
```

**Uninstall:**
```bash
~/.claude/waypoints/uninstall.sh
# Or if you have the repo cloned:
./uninstall.sh

# For custom directory installations:
~/.claude/waypoints/uninstall.sh --dir /path/to/custom/claude/dir
```

### Backup & Recovery

The installer backs up `~/.claude` automatically. Restore with `cp -r ~/.claude-backup-TIMESTAMP ~/.claude` if needed.

### Usage

In Claude Code, start the workflow:

```
/wp-start
```

Check status:
```
/wp-status
```

Reset and start over:
```
/wp-reset
```

Create a custom agent:
```
/wp-create-agent
```

## Supported Technologies

Supports Kotlin, TypeScript, JavaScript, Python, Go, Rust, and Java with auto-detection. See [full list](docs/supported-technologies.md) for details and override options.

## Supervisor Mode

For large features or multi-day projects, context accumulation in a single session can degrade AI performance. Supervisor mode solves this by running each phase in a **fresh Claude session**, passing only distilled summaries between phases.

**When to use it:**
- Large features (2+ hours of work)
- Multi-day projects
- When you notice AI getting "confused" in long sessions

**Additional dependency required:**

Supervisor mode uses [claude-agent-sdk](https://github.com/anthropics/claude-code-sdk-python) to programmatically manage Claude sessions. This is **not required for CLI mode** - only install if you need supervisor features.

```bash
pip install claude-agent-sdk
```

Then start the workflow:
```bash
wp-supervisor
```

See [Supervisor Mode Guide](docs/supervisor-mode.md) for details.

## The Four Phases

### Phase 1: Requirements Gathering

**Goal**: Achieve complete, unambiguous understanding of what needs to be built.

- Claude gathers requirements from the user
- Asks clarifying questions about edge cases, error handling, dependencies
- User confirms requirements are complete

### Phase 2: Interface Design

**Goal**: Create the structural skeleton without business logic.

- Design class/method signatures
- Method bodies contain TODO or throw NotImplementedError
- Code must compile successfully
- User approves the interfaces

### Phase 3: Test Writing

**Goal**: Write tests that define expected behavior.

- Write unit/integration tests based on requirements
- Tests must compile (but will fail when run)
- Cover happy paths, edge cases, error scenarios
- User approves the tests

### Phase 4: Implementation

**Goal**: Make all tests pass.

- Implement business logic method by method
- Automatic compile-test loop after each change
- Concurrent reviewer validates changes against requirements (Supervisor mode)
- Continue until all tests pass

## Troubleshooting

See [docs/troubleshooting.md](docs/troubleshooting.md) for debugging tips, log locations, and common issues.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Background

This workflow is inspired by Test-Driven Development principles - the structured approach of defining expectations before implementation. However, it's designed specifically for AI-assisted development, where the value comes from structured checkpoints and feedback loops rather than strict TDD practice.

The methodology draws from Robert C. Martin's work on disciplined development practices, adapted for a world where AI handles implementation while humans define intent.
