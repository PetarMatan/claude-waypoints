#!/bin/bash
set -e

# Waypoints Workflow Installer for Claude Code
# Version: 2.1.0
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/PetarMatan/claude-waypoints/main/install.sh | bash
#
# Or clone and run locally:
#   git clone https://github.com/PetarMatan/claude-waypoints.git
#   cd claude-waypoints && ./install.sh
#
# Options:
#   --dir /path/to/dir    Install to custom directory instead of ~/.claude
#                         The directory must exist. Example:
#                         ./install.sh --dir ~/.claude-feature

REPO_URL="https://github.com/PetarMatan/claude-waypoints.git"
VERSION="main"

# --- Interface: Functions ---

show_usage() {
    cat << 'EOF'
Waypoints Workflow Installer for Claude Code

Usage:
  ./install.sh [OPTIONS]

Options:
  --dir /path/to/dir    Install to custom directory instead of ~/.claude
                        The directory must exist.
  --help                Show this help message

Examples:
  ./install.sh                      # Install to ~/.claude (default)
  ./install.sh --dir ~/.claude-feature  # Install to custom directory
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
        echo "Please create the directory first or use an existing directory."
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

echo "=== Waypoints Workflow Installer ==="
echo ""

# Check for required tools
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is required but not installed."
    exit 1
fi

# Check Python version (need 3.6+ for f-strings)
python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
python_major=$(echo "$python_version" | cut -d. -f1)
python_minor=$(echo "$python_version" | cut -d. -f2)
if [[ "$python_major" -lt 3 ]] || [[ "$python_major" -eq 3 && "$python_minor" -lt 6 ]]; then
    echo "Error: Python 3.6+ is required. Found Python $python_version"
    exit 1
fi

if ! command -v git &> /dev/null; then
    echo "Error: git is required but not installed."
    exit 1
fi

# Determine if running from repo or via curl
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)" || SCRIPT_DIR=""
TEMP_DIR=""
SOURCE_DIR=""

if [[ -n "$SCRIPT_DIR" && -f "$SCRIPT_DIR/hooks/wp-orchestrator.py" ]]; then
    # Running from cloned repo
    echo "Installing from local repository..."
    SOURCE_DIR="$SCRIPT_DIR"
else
    # Running via curl - need to download
    echo "Downloading Waypoints Workflow..."
    TEMP_DIR=$(mktemp -d)
    trap "rm -rf '$TEMP_DIR'" EXIT

    git clone --depth 1 --branch "$VERSION" "$REPO_URL" "$TEMP_DIR/waypoints" 2>/dev/null || {
        echo "Error: Failed to download repository."
        exit 1
    }
    SOURCE_DIR="$TEMP_DIR/waypoints"
    echo "Download complete."
fi

echo ""

# Backup existing directory before any modifications
if [[ -d "${CLAUDE_DIR}" ]]; then
    BACKUP_DIR="${CLAUDE_DIR}-backup-$(date +%Y%m%d-%H%M%S)"
    echo "=== Creating Backup ==="
    echo "Backing up ${CLAUDE_DIR} to $BACKUP_DIR"
    cp -r "${CLAUDE_DIR}" "$BACKUP_DIR"
    echo "Backup complete: $BACKUP_DIR"
    echo ""
fi

# Create directories
echo "Creating directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$COMMANDS_DIR"
mkdir -p "${CLAUDE_DIR}/tmp"
mkdir -p "${CLAUDE_DIR}/logs/sessions"
mkdir -p "${CLAUDE_DIR}/agents"

# Copy hook files
echo "Installing hooks..."
cp -r "$SOURCE_DIR/hooks" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/hooks/"*.sh 2>/dev/null || true
chmod +x "$INSTALL_DIR/hooks/"*.py
chmod +x "$INSTALL_DIR/hooks/lib/"*.sh 2>/dev/null || true

# Copy config
echo "Installing configuration..."
cp -r "$SOURCE_DIR/config" "$INSTALL_DIR/"

# Copy agents (as examples)
echo "Installing example agents..."
cp -r "$SOURCE_DIR/agents" "$INSTALL_DIR/"

# Copy uninstall script
cp "$SOURCE_DIR/uninstall.sh" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/uninstall.sh"

