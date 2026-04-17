#!/usr/bin/env python3
"""
Unit tests for wp_supervisor/stdin_reader.py - StdinInterruptReader class

Tests for the background stdin reader that captures developer input during
Claude streaming for injection at the next natural break point.

Covers:
- StdinInterruptReader lifecycle (start/stop)
- Queue draining and concatenation (drain)
- Edge cases: empty queue, whitespace-only, EOF, multiple lines
- Thread safety and daemon thread behavior
- is_running property
"""

import os
import sys
import queue
import threading
import pytest
from unittest.mock import patch, MagicMock

# Mock claude_agent_sdk before importing (follows existing pattern)
from dataclasses import dataclass
from typing import Optional

mock_sdk = MagicMock()
mock_sdk.ClaudeSDKClient = MagicMock()
mock_sdk.ClaudeAgentOptions = MagicMock()
mock_types = MagicMock()
mock_sdk.types = mock_types
sys.modules['claude_agent_sdk'] = mock_sdk
sys.modules['claude_agent_sdk.types'] = mock_types

sys.path.insert(0, '.')
from wp_supervisor.stdin_reader import StdinInterruptReader


@pytest.fixture(autouse=True)
def clean_supervisor_env(monkeypatch):
    """Remove WP_SUPERVISOR_* env vars to isolate tests from live workflows."""
    for key in list(os.environ):
        if key.startswith("WP_SUPERVISOR_"):
            monkeypatch.delenv(key, raising=False)


# =============================================================================
# INITIALIZATION
# =============================================================================


class TestStdinInterruptReaderInit:
    """Tests for StdinInterruptReader initialization."""

    def test_class_exists(self):
        """StdinInterruptReader class should exist and be importable."""
        assert StdinInterruptReader is not None

    def test_init_creates_empty_queue(self):
        """__init__ should create an empty queue."""
        reader = StdinInterruptReader()
        assert reader._queue is not None
        assert reader._queue.empty()

    def test_init_creates_stop_event(self):
        """__init__ should create a threading.Event for stop signaling."""
        reader = StdinInterruptReader()
        assert reader._stop_event is not None
        assert isinstance(reader._stop_event, threading.Event)

    def test_init_thread_is_none(self):
        """__init__ should set _thread to None (not running)."""
        reader = StdinInterruptReader()
        assert reader._thread is None

    def test_is_running_false_initially(self):
        """is_running should be False before start() is called."""
        reader = StdinInterruptReader()
        assert reader.is_running is False


# =============================================================================
# START BEHAVIOR
# =============================================================================


class TestStdinInterruptReaderStart:
    """Tests for StdinInterruptReader.start() method."""

    def test_start_sets_thread(self):
        """start() should create a background thread."""
        reader = StdinInterruptReader()

        # given - mock stdin to avoid blocking
        with patch('select.select', return_value=([], [], [])):
            reader.start()

            # then
            try:
                assert reader._thread is not None
                assert reader.is_running is True
            finally:
                reader.stop()

    def test_start_creates_daemon_thread(self):
        """start() should create a daemon thread so it doesn't block process exit."""
        reader = StdinInterruptReader()

        with patch('select.select', return_value=([], [], [])):
            reader.start()

            # then
            try:
                assert reader._thread.daemon is True
            finally:
                reader.stop()

    def test_start_clears_stop_event(self):
        """start() should clear the stop event so the thread can run."""
        reader = StdinInterruptReader()
        reader._stop_event.set()  # simulate previous stop

        with patch('select.select', return_value=([], [], [])):
            reader.start()

            # then
            try:
                assert not reader._stop_event.is_set()
            finally:
                reader.stop()

    def test_start_clears_stale_queue_items(self):
        """start() should clear any stale items from the queue."""
        reader = StdinInterruptReader()
        reader._queue.put("stale line")

        with patch('select.select', return_value=([], [], [])):
            reader.start()

            # then
            try:
                assert reader._queue.empty()
            finally:
                reader.stop()

    def test_start_noop_if_already_running(self):
        """start() should be a no-op if the reader is already running."""
        reader = StdinInterruptReader()

        with patch('select.select', return_value=([], [], [])):
            reader.start()
            first_thread = reader._thread

            # when - call start again
            reader.start()

            # then - should be the same thread
            try:
                assert reader._thread is first_thread
            finally:
                reader.stop()


# =============================================================================
# STOP BEHAVIOR
# =============================================================================


class TestStdinInterruptReaderStop:
    """Tests for StdinInterruptReader.stop() method."""

    def test_stop_sets_stop_event(self):
        """stop() should set the stop event to signal the thread."""
        reader = StdinInterruptReader()

        with patch('select.select', return_value=([], [], [])):
            reader.start()
            reader.stop()

            # then
            assert reader._stop_event.is_set()

    def test_stop_clears_thread_reference(self):
        """stop() should set _thread to None after stopping."""
        reader = StdinInterruptReader()

        with patch('select.select', return_value=([], [], [])):
            reader.start()
            reader.stop()

            # then
            assert reader._thread is None

    def test_stop_noop_when_not_running(self):
        """stop() should be a no-op when reader is not running."""
        reader = StdinInterruptReader()

        # when/then - should not raise
        reader.stop()
        assert reader._thread is None

    def test_is_running_false_after_stop(self):
        """is_running should be False after stop() is called."""
        reader = StdinInterruptReader()

        with patch('select.select', return_value=([], [], [])):
            reader.start()
            assert reader.is_running is True

            reader.stop()

            # then
            assert reader.is_running is False


# =============================================================================
# DRAIN BEHAVIOR
# =============================================================================


