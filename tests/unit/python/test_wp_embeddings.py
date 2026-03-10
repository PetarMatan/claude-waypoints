#!/usr/bin/env python3
"""
Unit tests for wp_embeddings.py - Local RAG using sentence-transformers
"""

import sys
import tempfile
import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add hooks/lib to path
sys.path.insert(0, 'hooks/lib')
from wp_embeddings import (
    EmbeddingEntry,
    EmbeddingsModel,
    EmbeddingsIndex,
    EmbeddingsStorage,
    RAGService
)
from wp_graph import NodeId, KnowledgeNode


class TestEmbeddingEntry:
    """Tests for EmbeddingEntry dataclass."""

    def test_embedding_entry_creation(self):
        # given
        node_id = NodeId("lessons-learned", "Use Type Hints", "2026-03-09")
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

        # when
        entry = EmbeddingEntry(
            node_id=node_id,
            title="Use Type Hints",
            content="Always add type hints to functions for better IDE support.",
            embedding=embedding
        )

        # then
        assert entry.node_id == node_id
        assert entry.title == "Use Type Hints"
        assert entry.embedding == embedding
        assert len(entry.embedding) == 5

    def test_embedding_entry_to_dict_serializes(self):
        # given
        node_id = NodeId("lessons-learned", "Avoid Global State", "2026-03-09")
        entry = EmbeddingEntry(
            node_id=node_id,
            title="Avoid Global State",
            content="Global variables make testing difficult.",
            embedding=[0.5, 0.6, 0.7]
        )

        # when
        result = entry.to_dict()

        # then
        assert isinstance(result, dict)
        assert "node_id" in result
        assert "title" in result
        assert "content" in result
        assert "embedding" in result
        assert result["title"] == "Avoid Global State"

    def test_embedding_entry_from_dict_deserializes(self):
        # given
        data = {
            "node_id": {"category": "lessons-learned", "title": "DRY Principle", "date": "2026-03-09"},
            "title": "DRY Principle",
            "content": "Don't Repeat Yourself in code.",
            "embedding": [0.8, 0.9, 1.0]
        }

        # when
        entry = EmbeddingEntry.from_dict(data)

        # then
        assert entry.title == "DRY Principle"
        assert entry.content == "Don't Repeat Yourself in code."
        assert len(entry.embedding) == 3


class TestEmbeddingsModel:
    """Tests for EmbeddingsModel - wrapper around sentence-transformers."""

    def test_embeddings_model_has_correct_model_name(self):
        # when/then - [REQ-5] Use local embeddings model (sentence-transformers)
        assert EmbeddingsModel.MODEL_NAME == "sentence-transformers/all-MiniLM-L6-v2"

    def test_load_model_initializes_model(self):
        # given
        model = EmbeddingsModel()
        mock_sentence_transformer = MagicMock()

        # when
        with patch('wp_embeddings.SentenceTransformer', return_value=mock_sentence_transformer):
            result = model.load_model()

        # then
        assert result is True

    def test_load_model_returns_false_on_download_failure(self):
        # given - [ERR-1] Embedding model download failure: fail gracefully with clear error
        model = EmbeddingsModel()

        # when
        with patch('wp_embeddings.SentenceTransformer', side_effect=Exception("Network error")):
            result = model.load_model()

        # then
        assert result is False

    def test_encode_returns_embedding_vector(self):
        # given - [REQ-6] Generate embeddings for all lessons-learned entries
        model = EmbeddingsModel()
        mock_model = MagicMock()
        mock_model.encode.return_value = [0.1, 0.2, 0.3]
        model.model = mock_model

        # when
        result = model.encode("Test text")

        # then
        assert isinstance(result, list)
        assert len(result) == 3
        mock_model.encode.assert_called_once_with("Test text")

    def test_encode_handles_empty_text(self):
        # given
        model = EmbeddingsModel()
        mock_model = MagicMock()
        mock_model.encode.return_value = [0.0, 0.0, 0.0]
        model.model = mock_model

        # when
        result = model.encode("")

        # then
        assert isinstance(result, list)

    def test_encode_batch_processes_multiple_texts(self):
        # given
        model = EmbeddingsModel()
        mock_model = MagicMock()
        mock_model.encode.return_value = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        model.model = mock_model

        texts = ["Text 1", "Text 2", "Text 3"]

        # when
        result = model.encode_batch(texts)

        # then
        assert len(result) == 3
        assert len(result[0]) == 2
        mock_model.encode.assert_called_once()

    def test_encode_batch_returns_empty_for_empty_input(self):
        # given
        model = EmbeddingsModel()
        mock_model = MagicMock()
        mock_model.encode.return_value = []
        model.model = mock_model

        # when
        result = model.encode_batch([])

        # then
        assert len(result) == 0

    def test_compute_similarity_returns_score_between_zero_and_one(self):
        # given
        model = EmbeddingsModel()
        embedding1 = [0.5, 0.5, 0.0]
        embedding2 = [0.5, 0.5, 0.0]

        # when
        result = model.compute_similarity(embedding1, embedding2)

        # then
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0

    def test_compute_similarity_identical_embeddings_returns_high_score(self):
        # given
        model = EmbeddingsModel()
        embedding = [0.7, 0.3, 0.1]

        # when
        result = model.compute_similarity(embedding, embedding)

        # then
        assert result > 0.99  # Should be very close to 1.0

    def test_compute_similarity_orthogonal_embeddings_returns_low_score(self):
        # given
        model = EmbeddingsModel()
        embedding1 = [1.0, 0.0, 0.0]
        embedding2 = [0.0, 1.0, 0.0]

        # when
        result = model.compute_similarity(embedding1, embedding2)

        # then
        assert result < 0.1  # Should be close to 0.0


