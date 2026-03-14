"""
Waypoints Supervisor - Session orchestration for Waypoints workflow.

This module provides a supervisor that manages Claude Code sessions
across Waypoints phases, handling context transfer and session lifecycle.
"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("claude-waypoints")
except PackageNotFoundError:
    __version__ = "dev"
