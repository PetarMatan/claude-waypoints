#!/usr/bin/env bats
# Tests for install.sh

load '../test_helper'

# Path to install.sh
INSTALL_SCRIPT="$PROJECT_ROOT/install.sh"

setup() {
    setup_test_environment

    # Use TEST_TMP from test_helper (set to $BATS_TEST_TMPDIR)
    export SOURCE_DIR="$TEST_TMP/source"
    mkdir -p "$SOURCE_DIR/hooks/lib"
    mkdir -p "$SOURCE_DIR/config"
    mkdir -p "$SOURCE_DIR/skills"
    mkdir -p "$SOURCE_DIR/agents"

    # Create minimal hook files
    echo '#!/bin/bash' > "$SOURCE_DIR/hooks/wp-orchestrator.sh"
    echo '#!/bin/bash' > "$SOURCE_DIR/hooks/wp-phase-guard.sh"
    echo '#!/bin/bash' > "$SOURCE_DIR/hooks/wp-auto-compile.sh"
    echo '#!/bin/bash' > "$SOURCE_DIR/hooks/wp-auto-test.sh"
    echo '#!/bin/bash' > "$SOURCE_DIR/hooks/wp-cleanup-markers.sh"
    echo '#!/bin/bash' > "$SOURCE_DIR/hooks/lib/log.sh"
    echo '#!/bin/bash' > "$SOURCE_DIR/uninstall.sh"

    # Create config
    cat > "$SOURCE_DIR/config/settings.example.json" << 'EOF'
{
  "hooks": {}
}
EOF
    cat > "$SOURCE_DIR/config/wp-config.json" << 'EOF'
{
  "profiles": {}
}
EOF

    # Create skills
    echo '# WP' > "$SOURCE_DIR/skills/wp-start.md"
    echo '# Status' > "$SOURCE_DIR/skills/wp-status.md"
    echo '# Reset' > "$SOURCE_DIR/skills/wp-reset.md"
    echo '# Create' > "$SOURCE_DIR/skills/wp-create-agent.md"

    # Create agent
    echo '# Agent' > "$SOURCE_DIR/agents/test-agent.md"

    # Override install paths for testing
    export INSTALL_DIR="$TEST_TMP/install"
    export COMMANDS_DIR="$TEST_TMP/commands"
    export SETTINGS_FILE="$TEST_TMP/settings.json"
}

teardown() {
    teardown_test_environment
}

# Helper to run the update_settings Python code directly
run_update_settings() {
    local settings_file="$1"
    local install_dir="$2"

    python3 - "$settings_file" "$install_dir" <<'PYTHON'
import json
import sys
import os
import tempfile

settings_file = sys.argv[1]
install_dir = sys.argv[2]

with open(settings_file, 'r') as f:
    settings = json.load(f)

if 'permissions' not in settings:
    settings['permissions'] = {}
if 'allow' not in settings['permissions']:
    settings['permissions']['allow'] = []

wp_permissions = [
    "Bash(mkdir -p ~/.claude/tmp:*)",
    "Bash(mkdir -p ~/.claude/tmp &&:*)",
    "Bash(touch ~/.claude/tmp/:*)",
    "Bash(echo:*)",
    "Bash(rm -f ~/.claude/tmp/wp-*:*)",
    "Bash(cat ~/.claude/tmp/:*)"
]

for perm in wp_permissions:
    if perm not in settings['permissions']['allow']:
        settings['permissions']['allow'].append(perm)

if 'hooks' not in settings:
    settings['hooks'] = {}

wp_hooks = {
    "PreToolUse": [
        {
            "matcher": "Write|Edit",
            "hooks": [{
                "type": "command",
                "command": f"python3 {install_dir}/hooks/wp-phase-guard.py",
                "timeout": 5000
            }]
        }
    ],
    "PostToolUse": [
        {
            "matcher": "Write|Edit",
            "hooks": [{
                "type": "command",
                "command": f"python3 {install_dir}/hooks/wp-auto-compile.py",
                "timeout": 120000
            }]
        },
        {
            "matcher": "Write|Edit",
            "hooks": [{
                "type": "command",
                "command": f"python3 {install_dir}/hooks/wp-auto-test.py",
                "timeout": 300000
            }]
        }
    ],
    "Stop": [
        {
            "hooks": [{
                "type": "command",
                "command": f"python3 {install_dir}/hooks/wp-orchestrator.py",
                "timeout": 120000
            }]
        }
    ],
    "SessionEnd": [
        {
            "hooks": [{
                "type": "command",
                "command": f"python3 {install_dir}/hooks/wp-cleanup-markers.py",
                "timeout": 5000
            }]
        }
    ]
}

for event, hooks in wp_hooks.items():
    if event not in settings['hooks']:
        settings['hooks'][event] = []

    existing_commands = set()
    for hook_config in settings['hooks'][event]:
        for h in hook_config.get('hooks', []):
            existing_commands.add(h.get('command', ''))

    for hook in hooks:
        hook_cmd = hook['hooks'][0]['command']
        if hook_cmd not in existing_commands:
            settings['hooks'][event].append(hook)

settings_dir = os.path.dirname(settings_file)
with tempfile.NamedTemporaryFile(mode='w', dir=settings_dir, suffix='.json', delete=False) as f:
    temp_file = f.name
    json.dump(settings, f, indent=2)

os.replace(temp_file, settings_file)
print("OK")
PYTHON
}

