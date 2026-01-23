# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-01-22

### Added

- **Living Project Documents** - Persistent knowledge that accumulates across sessions
  - `wp_knowledge.py` - Core library for knowledge management with `KnowledgeCategory` enum
  - `wp:stage` command to persist learnings during sessions
  - Knowledge loading at `wp:init` (architecture, decisions, lessons-learned)
  - Auto-apply staged learnings when implementation phase completes
  - `wp-knowledge-curator.md` - Agent guiding knowledge extraction at phase transitions
  - Project identification via `.waypoints-project` file, git remote, or directory name
  - Per-project storage for architecture/decisions, global storage for lessons-learned

## [1.1.0] - 2026-01-16

### Added

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

- Supervisor mode now writes to unified waypoints logs in addition to workflow.log
- Updated documentation for correct log locations

### Fixed

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
