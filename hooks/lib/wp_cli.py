#!/usr/bin/env python3
"""
Waypoints CLI - Command-line interface for state management.

This CLI allows Claude (and users) to update Waypoints state without
relying on deprecated marker files. All state is managed via state.json.

Usage:
    python3 wp_cli.py [--dir DIR] init [--session-id ID]
    python3 wp_cli.py [--dir DIR] mark-complete <phase>
    python3 wp_cli.py [--dir DIR] set-phase <n>
    python3 wp_cli.py [--dir DIR] status
    python3 wp_cli.py [--dir DIR] reset

Examples:
    python3 wp_cli.py init --session-id abc123
    python3 wp_cli.py --dir ~/.claude/tmp/wp-abc123 mark-complete requirements
    python3 wp_cli.py --dir ~/.claude/tmp/wp-abc123 set-phase 2
    python3 wp_cli.py --dir ~/.claude/tmp/wp-abc123 status
"""

import argparse
import os
import sys
from pathlib import Path

# Add hooks/lib to path for imports
script_dir = Path(__file__).parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

from wp_state import WPState


def get_state(args) -> WPState:
    """Get WPState instance based on args."""
    # If --dir is specified, use it via env var (WPState checks this first)
    if hasattr(args, 'dir') and args.dir:
        dir_path = os.path.expanduser(args.dir)
        os.environ["WP_SUPERVISOR_MARKERS_DIR"] = dir_path
        return WPState(session_id="cli")

    # Otherwise use session_id
    session_id = getattr(args, 'session_id', None) or os.environ.get("CLAUDE_SESSION_ID", "default")
    return WPState(session_id=session_id)


def cmd_init(args) -> int:
    """Initialize Waypoints workflow."""
    state = get_state(args)
    state.initialize()
    print(f"✓ Waypoints initialized")
    print(f"  State directory: {state.get_marker_dir_display()}")
    return 0


def cmd_mark_complete(args) -> int:
    """Mark a phase as complete."""
    phase = args.phase.lower()
    valid_phases = ["requirements", "interfaces", "tests", "implementation"]

    if phase not in valid_phases:
        print(f"✗ Invalid phase: {phase}")
        print(f"  Valid phases: {', '.join(valid_phases)}")
        return 1

    state = get_state(args)

    if phase == "requirements":
        state.mark_requirements_complete()
    elif phase == "interfaces":
        state.mark_interfaces_complete()
    elif phase == "tests":
        state.mark_tests_complete()
    elif phase == "implementation":
        state.mark_implementation_complete()

    print(f"✓ Marked {phase} as complete")
    return 0


def cmd_set_phase(args) -> int:
    """Set current phase number."""
    try:
        phase_num = int(args.phase_number)
    except ValueError:
        print(f"✗ Invalid phase number: {args.phase_number}")
        return 1

    if phase_num < 1 or phase_num > 4:
        print(f"✗ Phase must be between 1 and 4")
        return 1

    state = get_state(args)
    state.set_phase(phase_num)

    phase_names = {
        1: "Requirements",
        2: "Interfaces",
        3: "Tests",
        4: "Implementation"
    }
    print(f"✓ Set phase to {phase_num} ({phase_names[phase_num]})")
    return 0


def cmd_status(args) -> int:
    """Show current Waypoints status."""
    state = get_state(args)

    active = state.is_active()
    phase = state.get_phase()
    supervisor = state.is_supervisor_mode()

    phase_names = {
        1: "Requirements",
        2: "Interfaces",
        3: "Tests",
        4: "Implementation"
    }

    print("Waypoints Status")
    print("=" * 40)
    print(f"Active:     {'Yes' if active else 'No'}")
    print(f"Mode:       {'Supervisor' if supervisor else 'CLI'}")
    print(f"Phase:      {phase} ({phase_names.get(phase, 'Unknown')})")
    print(f"Directory:  {state.get_marker_dir_display()}")
    print()
    print("Phase Completion:")
    print(f"  Requirements:   {'✓' if state.is_requirements_complete() else '○'}")
    print(f"  Interfaces:     {'✓' if state.is_interfaces_complete() else '○'}")
    print(f"  Tests:          {'✓' if state.is_tests_complete() else '○'}")
    print(f"  Implementation: {'✓' if state.is_implementation_complete() else '○'}")

    return 0


def cmd_reset(args) -> int:
    """Reset Waypoints state."""
    state = get_state(args)

    if args.full:
        state.cleanup_session()
        print("✓ Waypoints fully reset (directory removed)")
    else:
        state.cleanup_workflow_state()
        print("✓ Waypoints workflow state reset")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Waypoints CLI - State management for Waypoints workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Global --dir option
    parser.add_argument("--dir", "-d",
                       help="State directory path (e.g., ~/.claude/tmp/wp-session123)")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize Waypoints workflow")
    init_parser.add_argument("--session-id", help="Session ID (creates ~/.claude/tmp/wp-<session-id>)")
    init_parser.set_defaults(func=cmd_init)

    # mark-complete command
    mark_parser = subparsers.add_parser("mark-complete", help="Mark a phase as complete")
    mark_parser.add_argument("phase", choices=["requirements", "interfaces", "tests", "implementation"],
                            help="Phase to mark as complete")
    mark_parser.set_defaults(func=cmd_mark_complete)

    # set-phase command
    phase_parser = subparsers.add_parser("set-phase", help="Set current phase number")
    phase_parser.add_argument("phase_number", help="Phase number (1-4)")
    phase_parser.set_defaults(func=cmd_set_phase)

    # status command
    status_parser = subparsers.add_parser("status", help="Show current status")
    status_parser.set_defaults(func=cmd_status)

    # reset command
    reset_parser = subparsers.add_parser("reset", help="Reset Waypoints state")
    reset_parser.add_argument("--full", action="store_true",
                             help="Full reset (remove directory)")
    reset_parser.set_defaults(func=cmd_reset)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
