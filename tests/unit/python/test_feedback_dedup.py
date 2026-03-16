#!/usr/bin/env python3
"""
Unit tests for wp_supervisor/feedback_dedup.py

Tests cover:
- [REQ-4.1] Track which files have been reviewed and their findings
- [REQ-4.2] When same file is reviewed multiple times, merge findings (don't duplicate)
- [REQ-4.3] Deduplication keyed by file path + issue content (fuzzy match acceptable)
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, '.')
from wp_supervisor.feedback_dedup import (
    FeedbackDeduplicator,
    FileReviewState,
    DeduplicationResult,
)
from wp_supervisor.feedback_capping import CategorizedFinding, Severity


@pytest.fixture(autouse=True)
def clean_supervisor_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("WP_SUPERVISOR_"):
            monkeypatch.delenv(key, raising=False)


def create_mock_logger():
    logger = MagicMock()
    logger.log_event = MagicMock()
    return logger


# =============================================================================
# FileReviewState Dataclass Tests
# =============================================================================

class TestFileReviewState:
    """Tests for FileReviewState dataclass."""

    def test_file_review_state_has_file_path(self):
        """State should have file_path field."""
        state = FileReviewState(file_path="/src/module.py")
        assert state.file_path == "/src/module.py"

    def test_file_review_state_has_issue_hashes(self):
        """State should have issue_hashes set."""
        state = FileReviewState(file_path="/src/module.py")
        assert isinstance(state.issue_hashes, set)

    def test_file_review_state_issue_hashes_defaults_empty(self):
        """issue_hashes should default to empty set."""
        state = FileReviewState(file_path="/src/module.py")
        assert len(state.issue_hashes) == 0

    def test_file_review_state_has_issue_contents(self):
        """State should have issue_contents list."""
        state = FileReviewState(file_path="/src/module.py")
        assert isinstance(state.issue_contents, list)

    def test_file_review_state_issue_contents_defaults_empty(self):
        """issue_contents should default to empty list."""
        state = FileReviewState(file_path="/src/module.py")
        assert len(state.issue_contents) == 0

    def test_file_review_state_can_add_issues(self):
        """Should be able to track multiple issues."""
        state = FileReviewState(file_path="/src/module.py")
        state.issue_hashes.add("hash1")
        state.issue_hashes.add("hash2")
        state.issue_contents.append("Issue 1")
        state.issue_contents.append("Issue 2")

        assert len(state.issue_hashes) == 2
        assert len(state.issue_contents) == 2


# =============================================================================
# DeduplicationResult Dataclass Tests
# =============================================================================

class TestDeduplicationResult:
    """Tests for DeduplicationResult dataclass."""

    def test_deduplication_result_has_unique_findings(self):
        """Result should have unique_findings list."""
        result = DeduplicationResult(
            unique_findings=[],
            duplicate_count=0,
            new_count=0
        )
        assert isinstance(result.unique_findings, list)

    def test_deduplication_result_has_duplicate_count(self):
        """Result should have duplicate_count."""
        result = DeduplicationResult(
            unique_findings=[],
            duplicate_count=5,
            new_count=3
        )
        assert result.duplicate_count == 5

    def test_deduplication_result_has_new_count(self):
        """Result should have new_count."""
        result = DeduplicationResult(
            unique_findings=[],
            duplicate_count=0,
            new_count=10
        )
        assert result.new_count == 10


# =============================================================================
# FeedbackDeduplicator Init Tests
# =============================================================================

class TestFeedbackDeduplicatorInit:
    """Tests for FeedbackDeduplicator initialization."""

    def test_feedback_deduplicator_class_exists(self):
        """FeedbackDeduplicator class should exist."""
        assert FeedbackDeduplicator is not None

    def test_init_requires_logger(self):
        """Init should require logger parameter."""
        import inspect
        params = inspect.signature(FeedbackDeduplicator.__init__).parameters
        assert 'logger' in params

    def test_init_creates_empty_state(self):
        """Init should create empty file states."""
        # given
        logger = create_mock_logger()

        # when
        deduplicator = FeedbackDeduplicator(logger=logger)

        # then
        assert len(deduplicator.tracked_files) == 0


# =============================================================================
# FeedbackDeduplicator.tracked_files Tests
# =============================================================================

class TestFeedbackDeduplicatorTrackedFiles:
    """Tests for FeedbackDeduplicator.tracked_files property."""

    def test_tracked_files_property_exists(self):
        """tracked_files property should exist."""
        assert hasattr(FeedbackDeduplicator, 'tracked_files')

    def test_tracked_files_returns_set(self):
        """[REQ-4.1] Should return set of tracked file paths."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())

        # when
        result = deduplicator.tracked_files

        # then
        assert isinstance(result, set)

    def test_tracked_files_empty_initially(self):
        """tracked_files should be empty initially."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())

        # when/then
        assert len(deduplicator.tracked_files) == 0


# =============================================================================
# FeedbackDeduplicator.get_file_state Tests
# =============================================================================

class TestFeedbackDeduplicatorGetFileState:
    """Tests for FeedbackDeduplicator.get_file_state method."""

    def test_get_file_state_method_exists(self):
        """get_file_state method should exist."""
        assert hasattr(FeedbackDeduplicator, 'get_file_state')

    def test_get_file_state_returns_none_for_unknown_file(self):
        """Should return None for file not yet reviewed."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())

        # when
        result = deduplicator.get_file_state("/unknown/file.py")

        # then
        assert result is None

    def test_get_file_state_returns_state_for_tracked_file(self):
        """[REQ-4.1] Should return state for tracked file."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())
        finding = CategorizedFinding(
            content="Issue in file",
            severity=Severity.HIGH,
            file_path="/src/module.py"
        )
        deduplicator.record_findings([finding])

        # when
        result = deduplicator.get_file_state("/src/module.py")

        # then
        assert result is not None
        assert isinstance(result, FileReviewState)
        assert result.file_path == "/src/module.py"


# =============================================================================
# FeedbackDeduplicator.compute_issue_hash Tests
# =============================================================================

class TestFeedbackDeduplicatorComputeIssueHash:
    """Tests for FeedbackDeduplicator.compute_issue_hash method."""

    def test_compute_issue_hash_method_exists(self):
        """compute_issue_hash method should exist."""
        assert hasattr(FeedbackDeduplicator, 'compute_issue_hash')

    def test_compute_issue_hash_returns_string(self):
        """Should return string hash."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())

        # when
        result = deduplicator.compute_issue_hash("Missing null check")

        # then
        assert isinstance(result, str)
        assert len(result) > 0

    def test_compute_issue_hash_same_content_same_hash(self):
        """Same content should produce same hash."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())

        # when
        hash1 = deduplicator.compute_issue_hash("Missing null check")
        hash2 = deduplicator.compute_issue_hash("Missing null check")

        # then
        assert hash1 == hash2

    def test_compute_issue_hash_different_content_different_hash(self):
        """Different content should produce different hash."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())

        # when
        hash1 = deduplicator.compute_issue_hash("Missing null check")
        hash2 = deduplicator.compute_issue_hash("Variable naming issue")

        # then
        assert hash1 != hash2

    def test_compute_issue_hash_fuzzy_matches_whitespace(self):
        """[REQ-4.3] Should fuzzy match by normalizing whitespace."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())

        # when
        hash1 = deduplicator.compute_issue_hash("Missing null check")
        hash2 = deduplicator.compute_issue_hash("Missing  null   check")

        # then
        assert hash1 == hash2

    def test_compute_issue_hash_fuzzy_matches_case(self):
        """[REQ-4.3] Should fuzzy match by normalizing case."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())

        # when
        hash1 = deduplicator.compute_issue_hash("Missing NULL Check")
        hash2 = deduplicator.compute_issue_hash("missing null check")

        # then
        assert hash1 == hash2

    def test_compute_issue_hash_includes_file_path(self):
        """[REQ-4.3] Hash should include file path for context."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())

        # when
        hash1 = deduplicator.compute_issue_hash("Missing check", file_path="/a.py")
        hash2 = deduplicator.compute_issue_hash("Missing check", file_path="/b.py")

        # then
        assert hash1 != hash2

    def test_compute_issue_hash_same_file_same_hash(self):
        """Same file and content should produce same hash."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())

        # when
        hash1 = deduplicator.compute_issue_hash("Issue", file_path="/src/a.py")
        hash2 = deduplicator.compute_issue_hash("Issue", file_path="/src/a.py")

        # then
        assert hash1 == hash2