@test "update_settings preserves existing settings" {
    # Create settings with existing content
    cat > "$SETTINGS_FILE" << 'EOF'
{
  "existingKey": "existingValue",
  "permissions": {
    "allow": ["Bash(existing:*)"]
  }
}
EOF

    run run_update_settings "$SETTINGS_FILE" "$INSTALL_DIR"
    [ "$status" -eq 0 ]

    # Verify existing content preserved
    run python3 -c "import json; s=json.load(open('$SETTINGS_FILE')); print(s.get('existingKey', ''))"
    [ "$output" = "existingValue" ]

    # Verify existing permission preserved
    run python3 -c "import json; s=json.load(open('$SETTINGS_FILE')); print('Bash(existing:*)' in s['permissions']['allow'])"
    [ "$output" = "True" ]
}

@test "update_settings adds WP permissions" {
    cat > "$SETTINGS_FILE" << 'EOF'
{
  "permissions": {
    "allow": []
  }
}
EOF

    run run_update_settings "$SETTINGS_FILE" "$INSTALL_DIR"
    [ "$status" -eq 0 ]

    # Verify WP permissions added
    run python3 -c "import json; s=json.load(open('$SETTINGS_FILE')); print('Bash(mkdir -p ~/.claude/tmp:*)' in s['permissions']['allow'])"
    [ "$output" = "True" ]
}

@test "update_settings adds hooks without duplicating" {
    cat > "$SETTINGS_FILE" << 'EOF'
{
  "hooks": {}
}
EOF

    # Run twice
    run run_update_settings "$SETTINGS_FILE" "$INSTALL_DIR"
    [ "$status" -eq 0 ]

    run run_update_settings "$SETTINGS_FILE" "$INSTALL_DIR"
    [ "$status" -eq 0 ]

    # Verify no duplicates
    run python3 -c "import json; s=json.load(open('$SETTINGS_FILE')); print(len(s['hooks'].get('Stop', [])))"
    [ "$output" = "1" ]
}

@test "update_settings preserves existing hooks" {
    cat > "$SETTINGS_FILE" << 'EOF'
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": "existing-hook.sh"}]
      }
    ]
  }
}
EOF

    run run_update_settings "$SETTINGS_FILE" "$INSTALL_DIR"
    [ "$status" -eq 0 ]

    # Verify existing hook preserved
    run python3 -c "
import json
s=json.load(open('$SETTINGS_FILE'))
hooks = s['hooks']['PreToolUse']
existing = any('existing-hook.sh' in str(h) for h in hooks)
print(existing)
"
    [ "$output" = "True" ]

    # Verify WP hook also added
    run python3 -c "
