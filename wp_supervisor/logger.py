#!/usr/bin/env python3
"""
Waypoints Supervisor - Workflow Logger

Provides logging functionality for supervisor workflows.
Logs to both:
- Workflow-specific log (workflow_dir/workflow.log)
- Unified waypoints logs (~/.claude/waypoints/logs/)
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class SupervisorLogger:
    """Logger for Waypoints supervisor workflow events."""

    LOG_FILE = "workflow.log"

    def __init__(self, workflow_dir: Path, workflow_id: str = "unknown"):
        """
        Initialize logger for a supervisor workflow.

        Args:
            workflow_dir: Directory for this workflow (contains state.json)
            workflow_id: Workflow identifier for log entries
        """
        self.workflow_dir = Path(workflow_dir)
        self.workflow_id = workflow_id
        self.log_file = self.workflow_dir / self.LOG_FILE

        # Unified waypoints logs location (same as CLI mode)
        install_dir = os.environ.get("WP_INSTALL_DIR", str(Path.home() / ".claude" / "waypoints"))
        self.unified_log_dir = Path(install_dir) / "logs"
        self.unified_session_dir = self.unified_log_dir / "sessions"

        # Ensure directories exist
        self.workflow_dir.mkdir(parents=True, exist_ok=True)
        self.unified_log_dir.mkdir(parents=True, exist_ok=True)
        self.unified_session_dir.mkdir(parents=True, exist_ok=True)

    def _get_timestamp(self) -> str:
        """Get timestamp for log entries."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _sanitize_message(self, message: str) -> str:
        """Sanitize message by replacing newlines."""
        return message.replace("\n", "\\n")

    def _get_log_date(self) -> str:
        """Get date for log file naming."""
        return datetime.now().strftime("%Y-%m-%d")

    def log_event(self, category: str, message: str) -> None:
        """
        Log an event to both workflow-specific and unified log files.

        Args:
            category: Event category (e.g., WORKFLOW, PHASE, USER)
            message: Event message
        """
        timestamp = self._get_timestamp()
        log_date = self._get_log_date()
        safe_message = self._sanitize_message(message)
        log_line = f"[{timestamp}] [{category}] {safe_message}\n"

        # Write to workflow-specific log
        try:
            with open(self.log_file, "a") as f:
                f.write(log_line)
        except OSError:
            pass

        # Write to unified session log (same location as CLI mode)
        session_log = self.unified_session_dir / f"{log_date}-supervisor-{self.workflow_id}.log"
        try:
            with open(session_log, "a") as f:
                f.write(log_line)
        except OSError:
            pass

        # Write to unified daily log
        daily_log = self.unified_log_dir / f"{log_date}.log"
        try:
            with open(daily_log, "a") as f:
                f.write(f"[supervisor-{self.workflow_id}] {log_line}")
        except OSError:
            pass

        # Update current.log symlink to point to this session
        current_log = self.unified_log_dir / "current.log"
        try:
            if current_log.is_symlink() or current_log.exists():
                current_log.unlink()
            current_log.symlink_to(session_log)
        except OSError:
            pass

    # --- Workflow Events ---

    def log_workflow_start(self, task: str = "") -> None:
        """Log workflow start."""
        msg = "Workflow started"
        if task:
            msg = f"Workflow started: {task[:100]}"
        self.log_event("WORKFLOW", msg)

    def log_workflow_complete(self, usage_summary: str = "") -> None:
        """Log workflow completion."""
        msg = "Workflow completed successfully"
        if usage_summary:
            msg = f"{msg} | {usage_summary}"
        self.log_event("WORKFLOW", msg)

    def log_workflow_aborted(self, reason: str = "") -> None:
        """Log workflow abort."""
        msg = "Workflow aborted"
        if reason:
            msg = f"{msg}: {reason}"
        self.log_event("WORKFLOW", msg)

    # --- Phase Events ---

    def log_phase_start(self, phase: int, name: str) -> None:
        """Log phase start."""
        self.log_event("PHASE", f"Phase {phase} ({name}) started")

    def log_phase_complete(self, phase: int, name: str) -> None:
        """Log phase completion."""
        self.log_event("PHASE", f"Phase {phase} ({name}) completed")

    def log_phase_summary_saved(self, phase: int, path: str) -> None:
        """Log that phase summary was saved."""
        self.log_event("PHASE", f"Phase {phase} summary saved to {path}")

    def log_phase_context_saved(self, phase: int, path: str) -> None:
        """Log that phase context was saved."""
        self.log_event("PHASE", f"Phase {phase} context saved to {path}")

    # --- User Events ---

    def log_user_input(self, input_preview: str = "") -> None:
        """Log user input received."""
        if input_preview:
            preview = input_preview[:50] + "..." if len(input_preview) > 50 else input_preview
            self.log_event("USER", f"Input received: {preview}")
        else:
            self.log_event("USER", "Input received")

    def log_user_confirmation(self, phase: int) -> None:
        """Log user confirmation to proceed."""
        self.log_event("USER", f"Confirmed phase {phase} completion")

    def log_user_command(self, command: str) -> None:
        """Log user command (like /done, /quit)."""
        self.log_event("USER", f"Command: {command}")

    # --- Error Events ---

    def log_error(self, message: str, error: Optional[Exception] = None) -> None:
        """Log an error."""
        if error:
            self.log_event("ERROR", f"{message}: {type(error).__name__}: {error}")
        else:
            self.log_event("ERROR", message)

    # --- Claude Events ---

    def log_query_start(self, prompt_preview: str = "") -> None:
        """Log start of Claude query."""
        if prompt_preview:
            preview = prompt_preview[:50] + "..." if len(prompt_preview) > 50 else prompt_preview
            self.log_event("CLAUDE", f"Query started: {preview}")
        else:
            self.log_event("CLAUDE", "Query started")

    def log_query_complete(self, tokens: int = 0, cost: float = 0.0) -> None:
        """Log completion of Claude query."""
        if tokens > 0 or cost > 0:
            self.log_event("CLAUDE", f"Query complete | tokens: {tokens} | cost: ${cost:.4f}")
        else:
            self.log_event("CLAUDE", "Query complete")

    # --- Usage Events ---

    def log_usage_summary(
        self,
        total_tokens: int,
        total_cost: float,
        duration_sec: float
    ) -> None:
        """Log usage summary at workflow end."""
        self.log_event(
            "USAGE",
            f"Total: {total_tokens:,} tokens | ${total_cost:.4f} | {duration_sec:.1f}s"
        )

    # --- Agent Events ---

    def log_wp(self, message: str) -> None:
        """Log a Waypoints event (compatibility with WPLogger interface)."""
        self.log_event("WP", message)

    # --- Utility ---

    def get_log_path(self) -> str:
        """Get path to log file."""
        return str(self.log_file)

    def get_log_content(self) -> str:
        """Get full log file content."""
        try:
            with open(self.log_file, 'r') as f:
                return f.read()
        except OSError:
            return ""