class TestStdinInterruptReaderDrain:
    """Tests for StdinInterruptReader.drain() method."""

    def test_drain_returns_none_when_queue_empty(self):
        """drain() should return None when the queue is empty [EDGE-1]."""
        reader = StdinInterruptReader()

        # when
        result = reader.drain()

        # then
        assert result is None

    def test_drain_returns_single_line(self):
        """drain() should return a single queued line."""
        reader = StdinInterruptReader()
        reader._queue.put("hello world")

        # when
        result = reader.drain()

        # then
        assert result == "hello world"

    def test_drain_concatenates_multiple_lines_with_newline(self):
        """drain() should join multiple queued lines with newline [REQ-7]."""
        reader = StdinInterruptReader()
        reader._queue.put("line one")
        reader._queue.put("line two")
        reader._queue.put("line three")

        # when
        result = reader.drain()

        # then
        assert result == "line one\nline two\nline three"

    def test_drain_clears_queue(self):
        """drain() should clear the queue after draining."""
        reader = StdinInterruptReader()
        reader._queue.put("some input")

        # when
        reader.drain()

        # then
        assert reader._queue.empty()

    def test_drain_clears_queue_even_when_returning_none(self):
        """drain() should clear queue even when returning None [EDGE-4]."""
        reader = StdinInterruptReader()
        reader._queue.put("   ")  # whitespace only

        # when
        result = reader.drain()

        # then
        assert result is None
        assert reader._queue.empty()

    def test_drain_returns_none_for_whitespace_only_input(self):
        """drain() should return None if queue contains only whitespace [EDGE-4]."""
        reader = StdinInterruptReader()
        reader._queue.put("   ")
        reader._queue.put("\t")
        reader._queue.put("")

        # when
        result = reader.drain()

        # then
        assert result is None

    def test_drain_returns_none_for_empty_strings(self):
        """drain() should return None if queue contains only empty strings [EDGE-4]."""
        reader = StdinInterruptReader()
        reader._queue.put("")
        reader._queue.put("")

        # when
        result = reader.drain()

        # then
        assert result is None

    def test_drain_preserves_content_with_mixed_whitespace(self):
        """drain() should return content even if some lines are whitespace."""
        reader = StdinInterruptReader()
        reader._queue.put("")
        reader._queue.put("actual content")
        reader._queue.put("")

        # when
        result = reader.drain()

        # then - result should contain the actual content
        assert result is not None
        assert "actual content" in result

    def test_drain_consecutive_calls_return_none_after_first(self):
        """Second drain() call should return None since queue was cleared."""
        reader = StdinInterruptReader()
        reader._queue.put("some input")

        # when
        first = reader.drain()
        second = reader.drain()

        # then
        assert first is not None
        assert second is None


# =============================================================================
# READER THREAD BEHAVIOR
# =============================================================================


class TestStdinInterruptReaderThreadBehavior:
    """Tests for the background reader thread behavior."""

    def test_reader_enqueues_stdin_lines(self):
        """Background thread should enqueue lines read from stdin."""
        reader = StdinInterruptReader()

        # given - mock stdin with select returning readable
        mock_stdin = MagicMock()
        mock_stdin.readline.side_effect = ["test line\n", ""]  # line then EOF

        call_count = [0]
        def mock_select(rlist, wlist, xlist, timeout):
            call_count[0] += 1
            if call_count[0] == 1:
                return ([mock_stdin], [], [])
            return ([], [], [])

        with patch('select.select', side_effect=mock_select):
            with patch('sys.stdin', mock_stdin):
                reader.start()
                # Give thread time to read
                import time
                time.sleep(0.3)
                reader.stop()

        # then
        result = reader.drain()
        assert result is not None
        assert "test line" in result

    def test_reader_handles_eof_gracefully(self):
        """Background thread should exit gracefully on EOF [ERR-1]."""
        reader = StdinInterruptReader()

        # given - mock stdin that returns empty string (EOF)
        mock_stdin = MagicMock()
        mock_stdin.readline.return_value = ""  # EOF

        def mock_select(rlist, wlist, xlist, timeout):
            return ([mock_stdin], [], [])

        with patch('select.select', side_effect=mock_select):
            with patch('sys.stdin', mock_stdin):
                reader.start()
                import time
                time.sleep(0.3)

        # then - thread should have exited, no crash
        # Reader may or may not still report running (thread exited naturally)
        reader.stop()  # cleanup, should not raise

    def test_reader_stops_when_stop_event_set(self):
        """Background thread should stop when stop event is set."""
        reader = StdinInterruptReader()

        with patch('select.select', return_value=([], [], [])):
            reader.start()
            assert reader.is_running is True

            # when
            reader.stop()

            # then
            assert reader.is_running is False


# =============================================================================
# ERROR HANDLING
# =============================================================================


class TestStdinInterruptReaderErrors:
    """Tests for error handling in StdinInterruptReader [ERR-1]."""

    def test_stdin_read_error_does_not_crash(self):
        """stdin read failure should not crash the reader [ERR-1]."""
        reader = StdinInterruptReader()

        # given - mock stdin that raises an error
        mock_stdin = MagicMock()
        mock_stdin.readline.side_effect = IOError("stdin read error")

        def mock_select(rlist, wlist, xlist, timeout):
            return ([mock_stdin], [], [])

        with patch('select.select', side_effect=mock_select):
            with patch('sys.stdin', mock_stdin):
                reader.start()
                import time
                time.sleep(0.3)
                reader.stop()

        # then - should not have crashed, drain returns None
        result = reader.drain()
        # Result may be None (no successful reads) or contain partial data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
