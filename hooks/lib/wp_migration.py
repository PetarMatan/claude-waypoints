#!/usr/bin/env python3
"""
Waypoints Knowledge Migration

Migrates existing markdown knowledge files to graph structure [REQ-21, REQ-22, REQ-23].

Migration is manual via explicit CLI command, not automatic on first run.
Preserves all existing entry content, dates, and session metadata.
"""

import logging
import re
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional, Dict

from wp_knowledge import KnowledgeCategory
from wp_graph import KnowledgeGraph, KnowledgeNode, NodeId, GraphStorage, RelationshipParser


class MarkdownParser:
    """
    Parses existing markdown knowledge files to extract entries [REQ-23].

    Preserves dates, session IDs, and all content.
    """

    @staticmethod
    def parse_architecture_markdown(markdown_content: str) -> List[Dict]:
        """
        Parse architecture.md into structured entries.

        Expected format:
        ```
        ## YYYY-MM-DD (Session: session_id)

        ### Title
        Content

        ### Title2
        Content2
        ```

        Args:
            markdown_content: Raw markdown file content

        Returns:
            List of dicts with keys: title, content, date, session_id
        """
        entries = []
        lines = markdown_content.split('\n')

        current_date = None
        current_session_id = None
        current_title = None
        current_content_lines = []

        for line in lines:
            # Check for date header: ## YYYY-MM-DD (Session: session_id)
            date_header = MarkdownParser._parse_date_header(line)
            if date_header:
                # Save previous entry if exists
                if current_title:
                    entries.append({
                        "title": current_title,
                        "content": '\n'.join(current_content_lines).strip(),
                        "date": current_date or date.today().isoformat(),
                        "session_id": current_session_id or "unknown"
                    })
                current_date = date_header["date"]
                current_session_id = date_header["session_id"]
                current_title = None
                current_content_lines = []
                continue

            # Check for entry header: ### Title
            entry_title = MarkdownParser._parse_entry_header(line)
            if entry_title:
                # Save previous entry if exists
                if current_title:
                    entries.append({
                        "title": current_title,
                        "content": '\n'.join(current_content_lines).strip(),
                        "date": current_date or date.today().isoformat(),
                        "session_id": current_session_id or "unknown"
                    })
                current_title = entry_title
                current_content_lines = []
                # Set default date/session if not already set (malformed headers)
                if current_date is None:
                    current_date = date.today().isoformat()
                if current_session_id is None:
                    current_session_id = "unknown"
                continue

            # Accumulate content lines
            if current_title:
                current_content_lines.append(line)

        # Save last entry
        if current_title:
            entries.append({
                "title": current_title,
                "content": '\n'.join(current_content_lines).strip(),
                "date": current_date or date.today().isoformat(),
                "session_id": current_session_id or "unknown"
            })

        return entries

    @staticmethod
    def parse_decisions_markdown(markdown_content: str) -> List[Dict]:
        """
        Parse decisions.md into structured entries.

        Format same as architecture.md.

        Args:
            markdown_content: Raw markdown file content

        Returns:
            List of dicts with keys: title, content, date, session_id
        """
        # Same format as architecture
        return MarkdownParser.parse_architecture_markdown(markdown_content)

    @staticmethod
    def parse_lessons_markdown(markdown_content: str) -> List[Dict]:
        """
        Parse lessons-learned.md into structured entries.

        Expected format:
        ```
        ## [Tag]

        ### Title (YYYY-MM-DD)
        Content

        ### Title2 (YYYY-MM-DD)
        Content2
        ```

        Args:
            markdown_content: Raw markdown file content

        Returns:
            List of dicts with keys: title, content, date, tag
        """
        entries = []
        lines = markdown_content.split('\n')

        current_tag = None
        current_title = None
        current_date = None
        current_content_lines = []

        for line in lines:
            # Check for tag header: ## [Tag]
            tag_match = re.match(r'^##\s*\[([^\]]+)\]\s*$', line)
            if tag_match:
                # Save previous entry if exists
                if current_title:
                    entries.append({
                        "title": current_title,
                        "content": '\n'.join(current_content_lines).strip(),
                        "date": current_date or date.today().isoformat(),
                        "tag": current_tag
                    })
                current_tag = tag_match.group(1)
                current_title = None
                current_date = None
                current_content_lines = []
                continue

            # Check for entry header: ### Title or ### Title (YYYY-MM-DD)
            if line.startswith('### '):
                # Save previous entry if exists
                if current_title:
                    entries.append({
                        "title": current_title,
                        "content": '\n'.join(current_content_lines).strip(),
                        "date": current_date or date.today().isoformat(),
                        "tag": current_tag
                    })

                # Parse title and date
                title_text = line[4:].strip()
                title, entry_date = MarkdownParser._extract_date_from_title(title_text)
                current_title = title
                current_date = entry_date or date.today().isoformat()
                current_content_lines = []
                continue

            # Accumulate content lines
            if current_title:
                current_content_lines.append(line)

        # Save last entry
        if current_title:
            entries.append({
                "title": current_title,
                "content": '\n'.join(current_content_lines).strip(),
                "date": current_date or date.today().isoformat(),
                "tag": current_tag
            })

        return entries

    @staticmethod
    def _parse_date_header(line: str) -> Optional[Dict]:
        """
        Parse date header line: `## YYYY-MM-DD (Session: session_id)`

        Returns:
            Dict with 'date' and 'session_id' keys, or None if not a date header
        """
        # Pattern: ## YYYY-MM-DD (Session: session_id)
        match = re.match(r'^##\s*(\d{4}-\d{2}-\d{2})\s*\(Session:\s*([^\)]+)\)\s*$', line)
        if match:
            return {
                "date": match.group(1),
                "session_id": match.group(2)
            }
        return None

    @staticmethod
    def _parse_entry_header(line: str) -> Optional[str]:
        """
        Parse entry header line: `### Title` or `### Title (YYYY-MM-DD)`

        Returns:
            Title string, or None if not an entry header
        """
        if line.startswith('### '):
            title = line[4:].strip()
            # Remove date suffix if present
            title_clean, _ = MarkdownParser._extract_date_from_title(title)
            return title_clean
        return None

    @staticmethod
    def _extract_date_from_title(title: str) -> tuple:
        """
        Extract date from title like "Title (YYYY-MM-DD)".

        Returns:
            Tuple of (title_without_date, date_string)
        """
        # Pattern: Title (YYYY-MM-DD)
        match = re.match(r'^(.+?)\s*\((\d{4}-\d{2}-\d{2})\)\s*$', title)
        if match:
            return (match.group(1).strip(), match.group(2))
        return (title, None)


