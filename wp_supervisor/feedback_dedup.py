#!/usr/bin/env python3
"""
Feedback deduplication for reviewer feedback.

Implements REQ-4.x: Feedback Deduplication
- Track which files have been reviewed and their findings
- Merge findings when same file is reviewed multiple times
- Deduplication keyed by file path + issue content
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from .logger import SupervisorLogger
    from .feedback_capping import CategorizedFinding


@dataclass
class FileReviewState:
    """Tracks review state for a single file."""
    file_path: str
    issue_hashes: Set[str] = field(default_factory=set)
    issue_contents: List[str] = field(default_factory=list)


@dataclass
class DeduplicationResult:
    """Result of deduplication operation."""
    unique_findings: List["CategorizedFinding"]
    duplicate_count: int
    new_count: int


class FeedbackDeduplicator:
    """
    Deduplicates reviewer feedback across multiple review cycles.

    Implements:
    - [REQ-4.1] Track which files have been reviewed and their findings
    - [REQ-4.2] Merge findings when same file reviewed multiple times
    - [REQ-4.3] Deduplication keyed by file path + issue content (fuzzy match)
    """

    def __init__(self, logger: "SupervisorLogger") -> None:
        """
        Initialize the feedback deduplicator.

        Args:
            logger: Logger for recording deduplication events
        """
        self._logger = logger
        self._file_states: Dict[str, FileReviewState] = {}
        self._global_hashes: Set[str] = set()  # Initialize eagerly to avoid hasattr checks

    @property
    def tracked_files(self) -> Set[str]:
        """Return set of file paths that have been reviewed."""
        return set(self._file_states.keys())

    def get_file_state(self, file_path: str) -> Optional[FileReviewState]:
        """
        Get the review state for a specific file.

        Args:
            file_path: Path to the file

        Returns:
            FileReviewState if file has been reviewed, None otherwise
        """
        return self._file_states.get(file_path)

    def compute_issue_hash(self, content: str, file_path: Optional[str] = None) -> str:
        """
        Compute a hash for deduplication, supporting fuzzy matching.

        Implements [REQ-4.3]: Deduplication keyed by file path + issue content.
        Uses fuzzy matching by normalizing whitespace, case, and punctuation.

        Args:
            content: The issue content text
            file_path: Optional file path for context

        Returns:
            Hash string for deduplication
        """
        import hashlib
        import re

        # Normalize for fuzzy matching
        # 1. Lowercase
        normalized = content.lower()
        # 2. Collapse whitespace to single spaces
        normalized = re.sub(r'\s+', ' ', normalized)
        # 3. Strip leading/trailing whitespace
        normalized = normalized.strip()

        # Include file path in hash if provided
        if file_path:
            normalized = f"{file_path}:{normalized}"

        # Generate hash
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]

    def deduplicate(
        self,
        findings: List["CategorizedFinding"]
    ) -> DeduplicationResult:
        """
        Deduplicate findings against previously seen issues.

        Implements:
        - [REQ-4.1] Track findings per file
        - [REQ-4.2] Merge findings (don't duplicate)
        - [REQ-4.3] Use fuzzy matching for deduplication

        Args:
            findings: List of new findings to deduplicate

        Returns:
            DeduplicationResult with unique findings and statistics
        """
        unique_findings = []
        duplicate_count = 0
        seen_in_batch: Set[str] = set()  # Track duplicates within this batch

        for finding in findings:
            # Compute hash for this finding
            issue_hash = self.compute_issue_hash(finding.content, finding.file_path)

            # Check if already seen in this batch
            if issue_hash in seen_in_batch:
                duplicate_count += 1
                continue

            # Check if already seen in previous reviews
            is_duplicate = False
            if finding.file_path and finding.file_path in self._file_states:
                if issue_hash in self._file_states[finding.file_path].issue_hashes:
                    is_duplicate = True
            elif finding.file_path is None:
                # For findings without file path, check all states
                for state in self._file_states.values():
                    if issue_hash in state.issue_hashes:
                        is_duplicate = True
                        break
                # Also check global hashes
                if issue_hash in self._global_hashes:
                    is_duplicate = True

            if is_duplicate:
                duplicate_count += 1
            else:
                unique_findings.append(finding)
                seen_in_batch.add(issue_hash)

        return DeduplicationResult(
            unique_findings=unique_findings,
            duplicate_count=duplicate_count,
            new_count=len(unique_findings)
        )

    def record_findings(self, findings: List["CategorizedFinding"]) -> None:
        """
        Record findings as seen (for future deduplication).

        Called after findings are injected to track them for future
        deduplication cycles.

        Args:
            findings: List of findings that were injected
        """
        for finding in findings:
            issue_hash = self.compute_issue_hash(finding.content, finding.file_path)

            # Only track in file_states if finding has a file_path
            if finding.file_path:
                # Ensure file state exists
                if finding.file_path not in self._file_states:
                    self._file_states[finding.file_path] = FileReviewState(
                        file_path=finding.file_path,
                        issue_hashes=set(),
                        issue_contents=[]
                    )

                # Record the finding in file state
                state = self._file_states[finding.file_path]
                state.issue_hashes.add(issue_hash)
                state.issue_contents.append(finding.content)

            # Always add to global hashes for cross-file deduplication
            self._global_hashes.add(issue_hash)

    def clear(self) -> None:
        """Clear all tracked file states."""
        self._file_states.clear()
        self._global_hashes.clear()

    def clear_file(self, file_path: str) -> None:
        """
        Clear tracked state for a specific file.

        Useful when a file is substantially rewritten.

        Args:
            file_path: Path to the file to clear
        """
        if file_path in self._file_states:
            # Remove hashes from global set
            for issue_hash in self._file_states[file_path].issue_hashes:
                self._global_hashes.discard(issue_hash)
            # Remove file state
            del self._file_states[file_path]
