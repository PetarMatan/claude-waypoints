#!/usr/bin/env python3
"""
Waypoints State Management - Unified State File

Consolidates all Waypoints workflow state into a single state.json file.
Replaces multiple marker files with atomic JSON state management.

State Schema:
{
    "version": 1,
    "active": true,
    "supervisorActive": false,
    "phase": 2,
    "mode": "cli",
    "completedPhases": {
        "requirements": true,
        "interfaces": false,
        "tests": false,
        "implementation": false
    },
    "usage": {
        "phase1": {"input_tokens": 1000, "output_tokens": 500, "cost_usd": 0.05, "duration_ms": 5000, "turns": 3},
        "phase2": {"input_tokens": 2000, "output_tokens": 800, "cost_usd": 0.08, "duration_ms": 8000, "turns": 5},
        ...
    },
    "metadata": {
        "startedAt": "2026-01-09T10:30:00Z",
        "workflowId": "20260109-103000",
        "sessionId": "abc123"
    }
}

Note: Phase summaries are stored in dedicated document files (phase1-requirements.md, etc.)
rather than in state.json for better human readability and editing.
"""

import json
import os
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Literal, Dict


class _Phase(Enum):
    """Internal enum for phase names - prevents magic strings."""
    REQUIREMENTS = "requirements"
    INTERFACES = "interfaces"
    TESTS = "tests"
    IMPLEMENTATION = "implementation"


@dataclass
class CompletedPhases:
    """Tracks which Waypoints phases have been completed."""
    requirements: bool = False
    interfaces: bool = False
    tests: bool = False
    implementation: bool = False


@dataclass
class Metadata:
    """Workflow metadata."""
    startedAt: str = ""
    workflowId: str = ""
    sessionId: str = ""


@dataclass
class PhaseUsage:
    """Token usage for a single phase."""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    turns: int = 0


@dataclass
class Usage:
    """Token usage tracking per phase."""
    phase1: PhaseUsage = field(default_factory=PhaseUsage)
    phase2: PhaseUsage = field(default_factory=PhaseUsage)
    phase3: PhaseUsage = field(default_factory=PhaseUsage)
    phase4: PhaseUsage = field(default_factory=PhaseUsage)


@dataclass
class StateData:
    """Complete Waypoints state structure."""
    version: int = 1
    active: bool = False
    supervisorActive: bool = False
    phase: int = 1
    mode: Literal["cli", "supervisor"] = "cli"
    completedPhases: CompletedPhases = field(default_factory=CompletedPhases)
    usage: Usage = field(default_factory=Usage)
    metadata: Metadata = field(default_factory=Metadata)