# =============================================================================
# FeedbackDeduplicator.deduplicate Tests
# =============================================================================

class TestFeedbackDeduplicatorDeduplicate:
    """Tests for FeedbackDeduplicator.deduplicate method."""

    def test_deduplicate_method_exists(self):
        """deduplicate method should exist."""
        assert hasattr(FeedbackDeduplicator, 'deduplicate')

    def test_deduplicate_returns_deduplication_result(self):
        """Should return DeduplicationResult."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())
        findings = [
            CategorizedFinding(content="Issue 1", severity=Severity.HIGH)
        ]

        # when
        result = deduplicator.deduplicate(findings)

        # then
        assert isinstance(result, DeduplicationResult)

    def test_deduplicate_all_new_findings_returned(self):
        """All new findings should be returned."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())
        findings = [
            CategorizedFinding(content="Issue 1", severity=Severity.HIGH),
            CategorizedFinding(content="Issue 2", severity=Severity.MEDIUM),
        ]

        # when
        result = deduplicator.deduplicate(findings)

        # then
        assert len(result.unique_findings) == 2
        assert result.duplicate_count == 0
        assert result.new_count == 2

    def test_deduplicate_removes_exact_duplicates_in_batch(self):
        """[REQ-4.2] Should remove exact duplicates within same batch."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())
        findings = [
            CategorizedFinding(content="Same issue", severity=Severity.HIGH),
            CategorizedFinding(content="Same issue", severity=Severity.HIGH),
            CategorizedFinding(content="Different issue", severity=Severity.LOW),
        ]

        # when
        result = deduplicator.deduplicate(findings)

        # then
        assert len(result.unique_findings) == 2
        assert result.duplicate_count == 1

    def test_deduplicate_removes_previously_seen_findings(self):
        """[REQ-4.2] Should remove findings seen in previous reviews."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())
        # First review
        first_findings = [
            CategorizedFinding(content="Issue A", severity=Severity.HIGH)
        ]
        deduplicator.record_findings(first_findings)

        # Second review with duplicate
        second_findings = [
            CategorizedFinding(content="Issue A", severity=Severity.HIGH),
            CategorizedFinding(content="Issue B", severity=Severity.MEDIUM),
        ]

        # when
        result = deduplicator.deduplicate(second_findings)

        # then
        assert len(result.unique_findings) == 1
        assert result.unique_findings[0].content == "Issue B"
        assert result.duplicate_count == 1
        assert result.new_count == 1

    def test_deduplicate_fuzzy_matches_similar_issues(self):
        """[REQ-4.3] Should detect fuzzy duplicates."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())
        # First review
        first_findings = [
            CategorizedFinding(content="Missing null check", severity=Severity.CRITICAL)
        ]
        deduplicator.record_findings(first_findings)

        # Second review with fuzzy duplicate
        second_findings = [
            CategorizedFinding(content="missing  NULL  check", severity=Severity.CRITICAL),
        ]

        # when
        result = deduplicator.deduplicate(second_findings)

        # then
        assert len(result.unique_findings) == 0
        assert result.duplicate_count == 1

    def test_deduplicate_considers_file_path(self):
        """[REQ-4.1] Should track findings per file."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())
        # First review for file A
        first_findings = [
            CategorizedFinding(
                content="Issue X",
                severity=Severity.HIGH,
                file_path="/src/a.py"
            )
        ]
        deduplicator.record_findings(first_findings)

        # Second review for file B with same issue content
        second_findings = [
            CategorizedFinding(
                content="Issue X",
                severity=Severity.HIGH,
                file_path="/src/b.py"
            )
        ]

        # when
        result = deduplicator.deduplicate(second_findings)

        # then
        # Same issue in different file is NOT a duplicate
        assert len(result.unique_findings) == 1
        assert result.duplicate_count == 0

    def test_deduplicate_handles_empty_list(self):
        """Should handle empty findings list."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())

        # when
        result = deduplicator.deduplicate([])

        # then
        assert len(result.unique_findings) == 0
        assert result.duplicate_count == 0
        assert result.new_count == 0


# =============================================================================
# FeedbackDeduplicator.record_findings Tests
# =============================================================================

class TestFeedbackDeduplicatorRecordFindings:
    """Tests for FeedbackDeduplicator.record_findings method."""

    def test_record_findings_method_exists(self):
        """record_findings method should exist."""
        assert hasattr(FeedbackDeduplicator, 'record_findings')

    def test_record_findings_updates_tracked_files(self):
        """[REQ-4.1] Should update tracked_files after recording."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())
        findings = [
            CategorizedFinding(
                content="Issue",
                severity=Severity.HIGH,
                file_path="/src/module.py"
            )
        ]

        # when
        deduplicator.record_findings(findings)

        # then
        assert "/src/module.py" in deduplicator.tracked_files

    def test_record_findings_stores_issue_hash(self):
        """Should store issue hash for future deduplication."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())
        findings = [
            CategorizedFinding(
                content="Specific issue",
                severity=Severity.HIGH,
                file_path="/src/module.py"
            )
        ]

        # when
        deduplicator.record_findings(findings)

        # then
        state = deduplicator.get_file_state("/src/module.py")
        assert len(state.issue_hashes) == 1

    def test_record_findings_multiple_files(self):
        """Should track findings for multiple files."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())
        findings = [
            CategorizedFinding(content="Issue A", severity=Severity.HIGH, file_path="/a.py"),
            CategorizedFinding(content="Issue B", severity=Severity.HIGH, file_path="/b.py"),
        ]

        # when
        deduplicator.record_findings(findings)

        # then
        assert "/a.py" in deduplicator.tracked_files
        assert "/b.py" in deduplicator.tracked_files

    def test_record_findings_accumulates_for_same_file(self):
        """[REQ-4.1] Should accumulate findings for same file across calls."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())

        # Record first batch
        deduplicator.record_findings([
            CategorizedFinding(content="Issue 1", severity=Severity.HIGH, file_path="/src/a.py")
        ])

        # Record second batch
        deduplicator.record_findings([
            CategorizedFinding(content="Issue 2", severity=Severity.MEDIUM, file_path="/src/a.py")
        ])

        # then
        state = deduplicator.get_file_state("/src/a.py")
        assert len(state.issue_hashes) == 2

    def test_record_findings_handles_no_file_path(self):
        """Should handle findings without file_path."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())
        findings = [
            CategorizedFinding(content="General issue", severity=Severity.HIGH)
        ]

        # when - should not raise
        deduplicator.record_findings(findings)

        # then - no file should be tracked, but issue should be recorded for general dedup
        assert len(deduplicator.tracked_files) == 0


