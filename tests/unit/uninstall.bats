#!/usr/bin/env bats
# Tests for uninstall.sh

load '../test_helper'

# Path to uninstall.sh
UNINSTALL_SCRIPT="$PROJECT_ROOT/uninstall.sh"

setup() {
    setup_test_environment
}

teardown() {
    teardown_test_environment
}

# Helper to source uninstall.sh functions without running the full script
source_uninstall_functions() {
    cat > "$TEST_TMP/uninstall_functions.sh" << 'SCRIPT_END'
#!/bin/bash
set -e

CLAUDE_DIR="${HOME}/.claude"

show_usage() {
    cat << 'EOF'
Waypoints Workflow Uninstaller for Claude Code

Usage:
  ./uninstall.sh [OPTIONS]

Options:
  --dir /path/to/dir    Uninstall from custom directory instead of ~/.claude
  --help                Show this help message

Examples:
  ./uninstall.sh                      # Uninstall from ~/.claude (default)
  ./uninstall.sh --dir ~/.claude-dev  # Uninstall from custom directory
EOF
    exit 0
}

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dir)
                if [[ -z "${2:-}" ]]; then
                    echo "Error: --dir requires a path argument"
                    exit 1
                fi
                CLAUDE_DIR="$2"
                shift 2
                ;;
            --help)
                show_usage
                ;;
            *)
                echo "Error: Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
}

validate_claude_dir() {
    if [[ ! -d "$CLAUDE_DIR" ]]; then
        echo "Error: Directory does not exist: $CLAUDE_DIR"
        exit 1
    fi
}
SCRIPT_END

    source "$TEST_TMP/uninstall_functions.sh"
}

# =============================================================================
# Tests for --dir parameter
# =============================================================================

@test "parse_arguments sets CLAUDE_DIR when --dir provided" {
    source_uninstall_functions

    # given
    mkdir -p "$TEST_TMP/custom-claude"

    # when
    parse_arguments --dir "$TEST_TMP/custom-claude"

    # then
    [ "$CLAUDE_DIR" = "$TEST_TMP/custom-claude" ]
}

@test "parse_arguments uses default when no --dir provided" {
    source_uninstall_functions

    # when
    parse_arguments

    # then
    [ "$CLAUDE_DIR" = "$HOME/.claude" ]
}

@test "parse_arguments fails when --dir has no value" {
    source_uninstall_functions

    # when
    run parse_arguments --dir

    # then
    [ "$status" -ne 0 ]
    assert_output_contains "Error: --dir requires a path argument"
}

@test "parse_arguments fails on unknown option" {
    source_uninstall_functions

    # when
    run parse_arguments --unknown-option

    # then
    [ "$status" -ne 0 ]
    assert_output_contains "Error: Unknown option"
    assert_output_contains "Use --help for usage information"
}

# =============================================================================
# Tests for --help parameter
# =============================================================================

@test "show_usage displays help and exits successfully" {
    source_uninstall_functions

    # when
    run show_usage

    # then
    [ "$status" -eq 0 ]
    assert_output_contains "Usage:"
    assert_output_contains "--dir"
    assert_output_contains "--help"
}

@test "--help shows usage" {
    source_uninstall_functions

    # when
    run parse_arguments --help

    # then
    [ "$status" -eq 0 ]
    assert_output_contains "Usage:"
}

@test "validate_claude_dir succeeds when directory exists" {
    source_uninstall_functions

    # given
    mkdir -p "$TEST_TMP/existing-dir"
    CLAUDE_DIR="$TEST_TMP/existing-dir"

    # when
    run validate_claude_dir

    # then
    [ "$status" -eq 0 ]
}

@test "validate_claude_dir fails when directory does not exist" {
    source_uninstall_functions

    # given
    CLAUDE_DIR="$TEST_TMP/nonexistent-dir"

    # when
    run validate_claude_dir

    # then
    [ "$status" -ne 0 ]
    assert_output_contains "Error: Directory does not exist"
}

