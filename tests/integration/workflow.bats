#!/usr/bin/env bats
# Integration tests for full Waypoints workflow

load '../test_helper'

setup() {
    setup_test_environment

    export PROJECT_DIR="$TEST_TMP/project"
    create_mock_project "kotlin-maven" "$PROJECT_DIR"

    export WP_INSTALL_DIR="$PROJECT_ROOT"
    export WP_CONFIG_FILE="$PROJECT_ROOT/config/wp-config.json"

    set_mock_compile_result 0 "BUILD SUCCESS"
    set_mock_test_result 0 "Tests run: 10, Failures: 0"
}

teardown() {
    teardown_test_environment
}

# Helper to simulate the full workflow
run_orchestrator() {
    local input="$1"
    echo "$input" | python3 "$HOOKS_DIR/wp-orchestrator.py"
}

run_phase_guard() {
    local input="$1"
    echo "$input" | python3 "$HOOKS_DIR/wp-phase-guard.py"
}

# =============================================================================
# Full Workflow Integration Tests
# =============================================================================

@test "phase-guard blocks correctly through all phases" {
    # This test verifies phase-guard behavior at each phase
    # Phase transitions are handled by activation hook (tested separately)

    create_marker "wp-mode"
    local write_input=$(generate_hook_input "Write" "$PROJECT_DIR/src/main/kotlin/Service.kt" "$PROJECT_DIR")
    local test_input=$(generate_hook_input "Write" "$PROJECT_DIR/src/test/kotlin/ServiceTest.kt" "$PROJECT_DIR")

    # === PHASE 1: Requirements ===
    set_phase 1

    # Should block all source edits
    run run_phase_guard "$write_input"
    assert_decision_block
    run run_phase_guard "$test_input"
    assert_decision_block

    # === PHASE 2: Interfaces ===
    set_phase 2

    # Should allow main source, block tests
    run run_phase_guard "$write_input"
    assert_decision_allow
    run run_phase_guard "$test_input"
    assert_decision_block

    # === PHASE 3: Tests ===
    set_phase 3

    # Should block main source, allow tests
    run run_phase_guard "$write_input"
    assert_decision_block
    run run_phase_guard "$test_input"
    assert_decision_allow

    # === PHASE 4: Implementation ===
    set_phase 4

    # Should allow all edits
    run run_phase_guard "$write_input"
    assert_decision_allow
    run run_phase_guard "$test_input"
    assert_decision_allow
}

@test "orchestrator runs build verification in phase 4" {
    create_marker "wp-mode"
    set_phase 4

    local stop_input=$(generate_stop_hook_input "$PROJECT_DIR")

    # With passing compile and tests, should complete workflow
    set_mock_compile_result 0 "BUILD SUCCESS"
    set_mock_test_result 0 "Tests run: 10, Failures: 0"

    run run_orchestrator "$stop_input"
    [ "$status" -eq 0 ]

    # Verify completion
    marker_exists "wp-tests-passing"
    ! marker_exists "wp-mode"
}

@test "workflow handles compile failures in phase 2" {
    create_marker "wp-mode"
    set_phase 2

    set_mock_compile_result 1 "[ERROR] Cannot find symbol"

    local stop_input=$(generate_stop_hook_input "$PROJECT_DIR")
    run run_orchestrator "$stop_input"

    assert_decision_block
    assert_output_contains "Compilation FAILED"
    assert_output_contains "Cannot find symbol"

    # Should still be in phase 2
    [ "$(get_phase)" = "2" ]
}

@test "workflow handles test failures in phase 4" {
    create_marker "wp-mode"
    set_phase 4

    set_mock_compile_result 0 "BUILD SUCCESS"
    set_mock_test_result 1 "Tests run: 5, Failures: 2"

    local stop_input=$(generate_stop_hook_input "$PROJECT_DIR")
    run run_orchestrator "$stop_input"

    assert_decision_block
    assert_output_contains "Tests FAILED"

    # Should still be in phase 4 (loop until pass)
    [ "$(get_phase)" = "4" ]
    marker_exists "wp-mode"
}

# =============================================================================
# TypeScript Workflow Tests
# =============================================================================

@test "TypeScript project phase-guard works correctly" {
    # Create TypeScript project
    local ts_project="$TEST_TMP/ts-project"
    create_mock_project "typescript-npm" "$ts_project"

    create_marker "wp-mode"

    local ts_write=$(generate_hook_input "Write" "$ts_project/src/service.ts" "$ts_project")
    local ts_test=$(generate_hook_input "Write" "$ts_project/src/service.test.ts" "$ts_project")

    # Phase 1: Block all
    set_phase 1
    run run_phase_guard "$ts_write"
    assert_decision_block

    # Phase 2: Allow source, block tests
    set_phase 2
    run run_phase_guard "$ts_write"
    assert_decision_allow
    run run_phase_guard "$ts_test"
    assert_decision_block
}

# =============================================================================
# Reset Workflow Tests
# =============================================================================

@test "reset clears all state and allows restart" {
    # Set up mid-workflow state
    create_marker "wp-mode"
    set_phase 3
    create_marker "wp-requirements-confirmed"
    create_marker "wp-interfaces-designed"

    # Simulate reset by removing state.json
    rm -f "$TEST_MARKERS_DIR/state.json"

    # Orchestrator should do nothing now (TDD not active)
    local stop_input=$(generate_stop_hook_input "$PROJECT_DIR")
    run run_orchestrator "$stop_input"
    [ "$status" -eq 0 ]
    [ -z "$output" ]

    # Phase guard should allow everything
    local write_input=$(generate_hook_input "Write" "$PROJECT_DIR/src/main/kotlin/Service.kt" "$PROJECT_DIR")
    run run_phase_guard "$write_input"
    [ -z "$output" ]
}

# =============================================================================
# Session End Integration Tests
# =============================================================================

@test "session end cleans up mid-workflow state" {
    create_marker "wp-mode"
    set_phase 2
    create_marker "wp-requirements-confirmed"

    # Run session end cleanup (use same session_id as TEST_SESSION_ID)
    local cleanup_input='{"hook_event_name": "SessionEnd", "session_id": "test-session"}'
    echo "$cleanup_input" | python3 "$HOOKS_DIR/wp-cleanup-markers.py"

    # All state should be gone
    ! marker_exists "wp-mode"
    ! marker_exists "wp-phase"
    ! marker_exists "wp-requirements-confirmed"

    # New session should start fresh
    local stop_input=$(generate_stop_hook_input "$PROJECT_DIR")
    run run_orchestrator "$stop_input"
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

# =============================================================================
# Error Recovery Tests
# =============================================================================

@test "orchestrator silent in phase 1" {
    create_marker "wp-mode"
    set_phase 1

    local stop_input=$(generate_stop_hook_input "$PROJECT_DIR")
    run run_orchestrator "$stop_input"

    # Orchestrator should return silently in phase 1 (no build verification)
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "orchestrator silent when WP inactive" {
    # No wp-mode marker
    local stop_input=$(generate_stop_hook_input "$PROJECT_DIR")
    run run_orchestrator "$stop_input"

    [ "$status" -eq 0 ]
    [ -z "$output" ]
}