class TestEmbeddingsIndex:
    """Tests for EmbeddingsIndex - semantic search over lessons-learned."""

    def test_embeddings_index_initialization(self):
        # given
        mock_model = MagicMock(spec=EmbeddingsModel)

        # when
        index = EmbeddingsIndex(mock_model)

        # then
        assert index is not None

    def test_index_lessons_generates_embeddings(self):
        # given - [REQ-6] Generate embeddings for all lessons-learned entries
        mock_model = MagicMock(spec=EmbeddingsModel)
        mock_model.encode_batch.return_value = [[0.1, 0.2], [0.3, 0.4]]

        index = EmbeddingsIndex(mock_model)

        node1_id = NodeId("lessons-learned", "Lesson 1", "2026-03-09")
        node2_id = NodeId("lessons-learned", "Lesson 2", "2026-03-09")
        lessons = [
            KnowledgeNode(node1_id, "Lesson 1", "Content 1", "lessons-learned", "2026-03-09", "s1", tag="Python"),
            KnowledgeNode(node2_id, "Lesson 2", "Content 2", "lessons-learned", "2026-03-09", "s1", tag="Git")
        ]

        # when
        index.index_lessons(lessons)

        # then
        mock_model.encode_batch.assert_called_once()
        assert index.get_entry_count() == 2

    def test_index_lessons_handles_empty_list(self):
        # given
        mock_model = MagicMock(spec=EmbeddingsModel)
        index = EmbeddingsIndex(mock_model)

        # when
        index.index_lessons([])

        # then
        assert index.get_entry_count() == 0

    def test_search_returns_relevant_lessons(self):
        # given - [REQ-8] Retrieve only semantically relevant lessons-learned entries
        mock_model = MagicMock(spec=EmbeddingsModel)
        mock_model.encode.return_value = [0.5, 0.5]
        mock_model.compute_similarity.side_effect = [0.8, 0.3]  # First lesson is more relevant

        index = EmbeddingsIndex(mock_model)

        node1_id = NodeId("lessons-learned", "Relevant Lesson", "2026-03-09")
        node2_id = NodeId("lessons-learned", "Irrelevant Lesson", "2026-03-09")
        lessons = [
            KnowledgeNode(node1_id, "Relevant Lesson", "Highly relevant content", "lessons-learned", "2026-03-09", "s1", tag="Python"),
            KnowledgeNode(node2_id, "Irrelevant Lesson", "Unrelated content", "lessons-learned", "2026-03-09", "s1", tag="Go")
        ]

        mock_model.encode_batch.return_value = [[0.5, 0.5], [0.1, 0.1]]
        index.index_lessons(lessons)

        # when
        results = index.search("relevant query", top_k=10, min_similarity=0.3)

        # then
        assert len(results) == 2  # Both above threshold
        assert results[0][0].title == "Relevant Lesson"  # Most relevant first
        assert results[0][1] == 0.8  # Similarity score

    def test_search_filters_by_min_similarity_threshold(self):
        # given
        mock_model = MagicMock(spec=EmbeddingsModel)
        mock_model.encode.return_value = [0.5, 0.5]
        mock_model.compute_similarity.side_effect = [0.8, 0.2]  # Second below threshold

        index = EmbeddingsIndex(mock_model)

        node1_id = NodeId("lessons-learned", "High Match", "2026-03-09")
        node2_id = NodeId("lessons-learned", "Low Match", "2026-03-09")
        lessons = [
            KnowledgeNode(node1_id, "High Match", "Relevant", "lessons-learned", "2026-03-09", "s1", tag="Python"),
            KnowledgeNode(node2_id, "Low Match", "Not relevant", "lessons-learned", "2026-03-09", "s1", tag="Go")
        ]

        mock_model.encode_batch.return_value = [[0.5, 0.5], [0.1, 0.1]]
        index.index_lessons(lessons)

        # when
        results = index.search("query", top_k=10, min_similarity=0.3)

        # then
        assert len(results) == 1  # Only one above threshold
        assert results[0][0].title == "High Match"

    def test_search_respects_top_k_limit(self):
        # given
        mock_model = MagicMock(spec=EmbeddingsModel)
        mock_model.encode.return_value = [0.5, 0.5]
        mock_model.compute_similarity.side_effect = [0.9, 0.8, 0.7, 0.6, 0.5]

        index = EmbeddingsIndex(mock_model)

        lessons = []
        for i in range(5):
            node_id = NodeId("lessons-learned", f"Lesson {i}", "2026-03-09")
            lessons.append(KnowledgeNode(node_id, f"Lesson {i}", f"Content {i}", "lessons-learned", "2026-03-09", "s1", tag="Python"))

        mock_model.encode_batch.return_value = [[0.5, 0.5]] * 5
        index.index_lessons(lessons)

        # when
        results = index.search("query", top_k=3, min_similarity=0.3)

        # then
        assert len(results) == 3  # Limited by top_k

    def test_search_returns_empty_when_no_matches(self):
        # given - [EDGE-1] Zero RAG results: load nothing
        mock_model = MagicMock(spec=EmbeddingsModel)
        mock_model.encode.return_value = [0.5, 0.5]
        mock_model.compute_similarity.side_effect = [0.1, 0.05]  # All below threshold

        index = EmbeddingsIndex(mock_model)

        node1_id = NodeId("lessons-learned", "Lesson 1", "2026-03-09")
        node2_id = NodeId("lessons-learned", "Lesson 2", "2026-03-09")
        lessons = [
            KnowledgeNode(node1_id, "Lesson 1", "Content 1", "lessons-learned", "2026-03-09", "s1", tag="Python"),
            KnowledgeNode(node2_id, "Lesson 2", "Content 2", "lessons-learned", "2026-03-09", "s1", tag="Go")
        ]

        mock_model.encode_batch.return_value = [[0.5, 0.5], [0.1, 0.1]]
        index.index_lessons(lessons)

        # when
        results = index.search("unrelated query", top_k=10, min_similarity=0.3)

        # then
        assert len(results) == 0

    def test_search_returns_empty_when_index_empty(self):
        # given
        mock_model = MagicMock(spec=EmbeddingsModel)
        index = EmbeddingsIndex(mock_model)

        # when
        results = index.search("any query", top_k=10, min_similarity=0.3)

        # then
        assert len(results) == 0

    def test_get_entry_count_returns_zero_initially(self):
        # given
        mock_model = MagicMock(spec=EmbeddingsModel)
        index = EmbeddingsIndex(mock_model)

        # when
        count = index.get_entry_count()

        # then
        assert count == 0

    def test_get_entry_count_returns_indexed_count(self):
        # given - [REQ-9] Log the count of lessons loaded
        mock_model = MagicMock(spec=EmbeddingsModel)
        mock_model.encode_batch.return_value = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]

        index = EmbeddingsIndex(mock_model)

        lessons = []
        for i in range(3):
            node_id = NodeId("lessons-learned", f"Lesson {i}", "2026-03-09")
            lessons.append(KnowledgeNode(node_id, f"Lesson {i}", f"Content {i}", "lessons-learned", "2026-03-09", "s1", tag="Python"))

        index.index_lessons(lessons)

        # when
        count = index.get_entry_count()

        # then
        assert count == 3


