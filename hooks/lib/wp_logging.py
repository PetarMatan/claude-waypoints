#!/usr/bin/env python3
"""
Claude Waypoints - Logging Library

Provides logging functionality for Waypoints hooks.
Named wp_logging to avoid conflict with stdlib logging module.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class WPLogger:
    """Logger for Waypoints workflow events."""

    def __init__(self, session_id: str = "unknown"):
        """Initialize logger with session ID."""
        install_dir = os.environ.get("WP_INSTALL_DIR", str(Path.home() / ".claude" / "waypoints"))
        self.log_dir = Path(install_dir) / "logs"
        self.session_log_dir = self.log_dir / "sessions"
        self.session_id = session_id

        # Ensure directories exist
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.session_log_dir.mkdir(parents=True, exist_ok=True)

    def _get_timestamp(self) -> str:
        """Get timestamp for log entries."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _get_log_date(self) -> str:
        """Get date for log file naming."""
        return datetime.now().strftime("%Y-%m-%d")

    def _sanitize_message(self, message: str) -> str:
        """Sanitize message by replacing newlines."""
        return message.replace("\n", "\\n")

    def log_event(self, category: str, message: str) -> None:
        """Main logging function."""
        timestamp = self._get_timestamp()
        log_date = self._get_log_date()
        safe_message = self._sanitize_message(message)

        log_line = f"[{timestamp}] [{category}] {safe_message}"

        # Write to session-specific log
        session_log = self.session_log_dir / f"{log_date}-{self.session_id}.log"
        try:
            with open(session_log, "a") as f:
                f.write(log_line + "\n")
        except OSError:
            pass

        # Write to daily rolling log
        daily_log = self.log_dir / f"{log_date}.log"
        try:
            with open(daily_log, "a") as f:
                f.write(f"[{self.session_id}] {log_line}\n")
        except OSError:
            pass

        # Update current.log symlink
        current_log = self.log_dir / "current.log"
        try:
            if current_log.is_symlink() or current_log.exists():
                current_log.unlink()
            current_log.symlink_to(session_log)
        except OSError:
            pass

    def log_wp(self, message: str) -> None:
        """Log Waypoints-specific event."""
        self.log_event("WP", message)

    def log_build(self, result: str, details: str = "") -> None:
        """Log build/compile event."""
        msg = result
        if details:
            msg = f"{result} - {details}"
        self.log_event("BUILD", msg)

    def log_hook(self, hook_name: str, event: str, details: str = "") -> None:
        """Log hook event."""
        msg = event
        if details:
            msg = f"{event} - {details}"
        self.log_event(f"HOOK:{hook_name}", msg)

    def log_error(self, message: str) -> None:
        """Log error event."""
        self.log_event("ERROR", message)

    def log_session(self, event: str) -> None:
        """Log session event."""
        self.log_event("SESSION", event)
