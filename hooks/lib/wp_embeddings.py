#!/usr/bin/env python3
"""
Waypoints Embeddings - Local RAG for Lessons Learned

Uses sentence-transformers for local embeddings-based semantic search [REQ-5, REQ-6].
Only lessons-learned entries are embedded and searched; architecture and decisions
are always loaded in full [REQ-10, REQ-11, REQ-12].

RAG Query Strategy [REQ-7]:
- Query 1: At workflow start based on initial task description
- Query 2: After Phase 1 requirements gathering based on user-provided requirements

Embedding Model:
- sentence-transformers/all-MiniLM-L6-v2 (lightweight, good quality, offline-capable)
"""

import logging
import json
import math
import os
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import List, Optional, Tuple

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SentenceTransformer = None  # Make it patchable in tests
    SENTENCE_TRANSFORMERS_AVAILABLE = False

from wp_graph import KnowledgeNode, NodeId


@dataclass
class EmbeddingEntry:
    """
    A lessons-learned entry with its embedding vector.

    Attributes:
        node_id: Reference to the graph node
        title: Entry title (for display)
        content: Entry content
        embedding: Vector representation of title + content
        tag: Technology tag for lessons-learned (e.g., "Python", "Git")
        session_id: Session that created this entry
    """
    node_id: NodeId
    title: str
    content: str
    embedding: List[float]  # Vector from sentence-transformers
    tag: Optional[str] = None
    session_id: str = ""

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        result = {
            "node_id": self.node_id.to_dict(),
            "title": self.title,
            "content": self.content,
            "embedding": self.embedding
        }
        if self.tag is not None:
            result["tag"] = self.tag
        if self.session_id:
            result["session_id"] = self.session_id
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "EmbeddingEntry":
        """Create from dict."""
        return cls(
            node_id=NodeId.from_dict(data["node_id"]),
            title=data["title"],
            content=data["content"],
            embedding=data["embedding"],
            tag=data.get("tag"),
            session_id=data.get("session_id", "")
        )


@contextmanager
def _suppress_stderr():
    """Redirect stderr at the OS file-descriptor level to suppress noisy library output."""
    old_stderr_fd = os.dup(2)
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 2)
    os.close(devnull)
    old_stderr = sys.stderr
    sys.stderr = StringIO()
    try:
        yield
    finally:
        os.dup2(old_stderr_fd, 2)
        os.close(old_stderr_fd)
        sys.stderr = old_stderr