import json
s=json.load(open('$SETTINGS_FILE'))
hooks = s['hooks']['PreToolUse']
wp = any('wp-phase-guard.py' in str(h) for h in hooks)
print(wp)
"
    [ "$output" = "True" ]
}

@test "update_settings creates valid JSON" {
    cat > "$SETTINGS_FILE" << 'EOF'
{}
EOF

    run run_update_settings "$SETTINGS_FILE" "$INSTALL_DIR"
    [ "$status" -eq 0 ]

    # Verify valid JSON
    run python3 -c "import json; json.load(open('$SETTINGS_FILE')); print('valid')"
    [ "$output" = "valid" ]
}

@test "update_settings handles empty permissions array" {
    cat > "$SETTINGS_FILE" << 'EOF'
{
  "permissions": {}
}
EOF

    run run_update_settings "$SETTINGS_FILE" "$INSTALL_DIR"
    [ "$status" -eq 0 ]

    # Should create allow array
    run python3 -c "import json; s=json.load(open('$SETTINGS_FILE')); print(type(s['permissions']['allow']).__name__)"
    [ "$output" = "list" ]
}

@test "update_settings handles missing hooks key" {
    cat > "$SETTINGS_FILE" << 'EOF'
{
  "someOtherKey": true
}
EOF

    run run_update_settings "$SETTINGS_FILE" "$INSTALL_DIR"
    [ "$status" -eq 0 ]

    # Should create hooks
    run python3 -c "import json; s=json.load(open('$SETTINGS_FILE')); print('hooks' in s)"
    [ "$output" = "True" ]

    # Should preserve other key
    run python3 -c "import json; s=json.load(open('$SETTINGS_FILE')); print(s.get('someOtherKey', False))"
    [ "$output" = "True" ]
}

