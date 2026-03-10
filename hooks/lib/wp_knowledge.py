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
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict, field

# Lazy imports for graph and RAG (set at module level for test mocking)
GraphStorage = None
RAGService = None


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
        relationships: List of (relationship_type, target_title) parsed from content [REQ-3]
    """
    title: str
    content: str
    phase: int
    tag: Optional[str] = None
    relationships: List[Tuple[str, str]] = field(default_factory=list)  # [(type, target_title)]


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

    NEW [REQ-3, REQ-17]: Parses relationship markers from content.

    Args:
        section_text: Text content of the ARCHITECTURE section

    Returns:
        List of StagedKnowledgeEntry (without tag, phase set to 0 - caller sets phase)
    """
    from wp_graph import RelationshipParser

    entries = []
    lines = section_text.strip().split('\n')

    for line in lines:
        line = line.strip()
        if not line or not line.startswith('- '):
            continue

        # Parse: "- Title: Description"
        match = re.match(r'^-\s+([^:]+):\s*(.+)$', line)
        if match:
            title = match.group(1).strip()
            content = match.group(2).strip()

            # Parse relationships from content
            relationships = RelationshipParser.parse_relationships(content)

            entries.append(StagedKnowledgeEntry(
                title=title,
                content=content,
                phase=0,
                relationships=[(rel_type.value, target) for rel_type, target in relationships]
            ))

    return entries


def _parse_decisions_section(section_text: str) -> List[StagedKnowledgeEntry]:
    """
    Parse DECISIONS: section entries.

    Expected format: `- Title: Description`

    NEW [REQ-3, REQ-17]: Parses relationship markers from content.

    Args:
        section_text: Text content of the DECISIONS section

    Returns:
        List of StagedKnowledgeEntry (without tag, phase set to 0 - caller sets phase)
    """
    # Same format as architecture
    return _parse_architecture_section(section_text)


def _parse_lessons_learned_section(section_text: str) -> List[StagedKnowledgeEntry]:
    """
    Parse LESSONS_LEARNED: section entries.

    Expected format [REQ-10]: `- [Tag] Title: Description`

    NEW [REQ-3, REQ-17]: Parses relationship markers from content.

    Args:
        section_text: Text content of the LESSONS_LEARNED section

    Returns:
        List of StagedKnowledgeEntry (with tag, phase set to 0 - caller sets phase)
    """
    from wp_graph import RelationshipParser

    entries = []
    lines = section_text.strip().split('\n')

    for line in lines:
        line = line.strip()
        if not line or not line.startswith('- '):
            continue

        # Parse: "- [Tag] Title: Description"
        match = re.match(r'^-\s+\[([^\]]+)\]\s+([^:]+):\s*(.+)$', line)
        if match:
            tag = match.group(1).strip()
            title = match.group(2).strip()
            content = match.group(3).strip()

            # Parse relationships from content
            relationships = RelationshipParser.parse_relationships(content)

            entries.append(StagedKnowledgeEntry(
                title=title,
                content=content,
                phase=0,
                tag=tag,
                relationships=[(rel_type.value, target) for rel_type, target in relationships]
            ))

    return entries


