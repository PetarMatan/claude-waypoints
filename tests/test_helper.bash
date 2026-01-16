#!/bin/bash
# Test Helper for Waypoints Workflow Tests
# Provides common setup, teardown, and utility functions

# Get the project root directory
export PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export HOOKS_DIR="$PROJECT_ROOT/hooks"
export CONFIG_DIR="$PROJECT_ROOT/config"
export FIXTURES_DIR="$PROJECT_ROOT/tests/fixtures"
export MOCKS_DIR="$FIXTURES_DIR/mocks"

# Default session ID for tests
TEST_SESSION_ID="test-session"

# Setup function - called before each test
setup_test_environment() {
    # Create isolated temp directory for this test
    export TEST_TMP="$BATS_TEST_TMPDIR"
    export WP_TMP="$TEST_TMP/claude-tmp"
    export WP_LOGS="$TEST_TMP/logs"

    mkdir -p "$WP_TMP"
    mkdir -p "$WP_LOGS/sessions"

    # Override home directory for tests
    export REAL_HOME="$HOME"
    export HOME="$TEST_TMP"
    mkdir -p "$HOME/.claude/tmp"
    mkdir -p "$HOME/.claude/logs/sessions"

    # Create session-scoped marker directory
    export TEST_MARKERS_DIR="$HOME/.claude/tmp/wp-${TEST_SESSION_ID}"
    mkdir -p "$TEST_MARKERS_DIR"

    # Link config to test environment
    mkdir -p "$HOME/.claude/waypoints"
    ln -sf "$CONFIG_DIR" "$HOME/.claude/waypoints/config"
    ln -sf "$HOOKS_DIR" "$HOME/.claude/waypoints/hooks"

    # Set up agents directory for tests
    export WP_AGENTS_DIR="$HOME/.claude/agents"
    mkdir -p "$WP_AGENTS_DIR"

    # Set up mock commands path
    export PATH="$MOCKS_DIR:$PATH"

    # Reset mock state
    rm -f "$TEST_TMP/mock_compile_exit_code"
    rm -f "$TEST_TMP/mock_test_exit_code"
    rm -f "$TEST_TMP/mock_compile_output"
    rm -f "$TEST_TMP/mock_test_output"
}

# Teardown function - called after each test
teardown_test_environment() {
    # Restore home directory
    export HOME="$REAL_HOME"
}

# Create a mock project structure
# Usage: create_mock_project "kotlin-maven" "/path/to/project"
create_mock_project() {
    local profile="$1"
    local project_dir="$2"

    mkdir -p "$project_dir"

    case "$profile" in
        "kotlin-maven")
            touch "$project_dir/pom.xml"
            mkdir -p "$project_dir/src/main/kotlin"
            mkdir -p "$project_dir/src/test/kotlin"
            touch "$project_dir/src/main/kotlin/Main.kt"
            ;;
        "typescript-npm")
            echo '{"name": "test"}' > "$project_dir/package.json"
            touch "$project_dir/tsconfig.json"
            mkdir -p "$project_dir/src"
            touch "$project_dir/src/index.ts"
            ;;
        "python-pytest")
            touch "$project_dir/pyproject.toml"
            mkdir -p "$project_dir/src"
            mkdir -p "$project_dir/tests"
            touch "$project_dir/src/main.py"
            ;;
        "go")
            echo "module test" > "$project_dir/go.mod"
            touch "$project_dir/main.go"
            ;;
        *)
            echo "Unknown profile: $profile" >&2
            return 1
            ;;
    esac
}

# Set mock compile result
# Usage: set_mock_compile_result 0 "Build successful"
set_mock_compile_result() {
    local exit_code="$1"
    local output="${2:-}"

    echo "$exit_code" > "$TEST_TMP/mock_compile_exit_code"
    echo "$output" > "$TEST_TMP/mock_compile_output"
}

# Set mock test result
# Usage: set_mock_test_result 1 "Tests failed: 2 of 10"
set_mock_test_result() {
    local exit_code="$1"
    local output="${2:-}"

    echo "$exit_code" > "$TEST_TMP/mock_test_exit_code"
    echo "$output" > "$TEST_TMP/mock_test_output"
}

# Create/update Waypoints state.json file
# Usage: create_wp_state 1 true false false false
create_wp_state() {
    local phase="${1:-1}"
    local req="${2:-false}"
    local int="${3:-false}"
    local test="${4:-false}"
    local impl="${5:-false}"
    local active="${6:-true}"

    cat > "$TEST_MARKERS_DIR/state.json" <<EOF
{
  "version": 1,
  "active": $active,
  "supervisorActive": false,
  "phase": $phase,
  "mode": "cli",
  "completedPhases": {
    "requirements": $req,
    "interfaces": $int,
    "tests": $test,
    "implementation": $impl
  },
  "summaries": {
    "requirements": "",
    "interfaces": "",
    "tests": ""
  },
  "metadata": {
    "startedAt": "2026-01-10T00:00:00",
    "workflowId": "",
    "sessionId": "test-session"
  }
}
EOF
}

