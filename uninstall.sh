#!/bin/bash
set -e

# Waypoints Workflow Uninstaller for Claude Code
# Version: 1.0.0

INSTALL_DIR="${HOME}/.claude/waypoints"
COMMANDS_DIR="${HOME}/.claude/commands"
SETTINGS_FILE="${HOME}/.claude/settings.json"

echo "=== Waypoints Workflow Uninstaller ==="
echo ""

# Remove Waypoints markers (both old flat files and new session-scoped directories)
echo "Cleaning up Waypoints markers..."
rm -f ~/.claude/tmp/wp-mode 2>/dev/null || true
rm -f ~/.claude/tmp/wp-phase 2>/dev/null || true
rm -f ~/.claude/tmp/wp-requirements-confirmed 2>/dev/null || true
rm -f ~/.claude/tmp/wp-interfaces-designed 2>/dev/null || true
rm -f ~/.claude/tmp/wp-tests-approved 2>/dev/null || true
rm -f ~/.claude/tmp/wp-tests-passing 2>/dev/null || true
rm -rf ~/.claude/tmp/wp-* 2>/dev/null || true

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
echo "Waypoints Workflow has been removed."
echo "Restart Claude Code to apply changes."