# Install skills as commands
echo "Installing skills..."
cp "$SOURCE_DIR/skills/wp-start.md" "$COMMANDS_DIR/wp-start.md"
cp "$SOURCE_DIR/skills/wp-status.md" "$COMMANDS_DIR/wp-status.md"
cp "$SOURCE_DIR/skills/wp-reset.md" "$COMMANDS_DIR/wp-reset.md"
cp "$SOURCE_DIR/skills/wp-create-agent.md" "$COMMANDS_DIR/wp-create-agent.md"

# === Install Supervisor Mode ===
echo "Installing Supervisor Mode..."

# Copy supervisor module
cp -r "$SOURCE_DIR/wp_supervisor" "$INSTALL_DIR/"

# Copy bin scripts
mkdir -p "$INSTALL_DIR/bin"
cp "$SOURCE_DIR/bin/wp-supervisor" "$INSTALL_DIR/bin/"
chmod +x "$INSTALL_DIR/bin/wp-supervisor"

# Check for claude-agent-sdk
if python3 -c "import claude_agent_sdk" 2>/dev/null; then
    SDK_INSTALLED="yes"
    echo "  claude-agent-sdk: found"
else
    SDK_INSTALLED=""
    echo "  claude-agent-sdk: NOT FOUND"
    echo "  Supervisor Mode requires it. Install with: pip install claude-agent-sdk"
fi

echo "Supervisor Mode installed."

# Update settings.json
update_settings() {
    python3 "$INSTALL_DIR/hooks/lib/settings_manager.py" add "$SETTINGS_FILE" "$INSTALL_DIR"
}

if [[ -f "$SETTINGS_FILE" ]]; then
    # Validate JSON before attempting to modify
    if ! python3 "$INSTALL_DIR/hooks/lib/settings_manager.py" validate "$SETTINGS_FILE" 2>/dev/null; then
        echo "WARNING: $SETTINGS_FILE exists but is not valid JSON."
        echo "Please fix it manually or delete it and restart Claude Code."
        echo ""
        echo "Skipping settings configuration. See manual setup instructions below."
        SKIP_SETTINGS=true
    else
        echo "Updating settings.json..."
        # Backup existing settings
        cp "$SETTINGS_FILE" "${SETTINGS_FILE}.backup.$(date +%Y%m%d%H%M%S)"
        update_settings
        echo "Settings updated (backup created)."
    fi
else
    echo "No settings.json found."
    echo ""
    echo "Please start Claude Code at least once to create the default settings,"
    echo "then run this installer again to add Waypoints hooks."
    echo ""
    echo "Alternatively, you can manually create settings.json using the template at:"
    echo "  $INSTALL_DIR/config/settings.example.json"
    echo ""
    SKIP_SETTINGS=true
fi

if [[ "$SKIP_SETTINGS" == "true" ]]; then
    echo "=== Manual Settings Setup Required ==="
    echo ""
    echo "Add the following to your ${CLAUDE_DIR}/settings.json:"
    echo ""
    echo "See: $INSTALL_DIR/config/settings.example.json"
    echo ""
fi

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Installed to: $INSTALL_DIR"
if [[ -n "$BACKUP_DIR" ]]; then
    echo "Backup at:    $BACKUP_DIR"
fi
echo ""
echo "Available commands:"
echo "  /wp-start         - Start Waypoints workflow (CLI)"
echo "  /wp-status        - Check current workflow status"
echo "  /wp-reset         - Reset workflow state"
echo "  /wp-create-agent  - Create a custom agent"
echo ""
echo "Supervisor Mode:"
echo "  $INSTALL_DIR/bin/wp-supervisor"
echo ""
echo "  Or add to PATH (add to ~/.zshrc or ~/.bashrc):"
echo "    export PATH=\"\$PATH:$INSTALL_DIR/bin\""
echo ""
echo "  Then run: wp-supervisor"
if [[ "$SDK_INSTALLED" != "yes" ]]; then
    echo ""
    echo "  NOTE: Install claude-agent-sdk before using supervisor mode:"
    echo "    pip install claude-agent-sdk"
fi
echo ""
echo "Restart Claude Code to apply changes."
echo ""
if [[ -n "$BACKUP_DIR" ]]; then
    echo "If something goes wrong, restore with:"
    echo "  rm -rf ${CLAUDE_DIR} && cp -r $BACKUP_DIR ${CLAUDE_DIR}"
    echo ""
fi
echo "Documentation: https://github.com/PetarMatan/claude-waypoints"
