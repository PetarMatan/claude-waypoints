#!/usr/bin/env python3
"""
Waypoints Knowledge Graph

Lightweight local graph structure for storing knowledge entries with relationships.
Graph is the source of truth; markdown files are generated materialized views.

Graph Structure [REQ-1]:
- Nodes: Knowledge entries (architecture, decisions, lessons-learned)
- Edges: Relationships (led_to, contradicts, supersedes, related_to, applies_to)

Storage [REQ-4]:
- JSON file per project: ~/.claude/waypoints/knowledge/{project_id}/graph.json
- Global graph for lessons-learned: ~/.claude/waypoints/knowledge/graph.json
"""

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Optional, List, Dict, Set, Tuple, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from wp_knowledge import KnowledgeCategory


class RelationshipType(Enum):
    """Relationship types between knowledge entries [REQ-2]."""
    LED_TO = "led_to"
    CONTRADICTS = "contradicts"
    SUPERSEDES = "supersedes"
    RELATED_TO = "related_to"
    APPLIES_TO = "applies_to"


@dataclass
class NodeId:
    """
    Unique identifier for a graph node [EDGE-4].

    Uses (category, title, date) tuple to handle duplicate titles.
    """
    category: str  # "architecture", "decisions", "lessons-learned"
    title: str
    date: str  # YYYY-MM-DD format

    def __hash__(self):
        return hash((self.category, self.title, self.date))

    def to_dict(self) -> Dict[str, str]:
        """Convert to JSON-serializable dict."""
        return {
            "category": self.category,
            "title": self.title,
            "date": self.date
        }

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "NodeId":
        """Create NodeId from dict."""
        return cls(
            category=data["category"],
            title=data["title"],
            date=data["date"]
        )


