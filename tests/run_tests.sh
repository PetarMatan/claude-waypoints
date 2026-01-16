#!/bin/bash
# Test runner for Waypoints Workflow
# Usage: ./tests/run_tests.sh [options]
#
# Options:
#   -p, --python      Run only Python tests
#   -b, --bash        Run only Bash/bats tests
#   -u, --unit        Run only unit tests (bash)
#   -i, --integration Run only integration tests (bash)
#   -v, --verbose     Verbose output
#   -e, --e2e         Include E2E tests (skipped by default)
#   --filter PATTERN  Run tests matching pattern

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Default options - run everything
RUN_PYTHON=true
RUN_BASH=true
RUN_UNIT=true
RUN_INTEGRATION=true
VERBOSE=""
RUN_E2E=""
FILTER=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--python)
            RUN_PYTHON=true
            RUN_BASH=false
            shift
            ;;
        -b|--bash)
            RUN_PYTHON=false
            RUN_BASH=true
            shift
            ;;
        -u|--unit)
            RUN_UNIT=true
            RUN_INTEGRATION=false
            shift
            ;;
        -i|--integration)
            RUN_UNIT=false
            RUN_INTEGRATION=true
            shift
            ;;
        -v|--verbose)
            VERBOSE="yes"
            shift
            ;;
        -e|--e2e)
            RUN_E2E="yes"
            shift
            ;;
        --filter)
            FILTER="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  -p, --python      Run only Python tests"
            echo "  -b, --bash        Run only Bash/bats tests"
            echo "  -u, --unit        Run only unit tests (bash)"
            echo "  -i, --integration Run only integration tests (bash)"
            echo "  -v, --verbose     Verbose output"
            echo "  -e, --e2e         Include E2E tests (skipped by default)"
            echo "  --filter PATTERN  Run tests matching pattern"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Print header
echo "========================================"
echo "  Waypoints Workflow Test Suite"
echo "========================================"
echo ""

TESTS_PASSED=0
TESTS_FAILED=0

# ========================================
# Python Tests
# ========================================
if [[ "$RUN_PYTHON" == "true" ]]; then
    echo "----------------------------------------"
    echo "  Python Tests (pytest)"
    echo "----------------------------------------"

    # Check for pytest
    if ! python3 -m pytest --version &> /dev/null; then
        echo "Warning: pytest is not installed. Skipping Python tests."
        echo "Install with: pip install pytest"
        echo ""
    else
        # Default: show test names (like bats does)
        PYTEST_OPTS="-v --tb=short"
        if [[ -n "$VERBOSE" ]]; then
            # Extra verbose: show full tracebacks
            PYTEST_OPTS="-v --tb=long"
        fi

        # Apply filter if specified
        PYTEST_FILTER=""
        if [[ -n "$FILTER" ]]; then
            PYTEST_FILTER="-k $FILTER"
        fi

        # Set E2E environment variable if requested
        if [[ -n "$RUN_E2E" ]]; then
            export RUN_E2E_TESTS=1
            echo "E2E tests enabled"
        fi

        cd "$PROJECT_ROOT"
        if python3 -m pytest tests/unit/python/ $PYTEST_OPTS $PYTEST_FILTER; then
            echo ""
            TESTS_PASSED=$((TESTS_PASSED + 1))
        else
            echo ""
            TESTS_FAILED=$((TESTS_FAILED + 1))
        fi
    fi
fi

# ========================================
# Bash Tests (bats)
# ========================================
if [[ "$RUN_BASH" == "true" ]]; then
    echo "----------------------------------------"
    echo "  Bash Tests (bats)"
    echo "----------------------------------------"

    # Check for bats
    if ! command -v bats &> /dev/null; then
        echo "Warning: bats is not installed. Skipping Bash tests."
        echo "Install with:"
        echo "  brew install bats-core    # macOS"
        echo "  apt install bats          # Debian/Ubuntu"
        echo "  npm install -g bats       # npm"
        echo ""
    else
        # Collect test files
        TEST_FILES=()

        if [[ "$RUN_UNIT" == "true" ]]; then
            for f in "$SCRIPT_DIR"/unit/*.bats; do
                [[ -f "$f" ]] && TEST_FILES+=("$f")
            done
        fi

        if [[ "$RUN_INTEGRATION" == "true" ]]; then
            for f in "$SCRIPT_DIR"/integration/*.bats; do
                [[ -f "$f" ]] && TEST_FILES+=("$f")
            done
        fi

        # Apply filter if specified
        if [[ -n "$FILTER" ]]; then
            FILTERED=()
            for f in "${TEST_FILES[@]}"; do
                if [[ "$f" == *"$FILTER"* ]]; then
                    FILTERED+=("$f")
                fi
            done
            TEST_FILES=("${FILTERED[@]}")
        fi

        if [[ ${#TEST_FILES[@]} -eq 0 ]]; then
            echo "No bats test files found."
            echo ""
        else
            echo "Running ${#TEST_FILES[@]} bats test file(s)..."
            echo ""

            # Run tests
            BATS_OPTS="--timing"
            if [[ -n "$VERBOSE" ]]; then
                BATS_OPTS="$BATS_OPTS --verbose-run"
            fi

            if bats $BATS_OPTS "${TEST_FILES[@]}"; then
                TESTS_PASSED=$((TESTS_PASSED + 1))
            else
                TESTS_FAILED=$((TESTS_FAILED + 1))
            fi
        fi
    fi
fi

# ========================================
# Summary
# ========================================
echo ""
echo "========================================"
if [[ $TESTS_FAILED -eq 0 ]]; then
    echo "  All tests passed!"
else
    echo "  Some tests failed!"
fi
echo "========================================"

exit $TESTS_FAILED
