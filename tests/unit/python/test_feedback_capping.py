#!/usr/bin/env python3
"""
Unit tests for wp_supervisor/feedback_capping.py

Tests cover:
- [REQ-2.1] Reviewer categorizes each finding by severity
- [REQ-2.2] Update reviewer prompt to instruct severity categorization
- [REQ-2.3] Cap feedback injection at 20 items maximum
- [REQ-2.4] Sort feedback by severity (critical first, then high, medium, low)
- [REQ-2.5] When over cap, keep top 20 by severity, drop remainder
- [REQ-2.6] Log when feedback items are dropped due to cap
- [EDGE-2] If all 20 capped items are low severity, still inject them
- [ERR-2] Severity parsing failures should default to "medium"
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, '.')
from wp_supervisor.feedback_capping import (
    FeedbackCapper,
    Severity,
    CategorizedFinding,
    CappingResult,
    DEFAULT_FEEDBACK_CAP,
)


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
# Severity Enum Tests
# =============================================================================

class TestSeverityEnum:
    """Tests for Severity IntEnum ordering."""

    def test_severity_critical_has_lowest_value(self):
        """[REQ-2.4] CRITICAL should sort first (lowest value)."""
        assert Severity.CRITICAL.value == 1

    def test_severity_high_value(self):
        """HIGH should have second lowest value."""
        assert Severity.HIGH.value == 2

    def test_severity_medium_value(self):
        """MEDIUM should have middle value."""
        assert Severity.MEDIUM.value == 3

    def test_severity_low_has_highest_value(self):
        """[REQ-2.4] LOW should sort last (highest value)."""
        assert Severity.LOW.value == 4

    def test_severity_ordering_for_sort(self):
        """[REQ-2.4] Severities should sort correctly (critical first)."""
        severities = [Severity.LOW, Severity.CRITICAL, Severity.MEDIUM, Severity.HIGH]
        sorted_severities = sorted(severities)
        assert sorted_severities == [
            Severity.CRITICAL,
            Severity.HIGH,
            Severity.MEDIUM,
            Severity.LOW
        ]

    def test_exactly_four_severity_levels(self):
        """There should be exactly 4 severity levels as per spec."""
        assert len(Severity) == 4


# =============================================================================
# CategorizedFinding Dataclass Tests
# =============================================================================

class TestCategorizedFinding:
    """Tests for CategorizedFinding dataclass."""

    def test_categorized_finding_has_content_field(self):
        """Finding should have content field."""
        finding = CategorizedFinding(
            content="Missing null check",
            severity=Severity.CRITICAL
        )
        assert finding.content == "Missing null check"

    def test_categorized_finding_has_severity_field(self):
        """Finding should have severity field."""
        finding = CategorizedFinding(
            content="Test issue",
            severity=Severity.HIGH
        )
        assert finding.severity == Severity.HIGH

    def test_categorized_finding_has_optional_file_path(self):
        """Finding should have optional file_path field."""
        finding = CategorizedFinding(
            content="Issue in file",
            severity=Severity.MEDIUM,
            file_path="/src/module.py"
        )
        assert finding.file_path == "/src/module.py"

    def test_categorized_finding_file_path_defaults_to_none(self):
        """file_path should default to None."""
        finding = CategorizedFinding(
            content="General issue",
            severity=Severity.LOW
        )
        assert finding.file_path is None


# =============================================================================
# CappingResult Dataclass Tests
# =============================================================================

class TestCappingResult:
    """Tests for CappingResult dataclass."""

    def test_capping_result_has_findings_field(self):
        """Result should have findings list."""
        result = CappingResult(
            findings=[],
            dropped_count=0,
            original_count=0
        )
        assert isinstance(result.findings, list)

    def test_capping_result_has_dropped_count(self):
        """Result should track dropped count."""
        result = CappingResult(
            findings=[],
            dropped_count=5,
            original_count=25
        )
        assert result.dropped_count == 5

    def test_capping_result_has_original_count(self):
        """Result should track original count."""
        result = CappingResult(
            findings=[],
            dropped_count=5,
            original_count=25
        )
        assert result.original_count == 25


# =============================================================================
# DEFAULT_FEEDBACK_CAP Constant Tests
# =============================================================================

class TestDefaultFeedbackCap:
    """Tests for DEFAULT_FEEDBACK_CAP constant."""

    def test_default_feedback_cap_is_20(self):
        """[REQ-2.3] Default cap should be 20 items."""
        assert DEFAULT_FEEDBACK_CAP == 20


# =============================================================================
# FeedbackCapper Init Tests
# =============================================================================

class TestFeedbackCapperInit:
    """Tests for FeedbackCapper initialization."""

    def test_feedback_capper_class_exists(self):
        """FeedbackCapper class should exist."""
        assert FeedbackCapper is not None

    def test_init_requires_logger(self):
        """Init should require logger parameter."""
        import inspect
        params = inspect.signature(FeedbackCapper.__init__).parameters
        assert 'logger' in params

    def test_init_accepts_optional_cap(self):
        """Init should accept optional cap parameter."""
        import inspect
        params = inspect.signature(FeedbackCapper.__init__).parameters
        assert 'cap' in params
        assert params['cap'].default == DEFAULT_FEEDBACK_CAP

    def test_cap_property_returns_configured_cap(self):
        """cap property should return configured value."""
        # given
        logger = create_mock_logger()

        # when
        capper = FeedbackCapper(logger=logger, cap=15)

        # then
        assert capper.cap == 15

    def test_cap_property_returns_default_when_not_specified(self):
        """cap property should return default (20) when not specified."""
        # given
        logger = create_mock_logger()

        # when
        capper = FeedbackCapper(logger=logger)

        # then
        assert capper.cap == DEFAULT_FEEDBACK_CAP


# =============================================================================
# FeedbackCapper.parse_severity Tests
# =============================================================================

class TestFeedbackCapperParseSeverity:
    """Tests for FeedbackCapper.parse_severity method."""

    def test_parse_severity_method_exists(self):
        """parse_severity method should exist."""
        assert hasattr(FeedbackCapper, 'parse_severity')

    def test_parse_severity_critical_lowercase(self):
        """[REQ-2.1] Should parse 'critical' to Severity.CRITICAL."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger())

        # when
        result = capper.parse_severity("critical")

        # then
        assert result == Severity.CRITICAL

    def test_parse_severity_critical_uppercase(self):
        """[REQ-2.1] Should parse 'CRITICAL' to Severity.CRITICAL."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger())

        # when
        result = capper.parse_severity("CRITICAL")

        # then
        assert result == Severity.CRITICAL

    def test_parse_severity_high(self):
        """[REQ-2.1] Should parse 'high' to Severity.HIGH."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger())

        # when
        result = capper.parse_severity("high")

        # then
        assert result == Severity.HIGH

    def test_parse_severity_medium(self):
        """[REQ-2.1] Should parse 'medium' to Severity.MEDIUM."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger())

        # when
        result = capper.parse_severity("medium")

        # then
        assert result == Severity.MEDIUM

    def test_parse_severity_low(self):
        """[REQ-2.1] Should parse 'low' to Severity.LOW."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger())

        # when
        result = capper.parse_severity("low")

        # then
        assert result == Severity.LOW

    def test_parse_severity_invalid_defaults_to_medium(self):
        """[ERR-2] Invalid severity string should default to MEDIUM."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger())

        # when
        result = capper.parse_severity("invalid_severity")

        # then
        assert result == Severity.MEDIUM

    def test_parse_severity_empty_string_defaults_to_medium(self):
        """[ERR-2] Empty string should default to MEDIUM."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger())

        # when
        result = capper.parse_severity("")

        # then
        assert result == Severity.MEDIUM

    def test_parse_severity_mixed_case(self):
        """Should handle mixed case like 'High' or 'CrItIcAl'."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger())

        # when
        result = capper.parse_severity("High")

        # then
        assert result == Severity.HIGH

    def test_parse_severity_with_whitespace(self):
        """Should handle whitespace around severity string."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger())

        # when
        result = capper.parse_severity("  critical  ")

        # then
        assert result == Severity.CRITICAL


