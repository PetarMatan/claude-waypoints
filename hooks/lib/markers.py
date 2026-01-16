#!/usr/bin/env python3
"""
Claude Waypoints - Marker Management

Thin wrapper around WPState for backward compatibility with hooks.
Delegates all operations to WPState.
"""

from wp_state import WPState


class MarkerManager:
    """
    Manages Waypoints state with session isolation.

    This is a thin wrapper around WPState that provides
    the interface expected by hooks.
    """

    def __init__(self, session_id: str = "unknown"):
        """
        Initialize marker manager with session ID.

        In supervisor mode (WP_SUPERVISOR_MARKERS_DIR set), uses the
        supervisor's state directory instead of session-based one.
        """
        self._state = WPState(session_id=session_id, mode="cli")

        # Expose state directory for compatibility
        self.markers_dir = self._state.state_dir
        self.session_id = session_id

    # --- Mode Detection ---

    def is_supervisor_mode(self) -> bool:
        """Check if running under supervisor control."""
        return self._state.is_supervisor_mode()

    # --- Active State ---

    def is_wp_active(self) -> bool:
        """Check if Waypoints mode is active."""
        return self._state.is_active()

    # --- Phase Management ---

    def get_phase(self) -> int:
        """Get current Waypoints phase (1-4), defaults to 1."""
        return self._state.get_phase()

    def set_phase(self, phase: int) -> None:
        """Set the current Waypoints phase."""
        self._state.set_phase(phase)

    def phase_exists(self) -> bool:
        """Check if phase has been set (state is active)."""
        return self._state.phase_exists()

    # --- Requirements Phase ---

    def is_requirements_complete(self) -> bool:
        """Check if requirements phase is complete."""
        return self._state.is_requirements_complete()

    def mark_requirements_complete(self) -> None:
        """Mark requirements phase as complete."""
        self._state.mark_requirements_complete()

    def mark_requirements_incomplete(self) -> None:
        """Mark requirements phase as incomplete."""
        self._state.mark_requirements_incomplete()

    # --- Interfaces Phase ---

    def is_interfaces_complete(self) -> bool:
        """Check if interfaces phase is complete."""
        return self._state.is_interfaces_complete()

    def mark_interfaces_complete(self) -> None:
        """Mark interfaces phase as complete."""
        self._state.mark_interfaces_complete()

    def mark_interfaces_incomplete(self) -> None:
        """Mark interfaces phase as incomplete."""
        self._state.mark_interfaces_incomplete()

    # --- Tests Phase ---

    def is_tests_complete(self) -> bool:
        """Check if tests phase is complete."""
        return self._state.is_tests_complete()

    def mark_tests_complete(self) -> None:
        """Mark tests phase as complete."""
        self._state.mark_tests_complete()

    def mark_tests_incomplete(self) -> None:
        """Mark tests phase as incomplete."""
        self._state.mark_tests_incomplete()

    # --- Implementation Phase ---

    def is_implementation_complete(self) -> bool:
        """Check if implementation phase is complete."""
        return self._state.is_implementation_complete()

    def mark_implementation_complete(self) -> None:
        """Mark implementation phase as complete."""
        self._state.mark_implementation_complete()

    def mark_implementation_incomplete(self) -> None:
        """Mark implementation phase as incomplete."""
        self._state.mark_implementation_incomplete()

    # --- Cleanup ---

    def cleanup_session(self) -> None:
        """Remove all state for this session."""
        self._state.cleanup()

    def cleanup_workflow_state(self) -> None:
        """Reset workflow state (keeps implementation complete as success indicator)."""
        self._state.cleanup_workflow_state()

    # --- Utility ---

    def get_marker_dir_display(self) -> str:
        """Get displayable marker directory path (with ~)."""
        return self._state.get_marker_dir_display()
