#!/usr/bin/env python3
"""
Unit tests for wp_graph.py - Graph storage for knowledge entries
"""

import sys
import tempfile
import pytest
import json
from pathlib import Path
from datetime import datetime

# Add hooks/lib to path
sys.path.insert(0, 'hooks/lib')
from wp_graph import (
    NodeId,
    RelationshipType,
    KnowledgeNode,
    KnowledgeGraph,
    GraphStorage,
    RelationshipParser
)
from wp_knowledge import KnowledgeCategory


class TestNodeId:
    """Tests for NodeId class - unique identifier for graph nodes."""

    def test_node_id_creation_with_valid_fields(self):
        # given
        node_id = NodeId(
            category="architecture",
            title="Pipeline Pattern",
            date="2026-03-09"
        )

        # when/then
        assert node_id.category == "architecture"
        assert node_id.title == "Pipeline Pattern"
        assert node_id.date == "2026-03-09"

    def test_node_id_to_dict_returns_dict(self):
        # given
        node_id = NodeId(
            category="decisions",
            title="Use REST API",
            date="2026-03-08"
        )

        # when
        result = node_id.to_dict()

        # then
        assert isinstance(result, dict)
        assert result["category"] == "decisions"
        assert result["title"] == "Use REST API"
        assert result["date"] == "2026-03-08"

    def test_node_id_from_dict_creates_instance(self):
        # given
        data = {
            "category": "lessons-learned",
            "title": "Avoid Magic Numbers",
            "date": "2026-03-07"
        }

        # when
        node_id = NodeId.from_dict(data)

        # then
        assert node_id.category == "lessons-learned"
        assert node_id.title == "Avoid Magic Numbers"
        assert node_id.date == "2026-03-07"

    def test_node_id_equality_with_same_values(self):
        # given
        node1 = NodeId("architecture", "Pattern A", "2026-03-09")
        node2 = NodeId("architecture", "Pattern A", "2026-03-09")

        # when/then
        assert node1 == node2

    def test_node_id_inequality_with_different_titles(self):
        # given
        node1 = NodeId("architecture", "Pattern A", "2026-03-09")
        node2 = NodeId("architecture", "Pattern B", "2026-03-09")

        # when/then
        assert node1 != node2

    def test_node_id_inequality_with_different_dates(self):
        # given - [EDGE-4] Duplicate entry titles handled by (type, title, date) tuple
        node1 = NodeId("decisions", "Use REST", "2026-03-09")
        node2 = NodeId("decisions", "Use REST", "2026-03-08")

        # when/then
        assert node1 != node2

    def test_node_id_hashable_for_use_as_dict_key(self):
        # given
        node_id = NodeId("architecture", "Service Mesh", "2026-03-09")
        test_dict = {node_id: "value"}

        # when
        result = test_dict[node_id]

        # then
        assert result == "value"


class TestRelationshipType:
    """Tests for RelationshipType enum."""

    def test_relationship_type_led_to_exists(self):
        # when/then - [REQ-2] Support relationship type led_to
        assert RelationshipType.LED_TO is not None

    def test_relationship_type_contradicts_exists(self):
        # when/then - [REQ-2] Support relationship type contradicts
        assert RelationshipType.CONTRADICTS is not None

    def test_relationship_type_supersedes_exists(self):
        # when/then - [REQ-2] Support relationship type supersedes
        assert RelationshipType.SUPERSEDES is not None

    def test_relationship_type_related_to_exists(self):
        # when/then - [REQ-2] Support relationship type related_to
        assert RelationshipType.RELATED_TO is not None

    def test_relationship_type_applies_to_exists(self):
        # when/then - [REQ-2] Support relationship type applies_to
        assert RelationshipType.APPLIES_TO is not None