class KnowledgeManager:
    """
    Manages project knowledge files: loading and application.

    Knowledge Loading (for context injection):
    - Loads permanent knowledge files from ~/.claude/waypoints/knowledge/
    - Per-project files: architecture.md, decisions.md
    - Global file: lessons-learned.md (shared across projects)

    HYBRID GRAPH + RAG MODE [NEW]:
    - Loads architecture/decisions from graph (complete) [REQ-10, REQ-11]
    - Loads lessons-learned via RAG semantic search (filtered) [REQ-12]
    - Generates markdown files from graph at workflow end [REQ-14, REQ-15]

    Knowledge Application (at workflow end):
    - Applies staged knowledge to graph structure [REQ-1]
    - Parses relationships from content [REQ-3, REQ-18, REQ-19]
    - Regenerates markdown materialized views [REQ-15, REQ-16]

    Note: Staging is handled by SupervisorMarkers in supervisor mode.
    This class is responsible for loading and applying, not staging.
    """

    def __init__(
        self,
        project_dir: str = ".",
        enable_graph: bool = True,
        enable_rag: bool = True
    ):
        """
        Initialize knowledge manager.

        Args:
            project_dir: Project directory for project ID detection
            enable_graph: If True, use graph storage (default: True)
            enable_rag: If True, use RAG for lessons filtering (default: True)
        """
        self.project_dir = project_dir
        self._project_identifier = ProjectIdentifier(project_dir)
        claude_config = os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))
        self._knowledge_base_dir = Path(claude_config) / "waypoints" / "knowledge"
        self._logger = logging.getLogger(__name__)

        # Graph and RAG components (lazy-loaded)
        self._enable_graph = enable_graph
        self._enable_rag = enable_rag
        self._graph_storage = None
        self._rag_service = None
        self._project_graph = None
        self._global_graph = None

        # Stats from last load_knowledge_context call (for external logging)
        self.load_stats = None

    @property
    def project_id(self) -> str:
        """Get the project ID (lazy evaluation)."""
        return self._project_identifier.get_project_id()

    @property
    def graph_storage(self):
        """Get graph storage (lazy initialization)."""
        self._initialize_graph_storage()
        return self._graph_storage

    @graph_storage.setter
    def graph_storage(self, value):
        """Set graph storage (for testing)."""
        self._graph_storage = value

    @property
    def rag_service(self):
        """Get RAG service (lazy initialization)."""
        self._initialize_rag_service()
        return self._rag_service

    @rag_service.setter
    def rag_service(self, value):
        """Set RAG service (for testing)."""
        self._rag_service = value

    # --- Graph and RAG Initialization ---

    def _initialize_graph_storage(self):
        """Lazy-initialize graph storage."""
        global GraphStorage
        if self._graph_storage is None:
            if GraphStorage is None:
                from wp_graph import GraphStorage as _GraphStorage
                GraphStorage = _GraphStorage
            self._graph_storage = GraphStorage(self._knowledge_base_dir)

    def _initialize_rag_service(self):
        """
        Lazy-initialize RAG service.

        Note:
            [ERR-1] If embeddings model fails to load, logs error and disables RAG.
        """
        global RAGService
        if self._rag_service is None:
            if RAGService is None:
                from wp_embeddings import RAGService as _RAGService, EmbeddingsModel, EmbeddingsStorage, SENTENCE_TRANSFORMERS_AVAILABLE
                RAGService = _RAGService
            else:
                from wp_embeddings import EmbeddingsModel, EmbeddingsStorage, SENTENCE_TRANSFORMERS_AVAILABLE

            if not SENTENCE_TRANSFORMERS_AVAILABLE:
                self._logger.debug("RAG disabled: sentence-transformers not installed")
                self._enable_rag = False
                return

            embeddings_model = EmbeddingsModel()
            embeddings_storage = EmbeddingsStorage(self._knowledge_base_dir)
            self._rag_service = RAGService(embeddings_model, embeddings_storage)

    def _load_graphs(self):
        """Load project and global graphs from storage."""
        self._initialize_graph_storage()
        self._project_graph = self._graph_storage.load_project_graph(self.project_id)
        self._global_graph = self._graph_storage.load_global_graph()

    # --- Knowledge Loading [REQ-1, REQ-2, REQ-3, REQ-4] ---

    def load_knowledge_context(self, query_text: Optional[str] = None) -> str:
        """
        Load all relevant knowledge into a context string.

        HYBRID MODE [NEW]:
        - If graph enabled: Load architecture/decisions from graph (complete) [REQ-10, REQ-11]
        - If RAG enabled + query_text: Load lessons via semantic search [REQ-7, REQ-8, REQ-12]
        - If RAG disabled or no query: Load all lessons from graph
        - Fallback: Load from markdown files (legacy mode)

        Args:
            query_text: Optional query for RAG filtering of lessons [REQ-7]

        Returns:
            Formatted string for injection into Claude's context

        Note:
            [REQ-9] Logs count of lessons loaded to console/workflow output
        """
        self.load_stats = {"mode": "legacy", "rag_used": False}

        # Use legacy mode if graph disabled
        if not self._enable_graph:
            return self.load_knowledge_context_legacy()

        sections = []

        self._load_graphs()

        # Check if graphs are empty and are real dicts (not mocks)
        # If empty real graphs, fall back to markdown
        if (isinstance(self._project_graph.nodes, dict) and
            isinstance(self._global_graph.nodes, dict)):
            total_nodes = len(self._project_graph.nodes) + len(self._global_graph.nodes)
            if total_nodes == 0 and not (self._enable_rag and query_text):
                # No graph data, use legacy markdown loading
                self.load_stats = {"mode": "legacy_fallback", "rag_used": False, "reason": "empty graphs"}
                return self.load_knowledge_context_legacy()

        # Load architecture from graph [REQ-10]
        arch_nodes = self._project_graph.get_nodes_by_category(KnowledgeCategory.ARCHITECTURE)
        if arch_nodes:
            arch_content = self._format_nodes_as_markdown(arch_nodes)
            sections.append(f"## Architecture\n\n{arch_content}")
        else:
            sections.append("## Architecture\n\nNo architecture documented yet.")

        # Load decisions from graph [REQ-11]
        dec_nodes = self._project_graph.get_nodes_by_category(KnowledgeCategory.DECISIONS)
        if dec_nodes:
            dec_content = self._format_nodes_as_markdown(dec_nodes)
            sections.append(f"## Decisions\n\n{dec_content}")
        else:
            sections.append("## Decisions\n\nNo decisions documented yet.")

        # Load lessons from RAG or graph
        if self._enable_rag and query_text:
            # Initialize RAG and query [REQ-7, REQ-8, REQ-12]
            self._initialize_rag_service()

        if self._enable_rag and query_text and self._rag_service is not None:
            lessons_nodes = self._global_graph.get_nodes_by_category(KnowledgeCategory.LESSONS_LEARNED)

            # Initialize RAG index
            success = self._rag_service.initialize(lessons_nodes)
            if success:
                # Query relevant lessons
                relevant_lessons = self._rag_service.query_relevant_lessons(query_text)
                lessons_count = len(relevant_lessons)
                self.load_stats = {
                    "mode": "graph+rag", "rag_used": True,
                    "total_lessons": len(lessons_nodes), "relevant_lessons": lessons_count,
                }

                if relevant_lessons:
                    lessons_content = self._format_nodes_as_markdown(relevant_lessons)
                    sections.append(f"## Lessons Learned\n\n{lessons_content}")
                else:
                    sections.append("## Lessons Learned\n\nNo relevant lessons found for this task.")
            else:
                # RAG initialization failed, fall back to all lessons
                self.load_stats = {
                    "mode": "graph", "rag_used": False,
                    "total_lessons": len(lessons_nodes), "reason": "RAG init failed",
                }
                if lessons_nodes:
                    lessons_content = self._format_nodes_as_markdown(lessons_nodes)
                    sections.append(f"## Lessons Learned\n\n{lessons_content}")
                else:
                    sections.append("## Lessons Learned\n\nNo lessons learned documented yet.")
        else:
            # Load all lessons from graph (no RAG filtering)
            lessons_nodes = self._global_graph.get_nodes_by_category(KnowledgeCategory.LESSONS_LEARNED)
            self.load_stats = {
                "mode": "graph", "rag_used": False,
                "total_lessons": len(lessons_nodes),
            }
            if lessons_nodes:
                lessons_content = self._format_nodes_as_markdown(lessons_nodes)
                sections.append(f"## Lessons Learned\n\n{lessons_content}")
            else:
                sections.append("## Lessons Learned\n\nNo lessons learned documented yet.")

        return "# Project Knowledge\n\n" + "\n\n".join(sections)

    def _format_nodes_as_markdown(self, nodes: List) -> str:
        """Format knowledge nodes as markdown text."""
        # Group by session/date
        from collections import defaultdict
        by_date = defaultdict(list)

        for node in nodes:
            by_date[node.date_added].append(node)

        # Format as markdown
        lines = []
        for date_key in sorted(by_date.keys(), reverse=True):
            date_nodes = by_date[date_key]
            lines.append(f"## {date_key}")
            for node in date_nodes:
                if node.tag:
                    lines.append(f"\n### [{node.tag}] {node.title}")
                else:
                    lines.append(f"\n### {node.title}")
                lines.append(node.content)
            lines.append("")

        return "\n".join(lines)

    def load_knowledge_context_legacy(self) -> str:
        """
        Load all relevant knowledge files into a context string (LEGACY MODE).

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
        Apply staged knowledge to permanent storage.

        HYBRID MODE [NEW]:
        - If graph enabled: Apply to graph structure [REQ-1, REQ-19]
        - Parse relationships from content [REQ-3, REQ-18]
        - Generate markdown materialized views from graph [REQ-14, REQ-15]
        - Fallback: Apply to markdown files (legacy mode)

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

        if self._enable_graph:
            return self._apply_to_graph(staged, session_id)
        else:
            return self._apply_to_markdown_legacy(staged, session_id)

    def _apply_to_graph(
        self,
        staged: StagedKnowledge,
        session_id: str
    ) -> Dict[str, int]:
        """
        Apply staged knowledge to graph structure [REQ-1, REQ-19].

        Args:
            staged: StagedKnowledge container with all entries
            session_id: Session ID for node metadata

        Returns:
            Summary dict with counts
        """
        from wp_graph import RelationshipType
        from datetime import date

        self._load_graphs()
        counts: Dict[str, int] = {}

        # Apply architecture entries to project graph
        if staged.architecture:
            arch_count = self._add_entries_to_graph(
                staged.architecture,
                KnowledgeCategory.ARCHITECTURE,
                session_id,
                self._project_graph
            )
            if arch_count > 0:
                counts["architecture"] = arch_count

        # Apply decisions entries to project graph
        if staged.decisions:
            dec_count = self._add_entries_to_graph(
                staged.decisions,
                KnowledgeCategory.DECISIONS,
                session_id,
                self._project_graph
            )
            if dec_count > 0:
                counts["decisions"] = dec_count

        # Apply lessons-learned entries to global graph
        lessons_count = 0
        if staged.lessons_learned:
            lessons_count = self._add_entries_to_graph(
                staged.lessons_learned,
                KnowledgeCategory.LESSONS_LEARNED,
                session_id,
                self._global_graph
            )
            if lessons_count > 0:
                counts["lessons-learned"] = lessons_count

        # Save graphs [REQ-4]
        self._graph_storage.save_project_graph(self.project_id, self._project_graph)
        self._graph_storage.save_global_graph(self._global_graph)

        # Regenerate markdown views [REQ-15]
        self.regenerate_all_markdown_views()

        # Rebuild RAG index if RAG enabled [REQ-6]
        if self._enable_rag and lessons_count > 0:
            self._initialize_rag_service()
            if self._enable_rag and self._rag_service is not None:
                all_lessons = self._global_graph.get_nodes_by_category(KnowledgeCategory.LESSONS_LEARNED)
                self._rag_service.rebuild_index(all_lessons)

        return counts

    def _find_node_by_title(self, graph, title: str):
        """
        Find a node in the graph by title (searches all categories/dates).

        Args:
            graph: KnowledgeGraph to search
            title: Title to search for

        Returns:
            NodeId of matching node, or None if not found

        Note:
            If multiple nodes have the same title, returns the first match.
        """
        for node_id, node in graph.nodes.items():
            if node.title == title:
                return node_id
        return None

    def _add_entries_to_graph(
        self,
        entries: List[StagedKnowledgeEntry],
        category: KnowledgeCategory,
        session_id: str,
        graph
    ) -> int:
        """Add entries to graph with relationship parsing."""
        from wp_graph import KnowledgeNode, NodeId, RelationshipType, RelationshipParser
        from datetime import date

        for entry in entries:
            # Strip relationship markers from content
            clean_content = RelationshipParser.strip_relationships(entry.content)

            # Create node ID
            node_id = NodeId(
                category=category.value,
                title=entry.title,
                date=date.today().isoformat()
            )

            # Create knowledge node
            node = KnowledgeNode(
                node_id=node_id,
                title=entry.title,
                content=clean_content,
                category=category.value,
                date_added=date.today().isoformat(),
                session_id=session_id,
                tag=entry.tag
            )

            # Add node to graph
            graph.add_node(node)

            # Add relationships [REQ-19]
            for rel_type_str, target_title in entry.relationships:
                try:
                    rel_type = RelationshipType(rel_type_str)
                    # Find target node by title (search all nodes in graph)
                    target_id = self._find_node_by_title(graph, target_title)
                    if target_id:
                        graph.add_relationship(node_id, rel_type, target_id)
                    else:
                        self._logger.warning(
                            f"Relationship target not found: '{target_title}' "
                            f"(referenced by '{entry.title}')"
                        )
                except (ValueError, KeyError):
                    self._logger.warning(f"Failed to add relationship: {rel_type_str} -> {target_title}")

        return len(entries)

    def _apply_to_markdown_legacy(
        self,
        staged: StagedKnowledge,
        session_id: str
    ) -> Dict[str, int]:
        """
        Apply staged knowledge to markdown files (LEGACY MODE).

        Args:
            staged: StagedKnowledge container with all entries
            session_id: Session ID for date headers

        Returns:
            Summary dict: {"architecture": 2, "decisions": 1, "lessons-learned": 3}
        """
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

    # --- Graph Application and Markdown Generation [NEW] ---


    def generate_markdown_from_graph(
        self,
        graph,
        category: KnowledgeCategory
    ) -> str:
        """
        Generate markdown materialized view from graph [REQ-14, REQ-15].

        Args:
            graph: KnowledgeGraph containing nodes
            category: Category to generate markdown for

        Returns:
            Formatted markdown content
        """
        nodes = graph.get_nodes_by_category(category)
        if not nodes:
            return category.header

        # Group by date and session
        from collections import defaultdict
        by_session = defaultdict(list)

        for node in nodes:
            key = (node.date_added, node.session_id)
            by_session[key].append(node)

        # Generate markdown
        lines = [category.header.rstrip()]

        for (date_str, session_id), session_nodes in sorted(by_session.items(), reverse=True):
            lines.append(f"\n## {date_str} (Session: {session_id})\n")

            for node in session_nodes:
                if node.tag:
                    # Lessons-learned format with tag [REQ-14]
                    lines.append(f"### [{node.tag}] {node.title}")
                else:
                    lines.append(f"### {node.title}")
                lines.append(node.content)
                lines.append("")

        return '\n'.join(lines)

    def regenerate_all_markdown_views(self) -> bool:
        """
        Regenerate all markdown files from graph [REQ-15, REQ-16].

        Called after knowledge application at workflow end.

        Returns:
            True if successful, False on error
        """
        try:
            # Load graphs if not loaded
            if self._project_graph is None or self._global_graph is None:
                self._load_graphs()

            # Regenerate project markdown files
            arch_path = self._get_knowledge_file_path(KnowledgeCategory.ARCHITECTURE)
            arch_content = self.generate_markdown_from_graph(self._project_graph, KnowledgeCategory.ARCHITECTURE)
            arch_path.parent.mkdir(parents=True, exist_ok=True)
            arch_path.write_text(arch_content)

            dec_path = self._get_knowledge_file_path(KnowledgeCategory.DECISIONS)
            dec_content = self.generate_markdown_from_graph(self._project_graph, KnowledgeCategory.DECISIONS)
            dec_path.write_text(dec_content)

            # Regenerate global lessons-learned
            lessons_path = self._get_knowledge_file_path(KnowledgeCategory.LESSONS_LEARNED)
            lessons_content = self.generate_markdown_from_graph(self._global_graph, KnowledgeCategory.LESSONS_LEARNED)
            lessons_path.write_text(lessons_content)

            return True
        except Exception as e:
            self._logger.error(f"Failed to regenerate markdown views: {e}")
            return False

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