# =============================================================================
# FeedbackDeduplicator.clear Tests
# =============================================================================

class TestFeedbackDeduplicatorClear:
    """Tests for FeedbackDeduplicator.clear method."""

    def test_clear_method_exists(self):
        """clear method should exist."""
        assert hasattr(FeedbackDeduplicator, 'clear')

    def test_clear_removes_all_tracked_files(self):
        """clear should remove all tracked file states."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())
        deduplicator.record_findings([
            CategorizedFinding(content="Issue", severity=Severity.HIGH, file_path="/a.py"),
            CategorizedFinding(content="Issue", severity=Severity.HIGH, file_path="/b.py"),
        ])
        assert len(deduplicator.tracked_files) == 2

        # when
        deduplicator.clear()

        # then
        assert len(deduplicator.tracked_files) == 0

    def test_clear_allows_retracking(self):
        """After clear, findings can be tracked fresh."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())
        finding = CategorizedFinding(content="Issue", severity=Severity.HIGH, file_path="/a.py")
        deduplicator.record_findings([finding])
        deduplicator.clear()

        # when - record same finding again
        deduplicator.record_findings([finding])
        result = deduplicator.deduplicate([finding])

        # then - should be detected as duplicate again
        assert result.duplicate_count == 1


# =============================================================================
# FeedbackDeduplicator.clear_file Tests
# =============================================================================

