# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - TBD

### Added
- **Phase 1 Parallel Exploration via Subagents** (Supervisor mode)
  - Phase 1 now spawns specialized exploration agents that investigate the codebase in parallel
  - Three core subagents: business-logic-explorer, dependencies-explorer, test-usecase-explorer
  - Read-only exploration with tools restricted to [Read, Grep, Glob, Bash]
  - Static prompts + dynamic requirements passed via Task tool invocation
  - Graceful fallback to parent-session exploration if subagent build fails
  - Parent session can do targeted follow-up for cross-cutting concerns
- **Architecture Explorer subagent** for Phase 1 exploration
  - Fourth parallel exploration subagent focused on system architecture, end-to-end flows, integration points, and framework behavior
  - Addresses exploration gaps identified in production usage analysis
  - Traces complete data/event flows through the system
  - Identifies all integration points where new code must hook in
  - Documents framework-specific behaviors and concurrency patterns
  - Complements existing business-logic, dependencies, and test-usecase explorers

### Fixed
- **Phase 1 premature completion** - Claude no longer emits `---PHASE_COMPLETE---` in the same turn as clarifying questions
- **SessionRunner wiring** - Removed duplicated streaming logic by wiring session.py into orchestrator
- **Env var leak in tests** - WP_SUPERVISOR_MARKERS_DIR no longer leaks into pytest subprocesses
- **Regeneration tests** - Updated 15 tests after SessionRunner refactoring
- **AgentDefinition mock** - Replaced MagicMock with proper dataclass to prevent cross-test pollution

### Changed
- Split PHASE1_CONTEXT into PHASE1_SUPERVISOR_FALLBACK_CONTEXT for CLI/supervisor template separation
- Added refactoring-aware guidance to Phase 3 template for delegation/integration tests
- Removed backward-compatibility re-exports from WPOrchestrator
- Removed unused task_context and subagents parameters
- Fixed fragile relative sys.path in templates.py

## [1.2.0] - 2026-02-08

### Added

- **Uninstall Improvements** - `uninstall.sh` now supports `--help` flag and cleans up custom `CLAUDE_CONFIG_DIR` installations

### Changed

- Improved Phase 1 requirements gathering instructions in supervisor templates
- Removed TaskCreate/TaskUpdate task tracking from agent instructions (reduces unnecessary workflow turns)
- Streamlined `wp-developer.md` and `wp-uncle-bob.md` agent instructions

### Fixed

- **Windows Compatibility** - `Path.rename()` replaced with `Path.replace()` in `wp_state.py` (fixes `[WinError 183]` when state file already exists)
- **Windows PYTHONPATH** - `wp-supervisor` script detects Git Bash/MINGW via `cygpath` and uses correct path separator (`;`) and native Windows paths
- **Profile Detector Tie-Breaking** - Returns empty string instead of arbitrary winner when pattern-only scores are tied (fixes false `mvn clean compile` on non-Maven repos)
- Phase markers directory handling bugfix in supervisor orchestrator

## [1.1.1] - 2026-01-27

### Fixed

- Interface Design phase (Phase 2) agent instructions no longer biased toward creating new classes only — now correctly guides both creation and modification of existing code

## [1.1.0] - 2026-01-16

### Added

- **Property-Based Testing Support** - Enhanced Phase 3 to identify candidates for property-based testing
  - `wp-tester.md` agent updated with PBT decision flow and guidance
  - Support for Hypothesis (Python), fast-check (TypeScript), Kotest (Kotlin), jqwik (Java), gopter (Go)
  - Properties identified: invariants, relationships, boundaries, idempotence
  - Falls back to comprehensive example-based tests if user declines PBT
- **Living Project Documents** - Persistent knowledge that accumulates across sessions (Supervisor mode only)
  - `wp_knowledge.py` - Core library for knowledge management with `KnowledgeCategory` enum
  - Automatic knowledge extraction at phase transitions via supervisor orchestrator
  - Knowledge loaded into context at workflow start
  - Staged knowledge auto-applied to permanent files at workflow completion
  - Project identification via `.waypoints-project` file, git remote, or directory name
  - Per-project storage for architecture/decisions, global storage for lessons-learned
- **Supervisor Mode Hooks** - SDK-based hooks for phase guard, logging, and build verification
  - `phase_guard` - Blocks file edits that violate current phase rules
  - `log_tool_use` - Logs all tool usage to workflow.log
  - `build_verify` - Runs compile/test verification before phase completion
- **Unified Logging** - Both CLI and Supervisor modes now log to `~/.claude/waypoints/logs/`
  - Session logs: `sessions/{date}-{session-id}.log`
  - Daily aggregated log: `{date}.log`
  - `current.log` symlink to active session
- **Improved CLI Logging** - `wp-orchestrator.py` now logs build verification events
- **PHASE_COMPLETE Detection** - Supervisor detects multiple formats (`---PHASE_COMPLETE---`, `**PHASE_COMPLETE**`)

### Changed

- Living Project Documents clarified as **Supervisor mode only** feature
- Improved knowledge extraction prompts to reduce duplicate entries
- Knowledge extraction now includes staged-this-session context to prevent duplicates
- Supervisor mode now writes to unified waypoints logs in addition to workflow.log
- Updated documentation for correct log locations

### Fixed

- `is_empty()` method call bug in knowledge staging (was using method reference instead of calling method)
- Knowledge files now saved to correct directory when using custom `CLAUDE_CONFIG_DIR`
- Supervisor hooks no longer block event loop (using `asyncio.run_in_executor`)
- Phase completion detection works with Claude's markdown formatting

## [1.0.0] - 2026-01-03

### Added

- Initial release of Claude Waypoints
- Four-phase workflow inspired by TDD principles:
  - Phase 1: Requirements Gathering
  - Phase 2: Interface Design
  - Phase 3: Test Writing
  - Phase 4: Implementation
- Multi-language support with auto-detection:
  - Kotlin/Maven
  - Kotlin/Gradle
  - TypeScript/npm
  - TypeScript/pnpm
  - JavaScript/npm
  - JavaScript/pnpm
  - Python/pytest
  - Go
  - Rust
  - Java/Maven
- Hook system integration:
  - `wp-orchestrator.py` - Stop hook for phase control
  - `wp-phase-guard.py` - PreToolUse hook for file type enforcement
  - `wp-auto-test.py` - PostToolUse hook for compile+test loop
  - `wp-auto-compile.py` - PostToolUse hook for automatic compilation
  - `wp-cleanup-markers.py` - SessionEnd hook for state cleanup
- Skill commands:
  - `/wp-start` - Activate Waypoints workflow
  - `/wp-status` - Show current workflow status
  - `/wp-reset` - Reset workflow state
  - `/wp-create-agent` - Interactive custom agent generation
- Agent definitions:
  - `wp-developer.md` - Main Waypoints workflow guidance
  - `wp-tester.md` - Test writing expertise
  - `wp-uncle-bob.md` - Clean code principles
- Custom agent system:
  - Phase-bound agents via YAML frontmatter (`phases: [2, 3]`)
  - Auto-loading of agents when configured phases start
  - `agents.sh` library for agent discovery and loading
- Configuration system:
  - `wp-config.json` - Technology profiles configuration
  - `schema.json` - JSON Schema for config validation
  - Override support via `~/.claude/wp-override.json`
- Install/uninstall scripts
- Documentation:
  - README.md with quick start guide
  - Architecture documentation
  - Troubleshooting guide

### Security

- Marker files stored in user's home directory
- No external network requests
- No credential storage
