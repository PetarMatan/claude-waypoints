#!/usr/bin/env python3
"""
Waypoints Supervisor - Entry Point

Run the Waypoints supervisor with: python -m wp_supervisor

Usage:
    python -m wp_supervisor [OPTIONS]

Options:
    -d, --dir PATH      Project working directory (default: current)
    -t, --task TEXT     Initial task description
    -h, --help          Show this help message
"""

import argparse
import asyncio
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Waypoints Supervisor - Orchestrate workflow with managed sessions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Start Waypoints workflow in current directory
    python -m wp_supervisor

    # Start with specific project directory
    python -m wp_supervisor -d /path/to/project

    # Start with initial task description
    python -m wp_supervisor -t "Build a REST API for user management"

    # Combine options
    python -m wp_supervisor -d ./my-project -t "Add authentication"

User Commands During Session:
    /done, /complete, /next  - Signal phase completion
    /quit, /exit, /abort     - Abort workflow

Environment Variables:
    WP_SUPERVISOR_WORKFLOW_ID   - Set by supervisor for hooks
    WP_SUPERVISOR_MARKERS_DIR   - Marker directory for hooks
    WP_SUPERVISOR_ACTIVE        - Indicates supervisor mode
""",
    )

    parser.add_argument(
        "-d", "--dir",
        type=str,
        default=".",
        help="Project working directory (default: current directory)",
    )

    parser.add_argument(
        "-t", "--task",
        type=str,
        default=None,
        help="Initial task description",
    )

    args = parser.parse_args()

    # Resolve working directory
    working_dir = Path(args.dir).resolve()
    if not working_dir.is_dir():
        print(f"Error: Directory does not exist: {working_dir}", file=sys.stderr)
        sys.exit(1)

    # Import here to catch import errors with helpful message
    try:
        from .orchestrator import run_supervisor
    except ImportError as e:
        print(f"Error importing orchestrator: {e}", file=sys.stderr)
        print("\nMake sure claude-agent-sdk is installed:", file=sys.stderr)
        print("  pip install claude-agent-sdk", file=sys.stderr)
        sys.exit(1)

    # Run the supervisor
    try:
        asyncio.run(
            run_supervisor(
                working_dir=str(working_dir),
                task=args.task,
            )
        )
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