# =============================================================================
# FeedbackCapper.categorize_findings Tests
# =============================================================================

class TestFeedbackCapperCategorizeFindings:
    """Tests for FeedbackCapper.categorize_findings method."""

    def test_categorize_findings_method_exists(self):
        """categorize_findings method should exist."""
        assert hasattr(FeedbackCapper, 'categorize_findings')

    def test_categorize_findings_returns_list(self):
        """Should return list of CategorizedFinding objects."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger())
        raw_issues = ["[CRITICAL] Missing null check"]

        # when
        result = capper.categorize_findings(raw_issues)

        # then
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], CategorizedFinding)

    def test_categorize_findings_extracts_severity_from_text(self):
        """[REQ-2.1] Should extract severity from issue text."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger())
        raw_issues = ["[HIGH] Variable naming could be clearer"]

        # when
        result = capper.categorize_findings(raw_issues)

        # then
        assert result[0].severity == Severity.HIGH

    def test_categorize_findings_uses_hints_when_provided(self):
        """Should use severity_hints if provided."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger())
        raw_issues = ["Some issue without tag"]
        severity_hints = ["critical"]

        # when
        result = capper.categorize_findings(raw_issues, severity_hints)

        # then
        assert result[0].severity == Severity.CRITICAL

    def test_categorize_findings_defaults_to_medium(self):
        """[ERR-2] Should default to MEDIUM when no severity can be parsed."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger())
        raw_issues = ["Issue without any severity tag"]

        # when
        result = capper.categorize_findings(raw_issues)

        # then
        assert result[0].severity == Severity.MEDIUM

    def test_categorize_findings_preserves_content(self):
        """Should preserve issue content."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger())
        raw_issues = ["[CRITICAL] Missing error handling in process_data()"]

        # when
        result = capper.categorize_findings(raw_issues)

        # then
        assert "Missing error handling" in result[0].content

    def test_categorize_findings_handles_multiple_issues(self):
        """Should handle multiple issues correctly."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger())
        raw_issues = [
            "[CRITICAL] Issue 1",
            "[HIGH] Issue 2",
            "[LOW] Issue 3"
        ]

        # when
        result = capper.categorize_findings(raw_issues)

        # then
        assert len(result) == 3
        assert result[0].severity == Severity.CRITICAL
        assert result[1].severity == Severity.HIGH
        assert result[2].severity == Severity.LOW

    def test_categorize_findings_handles_empty_list(self):
        """Should handle empty input list."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger())

        # when
        result = capper.categorize_findings([])

        # then
        assert result == []


# =============================================================================
# FeedbackCapper.apply_cap Tests
# =============================================================================

class TestFeedbackCapperApplyCap:
    """Tests for FeedbackCapper.apply_cap method."""

    def test_apply_cap_method_exists(self):
        """apply_cap method should exist."""
        assert hasattr(FeedbackCapper, 'apply_cap')

    def test_apply_cap_returns_capping_result(self):
        """Should return CappingResult."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger())
        findings = [
            CategorizedFinding(content="Issue 1", severity=Severity.HIGH)
        ]

        # when
        result = capper.apply_cap(findings)

        # then
        assert isinstance(result, CappingResult)

    def test_apply_cap_keeps_all_when_under_limit(self):
        """Should keep all findings when under cap."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger(), cap=20)
        findings = [
            CategorizedFinding(content=f"Issue {i}", severity=Severity.MEDIUM)
            for i in range(10)
        ]

        # when
        result = capper.apply_cap(findings)

        # then
        assert len(result.findings) == 10
        assert result.dropped_count == 0
        assert result.original_count == 10

    def test_apply_cap_drops_excess_when_over_limit(self):
        """[REQ-2.5] Should drop excess items when over cap."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger(), cap=20)
        findings = [
            CategorizedFinding(content=f"Issue {i}", severity=Severity.LOW)
            for i in range(25)
        ]

        # when
        result = capper.apply_cap(findings)

        # then
        assert len(result.findings) == 20
        assert result.dropped_count == 5
        assert result.original_count == 25

    def test_apply_cap_sorts_by_severity(self):
        """[REQ-2.4] Should sort by severity (critical first)."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger())
        findings = [
            CategorizedFinding(content="Low issue", severity=Severity.LOW),
            CategorizedFinding(content="Critical issue", severity=Severity.CRITICAL),
            CategorizedFinding(content="Medium issue", severity=Severity.MEDIUM),
            CategorizedFinding(content="High issue", severity=Severity.HIGH),
        ]

        # when
        result = capper.apply_cap(findings)

        # then
        assert result.findings[0].severity == Severity.CRITICAL
        assert result.findings[1].severity == Severity.HIGH
        assert result.findings[2].severity == Severity.MEDIUM
        assert result.findings[3].severity == Severity.LOW

    def test_apply_cap_keeps_critical_over_low(self):
        """[REQ-2.5] Should keep critical issues over low when capping."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger(), cap=5)
        findings = [
            CategorizedFinding(content=f"Low {i}", severity=Severity.LOW)
            for i in range(10)
        ]
        # Add 3 critical at the end (should be sorted to front)
        for i in range(3):
            findings.append(
                CategorizedFinding(content=f"Critical {i}", severity=Severity.CRITICAL)
            )

        # when
        result = capper.apply_cap(findings)

        # then
        assert len(result.findings) == 5
        # All 3 critical should be kept
        critical_count = sum(1 for f in result.findings if f.severity == Severity.CRITICAL)
        assert critical_count == 3

    def test_apply_cap_keeps_all_low_if_no_higher_severity(self):
        """[EDGE-2] Should keep low-severity items if nothing higher exists."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger(), cap=20)
        findings = [
            CategorizedFinding(content=f"Low issue {i}", severity=Severity.LOW)
            for i in range(20)
        ]

        # when
        result = capper.apply_cap(findings)

        # then
        assert len(result.findings) == 20
        assert all(f.severity == Severity.LOW for f in result.findings)
        assert result.dropped_count == 0

    def test_apply_cap_logs_when_items_dropped(self):
        """[REQ-2.6] Should log when feedback items are dropped."""
        # given
        logger = create_mock_logger()
        capper = FeedbackCapper(logger=logger, cap=5)
        findings = [
            CategorizedFinding(content=f"Issue {i}", severity=Severity.LOW)
            for i in range(10)
        ]

        # when
        capper.apply_cap(findings)

        # then
        logger.log_event.assert_called()
        # Check that the log message mentions dropped items
        call_args_list = [call[0] for call in logger.log_event.call_args_list]
        assert any("dropped" in str(args).lower() or "5" in str(args) for args in call_args_list)

    def test_apply_cap_does_not_log_when_no_items_dropped(self):
        """Should not log when no items are dropped."""
        # given
        logger = create_mock_logger()
        capper = FeedbackCapper(logger=logger, cap=20)
        findings = [
            CategorizedFinding(content=f"Issue {i}", severity=Severity.LOW)
            for i in range(5)
        ]

        # when
        capper.apply_cap(findings)

        # then
        # Either no calls or no "dropped" in any call
        if logger.log_event.called:
            call_args_list = [call[0] for call in logger.log_event.call_args_list]
            assert not any("dropped" in str(args).lower() for args in call_args_list)

    def test_apply_cap_handles_empty_list(self):
        """Should handle empty findings list."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger())

        # when
        result = capper.apply_cap([])

        # then
        assert len(result.findings) == 0
        assert result.dropped_count == 0
        assert result.original_count == 0


