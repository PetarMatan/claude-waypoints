#!/usr/bin/env python3
"""
Feedback capping and severity handling for reviewer feedback.

Implements REQ-2.x: Feedback Capping
- Severity categorization (critical, high, medium, low)
- Cap feedback at 20 items maximum
- Sort by severity and keep top items
- Log when items are dropped
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .logger import SupervisorLogger


# Severity levels ordered by priority (lower value = higher priority)
class Severity(IntEnum):
    """Feedback severity levels ordered by priority."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


# Default cap for feedback items [REQ-2.3]
DEFAULT_FEEDBACK_CAP = 20


@dataclass
class CategorizedFinding:
    """A single finding with severity categorization."""
    content: str
    severity: Severity
    file_path: Optional[str] = None


@dataclass
class CappingResult:
    """Result of applying feedback capping."""
    findings: List[CategorizedFinding]
    dropped_count: int
    original_count: int


class FeedbackCapper:
    """
    Caps and sorts reviewer feedback by severity.

    Implements:
    - [REQ-2.3] Cap feedback injection at 20 items maximum
    - [REQ-2.4] Sort feedback by severity (critical first)
    - [REQ-2.5] Keep top 20 by severity, drop remainder
    - [REQ-2.6] Log when feedback items are dropped
    - [EDGE-2] Keep low-severity items if nothing higher exists
    - [ERR-2] Default to "medium" severity on parse failures
    """

    def __init__(
        self,
        logger: "SupervisorLogger",
        cap: int = DEFAULT_FEEDBACK_CAP
    ) -> None:
        """
        Initialize the feedback capper.

        Args:
            logger: Logger for recording dropped items
            cap: Maximum number of feedback items to keep (default: 20)
        """
        self._logger = logger
        self._cap = cap

    @property
    def cap(self) -> int:
        """Return the configured feedback cap."""
        return self._cap

    def parse_severity(self, severity_str: str) -> Severity:
        """
        Parse severity string to Severity enum.

        Implements [ERR-2]: Default to MEDIUM on parse failures.

        Args:
            severity_str: Severity string from reviewer output (e.g., "critical", "HIGH")

        Returns:
            Severity enum value
        """
        normalized = severity_str.strip().lower()

        severity_map = {
            "critical": Severity.CRITICAL,
            "high": Severity.HIGH,
            "medium": Severity.MEDIUM,
            "low": Severity.LOW,
        }

        # [ERR-2] Default to MEDIUM on parse failures
        return severity_map.get(normalized, Severity.MEDIUM)

    def categorize_findings(
        self,
        raw_issues: List[str],
        severity_hints: Optional[List[str]] = None
    ) -> List[CategorizedFinding]:
        """
        Categorize raw issue strings into CategorizedFinding objects.

        Parses severity from issue text or uses hints if provided.
        Implements [ERR-2]: Default to MEDIUM when severity cannot be parsed.

        Args:
            raw_issues: List of raw issue strings from reviewer
            severity_hints: Optional list of severity strings (parallel to raw_issues)

        Returns:
            List of CategorizedFinding objects with parsed severity
        """
        import re

        findings = []
        for i, issue in enumerate(raw_issues):
            severity = Severity.MEDIUM  # Default [ERR-2]
            content = issue

            # Use hint if provided
            if severity_hints and i < len(severity_hints):
                severity = self.parse_severity(severity_hints[i])
            else:
                # Try to extract severity from issue text like [CRITICAL], [HIGH], etc.
                match = re.search(r'\[(CRITICAL|HIGH|MEDIUM|LOW)\]', issue, re.IGNORECASE)
                if match:
                    severity = self.parse_severity(match.group(1))
                    # Clean the tag from content
                    content = re.sub(r'\[(?:CRITICAL|HIGH|MEDIUM|LOW)\]\s*', '', issue, flags=re.IGNORECASE)

            findings.append(CategorizedFinding(
                content=content.strip(),
                severity=severity,
                file_path=None  # No file path extraction for now
            ))

        return findings

    def apply_cap(
        self,
        findings: List[CategorizedFinding]
    ) -> CappingResult:
        """
        Apply feedback cap, sorting by severity and keeping top items.

        Implements:
        - [REQ-2.4] Sort by severity (critical first)
        - [REQ-2.5] Keep top 20 by severity, drop remainder
        - [REQ-2.6] Log when items are dropped
        - [EDGE-2] Keep low-severity items if nothing higher

        Args:
            findings: List of categorized findings to cap

        Returns:
            CappingResult with capped findings and drop statistics
        """
        original_count = len(findings)

        if original_count == 0:
            return CappingResult(
                findings=[],
                dropped_count=0,
                original_count=0
            )

        # [REQ-2.4] Sort by severity (stable sort preserves order within same severity)
        sorted_findings = sorted(findings, key=lambda f: f.severity.value)

        # [REQ-2.5] Keep top cap items
        capped_findings = sorted_findings[:self._cap]
        dropped_count = max(0, original_count - self._cap)

        # [REQ-2.6] Log when items are dropped
        if dropped_count > 0:
            self._logger.log_event(
                "FEEDBACK",
                f"Dropped {dropped_count} low-priority feedback items (cap: {self._cap})"
            )

        return CappingResult(
            findings=capped_findings,
            dropped_count=dropped_count,
            original_count=original_count
        )

    def cap_and_format(
        self,
        raw_issues: List[str],
        severity_hints: Optional[List[str]] = None
    ) -> tuple[List[str], int]:
        """
        Convenience method: categorize, cap, and return formatted issues.

        Args:
            raw_issues: List of raw issue strings from reviewer
            severity_hints: Optional list of severity strings

        Returns:
            Tuple of (capped issue strings, number of dropped items)
        """
        # Categorize
        findings = self.categorize_findings(raw_issues, severity_hints)

        # Apply cap
        result = self.apply_cap(findings)

        # Format back to strings
        formatted_issues = [f.content for f in result.findings]

        return (formatted_issues, result.dropped_count)