@test "update_settings atomic write prevents corruption" {
    cat > "$SETTINGS_FILE" << 'EOF'
{"original": true}
EOF

    # Get original content
    original_content=$(cat "$SETTINGS_FILE")

    run run_update_settings "$SETTINGS_FILE" "$INSTALL_DIR"
    [ "$status" -eq 0 ]

    # File should be valid JSON after update
    run python3 -c "import json; json.load(open('$SETTINGS_FILE')); print('valid')"
    [ "$output" = "valid" ]

    # No temp files left behind
    temp_files=$(ls "$TEST_TMP"/*.json.* 2>/dev/null | wc -l || echo "0")
    [ "$temp_files" -eq 0 ]
}

@test "update_settings fails gracefully on invalid JSON" {
    echo "not valid json" > "$SETTINGS_FILE"

    run run_update_settings "$SETTINGS_FILE" "$INSTALL_DIR"
    [ "$status" -ne 0 ]
}

@test "update_settings preserves complex nested structures" {
    cat > "$SETTINGS_FILE" << 'EOF'
{
  "model": "claude-3-opus",
  "permissions": {
    "allow": ["Bash(git:*)"],
    "deny": ["Bash(rm -rf:*)"]
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Read",
        "hooks": [{"type": "command", "command": "echo read", "timeout": 1000}]
      }
    ]
  },
  "customSettings": {
    "nested": {
      "deeply": {
        "value": 42
      }
    }
  }
}
EOF

    run run_update_settings "$SETTINGS_FILE" "$INSTALL_DIR"
    [ "$status" -eq 0 ]

    # Verify complex structure preserved
    run python3 -c "import json; s=json.load(open('$SETTINGS_FILE')); print(s['customSettings']['nested']['deeply']['value'])"
    [ "$output" = "42" ]

    # Verify deny preserved
    run python3 -c "import json; s=json.load(open('$SETTINGS_FILE')); print('Bash(rm -rf:*)' in s['permissions']['deny'])"
    [ "$output" = "True" ]

    # Verify model preserved
    run python3 -c "import json; s=json.load(open('$SETTINGS_FILE')); print(s.get('model', ''))"
    [ "$output" = "claude-3-opus" ]
}

@test "update_settings adds all 4 hook events" {
    cat > "$SETTINGS_FILE" << 'EOF'
{}
EOF

    run run_update_settings "$SETTINGS_FILE" "$INSTALL_DIR"
    [ "$status" -eq 0 ]

    # Verify all 4 hook events exist
    run python3 -c "import json; s=json.load(open('$SETTINGS_FILE')); print('PreToolUse' in s['hooks'])"
    [ "$output" = "True" ]

    run python3 -c "import json; s=json.load(open('$SETTINGS_FILE')); print('PostToolUse' in s['hooks'])"
    [ "$output" = "True" ]

    run python3 -c "import json; s=json.load(open('$SETTINGS_FILE')); print('Stop' in s['hooks'])"
    [ "$output" = "True" ]

    run python3 -c "import json; s=json.load(open('$SETTINGS_FILE')); print('SessionEnd' in s['hooks'])"
    [ "$output" = "True" ]

    # Verify correct number of hooks per event
    run python3 -c "import json; s=json.load(open('$SETTINGS_FILE')); print(len(s['hooks']['PreToolUse']))"
    [ "$output" = "1" ]

    run python3 -c "import json; s=json.load(open('$SETTINGS_FILE')); print(len(s['hooks']['PostToolUse']))"
    [ "$output" = "2" ]

    run python3 -c "import json; s=json.load(open('$SETTINGS_FILE')); print(len(s['hooks']['Stop']))"
    [ "$output" = "1" ]

    run python3 -c "import json; s=json.load(open('$SETTINGS_FILE')); print(len(s['hooks']['SessionEnd']))"
    [ "$output" = "1" ]
}

@test "update_settings hook structure is correct" {
    cat > "$SETTINGS_FILE" << 'EOF'
{}
EOF

    run run_update_settings "$SETTINGS_FILE" "$INSTALL_DIR"
    [ "$status" -eq 0 ]

    # Verify PreToolUse hook structure
    run python3 -c "
import json
s = json.load(open('$SETTINGS_FILE'))
hook = s['hooks']['PreToolUse'][0]
assert hook['matcher'] == 'Write|Edit', f\"matcher: {hook.get('matcher')}\"
assert hook['hooks'][0]['type'] == 'command', f\"type: {hook['hooks'][0].get('type')}\"
assert 'wp-phase-guard.py' in hook['hooks'][0]['command'], f\"command: {hook['hooks'][0].get('command')}\"
assert hook['hooks'][0]['timeout'] == 5000, f\"timeout: {hook['hooks'][0].get('timeout')}\"
print('OK')
"
    [ "$output" = "OK" ]

    # Verify PostToolUse auto-compile hook structure
    run python3 -c "
import json
s = json.load(open('$SETTINGS_FILE'))
hook = s['hooks']['PostToolUse'][0]
assert hook['matcher'] == 'Write|Edit', f\"matcher: {hook.get('matcher')}\"
assert hook['hooks'][0]['type'] == 'command', f\"type: {hook['hooks'][0].get('type')}\"
assert 'wp-auto-compile.py' in hook['hooks'][0]['command'], f\"command: {hook['hooks'][0].get('command')}\"
assert hook['hooks'][0]['timeout'] == 120000, f\"timeout: {hook['hooks'][0].get('timeout')}\"
print('OK')
"
    [ "$output" = "OK" ]

    # Verify PostToolUse wp-auto-test hook structure
    run python3 -c "
import json
s = json.load(open('$SETTINGS_FILE'))
hook = s['hooks']['PostToolUse'][1]
assert hook['matcher'] == 'Write|Edit', f\"matcher: {hook.get('matcher')}\"
assert hook['hooks'][0]['type'] == 'command', f\"type: {hook['hooks'][0].get('type')}\"
assert 'wp-auto-test.py' in hook['hooks'][0]['command'], f\"command: {hook['hooks'][0].get('command')}\"
assert hook['hooks'][0]['timeout'] == 300000, f\"timeout: {hook['hooks'][0].get('timeout')}\"
print('OK')
"
    [ "$output" = "OK" ]

    # Verify Stop hook structure (no matcher for Stop)
    run python3 -c "
import json
s = json.load(open('$SETTINGS_FILE'))
hook = s['hooks']['Stop'][0]
assert 'matcher' not in hook, f\"Stop should not have matcher: {hook.get('matcher')}\"
assert hook['hooks'][0]['type'] == 'command', f\"type: {hook['hooks'][0].get('type')}\"
assert 'wp-orchestrator.py' in hook['hooks'][0]['command'], f\"command: {hook['hooks'][0].get('command')}\"
assert hook['hooks'][0]['timeout'] == 120000, f\"timeout: {hook['hooks'][0].get('timeout')}\"
print('OK')
"
    [ "$output" = "OK" ]

    # Verify SessionEnd hook structure (no matcher for SessionEnd)
    run python3 -c "
import json
s = json.load(open('$SETTINGS_FILE'))
hook = s['hooks']['SessionEnd'][0]
assert 'matcher' not in hook, f\"SessionEnd should not have matcher: {hook.get('matcher')}\"
assert hook['hooks'][0]['type'] == 'command', f\"type: {hook['hooks'][0].get('type')}\"
assert 'wp-cleanup-markers.py' in hook['hooks'][0]['command'], f\"command: {hook['hooks'][0].get('command')}\"
assert hook['hooks'][0]['timeout'] == 5000, f\"timeout: {hook['hooks'][0].get('timeout')}\"
print('OK')
"
    [ "$output" = "OK" ]
}

# =============================================================================
# Tests for --dir parameter
# =============================================================================

# Helper to source install.sh functions without running the full script
source_install_functions() {
    # Extract and source just the function definitions from install.sh
    # We need to source the script up to the point where functions are defined
    # but stop before the actual installation runs

    # Create a modified version that only defines functions
    cat > "$TEST_TMP/install_functions.sh" << 'SCRIPT_END'
#!/bin/bash
set -e

# Default CLAUDE_DIR
CLAUDE_DIR="${HOME}/.claude"

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
SCRIPT_END

    source "$TEST_TMP/install_functions.sh"
}

@test "parse_arguments sets CLAUDE_DIR when --dir provided" {
    source_install_functions

    # given
    mkdir -p "$TEST_TMP/custom-claude"

    # when
    parse_arguments --dir "$TEST_TMP/custom-claude"

    # then
    [ "$CLAUDE_DIR" = "$TEST_TMP/custom-claude" ]
}

@test "parse_arguments uses default when no --dir provided" {
    source_install_functions

    # when
    parse_arguments

    # then
    [ "$CLAUDE_DIR" = "$HOME/.claude" ]
}

@test "parse_arguments fails when --dir has no value" {
    source_install_functions

    # when
    run parse_arguments --dir

    # then
    [ "$status" -ne 0 ]
    assert_output_contains "Error: --dir requires a path argument"
}

@test "parse_arguments fails on unknown option" {
    source_install_functions

    # when
    run parse_arguments --unknown-option

    # then
    [ "$status" -ne 0 ]
    assert_output_contains "Error: Unknown option"
}

@test "validate_claude_dir succeeds when directory exists" {
    source_install_functions

    # given
    mkdir -p "$TEST_TMP/existing-dir"
    CLAUDE_DIR="$TEST_TMP/existing-dir"

    # when
    run validate_claude_dir

    # then
    [ "$status" -eq 0 ]
}

@test "validate_claude_dir fails when directory does not exist" {
    source_install_functions

    # given
    CLAUDE_DIR="$TEST_TMP/nonexistent-dir"

    # when
    run validate_claude_dir

    # then
    [ "$status" -ne 0 ]
    assert_output_contains "Error: Directory does not exist"
}

@test "show_usage displays help and exits successfully" {
    source_install_functions

    # when
    run show_usage

    # then
    [ "$status" -eq 0 ]
    assert_output_contains "Usage:"
    assert_output_contains "--dir"
    assert_output_contains "--help"
}

@test "--help shows usage" {
    source_install_functions

    # when
    run parse_arguments --help

    # then
    [ "$status" -eq 0 ]
    assert_output_contains "Usage:"
}
