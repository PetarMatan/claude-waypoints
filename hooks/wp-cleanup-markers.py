#!/usr/bin/env python3
"""
Waypoints Cleanup Markers - SessionEnd Hook

Removes Waypoints marker files to ensure fresh state for next session.
"""

import os
import sys

# Add lib directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

from hook_io import HookInput
from markers import MarkerManager
from wp_logging import WPLogger


def main():
    # Parse hook input
    hook = HookInput.from_stdin()

    # Only process SessionEnd events
    if hook.hook_event_name != "SessionEnd":
        return

    # Initialize logger and markers
    logger = WPLogger(hook.session_id)
    markers = MarkerManager(hook.session_id)

    logger.log_session("Session ending - cleaning up Waypoints markers")

    # Clean up Waypoints workflow markers for this session
    markers.cleanup_session()

    logger.log_session("Waypoints markers cleanup complete")


if __name__ == '__main__':
    main()