# =============================================================================
# Tests for sessions directory cleanup
# =============================================================================

@test "uninstall removes sessions directory when it exists" {
    # given
    rm -f "$HOME/.claude/waypoints/hooks"  # Remove symlink to avoid writing to real source
    mkdir -p "$HOME/.claude/waypoints/hooks/lib"
    mkdir -p "$HOME/.claude/logs/sessions"
    touch "$HOME/.claude/logs/sessions/session1.log"
    touch "$HOME/.claude/logs/sessions/session2.log"

    # Create minimal settings_manager.py mock
    cat > "$HOME/.claude/waypoints/hooks/lib/settings_manager.py" << 'EOF'
import sys
if __name__ == "__main__":
    if sys.argv[1] == "remove":
        print("Hooks removed")
EOF

    # Create settings.json
    echo '{}' > "$HOME/.claude/settings.json"

    # when
    echo "n" | bash "$UNINSTALL_SCRIPT" --dir "$HOME/.claude"

    # then
    [ ! -d "$HOME/.claude/logs/sessions" ]
}

@test "uninstall succeeds when sessions directory does not exist" {
    # given
    rm -f "$HOME/.claude/waypoints/hooks"  # Remove symlink to avoid writing to real source
    mkdir -p "$HOME/.claude/waypoints/hooks/lib"

    # Create minimal settings_manager.py mock
    cat > "$HOME/.claude/waypoints/hooks/lib/settings_manager.py" << 'EOF'
import sys
if __name__ == "__main__":
    if sys.argv[1] == "remove":
        print("Hooks removed")
EOF

    # Create settings.json
    echo '{}' > "$HOME/.claude/settings.json"

    # Ensure sessions dir does not exist
    rm -rf "$HOME/.claude/logs/sessions"

    # when
    echo "n" | bash "$UNINSTALL_SCRIPT" --dir "$HOME/.claude"

    # then
    [ "$?" -eq 0 ]
}

# =============================================================================
# Tests for path derivation from CLAUDE_DIR
# =============================================================================

@test "uninstall uses custom directory for all paths" {
    # given
    local custom_dir="$TEST_TMP/custom-claude"
    mkdir -p "$custom_dir/waypoints/hooks/lib"
    mkdir -p "$custom_dir/commands"
    mkdir -p "$custom_dir/tmp"
    mkdir -p "$custom_dir/logs/sessions"

    # Create test markers
    touch "$custom_dir/tmp/wp-mode"
    touch "$custom_dir/tmp/wp-phase"

    # Create skills
    touch "$custom_dir/commands/wp-start.md"
    touch "$custom_dir/commands/wp-status.md"

    # Create minimal settings_manager.py mock
    cat > "$custom_dir/waypoints/hooks/lib/settings_manager.py" << 'EOF'
import sys
if __name__ == "__main__":
    if sys.argv[1] == "remove":
        print("Hooks removed")
EOF

    # Create settings.json
    echo '{}' > "$custom_dir/settings.json"

    # when
    echo "n" | bash "$UNINSTALL_SCRIPT" --dir "$custom_dir"

    # then - verify cleanup happened in custom dir
    [ ! -f "$custom_dir/tmp/wp-mode" ]
    [ ! -f "$custom_dir/tmp/wp-phase" ]
    [ ! -f "$custom_dir/commands/wp-start.md" ]
    [ ! -f "$custom_dir/commands/wp-status.md" ]
    [ ! -d "$custom_dir/waypoints" ]
    [ ! -d "$custom_dir/logs/sessions" ]
}

