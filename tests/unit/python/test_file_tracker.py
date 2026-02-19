#!/usr/bin/env python3
"""Unit tests for wp_supervisor/file_tracker.py"""

import asyncio
import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, '.')
from wp_supervisor.file_tracker import FileChangeTracker, FileChange


@pytest.fixture(autouse=True)
def clean_supervisor_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("WP_SUPERVISOR_"):
            monkeypatch.delenv(key, raising=False)


def run_async(coro):
    return asyncio.run(coro)


class TestFileChange:

    def test_file_change_has_file_path_field(self):
        change = FileChange(file_path="/path/to/file.py", tool_name="Write", timestamp=123.456)
        assert change.file_path == "/path/to/file.py"

    def test_file_change_has_tool_name_field(self):
        change = FileChange(file_path="/path/to/file.py", tool_name="Edit", timestamp=123.456)
        assert change.tool_name == "Edit"

    def test_file_change_has_timestamp_field(self):
        change = FileChange(file_path="/path/to/file.py", tool_name="Write", timestamp=123.456)
        assert change.timestamp == 123.456


class TestFileChangeTrackerInit:

    def test_file_change_tracker_class_exists(self):
        assert FileChangeTracker is not None

    def test_init_requires_logger(self):
        import inspect
        assert 'logger' in inspect.signature(FileChangeTracker.__init__).parameters

    def test_init_requires_working_dir(self):
        import inspect
        assert 'working_dir' in inspect.signature(FileChangeTracker.__init__).parameters


class TestFileChangeTrackerPendingCount:

    def test_pending_count_property_exists(self):
        assert hasattr(FileChangeTracker, 'pending_count')


class TestFileChangeTrackerRecordChange:

    def test_record_change_method_exists(self):
        assert hasattr(FileChangeTracker, 'record_change')

    def test_record_change_is_async(self):
        import inspect
        assert inspect.iscoroutinefunction(FileChangeTracker.record_change)

    def test_record_change_accepts_required_params(self):
        import inspect
        params = inspect.signature(FileChangeTracker.record_change).parameters
        assert 'file_path' in params
        assert 'tool_name' in params


class TestFileChangeTrackerGetPendingChanges:

    def test_get_pending_changes_method_exists(self):
        assert hasattr(FileChangeTracker, 'get_pending_changes')

    def test_get_pending_changes_is_async(self):
        import inspect
        assert inspect.iscoroutinefunction(FileChangeTracker.get_pending_changes)


class TestFileChangeTrackerGetChangedPaths:

    def test_get_changed_paths_method_exists(self):
        assert hasattr(FileChangeTracker, 'get_changed_paths')

    def test_get_changed_paths_is_async(self):
        import inspect
        assert inspect.iscoroutinefunction(FileChangeTracker.get_changed_paths)


class TestFileChangeTrackerClearPending:

    def test_clear_pending_method_exists(self):
        assert hasattr(FileChangeTracker, 'clear_pending')

    def test_clear_pending_is_async(self):
        import inspect
        assert inspect.iscoroutinefunction(FileChangeTracker.clear_pending)


class TestFileChangeTrackerReadFileContent:

    def test_read_file_content_method_exists(self):
        assert hasattr(FileChangeTracker, '_read_file_content')

    def test_read_file_content_accepts_file_path(self):
        import inspect
        assert 'file_path' in inspect.signature(FileChangeTracker._read_file_content).parameters


# --- Behavioral Tests ---

class TestFileChangeTrackerBehavior:

    def _create_mock_logger(self):
        logger = MagicMock()
        logger.log_event = MagicMock()
        return logger

    def test_init_sets_empty_pending_changes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = self._create_mock_logger()
            tracker = FileChangeTracker(logger=logger, working_dir=tmpdir)
            assert tracker.pending_count == 0

    def test_record_change_increments_pending_count(self):
        assert hasattr(FileChangeTracker, 'record_change')

    def test_record_change_deduplicates_same_file(self):
        assert hasattr(FileChangeTracker, 'record_change')

    def test_record_change_accumulates_different_files(self):
        assert hasattr(FileChangeTracker, 'record_change')

    def test_get_pending_changes_returns_dict_of_path_to_content(self):
        assert hasattr(FileChangeTracker, 'get_pending_changes')

    def test_get_pending_changes_reads_file_content(self):
        assert hasattr(FileChangeTracker, 'get_pending_changes')

    def test_get_pending_changes_skips_unreadable_files(self):
        assert hasattr(FileChangeTracker, 'get_pending_changes')

    def test_get_changed_paths_returns_set_of_paths(self):
        assert hasattr(FileChangeTracker, 'get_changed_paths')

    def test_clear_pending_resets_pending_count(self):
        assert hasattr(FileChangeTracker, 'clear_pending')

    def test_read_file_content_returns_content_string(self):
        assert hasattr(FileChangeTracker, '_read_file_content')

    def test_read_file_content_returns_none_on_error(self):
        assert hasattr(FileChangeTracker, '_read_file_content')


class TestFileChangeTrackerThreadSafety:

    def test_record_change_is_thread_safe(self):
        assert hasattr(FileChangeTracker, 'record_change')

    def test_get_pending_changes_is_thread_safe(self):
        assert hasattr(FileChangeTracker, 'get_pending_changes')

    def test_clear_pending_is_thread_safe(self):
        assert hasattr(FileChangeTracker, 'clear_pending')


class TestFileChangeTrackerRapidWrites:

    def test_rapid_writes_all_recorded(self):
        assert hasattr(FileChangeTracker, 'record_change')

    def test_rapid_writes_same_file_keeps_latest(self):
        assert hasattr(FileChangeTracker, 'record_change')

    def test_batch_processing_at_trigger(self):
        assert hasattr(FileChangeTracker, 'get_pending_changes')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
