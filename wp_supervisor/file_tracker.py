#!/usr/bin/env python3
"""Tracks file changes from Write/Edit tool calls via PostToolUse hook."""

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from .logger import SupervisorLogger


@dataclass
class FileChange:
    """Represents a single file change event."""
    file_path: str
    tool_name: str
    timestamp: float


class FileChangeTracker:
    """Tracks file changes from PostToolUse hook events. Thread-safe."""

    def __init__(
        self,
        logger: "SupervisorLogger",
        working_dir: str
    ) -> None:
        self._logger = logger
        self._working_dir = working_dir
        self._pending_changes: Dict[str, FileChange] = {}
        self._lock = asyncio.Lock()

    @property
    def pending_count(self) -> int:
        return len(self._pending_changes)

    async def record_change(self, file_path: str, tool_name: str) -> None:
        """Record a file change. Deduplicates by keeping latest change per file."""
        async with self._lock:
            change = FileChange(
                file_path=file_path,
                tool_name=tool_name,
                timestamp=time.monotonic()
            )
            self._pending_changes[file_path] = change

    async def get_pending_changes(self) -> Dict[str, str]:
        """Get pending changes as dict of path -> file content. Skips unreadable files."""
        async with self._lock:
            result: Dict[str, str] = {}
            for file_path in self._pending_changes.keys():
                content = self._read_file_content(file_path)
                if content is not None:
                    result[file_path] = content
                else:
                    self._logger.log_event(
                        "REVIEWER",
                        f"Skipping unreadable file: {file_path}"
                    )
            return result

    async def get_changed_paths(self) -> Set[str]:
        """Get set of file paths with pending changes."""
        async with self._lock:
            return set(self._pending_changes.keys())

    async def clear_pending(self) -> None:
        """Clear all pending changes after review completes."""
        async with self._lock:
            self._pending_changes.clear()

    def _read_file_content(self, file_path: str) -> Optional[str]:
        """Read file content, returning None if unreadable."""
        try:
            path = Path(file_path)
            if not path.is_absolute():
                path = Path(self._working_dir) / path
            return path.read_text(encoding='utf-8')
        except Exception:
            return None
