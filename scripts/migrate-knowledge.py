#!/usr/bin/env python3
"""
Waypoints Knowledge Migration Script

Migrates existing markdown knowledge files to graph structure.

Usage:
    python scripts/migrate-knowledge.py [--project-id PROJECT_ID] [--global-only] [--knowledge-dir DIR]

Examples:
    # Migrate specific project
    python scripts/migrate-knowledge.py --project-id my-project

    # Migrate only global lessons-learned
    python scripts/migrate-knowledge.py --global-only

    # Specify custom knowledge directory
    python scripts/migrate-knowledge.py --knowledge-dir /path/to/knowledge
"""

import sys
import argparse
from pathlib import Path

# Add hooks/lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks" / "lib"))

from wp_migration import migrate_knowledge_cli


def main():
    """CLI entry point for knowledge migration."""
    parser = argparse.ArgumentParser(
        description="Migrate Waypoints knowledge from markdown to graph structure"
    )

    parser.add_argument(
        "--project-id",
        help="Project ID to migrate (migrates both project and global knowledge)",
        default=None
    )

    parser.add_argument(
        "--global-only",
        action="store_true",
        help="Only migrate global lessons-learned (not project-specific)"
    )

    parser.add_argument(
        "--knowledge-dir",
        help="Path to knowledge base directory (default: ~/.claude/waypoints/knowledge)",
        default=None
    )

    args = parser.parse_args()

    # Determine knowledge directory
    if args.knowledge_dir:
        knowledge_dir = Path(args.knowledge_dir)
    else:
        knowledge_dir = Path.home() / ".claude" / "waypoints" / "knowledge"

    # Perform migration
    exit_code = migrate_knowledge_cli(
        knowledge_base_dir=knowledge_dir,
        project_id=args.project_id,
        global_only=args.global_only
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