class KnowledgeMigrator:
    """
    Migrates markdown knowledge files to graph structure [REQ-21].

    Usage:
        migrator = KnowledgeMigrator(knowledge_base_dir, project_id)
        success = migrator.migrate_project()
    """

    def __init__(self, knowledge_base_dir: Path, project_id: Optional[str] = None):
        """
        Initialize migrator.

        Args:
            knowledge_base_dir: Base directory for knowledge storage
            project_id: Optional project ID (None for global-only migration)
        """
        self._knowledge_base_dir = knowledge_base_dir
        self._project_id = project_id
        self._logger = logging.getLogger(__name__)

    def migrate_project(self) -> bool:
        """
        Migrate project-specific knowledge files to graph [REQ-21, REQ-23].

        Migrates:
        - architecture.md -> project graph
        - decisions.md -> project graph

        Returns:
            True if successful, False on error

        Note:
            [ERR-3] If graph already exists, checks for duplicate content and skips/warns.
        """
        if not self._project_id:
            self._logger.error("Cannot migrate project: no project_id specified")
            return False

        try:
            storage = GraphStorage(self._knowledge_base_dir)
            project_dir = self._knowledge_base_dir / self._project_id

            # Check if project directory exists
            if not project_dir.exists():
                self._logger.info(f"No project directory found at {project_dir}")
                return True  # Not an error, just nothing to migrate

            # Load or create graph
            graph_file = project_dir / "graph.json"
            if graph_file.exists():
                self._logger.info(f"Graph already exists at {graph_file}, skipping migration")
                return True  # [ERR-3] Already migrated

            graph = KnowledgeGraph()

            # Migrate architecture
            arch_file = project_dir / "architecture.md"
            if arch_file.exists():
                count = self._migrate_markdown_file(arch_file, KnowledgeCategory.ARCHITECTURE, graph)
                self._logger.info(f"Migrated {count} architecture entries")

            # Migrate decisions
            dec_file = project_dir / "decisions.md"
            if dec_file.exists():
                count = self._migrate_markdown_file(dec_file, KnowledgeCategory.DECISIONS, graph)
                self._logger.info(f"Migrated {count} decisions entries")

            # Save graph
            storage.save_project_graph(self._project_id, graph)
            self._logger.info(f"Successfully migrated project knowledge to {graph_file}")
            return True

        except Exception as e:
            self._logger.error(f"Failed to migrate project: {e}")
            return False

    def migrate_global(self) -> bool:
        """
        Migrate global lessons-learned.md to global graph [REQ-21, REQ-23].

        Returns:
            True if successful, False on error

        Note:
            [ERR-3] If graph already exists, checks for duplicate content and skips/warns.
        """
        try:
            storage = GraphStorage(self._knowledge_base_dir)

            # Check if global graph already exists
            graph_file = self._knowledge_base_dir / "global-graph.json"
            if graph_file.exists():
                self._logger.info(f"Global graph already exists at {graph_file}, skipping migration")
                return True  # [ERR-3] Already migrated

            graph = KnowledgeGraph()

            # Migrate lessons-learned
            lessons_file = self._knowledge_base_dir / "lessons-learned.md"
            if lessons_file.exists():
                count = self._migrate_markdown_file(lessons_file, KnowledgeCategory.LESSONS_LEARNED, graph)
                self._logger.info(f"Migrated {count} lessons-learned entries")

            # Save graph
            storage.save_global_graph(graph)
            self._logger.info(f"Successfully migrated global knowledge to {graph_file}")
            return True

        except Exception as e:
            self._logger.error(f"Failed to migrate global knowledge: {e}")
            return False

    def migrate_all(self) -> bool:
        """
        Migrate both project and global knowledge.

        Returns:
            True if both successful, False if either fails
        """
        project_success = True
        if self._project_id:
            project_success = self.migrate_project()

        global_success = self.migrate_global()

        return project_success and global_success

    def _migrate_markdown_file(
        self,
        markdown_path: Path,
        category: KnowledgeCategory,
        graph
    ) -> int:
        """
        Migrate a single markdown file to graph.

        Args:
            markdown_path: Path to markdown file
            category: Knowledge category
            graph: KnowledgeGraph to add entries to

        Returns:
            Number of entries migrated
        """
        try:
            markdown_content = markdown_path.read_text()

            # Parse markdown based on category
            if category == KnowledgeCategory.ARCHITECTURE:
                entries = MarkdownParser.parse_architecture_markdown(markdown_content)
            elif category == KnowledgeCategory.DECISIONS:
                entries = MarkdownParser.parse_decisions_markdown(markdown_content)
            elif category == KnowledgeCategory.LESSONS_LEARNED:
                entries = MarkdownParser.parse_lessons_markdown(markdown_content)
            else:
                return 0

            # First pass: Add all nodes to graph
            # Store relationships for second pass
            pending_relationships = []

            for entry in entries:
                # Parse relationships from content
                relationships = RelationshipParser.parse_relationships(entry.get("content", ""))
                clean_content = RelationshipParser.strip_relationships(entry.get("content", ""))

                # Create node ID
                node_id = NodeId(
                    category=category.value,
                    title=entry["title"],
                    date=entry["date"]
                )

                # Create knowledge node
                node = KnowledgeNode(
                    node_id=node_id,
                    title=entry["title"],
                    content=clean_content,
                    category=category.value,
                    date_added=entry["date"],
                    session_id=entry.get("session_id", "migrated"),
                    tag=entry.get("tag")
                )

                graph.add_node(node)

                # Store relationships for resolution after all nodes are added
                if relationships:
                    pending_relationships.append((node_id, relationships))

            # Second pass: Resolve and create relationship edges [REQ-18, REQ-19]
            for source_node_id, relationships in pending_relationships:
                for rel_type, target_title in relationships:
                    # Find target node by title (search all categories and dates)
                    target_node_id = self._find_node_by_title(graph, target_title)
                    if target_node_id:
                        graph.add_relationship(source_node_id, rel_type, target_node_id)
                    else:
                        self._logger.warning(
                            f"Relationship target not found: '{target_title}' "
                            f"(referenced by '{source_node_id.title}')"
                        )

            return len(entries)

        except Exception as e:
            self._logger.error(f"Failed to migrate {markdown_path}: {e}")
            return 0

    def _find_node_by_title(self, graph, title: str) -> Optional[NodeId]:
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

    def _check_for_duplicates(
        self,
        entries: List[Dict],
        existing_graph
    ) -> List[Dict]:
        """
        Filter out entries that already exist in graph [ERR-3].

        Args:
            entries: List of parsed entry dicts
            existing_graph: Existing KnowledgeGraph

        Returns:
            List of non-duplicate entries
        """
        non_duplicates = []
        for entry in entries:
            node_id = NodeId(
                category=entry.get("category", ""),
                title=entry["title"],
                date=entry["date"]
            )
            if existing_graph.get_node(node_id) is None:
                non_duplicates.append(entry)
        return non_duplicates

    def _backup_markdown_file(self, markdown_path: Path) -> bool:
        """
        Create backup of markdown file before migration.

        Creates: {filename}.backup.{timestamp}

        Args:
            markdown_path: Path to markdown file

        Returns:
            True if successful, False on error
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = markdown_path.parent / f"{markdown_path.name}.backup.{timestamp}"
            backup_path.write_text(markdown_path.read_text())
            return True
        except Exception as e:
            self._logger.error(f"Failed to backup {markdown_path}: {e}")
            return False


def migrate_knowledge_cli(
    knowledge_base_dir: Path,
    project_id: Optional[str] = None,
    global_only: bool = False
) -> int:
    """
    CLI entry point for knowledge migration [REQ-21, REQ-22].

    Args:
        knowledge_base_dir: Base directory for knowledge storage
        project_id: Project ID (required unless global_only=True)
        global_only: If True, only migrate global lessons-learned

    Returns:
        Exit code (0 = success, 1 = error)
    """
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    try:
        # Validate arguments
        if not knowledge_base_dir.exists():
            logger.error(f"Knowledge directory not found: {knowledge_base_dir}")
            return 1

        # Create migrator
        migrator = KnowledgeMigrator(knowledge_base_dir, project_id)

        # Perform migration
        if global_only:
            success = migrator.migrate_global()
        elif project_id:
            success = migrator.migrate_all()
        else:
            # No project_id and not global_only: try to migrate global only
            success = migrator.migrate_global()

        return 0 if success else 1

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return 1