# =============================================================================
# FeedbackCapper.cap_and_format Tests
# =============================================================================

class TestFeedbackCapperCapAndFormat:
    """Tests for FeedbackCapper.cap_and_format convenience method."""

    def test_cap_and_format_method_exists(self):
        """cap_and_format method should exist."""
        assert hasattr(FeedbackCapper, 'cap_and_format')

    def test_cap_and_format_returns_tuple(self):
        """Should return tuple of (capped issues, dropped count)."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger())
        raw_issues = ["[HIGH] Issue 1"]

        # when
        result = capper.cap_and_format(raw_issues)

        # then
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_cap_and_format_returns_string_list(self):
        """First element should be list of strings."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger())
        raw_issues = ["[HIGH] Issue 1"]

        # when
        capped_issues, _ = capper.cap_and_format(raw_issues)

        # then
        assert isinstance(capped_issues, list)
        assert all(isinstance(issue, str) for issue in capped_issues)

    def test_cap_and_format_returns_dropped_count(self):
        """Second element should be dropped count."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger(), cap=5)
        raw_issues = [f"[LOW] Issue {i}" for i in range(10)]

        # when
        _, dropped_count = capper.cap_and_format(raw_issues)

        # then
        assert dropped_count == 5

    def test_cap_and_format_integrates_categorize_and_cap(self):
        """Should integrate categorization and capping."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger(), cap=2)
        raw_issues = [
            "[LOW] Low priority issue",
            "[CRITICAL] Critical bug",
            "[HIGH] High priority issue"
        ]

        # when
        capped_issues, dropped_count = capper.cap_and_format(raw_issues)

        # then
        assert len(capped_issues) == 2
        assert dropped_count == 1
        # Critical and High should be kept
        assert any("Critical" in issue or "critical" in issue.lower() for issue in capped_issues)
        assert any("High" in issue or "high" in issue.lower() for issue in capped_issues)


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestFeedbackCapperEdgeCases:
    """Edge case tests for FeedbackCapper."""

    def test_exactly_at_cap_limit(self):
        """Should handle exactly cap number of items."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger(), cap=20)
        findings = [
            CategorizedFinding(content=f"Issue {i}", severity=Severity.MEDIUM)
            for i in range(20)
        ]

        # when
        result = capper.apply_cap(findings)

        # then
        assert len(result.findings) == 20
        assert result.dropped_count == 0

    def test_cap_of_one(self):
        """Should work with cap of 1."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger(), cap=1)
        findings = [
            CategorizedFinding(content="Low", severity=Severity.LOW),
            CategorizedFinding(content="Critical", severity=Severity.CRITICAL),
        ]

        # when
        result = capper.apply_cap(findings)

        # then
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.CRITICAL
        assert result.dropped_count == 1

    def test_preserves_file_path_through_capping(self):
        """Should preserve file_path when capping."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger())
        findings = [
            CategorizedFinding(
                content="Issue in file",
                severity=Severity.HIGH,
                file_path="/src/module.py"
            )
        ]

        # when
        result = capper.apply_cap(findings)

        # then
        assert result.findings[0].file_path == "/src/module.py"

    def test_stable_sort_within_same_severity(self):
        """Items with same severity should maintain relative order."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger())
        findings = [
            CategorizedFinding(content="First HIGH", severity=Severity.HIGH),
            CategorizedFinding(content="Second HIGH", severity=Severity.HIGH),
            CategorizedFinding(content="Third HIGH", severity=Severity.HIGH),
        ]

        # when
        result = capper.apply_cap(findings)

        # then
        assert result.findings[0].content == "First HIGH"
        assert result.findings[1].content == "Second HIGH"
        assert result.findings[2].content == "Third HIGH"

    def test_mixed_severity_large_batch(self):
        """Should handle large batch with mixed severities correctly."""
        # given
        capper = FeedbackCapper(logger=create_mock_logger(), cap=10)
        findings = []
        # Add 5 of each severity = 20 total
        for i in range(5):
            findings.append(CategorizedFinding(content=f"Critical {i}", severity=Severity.CRITICAL))
        for i in range(5):
            findings.append(CategorizedFinding(content=f"High {i}", severity=Severity.HIGH))
        for i in range(5):
            findings.append(CategorizedFinding(content=f"Medium {i}", severity=Severity.MEDIUM))
        for i in range(5):
            findings.append(CategorizedFinding(content=f"Low {i}", severity=Severity.LOW))

        # when
        result = capper.apply_cap(findings)

        # then
        assert len(result.findings) == 10
        assert result.dropped_count == 10
        # Should keep all 5 critical and all 5 high
        critical_count = sum(1 for f in result.findings if f.severity == Severity.CRITICAL)
        high_count = sum(1 for f in result.findings if f.severity == Severity.HIGH)
        assert critical_count == 5
        assert high_count == 5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
