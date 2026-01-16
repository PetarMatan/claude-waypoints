#!/usr/bin/env python3
"""
Unit tests for wp_logging.py
"""

import os
import sys
import tempfile
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

# Add hooks/lib to path
sys.path.insert(0, 'hooks/lib')
from wp_logging import WPLogger


class TestWPLogger:
    """Tests for WPLogger class."""

    def test_init_creates_log_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"WP_INSTALL_DIR": tmpdir}):
                logger = WPLogger("test-session")
                assert logger.log_dir.exists()
                assert logger.session_log_dir.exists()

    def test_session_id_stored(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"WP_INSTALL_DIR": tmpdir}):
                logger = WPLogger("my-session-123")
                assert logger.session_id == "my-session-123"

    def test_get_timestamp_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"WP_INSTALL_DIR": tmpdir}):
                logger = WPLogger("test")
                timestamp = logger._get_timestamp()
                # Should match format: 2024-01-15 10:30:45
                assert len(timestamp) == 19
                assert timestamp[4] == '-'
                assert timestamp[10] == ' '

    def test_get_log_date_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"WP_INSTALL_DIR": tmpdir}):
                logger = WPLogger("test")
                log_date = logger._get_log_date()
                # Should match format: 2024-01-15
                assert len(log_date) == 10
                assert log_date[4] == '-'

    def test_sanitize_message_replaces_newlines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"WP_INSTALL_DIR": tmpdir}):
                logger = WPLogger("test")
                result = logger._sanitize_message("line1\nline2\nline3")
                assert result == "line1\\nline2\\nline3"

    def test_log_event_writes_to_session_log(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"WP_INSTALL_DIR": tmpdir}):
                logger = WPLogger("test-session")
                logger.log_event("TEST", "Test message")

                # Find session log
                session_logs = list(logger.session_log_dir.glob("*.log"))
                assert len(session_logs) >= 1

                content = session_logs[0].read_text()
                assert "[TEST]" in content
                assert "Test message" in content

    def test_log_event_writes_to_daily_log(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"WP_INSTALL_DIR": tmpdir}):
                logger = WPLogger("test-session")
                logger.log_event("TEST", "Daily message")

                log_date = logger._get_log_date()
                daily_log = logger.log_dir / f"{log_date}.log"
                assert daily_log.exists()

                content = daily_log.read_text()
                assert "[test-session]" in content
                assert "Daily message" in content

    def test_log_event_creates_current_symlink(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"WP_INSTALL_DIR": tmpdir}):
                logger = WPLogger("test-session")
                logger.log_event("TEST", "Message")

                current_log = logger.log_dir / "current.log"
                assert current_log.is_symlink()

    def test_log_wp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"WP_INSTALL_DIR": tmpdir}):
                logger = WPLogger("test")
                logger.log_wp("Phase transition to 2")

                session_logs = list(logger.session_log_dir.glob("*.log"))
                content = session_logs[0].read_text()
                assert "[WP]" in content
                assert "Phase transition to 2" in content

    def test_log_build(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"WP_INSTALL_DIR": tmpdir}):
                logger = WPLogger("test")
                logger.log_build("SUCCESS", "0 errors")

                session_logs = list(logger.session_log_dir.glob("*.log"))
                content = session_logs[0].read_text()
                assert "[BUILD]" in content
                assert "SUCCESS - 0 errors" in content

    def test_log_build_without_details(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"WP_INSTALL_DIR": tmpdir}):
                logger = WPLogger("test")
                logger.log_build("FAILED")

                session_logs = list(logger.session_log_dir.glob("*.log"))
                content = session_logs[0].read_text()
                assert "[BUILD] FAILED" in content

    def test_log_hook(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"WP_INSTALL_DIR": tmpdir}):
                logger = WPLogger("test")
                logger.log_hook("phase-guard", "BLOCKED", "Edit in phase 2")

                session_logs = list(logger.session_log_dir.glob("*.log"))
                content = session_logs[0].read_text()
                assert "[HOOK:phase-guard]" in content
                assert "BLOCKED - Edit in phase 2" in content

    def test_log_hook_without_details(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"WP_INSTALL_DIR": tmpdir}):
                logger = WPLogger("test")
                logger.log_hook("cleanup", "STARTED")

                session_logs = list(logger.session_log_dir.glob("*.log"))
                content = session_logs[0].read_text()
                assert "[HOOK:cleanup] STARTED" in content

    def test_log_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"WP_INSTALL_DIR": tmpdir}):
                logger = WPLogger("test")
                logger.log_error("Something went wrong")

                session_logs = list(logger.session_log_dir.glob("*.log"))
                content = session_logs[0].read_text()
                assert "[ERROR]" in content
                assert "Something went wrong" in content

    def test_log_session(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"WP_INSTALL_DIR": tmpdir}):
                logger = WPLogger("test")
                logger.log_session("STARTED")

                session_logs = list(logger.session_log_dir.glob("*.log"))
                content = session_logs[0].read_text()
                assert "[SESSION]" in content
                assert "STARTED" in content

    def test_multiple_log_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"WP_INSTALL_DIR": tmpdir}):
                logger = WPLogger("test")
                logger.log_session("START")
                logger.log_wp("Phase 1")
                logger.log_build("SUCCESS")
                logger.log_session("END")

                session_logs = list(logger.session_log_dir.glob("*.log"))
                content = session_logs[0].read_text()
                lines = content.strip().split('\n')
                assert len(lines) == 4

    def test_handles_write_errors_gracefully(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"WP_INSTALL_DIR": tmpdir}):
                logger = WPLogger("test")
                # Make log dir read-only
                logger.log_dir.chmod(0o444)
                try:
                    # Should not raise, just silently fail
                    logger.log_event("TEST", "Message")
                finally:
                    logger.log_dir.chmod(0o755)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