class TestFeedbackDeduplicatorClearFile:
    """Tests for FeedbackDeduplicator.clear_file method."""

    def test_clear_file_method_exists(self):
        """clear_file method should exist."""
        assert hasattr(FeedbackDeduplicator, 'clear_file')

    def test_clear_file_removes_single_file(self):
        """clear_file should remove state for specific file only."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())
        deduplicator.record_findings([
            CategorizedFinding(content="Issue A", severity=Severity.HIGH, file_path="/a.py"),
            CategorizedFinding(content="Issue B", severity=Severity.HIGH, file_path="/b.py"),
        ])

        # when
        deduplicator.clear_file("/a.py")

        # then
        assert "/a.py" not in deduplicator.tracked_files
        assert "/b.py" in deduplicator.tracked_files

    def test_clear_file_allows_retracking_that_file(self):
        """After clear_file, that file's findings can be tracked fresh."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())
        finding = CategorizedFinding(content="Issue", severity=Severity.HIGH, file_path="/a.py")
        deduplicator.record_findings([finding])
        deduplicator.clear_file("/a.py")

        # when - same finding should not be a duplicate now
        result = deduplicator.deduplicate([finding])

        # then
        assert len(result.unique_findings) == 1
        assert result.duplicate_count == 0

    def test_clear_file_handles_unknown_file(self):
        """clear_file should handle unknown file gracefully."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())

        # when/then - should not raise
        deduplicator.clear_file("/unknown/file.py")


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestFeedbackDeduplicatorEdgeCases:
    """Edge case tests for FeedbackDeduplicator."""

    def test_handles_special_characters_in_content(self):
        """Should handle special characters in issue content."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())
        content = "Error: `foo()` returned None instead of {expected: 'value'}"
        findings = [CategorizedFinding(content=content, severity=Severity.HIGH)]

        # when - should not raise
        deduplicator.record_findings(findings)
        result = deduplicator.deduplicate(findings)

        # then
        assert result.duplicate_count == 1

    def test_handles_unicode_in_content(self):
        """Should handle unicode characters in issue content."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())
        content = "Variable naming: use descriptive names"
        findings = [CategorizedFinding(content=content, severity=Severity.LOW)]

        # when - should not raise
        deduplicator.record_findings(findings)

        # then
        assert len(deduplicator.tracked_files) == 0  # No file_path

    def test_handles_very_long_content(self):
        """Should handle very long issue content."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())
        content = "A" * 10000  # Very long content
        findings = [CategorizedFinding(content=content, severity=Severity.MEDIUM)]

        # when - should not raise
        hash_result = deduplicator.compute_issue_hash(content)

        # then
        assert isinstance(hash_result, str)
        assert len(hash_result) > 0

    def test_handles_empty_content(self):
        """Should handle empty issue content."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())

        # when
        hash_result = deduplicator.compute_issue_hash("")

        # then
        assert isinstance(hash_result, str)

    def test_many_findings_many_files(self):
        """Should handle many findings across many files."""
        # given
        deduplicator = FeedbackDeduplicator(logger=create_mock_logger())
        findings = []
        for i in range(100):
            findings.append(CategorizedFinding(
                content=f"Issue {i}",
                severity=Severity.MEDIUM,
                file_path=f"/src/file_{i}.py"
            ))

        # when
        deduplicator.record_findings(findings)

        # then
        assert len(deduplicator.tracked_files) == 100


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