class TestKnowledgeNode:
    """Tests for KnowledgeNode class - single knowledge entry with relationships."""

    def test_knowledge_node_creation_with_minimal_fields(self):
        # given
        node_id = NodeId("architecture", "Event-Driven", "2026-03-09")

        # when
        node = KnowledgeNode(
            node_id=node_id,
            title="Event-Driven",
            content="System uses events for communication.",
            category="architecture",
            date_added="2026-03-09",
            session_id="session-123"
        )

        # then
        assert node.title == "Event-Driven"
        assert node.content == "System uses events for communication."
        assert node.category == "architecture"
        assert node.session_id == "session-123"
        assert node.tag is None
        assert len(node.relationships) == 0

    def test_knowledge_node_creation_with_tag(self):
        # given
        node_id = NodeId("lessons-learned", "Use Context Managers", "2026-03-09")

        # when
        node = KnowledgeNode(
            node_id=node_id,
            title="Use Context Managers",
            content="Always use 'with' statements for file operations.",
            category="lessons-learned",
            date_added="2026-03-09",
            session_id="session-456",
            tag="Python"
        )

        # then
        assert node.tag == "Python"

    def test_knowledge_node_creation_with_relationships(self):
        # given - [REQ-19] Create graph edges when relationships are identified
        node_id = NodeId("decisions", "REST API", "2026-03-09")
        target_id = NodeId("architecture", "API Gateway", "2026-03-08")
        relationships = [(RelationshipType.LED_TO, target_id)]

        # when
        node = KnowledgeNode(
            node_id=node_id,
            title="REST API",
            content="Chose REST for simplicity.",
            category="decisions",
            date_added="2026-03-09",
            session_id="session-789",
            relationships=relationships
        )

        # then
        assert len(node.relationships) == 1
        assert node.relationships[0][0] == RelationshipType.LED_TO
        assert node.relationships[0][1] == target_id

    def test_knowledge_node_to_dict_serializes_all_fields(self):
        # given
        node_id = NodeId("architecture", "Microservices", "2026-03-09")
        node = KnowledgeNode(
            node_id=node_id,
            title="Microservices",
            content="System split into services.",
            category="architecture",
            date_added="2026-03-09",
            session_id="session-101"
        )

        # when
        result = node.to_dict()

        # then
        assert result["title"] == "Microservices"
        assert result["content"] == "System split into services."
        assert result["category"] == "architecture"
        assert result["session_id"] == "session-101"
        assert "node_id" in result

    def test_knowledge_node_to_dict_includes_relationships(self):
        # given
        node_id = NodeId("decisions", "Use GraphQL", "2026-03-09")
        target_id = NodeId("architecture", "API Design", "2026-03-08")
        node = KnowledgeNode(
            node_id=node_id,
            title="Use GraphQL",
            content="Flexible querying needed.",
            category="decisions",
            date_added="2026-03-09",
            session_id="session-202",
            relationships=[(RelationshipType.RELATED_TO, target_id)]
        )

        # when
        result = node.to_dict()

        # then
        assert "relationships" in result
        assert len(result["relationships"]) == 1

    def test_knowledge_node_from_dict_recreates_instance(self):
        # given
        data = {
            "node_id": {"category": "architecture", "title": "CQRS", "date": "2026-03-09"},
            "title": "CQRS",
            "content": "Separate read and write models.",
            "category": "architecture",
            "date_added": "2026-03-09",
            "session_id": "session-303",
            "tag": None,
            "relationships": []
        }

        # when
        node = KnowledgeNode.from_dict(data)

        # then
        assert node.title == "CQRS"
        assert node.content == "Separate read and write models."
        assert node.category == "architecture"


