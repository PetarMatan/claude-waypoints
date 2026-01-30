#!/bin/bash
set -e

# Waypoints Workflow Uninstaller for Claude Code
# Version: 2.1.0
#
# Usage:
#   ./uninstall.sh
#   ./uninstall.sh --dir /path/to/custom/claude/dir
#
# Options:
#   --dir /path/to/dir    Uninstall from custom directory instead of ~/.claude

# --- Interface: Functions ---

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

# --- Parse arguments ---
CLAUDE_DIR="${HOME}/.claude"
parse_arguments "$@"
validate_claude_dir

# --- Directory paths (derived from CLAUDE_DIR) ---
INSTALL_DIR="${CLAUDE_DIR}/waypoints"
COMMANDS_DIR="${CLAUDE_DIR}/commands"
SETTINGS_FILE="${CLAUDE_DIR}/settings.json"
SESSIONS_DIR="${CLAUDE_DIR}/logs/sessions"

echo "=== Waypoints Workflow Uninstaller ==="
echo "Uninstalling from: $CLAUDE_DIR"
echo ""

# Remove Waypoints markers (both old flat files and new session-scoped directories)
echo "Cleaning up Waypoints markers..."
rm -f "${CLAUDE_DIR}/tmp/wp-mode" 2>/dev/null || true
rm -f "${CLAUDE_DIR}/tmp/wp-phase" 2>/dev/null || true
rm -f "${CLAUDE_DIR}/tmp/wp-requirements-confirmed" 2>/dev/null || true
rm -f "${CLAUDE_DIR}/tmp/wp-interfaces-designed" 2>/dev/null || true
rm -f "${CLAUDE_DIR}/tmp/wp-tests-approved" 2>/dev/null || true
rm -f "${CLAUDE_DIR}/tmp/wp-tests-passing" 2>/dev/null || true
rm -rf "${CLAUDE_DIR}/tmp/wp-"* 2>/dev/null || true

# Remove sessions log directory
if [[ -d "$SESSIONS_DIR" ]]; then
    echo "Removing sessions log directory..."
    rm -rf "$SESSIONS_DIR"
fi

# Remove skills
echo "Removing skills..."
rm -f "$COMMANDS_DIR/wp-start.md" 2>/dev/null || true
rm -f "$COMMANDS_DIR/wp-status.md" 2>/dev/null || true
rm -f "$COMMANDS_DIR/wp-reset.md" 2>/dev/null || true
rm -f "$COMMANDS_DIR/wp-create-agent.md" 2>/dev/null || true

# Update settings.json (before removing install dir since we need settings_manager.py)
echo ""
echo "=== Settings Cleanup ==="
echo ""

if [[ -f "$SETTINGS_FILE" && -d "$INSTALL_DIR" ]]; then
    # Check if running interactively
    if [[ -t 0 ]]; then
        read -p "Would you like to remove Waypoints hooks from settings.json? (y/n): " -n 1 -r
        echo ""
    else
        # Non-interactive (piped) - default to yes
        echo "Running non-interactively, automatically removing hooks from settings..."
        REPLY="y"
    fi

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Backup existing settings
        cp "$SETTINGS_FILE" "${SETTINGS_FILE}.backup.$(date +%Y%m%d%H%M%S)"
        echo "Backup created."

        # Use settings_manager to remove Waypoints hooks
        python3 "$INSTALL_DIR/hooks/lib/settings_manager.py" remove "$SETTINGS_FILE"
    else
        echo "Skipping settings cleanup. You may need to manually remove Waypoints hooks."
    fi
elif [[ -f "$SETTINGS_FILE" ]]; then
    echo "Installation directory not found. Skipping settings cleanup."
    echo "You may need to manually remove Waypoints hooks from settings.json."
fi

# Remove installation directory (after settings cleanup)
if [[ -d "$INSTALL_DIR" ]]; then
    echo ""
    echo "Removing installation directory..."
    rm -rf "$INSTALL_DIR"
fi

echo ""
echo "=== Uninstall Complete ==="
echo ""
echo "Waypoints Workflow has been removed from: $CLAUDE_DIR"
echo "Restart Claude Code to apply changes."
