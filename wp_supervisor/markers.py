#!/usr/bin/env python3
"""
Waypoints Supervisor - Marker Management

Thin wrapper around WPState for supervisor mode. Uses a workflow ID that persists
across multiple Claude sessions within a single Waypoints workflow run.
"""

import sys
from pathlib import Path
from typing import Optional

# Add hooks/lib to path for WPState import
hooks_lib = Path(__file__).parent.parent / "hooks" / "lib"
sys.path.insert(0, str(hooks_lib))

from wp_state import WPState


class SupervisorMarkers:
    """
    Manages Waypoints state for supervisor-controlled workflows.

    This is a thin wrapper around WPState that provides
    the interface expected by the supervisor orchestrator.
    """

    def __init__(self, workflow_id: Optional[str] = None):
        """
        Initialize marker manager for supervisor mode.

        Args:
            workflow_id: Unique identifier for this workflow run.
                        If not provided, generates one from timestamp.
        """
        self._state = WPState(workflow_id=workflow_id, mode="supervisor")

        # Expose for compatibility
        self.workflow_id = self._state.workflow_id
        self.markers_dir = self._state.state_dir
        self.base_dir = self._state.base_dir

    # --- State Management ---

    def initialize(self) -> None:
        """Initialize state for a new Waypoints workflow."""
        self._state.initialize()

    def is_active(self) -> bool:
        """Check if Waypoints supervisor mode is active."""
        return self._state.is_active() and self._state.is_supervisor_mode()

    # --- Phase Management ---

    def get_phase(self) -> int:
        """Get current Waypoints phase (1-4)."""
        return self._state.get_phase()

    def set_phase(self, phase: int) -> None:
        """Set the current Waypoints phase."""
        self._state.set_phase(phase)

    # --- Requirements Phase ---

    def is_requirements_complete(self) -> bool:
        """Check if requirements phase is complete."""
        return self._state.is_requirements_complete()

    def mark_requirements_complete(self) -> None:
        """Mark requirements phase as complete."""
        self._state.mark_requirements_complete()

    def save_requirements_summary(self, summary: str) -> None:
        """Save requirements summary for passing to later phases."""
        self._state.save_requirements_summary(summary)

    def get_requirements_summary(self) -> str:
        """Get saved requirements summary."""
        return self._state.get_requirements_summary()

    # --- Interfaces Phase ---

    def is_interfaces_complete(self) -> bool:
        """Check if interfaces phase is complete."""
        return self._state.is_interfaces_complete()

    def mark_interfaces_complete(self) -> None:
        """Mark interfaces phase as complete."""
        self._state.mark_interfaces_complete()

    def save_interfaces_list(self, interfaces: str) -> None:
        """Save list of created interfaces."""
        self._state.save_interfaces_list(interfaces)

    def get_interfaces_list(self) -> str:
        """Get saved interfaces list."""
        return self._state.get_interfaces_list()

    # --- Tests Phase ---

    def is_tests_complete(self) -> bool:
        """Check if tests phase is complete."""
        return self._state.is_tests_complete()

    def mark_tests_complete(self) -> None:
        """Mark tests phase as complete."""
        self._state.mark_tests_complete()

    def save_tests_list(self, tests: str) -> None:
        """Save list of created tests."""
        self._state.save_tests_list(tests)

    def get_tests_list(self) -> str:
        """Get saved tests list."""
        return self._state.get_tests_list()

    # --- Implementation Phase ---

    def is_implementation_complete(self) -> bool:
        """Check if implementation phase is complete."""
        return self._state.is_implementation_complete()

    def mark_implementation_complete(self) -> None:
        """Mark implementation phase as complete."""
        self._state.mark_implementation_complete()

    # --- Cleanup ---

    def cleanup(self, keep_documents: bool = False) -> None:
        """
        Clean up state for this workflow.

        Args:
            keep_documents: If True, keeps document files for reference.
        """
        self._state.cleanup(keep_documents=keep_documents)

    # --- Utility ---

    def get_marker_dir(self) -> str:
        """Get the state directory path."""
        return self._state.get_state_dir()

    def get_env_vars(self) -> dict:
        """
        Get environment variables to pass to Claude sessions.

        These allow hooks to find the correct state directory.
        """
        return self._state.get_env_vars()

    # --- Usage Tracking ---

    def add_phase_usage(
        self,
        phase: int,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        duration_ms: int = 0,
        turns: int = 0
    ) -> None:
        """
        Add usage data for a phase. Accumulates with existing data.

        Args:
            phase: Phase number (1-4)
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens used
            cost_usd: Cost in USD
            duration_ms: Duration in milliseconds
            turns: Number of API turns
        """
        self._state.add_phase_usage(
            phase=phase,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            duration_ms=duration_ms,
            turns=turns
        )

    def get_phase_usage(self, phase: int) -> dict:
        """Get usage data for a specific phase."""
        return self._state.get_phase_usage(phase)

    def get_total_usage(self) -> dict:
        """Get total usage across all phases."""
        return self._state.get_total_usage()

    def get_all_usage(self) -> dict:
        """Get usage data for all phases plus total."""
        return self._state.get_all_usage()

    def get_total_tokens(self) -> int:
        """Get total tokens (input + output) across all phases."""
        total = self._state.get_total_usage()
        return total["input_tokens"] + total["output_tokens"]

    def get_total_cost(self) -> float:
        """Get total cost in USD across all phases."""
        return self._state.get_total_usage()["cost_usd"]

    def get_total_duration_sec(self) -> float:
        """Get total duration in seconds across all phases."""
        return self._state.get_total_usage()["duration_ms"] / 1000.0

    def get_usage_summary_text(self) -> str:
        """Get formatted usage summary text."""
        total = self._state.get_total_usage()
        tokens = total["input_tokens"] + total["output_tokens"]
        cost = total["cost_usd"]
        return f"{tokens:,} tokens, ${cost:.4f}"

    # --- Document Storage ---

    def save_phase_document(self, phase: int, content: str) -> str:
        """
        Save phase output document (human-readable markdown).

        Args:
            phase: Phase number (1-4)
            content: Markdown content to save

        Returns:
            Path to saved file as string, or empty string if failed
        """
        path = self._state.save_phase_document(phase, content)
        return str(path) if path else ""

    def get_phase_document(self, phase: int) -> str:
        """Get phase output document content."""
        return self._state.get_phase_document(phase)

    def get_phase_document_path(self, phase: int) -> str:
        """Get path to phase document."""
        path = self._state.get_phase_document_path(phase)
        return str(path) if path else ""

    def save_phase_context(self, phase: int, content: str) -> str:
        """
        Save context/input sent to Claude for a phase.

        Args:
            phase: Phase number (1-4)
            content: Context content that was sent to Claude

        Returns:
            Path to saved file as string, or empty string if failed
        """
        path = self._state.save_phase_context(phase, content)
        return str(path) if path else ""

    def get_phase_context(self, phase: int) -> str:
        """Get context/input that was sent to Claude for a phase."""
        return self._state.get_phase_context(phase)

    def get_phase_context_path(self, phase: int) -> str:
        """Get path to phase context file."""
        path = self._state.get_phase_context_path(phase)
        return str(path) if path else ""

    def list_documents(self) -> dict:
        """List all existing documents in the workflow directory."""
        docs = self._state.list_documents()
        return {k: str(v) for k, v in docs.items()}
