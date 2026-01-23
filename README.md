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

## Custom Agents Make It Yours

The default setup works fine for general development. But the real power comes when you add custom agents - domain experts, architecture guides, testing specialists that auto-load at each phase. They shape how Claude thinks about your specific problem space.

This isn't a magic tool that eliminates coding overnight. But it's a solid step toward a workflow where you focus on *what* and AI handles *how*.

See [Custom Agents](#custom-agents) for how to create phase-specific agents.

## Two Modes: CLI and Supervisor

The workflow supports two modes of operation, designed for different scales of work:

### CLI Mode (Single Session)

Best for: **Normal-sized features** that can be completed in one sitting.

```bash
# Inside Claude Code
/wp-start
```

Everything happens in one Claude session. The hooks manage phase transitions, and context accumulates naturally as you work.

### Supervisor Mode (Multi-Session)

Best for: **Large features or projects** where context accumulation becomes a problem.

```bash
# From terminal
wp-supervisor
```

Each phase runs in a **fresh Claude session** with clean context. Summaries are automatically generated and passed between phases.

See [Supervisor Mode](#supervisor-mode) for details on when and why to use it.

## Features

- **Multi-language Support** - Pre-configured profiles for Kotlin, TypeScript, JavaScript, Python, Go, Rust, and Java (with npm/pnpm variants)
- **Auto-detection** - Automatically detects project technology stack
- **Phase Guards** - Prevents editing wrong file types per phase
- **Auto Compile/Test** - Runs compile and test commands automatically
- **User Approval Gates** - Human confirms each phase transition
- **Clean Cleanup** - Session end automatically removes markers
- **Supervisor Mode** - Multi-session orchestration for large features (prevents context bloat)
- **Living Project Documents** - Persistent knowledge that accumulates across sessions (architecture decisions, lessons learned)

## Quick Start

### Prerequisites

- **Python 3.6+** - Required for hook scripts
- **Claude Code** - The CLI tool this integrates with

### Installation

**Quick install (recommended):**
```bash
curl -fsSL https://raw.githubusercontent.com/PetarMatan/claude-waypoints/main/install.sh | bash
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
```

### Backup & Recovery

The installer creates a **full backup** of your `~/.claude` directory before making any changes:

```
~/.claude-backup-20250105-143022/
```

If anything goes wrong during or after installation, restore with:
```bash
rm -rf ~/.claude && cp -r ~/.claude-backup-TIMESTAMP ~/.claude
```

The uninstaller also creates a backup of `settings.json` before removing hooks.

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

## Custom Agents

You can create custom agents that auto-load during specific phases. This is useful for domain-specific guidance (e.g., an API design expert for Phase 2, or a testing specialist for Phase 3).

See [Custom Agents Guide](docs/custom-agents.md) for detailed instructions, examples, and tips.

### Creating an Agent

Use `/wp-create-agent` to interactively create an agent, or manually create a file in `~/.claude/waypoints/agents/` with YAML frontmatter:

```markdown
---
name: API Designer
phases: [2, 3]
---

# API Designer Agent

## Role
Expert in REST API design...

## Core Expertise
- RESTful principles
- OpenAPI specification
...
```

### Phase Binding

The `phases` field in frontmatter specifies which phases auto-load this agent:

| Phase | Name | Use Case |
|-------|------|----------|
| 1 | Requirements | Domain experts, business analysts |
| 2 | Interfaces | Architects, API designers |
| 3 | Tests | Testing specialists |
| 4 | Implementation | Domain developers |

Agents can bind to multiple phases: `phases: [2, 3, 4]`

When a phase starts, all matching agents are automatically loaded into context.

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
- Continue until all tests pass

## Supported Technologies

| Profile | Detection | Compile Command | Test Command |
|---------|-----------|-----------------|--------------|
| Kotlin/Maven | `pom.xml` + `*.kt` | `mvn clean compile -q` | `mvn test -q` |
| Kotlin/Gradle | `build.gradle.kts` + `*.kt` | `./gradlew compileKotlin -q` | `./gradlew test -q` |
| TypeScript/npm | `package.json` + `tsconfig.json` | `npm run build` | `npm test` |
| TypeScript/pnpm | `package.json` + `tsconfig.json` + `pnpm-lock.yaml` | `pnpm run build` | `pnpm test` |
| JavaScript/npm | `package.json` + `*.js` | `npm run build` | `npm test` |
| JavaScript/pnpm | `package.json` + `pnpm-lock.yaml` + `*.js` | `pnpm run build` | `pnpm test` |
| Python/pytest | `pyproject.toml` + `*.py` | `python -m py_compile` | `python -m pytest -q` |
| Go | `go.mod` + `*.go` | `go build ./...` | `go test ./...` |
| Rust | `Cargo.toml` + `*.rs` | `cargo build` | `cargo test` |
| Java/Maven | `pom.xml` + `*.java` | `mvn clean compile -q` | `mvn test -q` |

### Override Auto-Detection (Optional)

The workflow automatically detects your project's technology stack. If auto-detection fails or you want to force a specific profile, create `~/.claude/wp-override.json`:

```json
{
  "activeProfile": "typescript-npm"
}
```

## Supervisor Mode

For large features or multi-day projects, context accumulation in a single session can degrade AI performance. Supervisor mode solves this by running each phase in a **fresh Claude session**, passing only distilled summaries between phases.

**When to use it:**
- Large features (2+ hours of work)
- Multi-day projects
- When you notice AI getting "confused" in long sessions

**Quick start:**
```bash
pip install claude-agent-sdk  # One-time setup
wp-supervisor                  # Start supervisor workflow
```

See [Supervisor Mode Guide](docs/supervisor-mode.md) for details.

## Living Project Documents

Waypoints automatically builds project knowledge that persists across sessions. Instead of starting fresh each time, Claude has access to:

- **Architecture** - System structure, services, integrations
- **Decisions** - Why choices were made, trade-offs considered
- **Lessons Learned** - Technology gotchas, patterns that work

### How It Works

1. **Session Start**: Existing knowledge is loaded into context
2. **During Work**: Claude stages valuable learnings using `wp:stage`
3. **Session End**: Staged learnings are auto-applied to permanent files

### Knowledge Storage

```
~/.claude/waypoints/knowledge/
├── {project-id}/
│   ├── architecture.md    # Per-project
│   └── decisions.md       # Per-project
└── lessons-learned.md     # Global (shared across projects)
```

Projects are identified by: `.waypoints-project` file > git remote name > directory name.

### Staging Learnings

The Knowledge Curator agent guides what to capture. Claude stages learnings with:

```bash
true # wp:stage architecture "Service Topology" "ServiceA calls ServiceB via Kafka"
true # wp:stage decisions "Async Pattern" "Chose async for exports due to timeouts"
true # wp:stage lessons-learned "[MongoDB] @BsonId" "Required for update operations"
```

Learnings are automatically applied when implementation completes.

## Troubleshooting

See [docs/troubleshooting.md](docs/troubleshooting.md) for debugging tips, log locations, and common issues.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Background

This workflow is inspired by Test-Driven Development principles - the structured approach of defining expectations before implementation. However, it's designed specifically for AI-assisted development, where the value comes from structured checkpoints and feedback loops rather than strict TDD practice.

The methodology draws from Robert C. Martin's work on disciplined development practices, adapted for a world where AI handles implementation while humans define intent.