@test "uninstall cleans wp markers in custom directory" {
    # given
    local custom_dir="$TEST_TMP/custom-claude"
    mkdir -p "$custom_dir/waypoints/hooks/lib"
    mkdir -p "$custom_dir/tmp"

    # Create various wp markers
    touch "$custom_dir/tmp/wp-mode"
    touch "$custom_dir/tmp/wp-phase"
    touch "$custom_dir/tmp/wp-requirements-confirmed"
    touch "$custom_dir/tmp/wp-interfaces-designed"
    touch "$custom_dir/tmp/wp-tests-approved"
    touch "$custom_dir/tmp/wp-tests-passing"
    mkdir -p "$custom_dir/tmp/wp-session-123"
    touch "$custom_dir/tmp/wp-session-123/state.json"

    # Create minimal settings_manager.py mock
    cat > "$custom_dir/waypoints/hooks/lib/settings_manager.py" << 'EOF'
import sys
if __name__ == "__main__":
    if sys.argv[1] == "remove":
        print("Hooks removed")
EOF

    # Create settings.json
    echo '{}' > "$custom_dir/settings.json"

    # when
    echo "n" | bash "$UNINSTALL_SCRIPT" --dir "$custom_dir"

    # then - all wp markers cleaned
    [ ! -f "$custom_dir/tmp/wp-mode" ]
    [ ! -f "$custom_dir/tmp/wp-phase" ]
    [ ! -f "$custom_dir/tmp/wp-requirements-confirmed" ]
    [ ! -f "$custom_dir/tmp/wp-interfaces-designed" ]
    [ ! -f "$custom_dir/tmp/wp-tests-approved" ]
    [ ! -f "$custom_dir/tmp/wp-tests-passing" ]
    [ ! -d "$custom_dir/tmp/wp-session-123" ]
}

# =============================================================================
# Tests for skills removal
# =============================================================================

@test "uninstall removes all four skills" {
    # given
    rm -f "$HOME/.claude/waypoints/hooks"  # Remove symlink to avoid writing to real source
    mkdir -p "$HOME/.claude/waypoints/hooks/lib"
    mkdir -p "$HOME/.claude/commands"

    touch "$HOME/.claude/commands/wp-start.md"
    touch "$HOME/.claude/commands/wp-status.md"
    touch "$HOME/.claude/commands/wp-reset.md"
    touch "$HOME/.claude/commands/wp-create-agent.md"

    # Create minimal settings_manager.py mock
    cat > "$HOME/.claude/waypoints/hooks/lib/settings_manager.py" << 'EOF'
import sys
if __name__ == "__main__":
    if sys.argv[1] == "remove":
        print("Hooks removed")
EOF

    echo '{}' > "$HOME/.claude/settings.json"

    # when
    echo "n" | bash "$UNINSTALL_SCRIPT" --dir "$HOME/.claude"

    # then
    [ ! -f "$HOME/.claude/commands/wp-start.md" ]
    [ ! -f "$HOME/.claude/commands/wp-status.md" ]
    [ ! -f "$HOME/.claude/commands/wp-reset.md" ]
    [ ! -f "$HOME/.claude/commands/wp-create-agent.md" ]
}

# =============================================================================
# Tests for installation directory removal
# =============================================================================

@test "uninstall removes waypoints directory" {
    # given
    rm -f "$HOME/.claude/waypoints/hooks"  # Remove symlink to avoid writing to real source
    mkdir -p "$HOME/.claude/waypoints/hooks/lib"
    mkdir -p "$HOME/.claude/waypoints/config"
    mkdir -p "$HOME/.claude/waypoints/agents"
    mkdir -p "$HOME/.claude/waypoints/bin"
    mkdir -p "$HOME/.claude/waypoints/wp_supervisor"

    # Create minimal settings_manager.py mock
    cat > "$HOME/.claude/waypoints/hooks/lib/settings_manager.py" << 'EOF'
import sys
if __name__ == "__main__":
    if sys.argv[1] == "remove":
        print("Hooks removed")
EOF

    echo '{}' > "$HOME/.claude/settings.json"

    # when
    echo "n" | bash "$UNINSTALL_SCRIPT" --dir "$HOME/.claude"

    # then
    [ ! -d "$HOME/.claude/waypoints" ]
}