class TestKnowledgeGraph:
    """Tests for KnowledgeGraph class - in-memory graph structure."""

    def test_knowledge_graph_creation_starts_empty(self):
        # when
        graph = KnowledgeGraph()

        # then
        assert len(graph.nodes) == 0

    def test_add_node_adds_to_graph(self):
        # given - [REQ-1] Store all knowledge entries as nodes
        graph = KnowledgeGraph()
        node_id = NodeId("architecture", "DDD", "2026-03-09")
        node = KnowledgeNode(
            node_id=node_id,
            title="DDD",
            content="Domain-Driven Design principles.",
            category="architecture",
            date_added="2026-03-09",
            session_id="session-404"
        )

        # when
        graph.add_node(node)

        # then
        assert len(graph.nodes) == 1
        assert node_id in graph.nodes

    def test_add_node_multiple_nodes_accumulate(self):
        # given
        graph = KnowledgeGraph()
        node1_id = NodeId("architecture", "Event Sourcing", "2026-03-09")
        node2_id = NodeId("decisions", "Use PostgreSQL", "2026-03-09")
        node1 = KnowledgeNode(node1_id, "Event Sourcing", "Content 1", "architecture", "2026-03-09", "s1")
        node2 = KnowledgeNode(node2_id, "Use PostgreSQL", "Content 2", "decisions", "2026-03-09", "s1")

        # when
        graph.add_node(node1)
        graph.add_node(node2)

        # then
        assert len(graph.nodes) == 2

    def test_add_node_replaces_existing_node_with_same_id(self):
        # given
        graph = KnowledgeGraph()
        node_id = NodeId("architecture", "Saga Pattern", "2026-03-09")
        node1 = KnowledgeNode(node_id, "Saga Pattern", "Original content", "architecture", "2026-03-09", "s1")
        node2 = KnowledgeNode(node_id, "Saga Pattern", "Updated content", "architecture", "2026-03-09", "s2")

        # when
        graph.add_node(node1)
        graph.add_node(node2)

        # then
        assert len(graph.nodes) == 1
        assert graph.nodes[node_id].content == "Updated content"

    def test_get_node_returns_node_when_exists(self):
        # given
        graph = KnowledgeGraph()
        node_id = NodeId("decisions", "Async Pattern", "2026-03-09")
        node = KnowledgeNode(node_id, "Async Pattern", "Use async/await", "decisions", "2026-03-09", "s1")
        graph.add_node(node)

        # when
        result = graph.get_node(node_id)

        # then
        assert result is not None
        assert result.title == "Async Pattern"

    def test_get_node_returns_none_when_not_exists(self):
        # given
        graph = KnowledgeGraph()
        node_id = NodeId("architecture", "Nonexistent", "2026-03-09")

        # when
        result = graph.get_node(node_id)

        # then
        assert result is None

    def test_get_nodes_by_category_returns_matching_nodes(self):
        # given - [REQ-10] Always load complete architecture entries
        graph = KnowledgeGraph()
        arch1_id = NodeId("architecture", "Pattern A", "2026-03-09")
        arch2_id = NodeId("architecture", "Pattern B", "2026-03-09")
        dec_id = NodeId("decisions", "Decision C", "2026-03-09")

        graph.add_node(KnowledgeNode(arch1_id, "Pattern A", "Arch 1", "architecture", "2026-03-09", "s1"))
        graph.add_node(KnowledgeNode(arch2_id, "Pattern B", "Arch 2", "architecture", "2026-03-09", "s1"))
        graph.add_node(KnowledgeNode(dec_id, "Decision C", "Dec 1", "decisions", "2026-03-09", "s1"))

        # when
        result = graph.get_nodes_by_category(KnowledgeCategory.ARCHITECTURE)

        # then
        assert len(result) == 2
        titles = [node.title for node in result]
        assert "Pattern A" in titles
        assert "Pattern B" in titles

    def test_get_nodes_by_category_returns_empty_when_none_match(self):
        # given
        graph = KnowledgeGraph()

        # when
        result = graph.get_nodes_by_category(KnowledgeCategory.DECISIONS)

        # then
        assert len(result) == 0

    def test_add_relationship_creates_edge_between_nodes(self):
        # given - [REQ-19] Create graph edges when relationships are identified
        graph = KnowledgeGraph()
        source_id = NodeId("decisions", "Use Redis", "2026-03-09")
        target_id = NodeId("architecture", "Caching Layer", "2026-03-08")

        source_node = KnowledgeNode(source_id, "Use Redis", "Fast cache", "decisions", "2026-03-09", "s1")
        target_node = KnowledgeNode(target_id, "Caching Layer", "Cache design", "architecture", "2026-03-08", "s1")

        graph.add_node(source_node)
        graph.add_node(target_node)

        # when
        result = graph.add_relationship(source_id, RelationshipType.LED_TO, target_id)

        # then
        assert result is True
        node = graph.get_node(source_id)
        assert len(node.relationships) == 1
        assert node.relationships[0] == (RelationshipType.LED_TO, target_id)

    def test_add_relationship_returns_false_when_source_not_found(self):
        # given - [EDGE-2] Relationship target not found: log warning but continue
        graph = KnowledgeGraph()
        source_id = NodeId("decisions", "Nonexistent Source", "2026-03-09")
        target_id = NodeId("architecture", "Target", "2026-03-09")

        graph.add_node(KnowledgeNode(target_id, "Target", "Content", "architecture", "2026-03-09", "s1"))

        # when
        result = graph.add_relationship(source_id, RelationshipType.RELATED_TO, target_id)

        # then
        assert result is False

    def test_add_relationship_returns_false_when_target_not_found(self):
        # given - [EDGE-2] Relationship target not found scenario
        graph = KnowledgeGraph()
        source_id = NodeId("decisions", "Source", "2026-03-09")
        target_id = NodeId("architecture", "Nonexistent Target", "2026-03-09")

        graph.add_node(KnowledgeNode(source_id, "Source", "Content", "decisions", "2026-03-09", "s1"))

        # when
        result = graph.add_relationship(source_id, RelationshipType.SUPERSEDES, target_id)

        # then
        assert result is False

    def test_get_related_nodes_returns_connected_nodes(self):
        # given
        graph = KnowledgeGraph()
        node1_id = NodeId("architecture", "API Gateway", "2026-03-09")
        node2_id = NodeId("architecture", "Load Balancer", "2026-03-09")
        node3_id = NodeId("decisions", "Use Nginx", "2026-03-09")

        node1 = KnowledgeNode(node1_id, "API Gateway", "Gateway", "architecture", "2026-03-09", "s1")
        node2 = KnowledgeNode(node2_id, "Load Balancer", "LB", "architecture", "2026-03-09", "s1")
        node3 = KnowledgeNode(node3_id, "Use Nginx", "Nginx", "decisions", "2026-03-09", "s1")

        graph.add_node(node1)
        graph.add_node(node2)
        graph.add_node(node3)

        graph.add_relationship(node1_id, RelationshipType.RELATED_TO, node2_id)
        graph.add_relationship(node1_id, RelationshipType.LED_TO, node3_id)

        # when
        result = graph.get_related_nodes(node1_id)

        # then
        assert len(result) == 2
        titles = [node.title for node in result]
        assert "Load Balancer" in titles
        assert "Use Nginx" in titles

    def test_get_related_nodes_filters_by_relationship_type(self):
        # given
        graph = KnowledgeGraph()
        node1_id = NodeId("decisions", "Use MongoDB", "2026-03-09")
        node2_id = NodeId("architecture", "NoSQL Storage", "2026-03-09")
        node3_id = NodeId("decisions", "Use Redis", "2026-03-09")

        graph.add_node(KnowledgeNode(node1_id, "Use MongoDB", "Doc DB", "decisions", "2026-03-09", "s1"))
        graph.add_node(KnowledgeNode(node2_id, "NoSQL Storage", "Storage", "architecture", "2026-03-09", "s1"))
        graph.add_node(KnowledgeNode(node3_id, "Use Redis", "Cache", "decisions", "2026-03-09", "s1"))

        graph.add_relationship(node1_id, RelationshipType.LED_TO, node2_id)
        graph.add_relationship(node1_id, RelationshipType.CONTRADICTS, node3_id)

        # when
        result = graph.get_related_nodes(node1_id, RelationshipType.LED_TO)

        # then
        assert len(result) == 1
        assert result[0].title == "NoSQL Storage"

    def test_get_related_nodes_returns_empty_when_no_relationships(self):
        # given - [REQ-20] Continue supporting entries without relationships
        graph = KnowledgeGraph()
        node_id = NodeId("architecture", "Isolated Pattern", "2026-03-09")
        graph.add_node(KnowledgeNode(node_id, "Isolated Pattern", "No edges", "architecture", "2026-03-09", "s1"))

        # when
        result = graph.get_related_nodes(node_id)

        # then
        assert len(result) == 0