# Create TDD marker (backward compatible - creates state.json)
# Usage: create_marker "wp-mode"
create_marker() {
    local marker="$1"
    case "$marker" in
        "wp-mode")
            # Create state.json with active=true if not exists
            if [[ ! -f "$TEST_MARKERS_DIR/state.json" ]]; then
                create_wp_state 1 false false false false true
            else
                # Update active to true
                local tmp=$(mktemp)
                jq '.active = true' "$TEST_MARKERS_DIR/state.json" > "$tmp" && mv "$tmp" "$TEST_MARKERS_DIR/state.json"
            fi
            ;;
        "wp-requirements-confirmed")
            # Update state.json to mark requirements complete
            local tmp=$(mktemp)
            jq '.completedPhases.requirements = true' "$TEST_MARKERS_DIR/state.json" > "$tmp" && mv "$tmp" "$TEST_MARKERS_DIR/state.json"
            ;;
        "wp-interfaces-designed")
            local tmp=$(mktemp)
            jq '.completedPhases.interfaces = true' "$TEST_MARKERS_DIR/state.json" > "$tmp" && mv "$tmp" "$TEST_MARKERS_DIR/state.json"
            ;;
        "wp-tests-approved")
            local tmp=$(mktemp)
            jq '.completedPhases.tests = true' "$TEST_MARKERS_DIR/state.json" > "$tmp" && mv "$tmp" "$TEST_MARKERS_DIR/state.json"
            ;;
        "wp-tests-passing")
            local tmp=$(mktemp)
            jq '.completedPhases.implementation = true' "$TEST_MARKERS_DIR/state.json" > "$tmp" && mv "$tmp" "$TEST_MARKERS_DIR/state.json"
            ;;
        *)
            # Unknown marker, just touch a file for backward compat
            touch "$TEST_MARKERS_DIR/$marker"
            ;;
    esac
}

# Set TDD phase (session-scoped)
# Usage: set_phase 2
set_phase() {
    local phase="$1"
    if [[ ! -f "$TEST_MARKERS_DIR/state.json" ]]; then
        create_wp_state "$phase" false false false false true
    else
        local tmp=$(mktemp)
        jq ".phase = $phase" "$TEST_MARKERS_DIR/state.json" > "$tmp" && mv "$tmp" "$TEST_MARKERS_DIR/state.json"
    fi
}

# Check if marker exists (session-scoped)
# Usage: marker_exists "wp-requirements-confirmed"
marker_exists() {
    local marker="$1"
    if [[ ! -f "$TEST_MARKERS_DIR/state.json" ]]; then
        return 1
    fi

    case "$marker" in
        "wp-mode")
            jq -e '.active == true' "$TEST_MARKERS_DIR/state.json" >/dev/null 2>&1
            ;;
        "wp-requirements-confirmed")
            jq -e '.completedPhases.requirements == true' "$TEST_MARKERS_DIR/state.json" >/dev/null 2>&1
            ;;
        "wp-interfaces-designed")
            jq -e '.completedPhases.interfaces == true' "$TEST_MARKERS_DIR/state.json" >/dev/null 2>&1
            ;;
        "wp-tests-approved")
            jq -e '.completedPhases.tests == true' "$TEST_MARKERS_DIR/state.json" >/dev/null 2>&1
            ;;
        "wp-tests-passing")
            jq -e '.completedPhases.implementation == true' "$TEST_MARKERS_DIR/state.json" >/dev/null 2>&1
            ;;
        "wp-phase")
            jq -e '.phase' "$TEST_MARKERS_DIR/state.json" >/dev/null 2>&1
            ;;
        *)
            [[ -f "$TEST_MARKERS_DIR/$marker" ]]
            ;;
    esac
}

# Get current phase (session-scoped)
get_phase() {
    if [[ -f "$TEST_MARKERS_DIR/state.json" ]]; then
        jq -r '.phase' "$TEST_MARKERS_DIR/state.json" 2>/dev/null || echo "0"
    else
        echo "0"
    fi
}

# Generate hook input JSON
# Usage: generate_hook_input "Write" "/path/to/file.kt" "/project/dir"
generate_hook_input() {
    local tool_name="$1"
    local file_path="$2"
    local cwd="${3:-/project}"
    local session_id="${4:-test-session}"

    cat <<EOF
{
    "tool_name": "$tool_name",
    "tool_input": {
        "file_path": "$file_path"
    },
    "cwd": "$cwd",
    "session_id": "$session_id",
    "stop_hook_active": false
}
EOF
}

# Generate stop hook input JSON
generate_stop_hook_input() {
    local cwd="${1:-/project}"
    local session_id="${2:-test-session}"

    cat <<EOF
{
    "cwd": "$cwd",
    "session_id": "$session_id",
    "stop_hook_active": false
}
EOF
}

# Assert output contains string
# Usage: assert_output_contains "block"
assert_output_contains() {
    local expected="$1"
    if [[ "$output" != *"$expected"* ]]; then
        echo "Expected output to contain: $expected"
        echo "Actual output: $output"
        return 1
    fi
}

# Assert output does not contain string
assert_output_not_contains() {
    local unexpected="$1"
    if [[ "$output" == *"$unexpected"* ]]; then
        echo "Expected output NOT to contain: $unexpected"
        echo "Actual output: $output"
        return 1
    fi
}

# Assert JSON decision is block
assert_decision_block() {
    assert_output_contains '"decision": "block"' || \
    assert_output_contains '"decision":"block"'
}

# Assert JSON decision is approve (or no output = allow)
assert_decision_allow() {
    if [[ -n "$output" ]]; then
        if [[ "$output" == *'"decision"'* ]]; then
            assert_output_contains '"decision": "approve"' || \
            assert_output_contains '"decision":"approve"'
        fi
    fi
    # Empty output also means allow
    return 0
}