class EmbeddingsModel:
    """
    Wrapper around sentence-transformers for embeddings generation [REQ-5].

    Uses all-MiniLM-L6-v2 model (lightweight, offline-capable).
    """

    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self):
        """
        Initialize embeddings model.

        Note:
            On first run, downloads model from HuggingFace [ERR-1].
            If download fails, raises ImportError with clear message.
        """
        self.model = None
        self._logger = logging.getLogger(__name__)

    @property
    def is_loaded(self) -> bool:
        """Whether the embeddings model is loaded and ready."""
        return self.model is not None

    def load_model(self) -> bool:
        """
        Load the sentence-transformers model.

        Returns:
            True if successful, False if model can't be loaded

        Note:
            [ERR-1] If download fails on first run, logs error and returns False.
            Caller should handle gracefully (e.g., disable RAG, use fallback).
        """
        if SentenceTransformer is None:
            self._logger.error("sentence-transformers library not available. Install with: pip install sentence-transformers")
            return False

        try:
            # Suppress noisy HuggingFace output (progress bars, auth warnings,
            # BertModel load reports). These come from tqdm, safetensors, and
            # print() calls that bypass Python logging, so we redirect stderr.
            os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
            os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
            with _suppress_stderr():
                self.model = SentenceTransformer(self.MODEL_NAME)
            return True
        except Exception as e:
            self._logger.error(f"Failed to load embeddings model {self.MODEL_NAME}: {e}")
            return False

    def encode(self, text: str) -> List[float]:
        """
        Generate embedding for text [REQ-6].

        Args:
            text: Text to embed (typically title + content)

        Returns:
            Embedding vector

        Raises:
            RuntimeError: If model not loaded
        """
        if self.model is None:
            raise RuntimeError("Embeddings model not loaded. Call load_model() first.")

        embedding = self.model.encode(text)
        return embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts (batch processing).

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors

        Raises:
            RuntimeError: If model not loaded
        """
        if self.model is None:
            raise RuntimeError("Embeddings model not loaded. Call load_model() first.")

        if not texts:
            return []

        embeddings = self.model.encode(texts)
        return [emb.tolist() if hasattr(emb, 'tolist') else list(emb) for emb in embeddings]

    def compute_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Similarity score (0.0 to 1.0, higher = more similar)

        Raises:
            ValueError: If embeddings have different dimensions
        """
        if len(embedding1) != len(embedding2):
            raise ValueError(
                f"Embedding dimension mismatch: {len(embedding1)} vs {len(embedding2)}"
            )

        # Cosine similarity: dot product / (norm1 * norm2)
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))

        # Compute norms
        norm1 = math.sqrt(sum(a * a for a in embedding1))
        norm2 = math.sqrt(sum(b * b for b in embedding2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)


class EmbeddingsIndex:
    """
    Index for semantic search over lessons-learned entries [REQ-6, REQ-8].

    Maintains embeddings for all lessons-learned entries and provides
    similarity-based retrieval.
    """

    def __init__(self, embeddings_model: EmbeddingsModel):
        """
        Initialize embeddings index.

        Args:
            embeddings_model: Model for generating embeddings
        """
        self._model = embeddings_model
        self._entries: List[EmbeddingEntry] = []
        self._logger = logging.getLogger(__name__)

    def index_lessons(self, lessons: List[KnowledgeNode]) -> None:
        """
        Generate embeddings for lessons-learned entries [REQ-6].

        Args:
            lessons: List of lessons-learned nodes from graph

        Note:
            Combines title + content for embedding to capture full context.
        """
        if not lessons:
            self._entries = []
            return

        # Combine title + content for each lesson
        texts = [f"{lesson.title}\n{lesson.content}" for lesson in lessons]

        # Generate embeddings in batch
        embeddings = self._model.encode_batch(texts)

        # Create embedding entries
        self._entries = [
            EmbeddingEntry(
                node_id=lesson.node_id,
                title=lesson.title,
                content=lesson.content,
                embedding=embedding,
                tag=lesson.tag,
                session_id=lesson.session_id
            )
            for lesson, embedding in zip(lessons, embeddings)
        ]

    def search(
        self,
        query: str,
        top_k: int = 10,
        min_similarity: float = 0.3
    ) -> List[Tuple[KnowledgeNode, float]]:
        """
        Semantic search for relevant lessons [REQ-8].

        Args:
            query: User's task description or requirements text
            top_k: Maximum number of results to return
            min_similarity: Minimum similarity threshold (0.0-1.0)

        Returns:
            List of (KnowledgeNode, similarity_score) tuples, sorted by relevance

        Note:
            [EDGE-1] If no results meet threshold, returns empty list.
        """
        if not self._entries:
            return []

        # Generate query embedding
        query_embedding = self._model.encode(query)

        # Compute similarities
        similarities = []
        for entry in self._entries:
            similarity = self._model.compute_similarity(query_embedding, entry.embedding)
            if similarity >= min_similarity:
                # Reconstruct KnowledgeNode from embedding entry
                node = KnowledgeNode(
                    node_id=entry.node_id,
                    title=entry.title,
                    content=entry.content,
                    category="lessons-learned",
                    date_added=entry.node_id.date,
                    session_id=entry.session_id,
                    tag=entry.tag
                )
                similarities.append((node, similarity))

        # Sort by similarity (descending) and take top_k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]

    def get_entry_count(self) -> int:
        """Get number of indexed entries."""
        return len(self._entries)

    def clear(self) -> None:
        """Clear all indexed entries."""
        self._entries = []

    def get_entries(self) -> List[EmbeddingEntry]:
        """Get all indexed entries."""
        return self._entries

    def set_entries(self, entries: List[EmbeddingEntry]) -> None:
        """Set indexed entries (used for loading cached embeddings)."""
        self._entries = entries


class EmbeddingsStorage:
    """
    Persists embeddings to disk to avoid recomputation [REQ-4].

    Storage location: ~/.claude/waypoints/knowledge/embeddings.json
    """

    def __init__(self, knowledge_base_dir: Path):
        """
        Initialize embeddings storage.

        Args:
            knowledge_base_dir: Base directory for knowledge storage
        """
        self._knowledge_base_dir = knowledge_base_dir
        self._logger = logging.getLogger(__name__)

    def load_embeddings(self) -> List[EmbeddingEntry]:
        """
        Load embeddings from disk.

        Returns:
            List of EmbeddingEntry (empty if file doesn't exist)
        """
        path = self._get_embeddings_path()
        if not path.exists():
            return []

        try:
            data = json.loads(path.read_text())
            return [EmbeddingEntry.from_dict(entry) for entry in data]
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self._logger.error(f"Corrupted embeddings file {path}: {e}. Returning empty list.")
            return []

    def save_embeddings(self, entries: List[EmbeddingEntry]) -> bool:
        """
        Save embeddings to disk (atomic write via temp file + rename).

        Args:
            entries: List of EmbeddingEntry to save

        Returns:
            True if successful, False on error
        """
        try:
            path = self._get_embeddings_path()
            path.parent.mkdir(parents=True, exist_ok=True)

            # Serialize before creating temp file to avoid leaking on TypeError/AttributeError
            json_str = json.dumps([entry.to_dict() for entry in entries], indent=2)

            # Atomic write via temp file + rename
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(
                    'w', dir=path.parent, delete=False, suffix='.tmp'
                ) as tmp:
                    tmp_path = tmp.name
                    tmp.write(json_str)
                os.replace(tmp_path, str(path))
            except BaseException:
                if tmp_path:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                raise
            return True
        except (OSError, IOError) as e:
            self._logger.error(f"Failed to save embeddings: {e}")
            return False

    def _get_embeddings_path(self) -> Path:
        """Get path to embeddings file."""
        return self._knowledge_base_dir / "embeddings.json"


class RAGService:
    """
    High-level service for RAG-based lessons retrieval [REQ-7, REQ-8, REQ-9].

    Orchestrates embeddings generation, indexing, and semantic search.
    """

    def __init__(
        self,
        embeddings_model: EmbeddingsModel,
        embeddings_storage: EmbeddingsStorage
    ):
        """
        Initialize RAG service.

        Args:
            embeddings_model: Model for generating embeddings
            embeddings_storage: Storage for persisting embeddings
        """
        self._model = embeddings_model
        self._storage = embeddings_storage
        self._index = EmbeddingsIndex(embeddings_model)
        self._logger = logging.getLogger(__name__)

    def initialize(self, lessons: List[KnowledgeNode]) -> bool:
        """
        Initialize RAG index from lessons-learned nodes [REQ-6].

        Args:
            lessons: All lessons-learned nodes from global graph

        Returns:
            True if successful, False if embeddings model failed to load

        Note:
            [ERR-1] If model can't be loaded, logs error and returns False.
            Caller should handle gracefully (disable RAG, load all lessons).
        """
        # Load model if not already loaded
        if not self._model.is_loaded:
            if not self._model.load_model():
                return False

        # Try to load cached embeddings
        cached_entries = self._storage.load_embeddings()

        # Create a map of cached embeddings by node_id
        cached_map = {
            entry.node_id: entry
            for entry in cached_entries
        }

        # Check if we need to regenerate embeddings
        needs_regeneration = False
        if len(cached_entries) != len(lessons):
            needs_regeneration = True
        else:
            # Check if all lessons have cached embeddings
            for lesson in lessons:
                if lesson.node_id not in cached_map:
                    needs_regeneration = True
                    break

        if needs_regeneration:
            # Generate new embeddings
            self._logger.info(f"Generating embeddings for {len(lessons)} lessons...")
            self._index.index_lessons(lessons)

            # Save to cache
            self._storage.save_embeddings(self._index.get_entries())
        else:
            # Use cached embeddings
            self._logger.info(f"Using cached embeddings for {len(cached_entries)} lessons")
            self._index.set_entries(cached_entries)

        return True

    def query_relevant_lessons(
        self,
        query_text: str,
        top_k: int = 10,
        min_similarity: float = 0.3
    ) -> List[KnowledgeNode]:
        """
        Query for relevant lessons-learned [REQ-8].

        Args:
            query_text: Task description or requirements text
            top_k: Maximum number of results
            min_similarity: Minimum similarity threshold

        Returns:
            List of relevant KnowledgeNode entries

        Note:
            [EDGE-1] If no results meet threshold, returns empty list.
        """
        results = self._index.search(query_text, top_k=top_k, min_similarity=min_similarity)
        # Extract nodes without similarity scores
        return [node for node, _ in results]

    def get_indexed_count(self) -> int:
        """Get number of indexed lessons [REQ-9]."""
        return self._index.get_entry_count()

    def rebuild_index(self, lessons: List[KnowledgeNode]) -> bool:
        """
        Rebuild embeddings index from scratch.

        Args:
            lessons: All lessons-learned nodes

        Returns:
            True if successful, False on error
        """
        try:
            # Ensure model is loaded (rebuild_index may be called without initialize)
            if not self._model.is_loaded:
                if not self._model.load_model():
                    self._logger.error("Cannot rebuild index: embeddings model failed to load")
                    return False

            # Clear old index
            self._index.clear()

            # Generate new embeddings
            self._index.index_lessons(lessons)

            # Save to cache
            self._storage.save_embeddings(self._index.get_entries())

            return True
        except Exception as e:
            self._logger.error(f"Failed to rebuild embeddings index: {e}")
            return False