class TestEmbeddingsStorage:
    """Tests for EmbeddingsStorage - persists embeddings to disk."""

    def test_embeddings_storage_initialization(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)

            # when
            storage = EmbeddingsStorage(knowledge_dir)

            # then
            assert storage is not None

    def test_save_embeddings_creates_file(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            storage = EmbeddingsStorage(knowledge_dir)

            node_id = NodeId("lessons-learned", "Lesson A", "2026-03-09")
            entries = [
                EmbeddingEntry(node_id, "Lesson A", "Content", [0.1, 0.2, 0.3])
            ]

            # when
            result = storage.save_embeddings(entries)

            # then
            assert result is True
            embeddings_file = knowledge_dir / "embeddings.json"
            assert embeddings_file.exists()

    def test_save_embeddings_persists_data(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            storage = EmbeddingsStorage(knowledge_dir)

            node_id = NodeId("lessons-learned", "Lesson B", "2026-03-09")
            entries = [
                EmbeddingEntry(node_id, "Lesson B", "Content B", [0.4, 0.5, 0.6])
            ]

            # when
            storage.save_embeddings(entries)

            # then
            embeddings_file = knowledge_dir / "embeddings.json"
            data = json.loads(embeddings_file.read_text())
            assert len(data) == 1
            assert data[0]["title"] == "Lesson B"

    def test_load_embeddings_returns_empty_when_no_file(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            storage = EmbeddingsStorage(knowledge_dir)

            # when
            entries = storage.load_embeddings()

            # then
            assert isinstance(entries, list)
            assert len(entries) == 0

    def test_load_embeddings_reconstructs_entries(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            storage = EmbeddingsStorage(knowledge_dir)

            node_id = NodeId("lessons-learned", "Lesson C", "2026-03-09")
            original_entries = [
                EmbeddingEntry(node_id, "Lesson C", "Content C", [0.7, 0.8, 0.9])
            ]
            storage.save_embeddings(original_entries)

            # when
            loaded_entries = storage.load_embeddings()

            # then
            assert len(loaded_entries) == 1
            assert loaded_entries[0].title == "Lesson C"
            assert loaded_entries[0].embedding == [0.7, 0.8, 0.9]

    def test_load_embeddings_handles_corrupted_file(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            embeddings_file = knowledge_dir / "embeddings.json"
            embeddings_file.write_text("{ invalid json }")

            storage = EmbeddingsStorage(knowledge_dir)

            # when
            entries = storage.load_embeddings()

            # then - Should return empty list gracefully
            assert isinstance(entries, list)
            assert len(entries) == 0

    def test_save_embeddings_overwrites_existing_file(self):
        # given
        with tempfile.TemporaryDirectory() as tmpdir:
            knowledge_dir = Path(tmpdir)
            storage = EmbeddingsStorage(knowledge_dir)

            node1_id = NodeId("lessons-learned", "Old Lesson", "2026-03-08")
            node2_id = NodeId("lessons-learned", "New Lesson", "2026-03-09")

            old_entries = [EmbeddingEntry(node1_id, "Old Lesson", "Old", [0.1, 0.2])]
            new_entries = [EmbeddingEntry(node2_id, "New Lesson", "New", [0.3, 0.4])]

            storage.save_embeddings(old_entries)

            # when
            storage.save_embeddings(new_entries)

            # then
            loaded = storage.load_embeddings()
            assert len(loaded) == 1
            assert loaded[0].title == "New Lesson"


class TestRAGService:
    """Tests for RAGService - high-level service for RAG-based lessons retrieval."""

    def test_rag_service_initialization(self):
        # given
        mock_model = MagicMock(spec=EmbeddingsModel)
        mock_storage = MagicMock(spec=EmbeddingsStorage)

        # when
        service = RAGService(mock_model, mock_storage)

        # then
        assert service is not None

    def test_initialize_loads_existing_embeddings_when_available(self):
        # given
        mock_model = MagicMock(spec=EmbeddingsModel)
        mock_storage = MagicMock(spec=EmbeddingsStorage)

        node_id = NodeId("lessons-learned", "Cached Lesson", "2026-03-09")
        cached_entry = EmbeddingEntry(node_id, "Cached Lesson", "Content", [0.1, 0.2, 0.3])
        mock_storage.load_embeddings.return_value = [cached_entry]

        service = RAGService(mock_model, mock_storage)
        lessons = [KnowledgeNode(node_id, "Cached Lesson", "Content", "lessons-learned", "2026-03-09", "s1", tag="Python")]

        # when
        result = service.initialize(lessons)

        # then
        assert result is True
        mock_storage.load_embeddings.assert_called_once()

    def test_initialize_generates_new_embeddings_when_not_cached(self):
        # given
        mock_model = MagicMock(spec=EmbeddingsModel)
        mock_model.encode_batch.return_value = [[0.1, 0.2], [0.3, 0.4]]
        mock_storage = MagicMock(spec=EmbeddingsStorage)
        mock_storage.load_embeddings.return_value = []  # No cache

        service = RAGService(mock_model, mock_storage)

        node1_id = NodeId("lessons-learned", "New Lesson 1", "2026-03-09")
        node2_id = NodeId("lessons-learned", "New Lesson 2", "2026-03-09")
        lessons = [
            KnowledgeNode(node1_id, "New Lesson 1", "Content 1", "lessons-learned", "2026-03-09", "s1", tag="Python"),
            KnowledgeNode(node2_id, "New Lesson 2", "Content 2", "lessons-learned", "2026-03-09", "s1", tag="Go")
        ]

        # when
        result = service.initialize(lessons)

        # then
        assert result is True
        mock_model.encode_batch.assert_called_once()
        mock_storage.save_embeddings.assert_called_once()

    def test_initialize_returns_false_when_model_load_fails(self):
        # given - [ERR-1] Embedding model download failure
        mock_model = MagicMock(spec=EmbeddingsModel)
        mock_model.load_model.return_value = False
        mock_storage = MagicMock(spec=EmbeddingsStorage)

        service = RAGService(mock_model, mock_storage)
        lessons = []

        # when
        result = service.initialize(lessons)

        # then
        assert result is False

    def test_query_relevant_lessons_returns_matching_lessons(self):
        # given - [REQ-7] Query RAG twice per workflow
        mock_model = MagicMock(spec=EmbeddingsModel)
        mock_model.encode.return_value = [0.5, 0.5]
        mock_model.compute_similarity.side_effect = [0.9, 0.4]

        mock_storage = MagicMock(spec=EmbeddingsStorage)
        mock_storage.load_embeddings.return_value = []

        service = RAGService(mock_model, mock_storage)

        node1_id = NodeId("lessons-learned", "Relevant", "2026-03-09")
        node2_id = NodeId("lessons-learned", "Irrelevant", "2026-03-09")
        lessons = [
            KnowledgeNode(node1_id, "Relevant", "Highly relevant", "lessons-learned", "2026-03-09", "s1", tag="Python"),
            KnowledgeNode(node2_id, "Irrelevant", "Not relevant", "lessons-learned", "2026-03-09", "s1", tag="Go")
        ]

        mock_model.encode_batch.return_value = [[0.5, 0.5], [0.1, 0.1]]
        service.initialize(lessons)

        # when
        results = service.query_relevant_lessons("python testing", top_k=10, min_similarity=0.3)

        # then
        assert len(results) == 2
        assert results[0].title == "Relevant"

    def test_query_relevant_lessons_returns_empty_when_no_matches(self):
        # given - [EDGE-1] Zero RAG results: load nothing
        mock_model = MagicMock(spec=EmbeddingsModel)
        mock_model.encode.return_value = [0.5, 0.5]
        mock_model.compute_similarity.side_effect = [0.1, 0.05]

        mock_storage = MagicMock(spec=EmbeddingsStorage)
        mock_storage.load_embeddings.return_value = []

        service = RAGService(mock_model, mock_storage)

        node_id = NodeId("lessons-learned", "Unrelated", "2026-03-09")
        lessons = [KnowledgeNode(node_id, "Unrelated", "Content", "lessons-learned", "2026-03-09", "s1", tag="Go")]

        mock_model.encode_batch.return_value = [[0.1, 0.1]]
        service.initialize(lessons)

        # when
        results = service.query_relevant_lessons("completely different topic", min_similarity=0.3)

        # then
        assert len(results) == 0

    def test_query_relevant_lessons_logs_count(self):
        # given - [REQ-9] Log the count of lessons loaded to console
        mock_model = MagicMock(spec=EmbeddingsModel)
        mock_model.encode.return_value = [0.5, 0.5]
        mock_model.compute_similarity.return_value = 0.8

        mock_storage = MagicMock(spec=EmbeddingsStorage)
        mock_storage.load_embeddings.return_value = []

        service = RAGService(mock_model, mock_storage)

        node_id = NodeId("lessons-learned", "Lesson", "2026-03-09")
        lessons = [KnowledgeNode(node_id, "Lesson", "Content", "lessons-learned", "2026-03-09", "s1", tag="Python")]

        mock_model.encode_batch.return_value = [[0.5, 0.5]]
        service.initialize(lessons)

        # when
        count = service.get_indexed_count()

        # then
        assert count == 1

    def test_get_indexed_count_returns_zero_when_not_initialized(self):
        # given
        mock_model = MagicMock(spec=EmbeddingsModel)
        mock_storage = MagicMock(spec=EmbeddingsStorage)
        service = RAGService(mock_model, mock_storage)

        # when
        count = service.get_indexed_count()

        # then
        assert count == 0

    def test_rebuild_index_regenerates_embeddings(self):
        # given
        mock_model = MagicMock(spec=EmbeddingsModel)
        mock_model.encode_batch.return_value = [[0.1, 0.2], [0.3, 0.4]]
        mock_storage = MagicMock(spec=EmbeddingsStorage)

        service = RAGService(mock_model, mock_storage)

        node1_id = NodeId("lessons-learned", "Lesson 1", "2026-03-09")
        node2_id = NodeId("lessons-learned", "Lesson 2", "2026-03-09")
        lessons = [
            KnowledgeNode(node1_id, "Lesson 1", "Content 1", "lessons-learned", "2026-03-09", "s1", tag="Python"),
            KnowledgeNode(node2_id, "Lesson 2", "Content 2", "lessons-learned", "2026-03-09", "s1", tag="Go")
        ]

        # when
        result = service.rebuild_index(lessons)

        # then
        assert result is True
        assert mock_model.encode_batch.call_count >= 1
        mock_storage.save_embeddings.assert_called()

    def test_rebuild_index_clears_old_embeddings(self):
        # given
        mock_model = MagicMock(spec=EmbeddingsModel)
        mock_model.encode_batch.return_value = [[0.5, 0.5]]
        mock_storage = MagicMock(spec=EmbeddingsStorage)

        service = RAGService(mock_model, mock_storage)

        # Initialize with one lesson
        node1_id = NodeId("lessons-learned", "Old Lesson", "2026-03-08")
        service.initialize([KnowledgeNode(node1_id, "Old Lesson", "Old", "lessons-learned", "2026-03-08", "s1", tag="Python")])

        # Rebuild with different lesson
        node2_id = NodeId("lessons-learned", "New Lesson", "2026-03-09")
        new_lessons = [KnowledgeNode(node2_id, "New Lesson", "New", "lessons-learned", "2026-03-09", "s1", tag="Go")]

        # when
        service.rebuild_index(new_lessons)

        # then
        count = service.get_indexed_count()
        assert count == 1  # Should only have new lesson


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