class WPState:
    """
    Unified Waypoints state management using a single state.json file.

    Supports both CLI (hook-based) and supervisor modes.
    Provides atomic reads/writes and simpler state management.
    """

    STATE_FILE = "state.json"
    VERSION = 1

    def __init__(
        self,
        session_id: str = "unknown",
        workflow_id: Optional[str] = None,
        mode: Literal["cli", "supervisor"] = "cli"
    ):
        """
        Initialize Waypoints state manager.

        Args:
            session_id: Session identifier (for CLI mode)
            workflow_id: Workflow identifier (for supervisor mode, auto-generated if not provided)
            mode: Operating mode - "cli" or "supervisor"
        """
        claude_config = os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))
        self.base_dir = Path(claude_config) / "tmp"
        self.session_id = session_id
        self.mode = mode

        # Check for supervisor mode via environment
        supervisor_markers_dir = os.environ.get("WP_SUPERVISOR_MARKERS_DIR")
        if supervisor_markers_dir:
            self.state_dir = Path(supervisor_markers_dir)
            self._env_supervisor_mode = True
            # Extract workflow_id from directory name if possible
            dir_name = self.state_dir.name
            if dir_name.startswith("wp-supervisor-"):
                self.workflow_id = dir_name[len("wp-supervisor-"):]
            else:
                self.workflow_id = os.environ.get("WP_SUPERVISOR_WORKFLOW_ID", "")
        else:
            self._env_supervisor_mode = False
            if mode == "supervisor":
                self.workflow_id = workflow_id or self._generate_workflow_id()
                self.state_dir = self.base_dir / f"wp-supervisor-{self.workflow_id}"
            else:
                self.workflow_id = workflow_id or ""
                self.state_dir = self.base_dir / f"wp-{session_id}"

        # Ensure directory exists
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self.state_dir / self.STATE_FILE

    def _generate_workflow_id(self) -> str:
        """Generate a unique workflow ID from timestamp."""
        return datetime.now().strftime("%Y%m%d-%H%M%S")

    # --- Core State Operations ---

    def _load_state(self) -> StateData:
        """Load state from file, returning defaults if not exists."""
        if not self._state_file.exists():
            return StateData()

        try:
            with open(self._state_file, 'r') as f:
                data = json.load(f)

            # Parse usage data with nested PhaseUsage objects
            usage_data = data.get("usage", {})
            usage = Usage(
                phase1=PhaseUsage(**usage_data.get("phase1", {})),
                phase2=PhaseUsage(**usage_data.get("phase2", {})),
                phase3=PhaseUsage(**usage_data.get("phase3", {})),
                phase4=PhaseUsage(**usage_data.get("phase4", {})),
            )

            # Reconstruct dataclasses from dict
            return StateData(
                version=data.get("version", self.VERSION),
                active=data.get("active", False),
                supervisorActive=data.get("supervisorActive", False),
                phase=data.get("phase", 1),
                mode=data.get("mode", "cli"),
                completedPhases=CompletedPhases(**data.get("completedPhases", {})),
                usage=usage,
                metadata=Metadata(**data.get("metadata", {}))
            )
        except (json.JSONDecodeError, TypeError, KeyError):
            # Corrupted state, return defaults
            return StateData()

    def _save_state(self, state: StateData) -> None:
        """Save state to file atomically."""
        # Convert dataclasses to dict
        data = {
            "version": state.version,
            "active": state.active,
            "supervisorActive": state.supervisorActive,
            "phase": state.phase,
            "mode": state.mode,
            "completedPhases": asdict(state.completedPhases),
            "usage": asdict(state.usage),
            "metadata": asdict(state.metadata)
        }

        # Write to temp file first, then replace (atomic on POSIX, works on Windows)
        temp_file = self._state_file.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=2)
        temp_file.replace(self._state_file)

    def _update_state(self, **updates) -> StateData:
        """Load state, apply updates, save, and return updated state."""
        state = self._load_state()
        for key, value in updates.items():
            if hasattr(state, key):
                setattr(state, key, value)
        self._save_state(state)
        return state

    # --- Initialization ---

    def initialize(self) -> None:
        """Initialize state for a new Waypoints workflow."""
        now = datetime.now().isoformat()
        workflow_id = getattr(self, 'workflow_id', '') or self._generate_workflow_id()

        state = StateData(
            version=self.VERSION,
            active=True,
            supervisorActive=(self.mode == "supervisor"),
            phase=1,
            mode=self.mode,
            completedPhases=CompletedPhases(),
            metadata=Metadata(
                startedAt=now,
                workflowId=workflow_id,
                sessionId=self.session_id
            )
        )
        self._save_state(state)

    # --- Active State ---

    def is_active(self) -> bool:
        """Check if Waypoints mode is active."""
        state = self._load_state()
        return state.active

    def is_wp_active(self) -> bool:
        """Alias for is_active()."""
        return self.is_active()

    def is_supervisor_mode(self) -> bool:
        """Check if running under supervisor control."""
        if self._env_supervisor_mode:
            return True
        if os.environ.get("WP_SUPERVISOR_ACTIVE") == "1":
            return True
        state = self._load_state()
        return state.supervisorActive

    # --- Phase Management ---

    def get_phase(self) -> int:
        """Get current Waypoints phase (1-4)."""
        state = self._load_state()
        phase = state.phase
        if phase < 1 or phase > 4:
            return 1
        return phase

    def set_phase(self, phase: int) -> None:
        """Set the current Waypoints phase."""
        if phase < 1:
            phase = 1
        elif phase > 4:
            phase = 4
        self._update_state(phase=phase)

    def phase_exists(self) -> bool:
        """Check if phase has been set (state file exists and is active)."""
        if not self._state_file.exists():
            return False
        state = self._load_state()
        return state.active

    # --- Phase Completion (Internal) ---

    def _is_phase_complete(self, phase: _Phase) -> bool:
        """Internal: Check if a phase is complete."""
        state = self._load_state()
        return getattr(state.completedPhases, phase.value, False)

    def _mark_phase_complete(self, phase: _Phase) -> None:
        """Internal: Mark a phase as complete."""
        state = self._load_state()
        setattr(state.completedPhases, phase.value, True)
        self._save_state(state)

    def _mark_phase_incomplete(self, phase: _Phase) -> None:
        """Internal: Mark a phase as incomplete."""
        state = self._load_state()
        setattr(state.completedPhases, phase.value, False)
        self._save_state(state)

    # --- Requirements Phase ---

    def is_requirements_complete(self) -> bool:
        """Check if requirements phase is complete."""
        return self._is_phase_complete(_Phase.REQUIREMENTS)

    def mark_requirements_complete(self) -> None:
        """Mark requirements phase as complete."""
        self._mark_phase_complete(_Phase.REQUIREMENTS)

    def mark_requirements_incomplete(self) -> None:
        """Mark requirements phase as incomplete."""
        self._mark_phase_incomplete(_Phase.REQUIREMENTS)

    def save_requirements_summary(self, summary: str) -> None:
        """Save requirements summary for passing to later phases."""
        self.save_phase_document(1, summary)

    def get_requirements_summary(self) -> str:
        """Get saved requirements summary."""
        return self.get_phase_document(1)

    # --- Interfaces Phase ---

    def is_interfaces_complete(self) -> bool:
        """Check if interfaces phase is complete."""
        return self._is_phase_complete(_Phase.INTERFACES)

    def mark_interfaces_complete(self) -> None:
        """Mark interfaces phase as complete."""
        self._mark_phase_complete(_Phase.INTERFACES)

    def mark_interfaces_incomplete(self) -> None:
        """Mark interfaces phase as incomplete."""
        self._mark_phase_incomplete(_Phase.INTERFACES)

    def save_interfaces_list(self, interfaces: str) -> None:
        """Save list of created interfaces."""
        self.save_phase_document(2, interfaces)

    def get_interfaces_list(self) -> str:
        """Get saved interfaces list."""
        return self.get_phase_document(2)

    # --- Tests Phase ---

    def is_tests_complete(self) -> bool:
        """Check if tests phase is complete."""
        return self._is_phase_complete(_Phase.TESTS)

    def mark_tests_complete(self) -> None:
        """Mark tests phase as complete."""
        self._mark_phase_complete(_Phase.TESTS)

    def mark_tests_incomplete(self) -> None:
        """Mark tests phase as incomplete."""
        self._mark_phase_incomplete(_Phase.TESTS)

    def save_tests_list(self, tests: str) -> None:
        """Save list of created tests."""
        self.save_phase_document(3, tests)

    def get_tests_list(self) -> str:
        """Get saved tests list."""
        return self.get_phase_document(3)

    # --- Implementation Phase ---

    def is_implementation_complete(self) -> bool:
        """Check if implementation phase is complete."""
        return self._is_phase_complete(_Phase.IMPLEMENTATION)

    def mark_implementation_complete(self) -> None:
        """Mark implementation phase as complete."""
        self._mark_phase_complete(_Phase.IMPLEMENTATION)

    def mark_implementation_incomplete(self) -> None:
        """Mark implementation phase as incomplete."""
        self._mark_phase_incomplete(_Phase.IMPLEMENTATION)

    # --- Cleanup ---

    def cleanup(self, keep_documents: bool = False) -> None:
        """
        Clean up state for this workflow.

        Args:
            keep_documents: If True, only removes state.json but keeps documents.
                          If False, deletes entire directory.
        """
        if not self.state_dir.exists():
            return

        if keep_documents:
            # Only remove state.json, keep documents for reference
            if self._state_file.exists():
                self._state_file.unlink()
        else:
            # Remove entire directory
            shutil.rmtree(self.state_dir, ignore_errors=True)

    def cleanup_session(self) -> None:
        """Alias for cleanup() - removes entire directory."""
        self.cleanup(keep_documents=False)

    def cleanup_workflow_state(self) -> None:
        """
        Reset workflow state but keep implementation complete as success indicator.
        Used when Waypoints workflow completes successfully.
        """
        state = self._load_state()
        state.active = False
        state.phase = 1
        state.completedPhases.requirements = False
        state.completedPhases.interfaces = False
        state.completedPhases.tests = False
        # Keep implementation = True as success indicator
        self._save_state(state)

    # --- Environment Variables (for supervisor mode) ---

    def get_env_vars(self) -> Dict[str, str]:
        """
        Get environment variables to pass to Claude sessions.

        These allow hooks to find the correct state directory.
        """
        workflow_id = getattr(self, 'workflow_id', '') or self._load_state().metadata.workflowId
        return {
            "WP_SUPERVISOR_WORKFLOW_ID": workflow_id,
            "WP_SUPERVISOR_MARKERS_DIR": str(self.state_dir),
            "WP_SUPERVISOR_ACTIVE": "1",
        }

    # --- Utility ---

    def get_state_dir(self) -> str:
        """Get the state directory path."""
        return str(self.state_dir)

    def get_marker_dir_display(self) -> str:
        """Get displayable state directory path (with ~)."""
        home = str(Path.home())
        path = str(self.state_dir)
        if path.startswith(home):
            return "~" + path[len(home):]
        return path

    # --- Usage Tracking (Supervisor Mode) ---

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
        if phase < 1 or phase > 4:
            return

        state = self._load_state()
        phase_usage = getattr(state.usage, f"phase{phase}")

        # Accumulate values
        phase_usage.input_tokens += input_tokens
        phase_usage.output_tokens += output_tokens
        phase_usage.cost_usd += cost_usd
        phase_usage.duration_ms += duration_ms
        phase_usage.turns += turns

        self._save_state(state)

    def get_phase_usage(self, phase: int) -> Dict[str, any]:
        """
        Get usage data for a specific phase.

        Args:
            phase: Phase number (1-4)

        Returns:
            Dict with input_tokens, output_tokens, cost_usd, duration_ms, turns
        """
        if phase < 1 or phase > 4:
            return {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "duration_ms": 0, "turns": 0}

        state = self._load_state()
        phase_usage = getattr(state.usage, f"phase{phase}")
        return asdict(phase_usage)

    def get_total_usage(self) -> Dict[str, any]:
        """
        Get total usage across all phases.

        Returns:
            Dict with total input_tokens, output_tokens, cost_usd, duration_ms, turns
        """
        state = self._load_state()

        total = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "duration_ms": 0,
            "turns": 0,
        }

        for phase_num in [1, 2, 3, 4]:
            phase_usage = getattr(state.usage, f"phase{phase_num}")
            total["input_tokens"] += phase_usage.input_tokens
            total["output_tokens"] += phase_usage.output_tokens
            total["cost_usd"] += phase_usage.cost_usd
            total["duration_ms"] += phase_usage.duration_ms
            total["turns"] += phase_usage.turns

        return total

    def get_all_usage(self) -> Dict[str, Dict[str, any]]:
        """
        Get usage data for all phases plus total.

        Returns:
            Dict with phase1, phase2, phase3, phase4, and total usage
        """
        state = self._load_state()

        result = {}
        for phase_num in [1, 2, 3, 4]:
            phase_usage = getattr(state.usage, f"phase{phase_num}")
            result[f"phase{phase_num}"] = asdict(phase_usage)

        result["total"] = self.get_total_usage()
        return result

    # --- Document Storage (Supervisor Mode) ---

    PHASE_DOC_NAMES = {
        1: "phase1-requirements.md",
        2: "phase2-interfaces.md",
        3: "phase3-tests.md",
        4: "phase4-summary.md",
    }

    PHASE_CONTEXT_NAMES = {
        1: "phase1-input.md",
        2: "phase2-input.md",
        3: "phase3-input.md",
        4: "phase4-input.md",
    }

    def _ensure_context_dir(self) -> Path:
        """Ensure context directory exists and return path."""
        context_dir = self.state_dir / "context"
        context_dir.mkdir(parents=True, exist_ok=True)
        return context_dir

    def save_phase_document(self, phase: int, content: str) -> Optional[Path]:
        """
        Save phase output document (human-readable markdown).

        Args:
            phase: Phase number (1-4)
            content: Markdown content to save

        Returns:
            Path to saved file, or None if invalid phase
        """
        if phase < 1 or phase > 4:
            return None

        filename = self.PHASE_DOC_NAMES[phase]
        filepath = self.state_dir / filename

        try:
            with open(filepath, 'w') as f:
                f.write(content)
            return filepath
        except OSError:
            return None

    def get_phase_document(self, phase: int) -> str:
        """
        Get phase output document content.

        Args:
            phase: Phase number (1-4)

        Returns:
            Document content, or empty string if not found
        """
        if phase < 1 or phase > 4:
            return ""

        filename = self.PHASE_DOC_NAMES[phase]
        filepath = self.state_dir / filename

        try:
            with open(filepath, 'r') as f:
                return f.read()
        except OSError:
            return ""

    def get_phase_document_path(self, phase: int) -> Optional[Path]:
        """Get path to phase document (may not exist yet)."""
        if phase < 1 or phase > 4:
            return None
        return self.state_dir / self.PHASE_DOC_NAMES[phase]

    def save_phase_context(self, phase: int, content: str) -> Optional[Path]:
        """
        Save context/input sent to Claude for a phase.

        Args:
            phase: Phase number (1-4)
            content: Context content that was sent to Claude

        Returns:
            Path to saved file, or None if invalid phase
        """
        if phase < 1 or phase > 4:
            return None

        context_dir = self._ensure_context_dir()
        filename = self.PHASE_CONTEXT_NAMES[phase]
        filepath = context_dir / filename

        try:
            with open(filepath, 'w') as f:
                f.write(content)
            return filepath
        except OSError:
            return None

    def get_phase_context(self, phase: int) -> str:
        """
        Get context/input that was sent to Claude for a phase.

        Args:
            phase: Phase number (1-4)

        Returns:
            Context content, or empty string if not found
        """
        if phase < 1 or phase > 4:
            return ""

        context_dir = self.state_dir / "context"
        filename = self.PHASE_CONTEXT_NAMES[phase]
        filepath = context_dir / filename

        try:
            with open(filepath, 'r') as f:
                return f.read()
        except OSError:
            return ""

    def get_phase_context_path(self, phase: int) -> Optional[Path]:
        """Get path to phase context file (may not exist yet)."""
        if phase < 1 or phase > 4:
            return None
        return self.state_dir / "context" / self.PHASE_CONTEXT_NAMES[phase]

    def list_documents(self) -> Dict[str, Path]:
        """
        List all existing documents in the workflow directory.

        Returns:
            Dict mapping document type to path
        """
        docs = {}

        # Phase documents
        for phase, filename in self.PHASE_DOC_NAMES.items():
            filepath = self.state_dir / filename
            if filepath.exists():
                docs[f"phase{phase}"] = filepath

        # Context files
        context_dir = self.state_dir / "context"
        if context_dir.exists():
            for phase, filename in self.PHASE_CONTEXT_NAMES.items():
                filepath = context_dir / filename
                if filepath.exists():
                    docs[f"phase{phase}_context"] = filepath

        return docs