class TestGraphStorage:
    """Tests for GraphStorage class - persistence layer for graphs."""

    def test_graph_storage_initialization(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)

            # when
            storage = GraphStorage(knowledge_dir)

            # then
            assert storage is not None

    def test_save_project_graph_creates_json_file(self):
        # given - [REQ-4] Persist graph structure locally
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            storage = GraphStorage(knowledge_dir)

            graph = KnowledgeGraph()
            node_id = NodeId("architecture", "Service Mesh", "2026-03-09")
            graph.add_node(KnowledgeNode(node_id, "Service Mesh", "Mesh pattern", "architecture", "2026-03-09", "s1"))

            # when
            result = storage.save_project_graph("test-project", graph)

            # then
            assert result is True
            graph_file = knowledge_dir / "test-project" / "graph.json"
            assert graph_file.exists()

    def test_save_project_graph_persists_nodes(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            storage = GraphStorage(knowledge_dir)

            graph = KnowledgeGraph()
            node_id = NodeId("decisions", "Use Kafka", "2026-03-09")
            graph.add_node(KnowledgeNode(node_id, "Use Kafka", "Event streaming", "decisions", "2026-03-09", "s1"))

            # when
            storage.save_project_graph("project-a", graph)

            # then
            graph_file = knowledge_dir / "project-a" / "graph.json"
            data = json.loads(graph_file.read_text())
            assert "nodes" in data
            assert len(data["nodes"]) == 1

    def test_load_project_graph_returns_empty_when_no_file(self):
        # given - [REQ-4] Persist graph structure locally without external dependencies
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            storage = GraphStorage(knowledge_dir)

            # when
            graph = storage.load_project_graph("nonexistent-project")

            # then
            assert isinstance(graph, KnowledgeGraph)
            assert len(graph.nodes) == 0

    def test_load_project_graph_reconstructs_graph_from_json(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            storage = GraphStorage(knowledge_dir)

            original_graph = KnowledgeGraph()
            node_id = NodeId("architecture", "CQRS", "2026-03-09")
            original_graph.add_node(KnowledgeNode(node_id, "CQRS", "Command Query", "architecture", "2026-03-09", "s1"))
            storage.save_project_graph("project-b", original_graph)

            # when
            loaded_graph = storage.load_project_graph("project-b")

            # then
            assert len(loaded_graph.nodes) == 1
            node = loaded_graph.get_node(node_id)
            assert node is not None
            assert node.title == "CQRS"

    def test_load_project_graph_reconstructs_relationships(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            storage = GraphStorage(knowledge_dir)

            graph = KnowledgeGraph()
            node1_id = NodeId("decisions", "Use GraphQL", "2026-03-09")
            node2_id = NodeId("architecture", "API Design", "2026-03-09")

            graph.add_node(KnowledgeNode(node1_id, "Use GraphQL", "Flexible API", "decisions", "2026-03-09", "s1"))
            graph.add_node(KnowledgeNode(node2_id, "API Design", "API patterns", "architecture", "2026-03-09", "s1"))
            graph.add_relationship(node1_id, RelationshipType.LED_TO, node2_id)

            storage.save_project_graph("project-c", graph)

            # when
            loaded_graph = storage.load_project_graph("project-c")

            # then
            node = loaded_graph.get_node(node1_id)
            assert len(node.relationships) == 1
            assert node.relationships[0][0] == RelationshipType.LED_TO

    def test_save_global_graph_creates_file_in_root(self):
        # given - Lessons-learned are global [REQ-11]
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            storage = GraphStorage(knowledge_dir)

            graph = KnowledgeGraph()
            node_id = NodeId("lessons-learned", "Avoid Mutable Defaults", "2026-03-09")
            graph.add_node(KnowledgeNode(node_id, "Avoid Mutable Defaults", "Use None", "lessons-learned", "2026-03-09", "s1", tag="Python"))

            # when
            result = storage.save_global_graph(graph)

            # then
            assert result is True
            graph_file = knowledge_dir / "global-graph.json"
            assert graph_file.exists()

    def test_load_global_graph_returns_empty_when_no_file(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            storage = GraphStorage(knowledge_dir)

            # when
            graph = storage.load_global_graph()

            # then
            assert isinstance(graph, KnowledgeGraph)
            assert len(graph.nodes) == 0

    def test_load_global_graph_reconstructs_lessons_learned(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            storage = GraphStorage(knowledge_dir)

            original_graph = KnowledgeGraph()
            node_id = NodeId("lessons-learned", "Use Context Managers", "2026-03-09")
            original_graph.add_node(
                KnowledgeNode(node_id, "Use Context Managers", "Always use with", "lessons-learned", "2026-03-09", "s1", tag="Python")
            )
            storage.save_global_graph(original_graph)

            # when
            loaded_graph = storage.load_global_graph()

            # then
            assert len(loaded_graph.nodes) == 1
            node = loaded_graph.get_node(node_id)
            assert node.tag == "Python"

    def test_load_project_graph_handles_corrupted_json(self):
        # given - [ERR-2] Graph corruption: attempt to rebuild from markdown views
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            project_dir = knowledge_dir / "corrupted-project"
            project_dir.mkdir(parents=True)

            graph_file = project_dir / "graph.json"
            graph_file.write_text("{ invalid json }")

            storage = GraphStorage(knowledge_dir)

            # when
            graph = storage.load_project_graph("corrupted-project")

            # then - Should return empty graph gracefully
            assert isinstance(graph, KnowledgeGraph)
            assert len(graph.nodes) == 0

    def test_save_project_graph_creates_directory_if_not_exists(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            storage = GraphStorage(knowledge_dir)

            graph = KnowledgeGraph()
            node_id = NodeId("architecture", "Hexagonal", "2026-03-09")
            graph.add_node(KnowledgeNode(node_id, "Hexagonal", "Ports and adapters", "architecture", "2026-03-09", "s1"))

            # when
            result = storage.save_project_graph("new-project", graph)

            # then
            assert result is True
            project_dir = knowledge_dir / "new-project"
            assert project_dir.exists()
            assert (project_dir / "graph.json").exists()


class TestRelationshipParser:
    """Tests for RelationshipParser - parses relationship markers from Claude's output."""

    def test_parse_relationships_with_led_to_marker(self):
        # given - [REQ-3] Parse relationships using inline bracket notation
        content = "This decision [led_to: \"API Gateway Pattern\"] improved scalability."

        # when
        result = RelationshipParser.parse_relationships(content)

        # then
        assert len(result) == 1
        assert result[0] == (RelationshipType.LED_TO, "API Gateway Pattern")

    def test_parse_relationships_with_contradicts_marker(self):
        # given
        content = "This approach [contradicts: \"Monolithic Architecture\"] by splitting services."

        # when
        result = RelationshipParser.parse_relationships(content)

        # then
        assert len(result) == 1
        assert result[0] == (RelationshipType.CONTRADICTS, "Monolithic Architecture")

    def test_parse_relationships_with_supersedes_marker(self):
        # given
        content = "New design [supersedes: \"Old REST API Design\"] with GraphQL."

        # when
        result = RelationshipParser.parse_relationships(content)

        # then
        assert len(result) == 1
        assert result[0] == (RelationshipType.SUPERSEDES, "Old REST API Design")

    def test_parse_relationships_with_related_to_marker(self):
        # given
        content = "This pattern [related_to: \"Microservices Architecture\"] enables scaling."

        # when
        result = RelationshipParser.parse_relationships(content)

        # then
        assert len(result) == 1
        assert result[0] == (RelationshipType.RELATED_TO, "Microservices Architecture")

    def test_parse_relationships_with_applies_to_marker(self):
        # given
        content = "This lesson [applies_to: \"Pipeline Pattern\"] for better composability."

        # when
        result = RelationshipParser.parse_relationships(content)

        # then
        assert len(result) == 1
        assert result[0] == (RelationshipType.APPLIES_TO, "Pipeline Pattern")

    def test_parse_relationships_with_multiple_markers(self):
        # given
        content = "This [led_to: \"Pattern A\"] and [related_to: \"Pattern B\"] in architecture."

        # when
        result = RelationshipParser.parse_relationships(content)

        # then
        assert len(result) == 2
        relationship_types = [rel[0] for rel in result]
        assert RelationshipType.LED_TO in relationship_types
        assert RelationshipType.RELATED_TO in relationship_types

    def test_parse_relationships_returns_empty_when_no_markers(self):
        # given - [REQ-20] Continue supporting entries without relationships
        content = "This is plain content with no relationship markers."

        # when
        result = RelationshipParser.parse_relationships(content)

        # then
        assert len(result) == 0

    def test_parse_relationships_handles_malformed_marker(self):
        # given - [EDGE-3] Malformed relationship syntax: treat as no relationships, log warning
        content = "Malformed [led_to: Missing closing quote] marker."

        # when
        result = RelationshipParser.parse_relationships(content)

        # then - Should return empty list and not crash
        assert len(result) == 0

    def test_parse_relationships_handles_empty_content(self):
        # given
        content = ""

        # when
        result = RelationshipParser.parse_relationships(content)

        # then
        assert len(result) == 0

    def test_strip_relationships_removes_markers(self):
        # given - [REQ-18] Parse relationship markers from extraction response
        content = "This decision [led_to: \"Pattern A\"] improved performance."

        # when
        result = RelationshipParser.strip_relationships(content)

        # then
        assert "[led_to:" not in result
        assert "Pattern A" not in result
        assert "This decision" in result
        assert "improved performance" in result

    def test_strip_relationships_removes_all_markers(self):
        # given
        content = "Content [led_to: \"A\"] and [contradicts: \"B\"] and [supersedes: \"C\"]."

        # when
        result = RelationshipParser.strip_relationships(content)

        # then
        assert "[led_to:" not in result
        assert "[contradicts:" not in result
        assert "[supersedes:" not in result
        assert "Content" in result

    def test_strip_relationships_preserves_content_without_markers(self):
        # given
        content = "Plain content without any relationship markers."

        # when
        result = RelationshipParser.strip_relationships(content)

        # then
        assert result == content

    def test_parse_relationships_case_sensitive_for_marker_names(self):
        # given
        content = "Invalid [LED_TO: \"Pattern A\"] with uppercase."

        # when
        result = RelationshipParser.parse_relationships(content)

        # then - Should not match uppercase variant
        assert len(result) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
