#!/usr/bin/env python3
"""
Claude Waypoints - Knowledge Management

Handles project knowledge: loading and application.

Knowledge Loading:
- Loads permanent knowledge files from ~/.claude/waypoints/knowledge/
- Per-project files: architecture.md, decisions.md
- Global file: lessons-learned.md (shared across projects)

Knowledge Application:
- Applies staged knowledge to permanent files
- Called by supervisor after Phase 4 completion

Note: Knowledge staging is handled by SupervisorMarkers in supervisor mode.
CLI mode no longer supports knowledge staging [DEC-1].
"""

import json
import logging
import os
import re
import subprocess
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict, field


class KnowledgeCategory(Enum):
    """Categories for knowledge storage."""
    ARCHITECTURE = "architecture"
    DECISIONS = "decisions"
    LESSONS_LEARNED = "lessons-learned"

    @property
    def filename(self) -> str:
        """Get the markdown filename for this category."""
        return f"{self.value}.md"

    @property
    def header(self) -> str:
        """Get the file header for this category."""
        headers = {
            KnowledgeCategory.ARCHITECTURE: "# Architecture\n\n",
            KnowledgeCategory.DECISIONS: "# Decisions\n\n",
            KnowledgeCategory.LESSONS_LEARNED: "# Lessons Learned\n\n"
        }
        return headers[self]

    @property
    def is_global(self) -> bool:
        """Check if this category is global (not per-project)."""
        return self == KnowledgeCategory.LESSONS_LEARNED


@dataclass
class StagedKnowledgeEntry:
    """
    A single knowledge entry staged for later application.

    Attributes:
        title: Short title describing the learning
        content: Detailed description of the learning
        phase: Phase number where this was extracted (1-4)
        tag: Technology tag for lessons-learned entries (e.g., "Python", "Git")
             Required for LESSONS_LEARNED, optional for others
    """
    title: str
    content: str
    phase: int
    tag: Optional[str] = None


@dataclass
class StagedKnowledge:
    """
    Container for all staged knowledge across categories.

    Stored in workflow state directory as staged-knowledge.json.
    Structure matches [REQ-14]:
    {
        "architecture": [...],
        "decisions": [...],
        "lessons_learned": [...]
    }
    """
    architecture: List[StagedKnowledgeEntry] = field(default_factory=list)
    decisions: List[StagedKnowledgeEntry] = field(default_factory=list)
    lessons_learned: List[StagedKnowledgeEntry] = field(default_factory=list)

    def is_empty(self) -> bool:
        """Check if there is any staged knowledge."""
        return (
            len(self.architecture) == 0
            and len(self.decisions) == 0
            and len(self.lessons_learned) == 0
        )

    def total_count(self) -> int:
        """Get total number of staged entries across all categories."""
        return len(self.architecture) + len(self.decisions) + len(self.lessons_learned)


@dataclass
class ExtractionResult:
    """
    Result of parsing Claude's knowledge extraction response.

    Attributes:
        knowledge: Extracted knowledge entries by category
        had_content: True if Claude found knowledge to extract (not NO_KNOWLEDGE_EXTRACTED)
        parse_error: Error message if parsing failed, None otherwise
    """
    knowledge: StagedKnowledge
    had_content: bool
    parse_error: Optional[str] = None


# Legacy dataclass for backward compatibility with CLI mode
@dataclass
class StagedLearning:
    """
    A single learning staged for later merge.

    DEPRECATED: Use StagedKnowledgeEntry instead. Kept for backward compatibility
    with CLI mode staging via wp:stage command.
    """
    category: str          # Use KnowledgeCategory.value for serialization
    title: str
    content: str
    source_phase: int


