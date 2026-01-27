#!/usr/bin/env python3
"""
Waypoints Supervisor - Marker Management

Thin wrapper around WPState for supervisor mode. Uses a workflow ID that persists
across multiple Claude sessions within a single Waypoints workflow run.

Also manages knowledge staging for supervisor-controlled knowledge extraction.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add hooks/lib to path for WPState import
hooks_lib = Path(__file__).parent.parent / "hooks" / "lib"
sys.path.insert(0, str(hooks_lib))

from wp_state import WPState
from wp_knowledge import (
    StagedKnowledge,
    StagedKnowledgeEntry,
    KnowledgeManager,
    extract_from_text,
    ExtractionResult,
)


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

    # --- Knowledge Staging [REQ-13, REQ-14, REQ-15, REQ-16] ---

    STAGED_KNOWLEDGE_FILE = "staged-knowledge.json"

    def stage_knowledge(self, knowledge: StagedKnowledge) -> None:
        """
        Stage extracted knowledge for later application.

        Merges with any existing staged knowledge (accumulates across phases) [REQ-15].
        Stored in workflow state directory [REQ-13].

        Args:
            knowledge: StagedKnowledge container with entries to stage

        Note:
            On file write failure: Logs error, continues workflow normally.
        """
        # Load existing staged knowledge
        existing_data = self._load_staged_knowledge_from_file()

        # Merge new knowledge with existing [REQ-15]
        for entry in knowledge.architecture:
            existing_data["architecture"].append({
                "title": entry.title,
                "content": entry.content,
                "phase": entry.phase,
                "tag": entry.tag
            })

        for entry in knowledge.decisions:
            existing_data["decisions"].append({
                "title": entry.title,
                "content": entry.content,
                "phase": entry.phase,
                "tag": entry.tag
            })

        for entry in knowledge.lessons_learned:
            existing_data["lessons_learned"].append({
                "title": entry.title,
                "content": entry.content,
                "phase": entry.phase,
                "tag": entry.tag
            })

        # Save merged data
        self._save_staged_knowledge_to_file(existing_data)

    def get_staged_knowledge(self) -> StagedKnowledge:
        """
        Get all staged knowledge for this workflow.

        Returns:
            StagedKnowledge container. Returns empty StagedKnowledge if
            no staged knowledge exists [EDGE-6].
        """
        data = self._load_staged_knowledge_from_file()

        # Convert JSON data to StagedKnowledgeEntry objects
        architecture = [
            StagedKnowledgeEntry(
                title=e["title"],
                content=e["content"],
                phase=e["phase"],
                tag=e.get("tag")
            )
            for e in data.get("architecture", [])
        ]

        decisions = [
            StagedKnowledgeEntry(
                title=e["title"],
                content=e["content"],
                phase=e["phase"],
                tag=e.get("tag")
            )
            for e in data.get("decisions", [])
        ]

        lessons_learned = [
            StagedKnowledgeEntry(
                title=e["title"],
                content=e["content"],
                phase=e["phase"],
                tag=e.get("tag")
            )
            for e in data.get("lessons_learned", [])
        ]

        return StagedKnowledge(
            architecture=architecture,
            decisions=decisions,
            lessons_learned=lessons_learned
        )

    def has_staged_knowledge(self) -> bool:
        """
        Check if there is any staged knowledge.

        Returns:
            True if there are staged entries, False otherwise
        """
        staged = self.get_staged_knowledge()
        return not staged.is_empty()

    def clear_staged_knowledge(self) -> None:
        """
        Delete the staged knowledge file [REQ-23, REQ-25].

        Called after successful application at end of Phase 4,
        or on workflow abort.
        """
        path = self._get_staged_knowledge_path()
        if path.exists():
            try:
                path.unlink()
            except IOError:
                pass  # Ignore errors on cleanup

    def _get_staged_knowledge_path(self) -> Path:
        """Get path to staged knowledge file."""
        return Path(self.markers_dir) / self.STAGED_KNOWLEDGE_FILE

    def _load_staged_knowledge_from_file(self) -> Dict[str, Any]:
        """
        Load staged knowledge from JSON file.

        Returns:
            Dict with structure matching [REQ-14], or empty dict if not exists
        """
        path = self._get_staged_knowledge_path()

        if not path.exists():
            # Return empty structure [EDGE-6]
            return {
                "architecture": [],
                "decisions": [],
                "lessons_learned": []
            }

        try:
            with open(path, 'r') as f:
                data = json.load(f)
                # Ensure all keys exist
                if "architecture" not in data:
                    data["architecture"] = []
                if "decisions" not in data:
                    data["decisions"] = []
                if "lessons_learned" not in data:
                    data["lessons_learned"] = []
                return data
        except (IOError, json.JSONDecodeError):
            return {
                "architecture": [],
                "decisions": [],
                "lessons_learned": []
            }

    def _save_staged_knowledge_to_file(self, data: Dict[str, Any]) -> None:
        """
        Save staged knowledge to JSON file.

        Args:
            data: Dict with structure matching [REQ-14]
        """
        path = self._get_staged_knowledge_path()

        try:
            # Ensure directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError:
            pass  # Log error but continue workflow normally [ERR-2]

    # --- Knowledge Application Integration ---

    def apply_staged_knowledge(self, project_dir: str = ".") -> Dict[str, int]:
        """
        Apply staged knowledge to permanent files [REQ-17].

        Only call after Phase 4 completion (workflow success).

        Args:
            project_dir: Project directory for determining project ID

        Returns:
            Summary dict: {"architecture": 2, "decisions": 1, "lessons-learned": 3}
            Returns empty dict if no staged knowledge.
        """
        staged = self.get_staged_knowledge()
        if staged.is_empty():
            return {}

        manager = KnowledgeManager(project_dir)
        return manager.apply_staged_knowledge(staged, self.workflow_id)