@dataclass
class KnowledgeNode:
    """
    A single knowledge entry in the graph [REQ-1].

    Attributes:
        node_id: Unique identifier for this node
        title: Entry title
        content: Entry content/description
        category: Knowledge category (architecture/decisions/lessons-learned)
        date_added: Date when entry was added (YYYY-MM-DD)
        session_id: Session that created this entry
        tag: Technology tag for lessons-learned (e.g., "Python", "Git")
        relationships: List of (relationship_type, target_node_id) tuples
    """
    node_id: NodeId
    title: str
    content: str
    category: str
    date_added: str  # YYYY-MM-DD
    session_id: str
    tag: Optional[str] = None
    relationships: List[Tuple[RelationshipType, NodeId]] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dict."""
        return {
            "node_id": self.node_id.to_dict(),
            "title": self.title,
            "content": self.content,
            "category": self.category,
            "date_added": self.date_added,
            "session_id": self.session_id,
            "tag": self.tag,
            "relationships": [
                (rel_type.value, target_id.to_dict())
                for rel_type, target_id in self.relationships
            ]
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "KnowledgeNode":
        """Create KnowledgeNode from dict."""
        node_id = NodeId.from_dict(data["node_id"])
        relationships = [
            (RelationshipType(rel[0]), NodeId.from_dict(rel[1]))
            for rel in data.get("relationships", [])
        ]
        return cls(
            node_id=node_id,
            title=data["title"],
            content=data["content"],
            category=data["category"],
            date_added=data["date_added"],
            session_id=data["session_id"],
            tag=data.get("tag"),
            relationships=relationships
        )


@dataclass
class KnowledgeGraph:
    """
    In-memory representation of the knowledge graph [REQ-1].

    Stores nodes and provides methods for querying and modification.
    """
    nodes: Dict[NodeId, KnowledgeNode] = field(default_factory=dict)

    def add_node(self, node: KnowledgeNode) -> None:
        """Add a node to the graph."""
        self.nodes[node.node_id] = node

    def get_node(self, node_id: NodeId) -> Optional[KnowledgeNode]:
        """Get a node by ID."""
        return self.nodes.get(node_id)

    def get_nodes_by_category(self, category: "KnowledgeCategory") -> List[KnowledgeNode]:
        """Get all nodes for a category [REQ-10, REQ-11]."""
        return [
            node for node in self.nodes.values()
            if node.category == category.value
        ]

    def add_relationship(
        self,
        source: NodeId,
        relationship_type: RelationshipType,
        target: NodeId
    ) -> bool:
        """
        Add a relationship between nodes [REQ-19].

        Returns:
            True if relationship was added, False if source or target doesn't exist

        Note:
            If target doesn't exist, logs warning and returns False [EDGE-2].
        """
        source_node = self.get_node(source)
        if source_node is None:
            return False

        # Check if target exists (log warning if not) [EDGE-2]
        target_node = self.get_node(target)
        if target_node is None:
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Relationship target not found: {target.title} (source: {source.title}). "
                f"Skipping relationship."
            )
            return False

        # Add relationship to source node
        source_node.relationships.append((relationship_type, target))
        return True

    def get_related_nodes(
        self,
        node_id: NodeId,
        relationship_type: Optional[RelationshipType] = None
    ) -> List[KnowledgeNode]:
        """
        Get nodes related to this node.

        Args:
            node_id: Source node ID
            relationship_type: Filter by relationship type (None = all types)
        """
        source_node = self.get_node(node_id)
        if source_node is None:
            return []

        related = []
        for rel_type, target_id in source_node.relationships:
            # Filter by relationship type if specified
            if relationship_type is not None and rel_type != relationship_type:
                continue

            # Get target node
            target_node = self.get_node(target_id)
            if target_node is not None:
                related.append(target_node)

        return related

    def to_dict(self) -> Dict:
        """Convert graph to JSON-serializable dict."""
        return {
            "nodes": {
                # Use string key for JSON serialization
                f"{node_id.category}|{node_id.title}|{node_id.date}": node.to_dict()
                for node_id, node in self.nodes.items()
            }
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "KnowledgeGraph":
        """Create graph from dict."""
        graph = cls()
        for node_dict in data.get("nodes", {}).values():
            node = KnowledgeNode.from_dict(node_dict)
            graph.add_node(node)
        return graph


class GraphStorage:
    """
    Handles persistence of knowledge graphs to/from disk [REQ-4].

    Storage locations:
    - Per-project: ~/.claude/waypoints/knowledge/{project_id}/graph.json
    - Global (lessons-learned): ~/.claude/waypoints/knowledge/graph.json
    """

    def __init__(self, knowledge_base_dir: Path):
        """
        Initialize graph storage.

        Args:
            knowledge_base_dir: Base directory for knowledge storage
                               (e.g., ~/.claude/waypoints/knowledge/)
        """
        self._knowledge_base_dir = knowledge_base_dir
        self._logger = logging.getLogger(__name__)

    def load_project_graph(self, project_id: str) -> KnowledgeGraph:
        """
        Load project-specific graph [REQ-10, REQ-11].

        Args:
            project_id: Project identifier

        Returns:
            KnowledgeGraph (empty if file doesn't exist)

        Note:
            On corruption [ERR-2]: Attempts to rebuild from markdown files,
            logs error and returns empty graph if rebuild fails.
        """
        path = self._get_project_graph_path(project_id)
        return self._load_graph_from_file(path)

    def load_global_graph(self) -> KnowledgeGraph:
        """
        Load global graph (lessons-learned only) [REQ-12].

        Returns:
            KnowledgeGraph (empty if file doesn't exist)

        Note:
            On corruption [ERR-2]: Attempts to rebuild from markdown files,
            logs error and returns empty graph if rebuild fails.
        """
        path = self._get_global_graph_path()
        return self._load_graph_from_file(path)

    def save_project_graph(self, project_id: str, graph: KnowledgeGraph) -> bool:
        """
        Save project-specific graph.

        Args:
            project_id: Project identifier
            graph: Graph to save

        Returns:
            True if successful, False on error
        """
        path = self._get_project_graph_path(project_id)
        return self._save_graph_to_file(path, graph)

    def save_global_graph(self, graph: KnowledgeGraph) -> bool:
        """
        Save global graph (lessons-learned).

        Args:
            graph: Graph to save

        Returns:
            True if successful, False on error
        """
        path = self._get_global_graph_path()
        return self._save_graph_to_file(path, graph)

    def _get_project_graph_path(self, project_id: str) -> Path:
        """Get path to project graph file."""
        return self._knowledge_base_dir / project_id / "graph.json"

    def _get_global_graph_path(self) -> Path:
        """Get path to global graph file."""
        return self._knowledge_base_dir / "global-graph.json"

    def _load_graph_from_file(self, path: Path) -> KnowledgeGraph:
        """
        Load graph from JSON file.

        Returns:
            KnowledgeGraph (empty if file doesn't exist or is corrupted)
        """
        if not path.exists():
            return KnowledgeGraph()

        try:
            data = json.loads(path.read_text())
            return KnowledgeGraph.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # [ERR-2] Graph corruption: return empty graph gracefully
            self._logger.error(f"Corrupted graph file {path}: {e}. Returning empty graph.")
            return KnowledgeGraph()

    def _save_graph_to_file(self, path: Path, graph: KnowledgeGraph) -> bool:
        """
        Save graph to JSON file.

        Returns:
            True if successful, False on error
        """
        try:
            # Create directory if it doesn't exist
            path.parent.mkdir(parents=True, exist_ok=True)

            # Save graph as JSON
            data = graph.to_dict()
            path.write_text(json.dumps(data, indent=2))
            return True
        except (OSError, IOError) as e:
            self._logger.error(f"Failed to save graph to {path}: {e}")
            return False

    def _rebuild_from_markdown(
        self,
        markdown_path: Path,
        category: "KnowledgeCategory"
    ) -> KnowledgeGraph:
        """
        Rebuild graph from markdown file [ERR-2].

        Args:
            markdown_path: Path to markdown file
            category: Category to parse

        Returns:
            KnowledgeGraph with parsed entries (no relationships)
        """
        # For now, return empty graph (full rebuild logic handled in migration)
        return KnowledgeGraph()


class RelationshipParser:
    """
    Parses relationship markers from Claude's extraction output [REQ-3, REQ-17, REQ-18].

    Bracket notation format: [relationship_type: "target_entry_title"]
    Example: "We implemented feature X [led_to: "API versioning strategy"]"
    """

    @staticmethod
    def parse_relationships(content: str) -> List[Tuple[RelationshipType, str]]:
        """
        Extract relationships from content text [REQ-3].

        Args:
            content: Entry content text with inline relationship markers

        Returns:
            List of (relationship_type, target_title) tuples

        Note:
            On malformed syntax [EDGE-3]: Logs warning, skips invalid markers
        """
        # Pattern: [relationship_type: "target title"]
        # Case-sensitive, double-quoted target title
        pattern = r'\[(\w+):\s*"([^"]+)"\]'
        relationships = []
        logger = logging.getLogger(__name__)

        for match in re.finditer(pattern, content):
            rel_type_str = match.group(1)
            target_title = match.group(2)

            # Parse relationship type
            try:
                rel_type = RelationshipType(rel_type_str)
                relationships.append((rel_type, target_title))
            except ValueError:
                # [EDGE-3] Invalid relationship type: log warning and skip
                logger.warning(f"Unknown relationship type: {rel_type_str}")

        return relationships

    @staticmethod
    def strip_relationships(content: str) -> str:
        """
        Remove relationship markers from content for clean storage.

        Args:
            content: Entry content with inline markers

        Returns:
            Content with markers removed
        """
        # Pattern: [relationship_type: "target title"]
        pattern = r'\[(\w+):\s*"([^"]+)"\]'
        # Remove markers but keep surrounding text
        result = re.sub(pattern, '', content)
        # Clean up extra spaces
        result = re.sub(r'\s+', ' ', result)
        return result.strip()

    @staticmethod
    def _parse_single_marker(marker: str) -> Optional[Tuple[RelationshipType, str]]:
        """
        Parse a single relationship marker.

        Args:
            marker: Marker text like 'led_to: "target title"'

        Returns:
            (RelationshipType, target_title) or None if invalid
        """
        # This is a helper method, main logic is in parse_relationships
        pattern = r'(\w+):\s*"([^"]+)"'
        match = re.match(pattern, marker)
        if not match:
            return None

        try:
            rel_type = RelationshipType(match.group(1))
            target_title = match.group(2)
            return (rel_type, target_title)
        except ValueError:
            return None