class ProjectIdentifier:
    """Identifies the current project for knowledge scoping."""

    def __init__(self, project_dir: str = "."):
        self.project_dir = os.path.abspath(project_dir)

    def get_project_id(self) -> str:
        """
        Get project identifier.
        Priority: .waypoints-project file > git remote > directory name
        """
        # Try .waypoints-project file first
        from_file = self._read_waypoints_project_file()
        if from_file:
            return from_file

        # Try git remote
        from_git = self._get_git_repo_name()
        if from_git:
            return from_git

        # Fallback to directory name
        return self._get_directory_name()

    def _read_waypoints_project_file(self) -> Optional[str]:
        """Read project ID from .waypoints-project file if exists."""
        project_file = Path(self.project_dir) / ".waypoints-project"
        if project_file.exists():
            content = project_file.read_text().strip()
            if content:
                return content
        return None

    def _get_git_repo_name(self) -> Optional[str]:
        """Extract repo name from git remote URL."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=5
            )
            if result.returncode != 0:
                return None

            url = result.stdout.strip()
            if not url:
                return None

            # Handle SSH URLs: git@github.com:user/repo.git
            ssh_match = re.search(r':([^/]+)/([^/]+?)(?:\.git)?$', url)
            if ssh_match:
                return ssh_match.group(2)

            # Handle HTTPS URLs: https://github.com/user/repo.git
            https_match = re.search(r'/([^/]+?)(?:\.git)?$', url)
            if https_match:
                return https_match.group(1)

            return None
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return None

    def _get_directory_name(self) -> str:
        """Get the directory name as fallback project ID."""
        return Path(self.project_dir).name


def extract_from_text(response_text: str) -> ExtractionResult:
    """
    Parse Claude's knowledge extraction response into structured data.

    Expected format from Claude [REQ-9]:
    ```
    ARCHITECTURE:
    - Title: Description
    - Title2: Description2

    DECISIONS:
    - Title: Description

    LESSONS_LEARNED:
    - [Tag] Title: Description
    ```

    Or if nothing notable:
    ```
    NO_KNOWLEDGE_EXTRACTED
    ```

    Args:
        response_text: Raw text response from Claude's extraction prompt

    Returns:
        ExtractionResult with parsed knowledge or error information

    Note:
        On malformed response [ERR-1]: Returns ExtractionResult with parse_error set,
        empty knowledge, and had_content=False. Caller should log warning and continue.
    """
    text = response_text.strip()

    # Check for NO_KNOWLEDGE_EXTRACTED signal
    if text == "NO_KNOWLEDGE_EXTRACTED":
        return ExtractionResult(
            knowledge=StagedKnowledge(),
            had_content=False,
            parse_error=None
        )

    # Try to parse sections
    architecture_entries: List[StagedKnowledgeEntry] = []
    decisions_entries: List[StagedKnowledgeEntry] = []
    lessons_entries: List[StagedKnowledgeEntry] = []

    # Extract ARCHITECTURE section - stops at DECISIONS: or LESSONS_LEARNED: on new line
    arch_match = re.search(
        r'ARCHITECTURE:\s*\n(.*?)(?=^DECISIONS:$|^LESSONS_LEARNED:$|\Z)',
        text,
        re.DOTALL | re.MULTILINE
    )
    if arch_match:
        architecture_entries = _parse_architecture_section(arch_match.group(1))

    # Extract DECISIONS section
    dec_match = re.search(
        r'DECISIONS:\s*\n(.*?)(?=^ARCHITECTURE:$|^LESSONS_LEARNED:$|\Z)',
        text,
        re.DOTALL | re.MULTILINE
    )
    if dec_match:
        decisions_entries = _parse_decisions_section(dec_match.group(1))

    # Extract LESSONS_LEARNED section
    lessons_match = re.search(
        r'LESSONS_LEARNED:\s*\n(.*?)(?=^ARCHITECTURE:$|^DECISIONS:$|\Z)',
        text,
        re.DOTALL | re.MULTILINE
    )
    if lessons_match:
        lessons_entries = _parse_lessons_learned_section(lessons_match.group(1))

    knowledge = StagedKnowledge(
        architecture=architecture_entries,
        decisions=decisions_entries,
        lessons_learned=lessons_entries
    )

    # Determine if we had content
    had_content = not knowledge.is_empty()

    return ExtractionResult(
        knowledge=knowledge,
        had_content=had_content,
        parse_error=None
    )


def _parse_architecture_section(section_text: str) -> List[StagedKnowledgeEntry]:
    """
    Parse ARCHITECTURE: section entries.

    Expected format: `- Title: Description`

    Args:
        section_text: Text content of the ARCHITECTURE section

    Returns:
        List of StagedKnowledgeEntry (without tag, phase set to 0 - caller sets phase)
    """
    entries = []
    if not section_text.strip():
        return entries

    # Match entries starting with "- "
    for line in section_text.strip().split('\n'):
        line = line.strip()
        if line.startswith('- '):
            # Remove the "- " prefix
            entry_text = line[2:].strip()
            # Split on first ": " to get title and content
            if ': ' in entry_text:
                title, content = entry_text.split(': ', 1)
                entries.append(StagedKnowledgeEntry(
                    title=title.strip(),
                    content=content.strip(),
                    phase=0,  # Caller sets phase
                    tag=None
                ))

    return entries


def _parse_decisions_section(section_text: str) -> List[StagedKnowledgeEntry]:
    """
    Parse DECISIONS: section entries.

    Expected format: `- Title: Description`

    Args:
        section_text: Text content of the DECISIONS section

    Returns:
        List of StagedKnowledgeEntry (without tag, phase set to 0 - caller sets phase)
    """
    entries = []
    if not section_text.strip():
        return entries

    # Match entries starting with "- "
    for line in section_text.strip().split('\n'):
        line = line.strip()
        if line.startswith('- '):
            # Remove the "- " prefix
            entry_text = line[2:].strip()
            # Split on first ": " to get title and content
            if ': ' in entry_text:
                title, content = entry_text.split(': ', 1)
                entries.append(StagedKnowledgeEntry(
                    title=title.strip(),
                    content=content.strip(),
                    phase=0,  # Caller sets phase
                    tag=None
                ))

    return entries


def _parse_lessons_learned_section(section_text: str) -> List[StagedKnowledgeEntry]:
    """
    Parse LESSONS_LEARNED: section entries.

    Expected format [REQ-10]: `- [Tag] Title: Description`

    Args:
        section_text: Text content of the LESSONS_LEARNED section

    Returns:
        List of StagedKnowledgeEntry (with tag, phase set to 0 - caller sets phase)
    """
    entries = []
    if not section_text.strip():
        return entries

    # Match entries starting with "- "
    for line in section_text.strip().split('\n'):
        line = line.strip()
        if line.startswith('- '):
            # Remove the "- " prefix
            entry_text = line[2:].strip()

            # Try to extract tag in [Tag] format
            tag = None
            tag_match = re.match(r'\[([^\]]+)\]\s*', entry_text)
            if tag_match:
                tag = tag_match.group(1)
                entry_text = entry_text[tag_match.end():].strip()

            # Split on first ": " to get title and content
            if ': ' in entry_text:
                title, content = entry_text.split(': ', 1)
                entries.append(StagedKnowledgeEntry(
                    title=title.strip(),
                    content=content.strip(),
                    phase=0,  # Caller sets phase
                    tag=tag
                ))

    return entries


class KnowledgeManager:
    """
    Manages project knowledge files: loading and application.

    Knowledge Loading (for context injection):
    - Loads permanent knowledge files from ~/.claude/waypoints/knowledge/
    - Per-project files: architecture.md, decisions.md
    - Global file: lessons-learned.md (shared across projects)

    Knowledge Application (at workflow end):
    - Applies staged knowledge to permanent files
    - Creates directories if needed [REQ-18]
    - Uses date headers for architecture/decisions [REQ-20]
    - Groups lessons-learned by technology tag [REQ-21]

    Note: Staging is handled by SupervisorMarkers in supervisor mode.
    This class is responsible for loading and applying, not staging.
    """

    def __init__(self, project_dir: str = "."):
        """
        Initialize knowledge manager.

        Args:
            project_dir: Project directory for project ID detection
        """
        self.project_dir = project_dir
        self._project_identifier = ProjectIdentifier(project_dir)
        self._knowledge_base_dir = Path.home() / ".claude" / "waypoints" / "knowledge"
        self._logger = logging.getLogger(__name__)

    @property
    def project_id(self) -> str:
        """Get the project ID (lazy evaluation)."""
        return self._project_identifier.get_project_id()

    # --- Knowledge Loading [REQ-1, REQ-2, REQ-3, REQ-4] ---

    def load_knowledge_context(self) -> str:
        """
        Load all relevant knowledge files into a context string.

        Returns formatted "Project Knowledge" section with subsections [REQ-3]:
        - Architecture
        - Decisions
        - Lessons Learned

        Files that don't exist show placeholder text [REQ-4].

        Returns:
            Formatted string for injection into Claude's context
        """
        sections = []

        # Load architecture [REQ-2]
        arch_content = self._load_architecture()
        if arch_content:
            sections.append(f"## Architecture\n\n{arch_content}")
        else:
            sections.append("## Architecture\n\nNo architecture documented yet.")

        # Load decisions [REQ-2]
        dec_content = self._load_decisions()
        if dec_content:
            sections.append(f"## Decisions\n\n{dec_content}")
        else:
            sections.append("## Decisions\n\nNo decisions documented yet.")

        # Load lessons learned [REQ-2]
        lessons_content = self._load_lessons_learned()
        if lessons_content:
            sections.append(f"## Lessons Learned\n\n{lessons_content}")
        else:
            sections.append("## Lessons Learned\n\nNo lessons learned documented yet.")

        # Format as Project Knowledge section [REQ-3]
        return "# Project Knowledge\n\n" + "\n\n".join(sections)

    def _load_architecture(self) -> Optional[str]:
        """
        Load project-specific architecture.md.

        Returns:
            File content if exists, None otherwise
        """
        path = self._get_knowledge_file_path(KnowledgeCategory.ARCHITECTURE)
        if path.exists():
            try:
                return path.read_text()
            except IOError:
                return None
        return None

    def _load_decisions(self) -> Optional[str]:
        """
        Load project-specific decisions.md.

        Returns:
            File content if exists, None otherwise
        """
        path = self._get_knowledge_file_path(KnowledgeCategory.DECISIONS)
        if path.exists():
            try:
                return path.read_text()
            except IOError:
                return None
        return None

    def _load_lessons_learned(self) -> Optional[str]:
        """
        Load global lessons-learned.md.

        Returns:
            File content if exists, None otherwise
        """
        path = self._get_knowledge_file_path(KnowledgeCategory.LESSONS_LEARNED)
        if path.exists():
            try:
                return path.read_text()
            except IOError:
                return None
        return None

    # --- Knowledge Application [REQ-17, REQ-18, REQ-19, REQ-20, REQ-21] ---

    def apply_staged_knowledge(
        self,
        staged: StagedKnowledge,
        session_id: str
    ) -> Dict[str, int]:
        """
        Apply staged knowledge to permanent files.

        Only called after Phase 4 completion (workflow success) [REQ-17].

        Args:
            staged: StagedKnowledge container with all entries
            session_id: Session ID for date headers [REQ-20]

        Returns:
            Summary dict: {"architecture": 2, "decisions": 1, "lessons-learned": 3}

        Note:
            On file write failure [ERR-2]: Logs error, continues with other files,
            returns partial summary. Workflow continues normally.
        """
        if staged.is_empty():
            return {}

        counts: Dict[str, int] = {}

        # Apply architecture entries
        if staged.architecture:
            arch_count = self._apply_architecture_entries(staged.architecture, session_id)
            if arch_count > 0:
                counts["architecture"] = arch_count

        # Apply decisions entries
        if staged.decisions:
            dec_count = self._apply_decisions_entries(staged.decisions, session_id)
            if dec_count > 0:
                counts["decisions"] = dec_count

        # Apply lessons-learned entries
        if staged.lessons_learned:
            lessons_count = self._apply_lessons_learned_entries(staged.lessons_learned)
            if lessons_count > 0:
                counts["lessons-learned"] = lessons_count

        return counts

    def _apply_architecture_entries(
        self,
        entries: List[StagedKnowledgeEntry],
        session_id: str
    ) -> int:
        """
        Apply architecture entries to architecture.md.

        Format [REQ-20]:
        ```
        ## YYYY-MM-DD (Session: {session_id})

        ### Title
        Content

        ### Title2
        Content2
        ```

        Args:
            entries: Architecture entries to apply
            session_id: Session ID for header

        Returns:
            Number of entries successfully applied
        """
        if not entries:
            return 0

        path = self._get_knowledge_file_path(KnowledgeCategory.ARCHITECTURE)
        today = date.today().strftime("%Y-%m-%d")

        # Build content with date header
        lines = [f"\n## {today} (Session: {session_id})\n"]
        for entry in entries:
            lines.append(f"\n### {entry.title}")
            lines.append(entry.content)
            lines.append("")

        content = "\n".join(lines)

        if self._append_to_file(path, content, KnowledgeCategory.ARCHITECTURE.header):
            return len(entries)
        return 0

    def _apply_decisions_entries(
        self,
        entries: List[StagedKnowledgeEntry],
        session_id: str
    ) -> int:
        """
        Apply decisions entries to decisions.md.

        Format [REQ-20]:
        ```
        ## YYYY-MM-DD (Session: {session_id})

        ### Title
        Content

        ### Title2
        Content2
        ```

        Args:
            entries: Decisions entries to apply
            session_id: Session ID for header

        Returns:
            Number of entries successfully applied
        """
        if not entries:
            return 0

        path = self._get_knowledge_file_path(KnowledgeCategory.DECISIONS)
        today = date.today().strftime("%Y-%m-%d")

        # Build content with date header
        lines = [f"\n## {today} (Session: {session_id})\n"]
        for entry in entries:
            lines.append(f"\n### {entry.title}")
            lines.append(entry.content)
            lines.append("")

        content = "\n".join(lines)

        if self._append_to_file(path, content, KnowledgeCategory.DECISIONS.header):
            return len(entries)
        return 0

    def _apply_lessons_learned_entries(
        self,
        entries: List[StagedKnowledgeEntry]
    ) -> int:
        """
        Apply lessons-learned entries to global lessons-learned.md.

        Format [REQ-21] - grouped by technology tag:
        ```
        ## [Python]

        ### Title (YYYY-MM-DD)
        Content

        ## [Git]

        ### Title2 (YYYY-MM-DD)
        Content2
        ```

        Args:
            entries: Lessons-learned entries to apply (must have tag set)

        Returns:
            Number of entries successfully applied
        """
        if not entries:
            return 0

        path = self._get_knowledge_file_path(KnowledgeCategory.LESSONS_LEARNED)
        today = date.today().strftime("%Y-%m-%d")

        # Group entries by tag [REQ-21]
        entries_by_tag: Dict[str, List[StagedKnowledgeEntry]] = {}
        for entry in entries:
            tag = entry.tag or "General"
            if tag not in entries_by_tag:
                entries_by_tag[tag] = []
            entries_by_tag[tag].append(entry)

        # Build content grouped by tag
        lines = ["\n"]
        for tag, tag_entries in entries_by_tag.items():
            lines.append(f"## [{tag}]\n")
            for entry in tag_entries:
                lines.append(f"### {entry.title} ({today})")
                lines.append(entry.content)
                lines.append("")

        content = "\n".join(lines)

        if self._append_to_file(path, content, KnowledgeCategory.LESSONS_LEARNED.header):
            return len(entries)
        return 0

    def _append_to_file(self, path: Path, content: str, header: str = "") -> bool:
        """
        Append content to a file, creating it with header if needed.

        Args:
            path: File path to append to
            content: Content to append
            header: Header to use if creating new file

        Returns:
            True if successful, False on error
        """
        try:
            # Create directories if needed [REQ-18]
            path.parent.mkdir(parents=True, exist_ok=True)

            # If file doesn't exist, create with header
            if not path.exists():
                with open(path, 'w') as f:
                    f.write(header)
                    f.write(content)
            else:
                # Append to existing file [REQ-19]
                with open(path, 'a') as f:
                    f.write(content)

            return True
        except IOError as e:
            self._logger.error(f"Failed to write to {path}: {e}")
            return False

    def _get_knowledge_file_path(self, category: KnowledgeCategory) -> Path:
        """
        Get path to knowledge file for category.

        Per-project files: ~/.claude/waypoints/knowledge/{project_id}/{filename}
        Global files: ~/.claude/waypoints/knowledge/{filename}

        Args:
            category: Knowledge category

        Returns:
            Path to the knowledge file
        """
        if category.is_global:
            # Global files go in the base knowledge directory [DEC-6]
            return self._knowledge_base_dir / category.filename
        else:
            # Per-project files go in project-specific subdirectory
            return self._knowledge_base_dir / self.project_id / category.filename

    # --- Utility ---

    def get_updated_files_summary(self, counts: Dict[str, int]) -> str:
        """
        Format console message for updated files [REQ-22].

        Args:
            counts: Dict from apply_staged_knowledge()

        Returns:
            Formatted string like "📚 Updated: architecture.md, decisions.md"
        """
        if not counts:
            return ""

        files = []
        if "architecture" in counts and counts["architecture"] > 0:
            files.append("architecture.md")
        if "decisions" in counts and counts["decisions"] > 0:
            files.append("decisions.md")
        if "lessons-learned" in counts and counts["lessons-learned"] > 0:
            files.append("lessons-learned.md")

        if not files:
            return ""

        return f"📚 Updated: {', '.join(files)}"
