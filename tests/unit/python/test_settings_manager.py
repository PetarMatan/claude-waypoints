#!/usr/bin/env python3
"""
Unit tests for settings_manager.py

Tests the settings.json management functions for install/uninstall.
"""

import json
import os
import sys
import tempfile
import pytest
from unittest.mock import patch

# Add the hooks/lib directory to the path
sys.path.insert(0, 'hooks/lib')
from settings_manager import (
    WP_PERMISSIONS,
    get_wp_hooks,
    atomic_write,
    validate_settings,
    add_wp_settings,
    remove_wp_settings,
)


class TestGetWpHooks:
    """Tests for get_wp_hooks function."""

    def test_returns_all_hook_events(self):
        hooks = get_wp_hooks('/install/dir')

        assert 'PreToolUse' in hooks
        assert 'PostToolUse' in hooks
        assert 'Stop' in hooks
        assert 'SessionEnd' in hooks

    def test_uses_install_dir_in_commands(self):
        hooks = get_wp_hooks('/custom/path')

        # First PreToolUse hook is wp-activation.py (Bash matcher)
        activation_cmd = hooks['PreToolUse'][0]['hooks'][0]['command']
        assert '/custom/path/hooks/wp-activation.py' in activation_cmd

        # Second PreToolUse hook is wp-phase-guard.py (Write|Edit matcher)
        phase_guard_cmd = hooks['PreToolUse'][1]['hooks'][0]['command']
        assert '/custom/path/hooks/wp-phase-guard.py' in phase_guard_cmd

    def test_pre_tool_use_has_correct_matchers(self):
        hooks = get_wp_hooks('/dir')

        # First hook matches Bash for activation
        assert hooks['PreToolUse'][0]['matcher'] == 'Bash'
        # Second hook matches Write|Edit for phase guard
        assert hooks['PreToolUse'][1]['matcher'] == 'Write|Edit'

    def test_post_tool_use_has_two_hooks(self):
        hooks = get_wp_hooks('/dir')

        assert len(hooks['PostToolUse']) == 2

    def test_stop_hook_has_orchestrator(self):
        hooks = get_wp_hooks('/dir')

        cmd = hooks['Stop'][0]['hooks'][0]['command']
        assert 'wp-orchestrator.py' in cmd

    def test_session_end_has_cleanup(self):
        hooks = get_wp_hooks('/dir')

        cmd = hooks['SessionEnd'][0]['hooks'][0]['command']
        assert 'wp-cleanup-markers.py' in cmd

    def test_hooks_have_timeouts(self):
        hooks = get_wp_hooks('/dir')

        for event, hook_list in hooks.items():
            for hook_config in hook_list:
                for hook in hook_config['hooks']:
                    assert 'timeout' in hook
                    assert isinstance(hook['timeout'], int)


class TestAtomicWrite:
    """Tests for atomic_write function."""

    def test_writes_json_to_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'test.json')
            data = {'key': 'value'}

            atomic_write(filepath, data)

            with open(filepath) as f:
                result = json.load(f)
            assert result == data

    def test_overwrites_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'test.json')

            # Write initial data
            with open(filepath, 'w') as f:
                json.dump({'old': 'data'}, f)

            # Atomic write new data
            atomic_write(filepath, {'new': 'data'})

            with open(filepath) as f:
                result = json.load(f)
            assert result == {'new': 'data'}

    def test_writes_formatted_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'test.json')

            atomic_write(filepath, {'key': 'value'})

            with open(filepath) as f:
                content = f.read()
            # Should be indented (not single line)
            assert '\n' in content

    def test_no_temp_file_left_behind(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'test.json')

            atomic_write(filepath, {'key': 'value'})

            files = os.listdir(tmpdir)
            assert files == ['test.json']


class TestValidateSettings:
    """Tests for validate_settings function."""

    def test_valid_json_returns_true(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({'valid': 'json'}, f)
            filepath = f.name

        try:
            assert validate_settings(filepath) is True
        finally:
            os.unlink(filepath)

    def test_invalid_json_returns_false(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('not valid json {')
            filepath = f.name

        try:
            assert validate_settings(filepath) is False
        finally:
            os.unlink(filepath)

    def test_missing_file_returns_false(self):
        assert validate_settings('/nonexistent/path.json') is False

    def test_empty_file_returns_false(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name

        try:
            assert validate_settings(filepath) is False
        finally:
            os.unlink(filepath)


class TestAddWpSettings:
    """Tests for add_wp_settings function."""

    def test_adds_permissions_to_empty_settings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'settings.json')
            with open(filepath, 'w') as f:
                json.dump({}, f)

            add_wp_settings(filepath, '/install/dir')

            with open(filepath) as f:
                result = json.load(f)

            assert 'permissions' in result
            assert 'allow' in result['permissions']
            for perm in WP_PERMISSIONS:
                assert perm in result['permissions']['allow']

    def test_adds_hooks_to_empty_settings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'settings.json')
            with open(filepath, 'w') as f:
                json.dump({}, f)

            add_wp_settings(filepath, '/install/dir')

            with open(filepath) as f:
                result = json.load(f)

            assert 'hooks' in result
            assert 'PreToolUse' in result['hooks']
            assert 'PostToolUse' in result['hooks']
            assert 'Stop' in result['hooks']
            assert 'SessionEnd' in result['hooks']

    def test_preserves_existing_permissions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'settings.json')
            with open(filepath, 'w') as f:
                json.dump({
                    'permissions': {
                        'allow': ['Bash(git:*)']
                    }
                }, f)

            add_wp_settings(filepath, '/install/dir')

            with open(filepath) as f:
                result = json.load(f)

            assert 'Bash(git:*)' in result['permissions']['allow']

    def test_preserves_existing_hooks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'settings.json')
            with open(filepath, 'w') as f:
                json.dump({
                    'hooks': {
                        'PreToolUse': [{
                            'matcher': 'Bash',
                            'hooks': [{'type': 'command', 'command': 'echo test'}]
                        }]
                    }
                }, f)

            add_wp_settings(filepath, '/install/dir')

            with open(filepath) as f:
                result = json.load(f)

            # Should have both existing and new hooks
            pre_tool_hooks = result['hooks']['PreToolUse']
            commands = [h['hooks'][0]['command'] for h in pre_tool_hooks]
            assert 'echo test' in commands
            assert any('wp-phase-guard' in cmd for cmd in commands)

    def test_does_not_duplicate_hooks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'settings.json')
            with open(filepath, 'w') as f:
                json.dump({}, f)

            # Add twice
            add_wp_settings(filepath, '/install/dir')
            add_wp_settings(filepath, '/install/dir')

            with open(filepath) as f:
                result = json.load(f)

            # Should only have one of each WP hook
            pre_tool_hooks = result['hooks']['PreToolUse']
            phase_guard_count = sum(
                1 for h in pre_tool_hooks
                if 'wp-phase-guard' in h['hooks'][0]['command']
            )
            assert phase_guard_count == 1

    def test_does_not_duplicate_permissions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'settings.json')
            with open(filepath, 'w') as f:
                json.dump({}, f)

            # Add twice
            add_wp_settings(filepath, '/install/dir')
            add_wp_settings(filepath, '/install/dir')

            with open(filepath) as f:
                result = json.load(f)

            # Count occurrences of first WP permission
            count = result['permissions']['allow'].count(WP_PERMISSIONS[0])
            assert count == 1

    def test_preserves_other_settings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'settings.json')
            with open(filepath, 'w') as f:
                json.dump({
                    'model': 'claude-3',
                    'customKey': {'nested': 'value'}
                }, f)

            add_wp_settings(filepath, '/install/dir')

            with open(filepath) as f:
                result = json.load(f)

            assert result['model'] == 'claude-3'
            assert result['customKey'] == {'nested': 'value'}

    def test_preserves_complex_nested_structures(self):
        """Should preserve complex nested structures like deny permissions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'settings.json')
            with open(filepath, 'w') as f:
                json.dump({
                    'model': 'claude-3-opus',
                    'permissions': {
                        'allow': ['Bash(git:*)'],
                        'deny': ['Bash(rm -rf:*)']
                    },
                    'hooks': {
                        'PreToolUse': [{
                            'matcher': 'Read',
                            'hooks': [{'type': 'command', 'command': 'echo read', 'timeout': 1000}]
                        }]
                    },
                    'customSettings': {
                        'nested': {
                            'deeply': {
                                'value': 42
                            }
                        }
                    }
                }, f)

            add_wp_settings(filepath, '/install/dir')

            with open(filepath) as f:
                result = json.load(f)

            # Verify complex structure preserved
            assert result['customSettings']['nested']['deeply']['value'] == 42
            # Verify deny preserved
            assert 'Bash(rm -rf:*)' in result['permissions']['deny']
            # Verify model preserved
            assert result['model'] == 'claude-3-opus'
            # Verify existing hook preserved
            assert any('echo read' in str(h) for h in result['hooks']['PreToolUse'])

    def test_hook_structure_is_correct(self):
        """Should create hooks with correct structure including matchers and timeouts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'settings.json')
            with open(filepath, 'w') as f:
                json.dump({}, f)

            add_wp_settings(filepath, '/install/dir')

            with open(filepath) as f:
                result = json.load(f)

            # Verify PreToolUse activation hook structure (first hook)
            activation_hook = result['hooks']['PreToolUse'][0]
            assert activation_hook['matcher'] == 'Bash'
            assert activation_hook['hooks'][0]['type'] == 'command'
            assert 'wp-activation.py' in activation_hook['hooks'][0]['command']
            assert activation_hook['hooks'][0]['timeout'] == 5000

            # Verify PreToolUse phase-guard hook structure (second hook)
            phase_guard_hook = result['hooks']['PreToolUse'][1]
            assert phase_guard_hook['matcher'] == 'Write|Edit'
            assert phase_guard_hook['hooks'][0]['type'] == 'command'
            assert 'wp-phase-guard.py' in phase_guard_hook['hooks'][0]['command']
            assert phase_guard_hook['hooks'][0]['timeout'] == 5000

            # Verify PostToolUse auto-compile hook structure
            post_tool_compile = result['hooks']['PostToolUse'][0]
            assert post_tool_compile['matcher'] == 'Write|Edit'
            assert 'wp-auto-compile.py' in post_tool_compile['hooks'][0]['command']
            assert post_tool_compile['hooks'][0]['timeout'] == 120000

            # Verify PostToolUse auto-test hook structure
            post_tool_test = result['hooks']['PostToolUse'][1]
            assert post_tool_test['matcher'] == 'Write|Edit'
            assert 'wp-auto-test.py' in post_tool_test['hooks'][0]['command']
            assert post_tool_test['hooks'][0]['timeout'] == 300000

            # Verify Stop hook structure (no matcher)
            stop_hook = result['hooks']['Stop'][0]
            assert 'matcher' not in stop_hook
            assert 'wp-orchestrator.py' in stop_hook['hooks'][0]['command']
            assert stop_hook['hooks'][0]['timeout'] == 120000

            # Verify SessionEnd hook structure (no matcher)
            session_end_hook = result['hooks']['SessionEnd'][0]
            assert 'matcher' not in session_end_hook
            assert 'wp-cleanup-markers.py' in session_end_hook['hooks'][0]['command']
            assert session_end_hook['hooks'][0]['timeout'] == 5000

    def test_fails_gracefully_on_invalid_json(self):
        """Should raise error on invalid JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'settings.json')
            with open(filepath, 'w') as f:
                f.write('not valid json')

            with pytest.raises(json.JSONDecodeError):
                add_wp_settings(filepath, '/install/dir')


class TestRemoveWpSettings:
    """Tests for remove_wp_settings function."""

    def test_removes_wp_permissions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'settings.json')
            with open(filepath, 'w') as f:
                json.dump({
                    'permissions': {
                        'allow': [
                            'Bash(git:*)',
                            'Bash(mkdir -p ~/.claude/tmp:*)',
                            'Bash(touch ~/.claude/tmp/:*)',
                        ]
                    }
                }, f)

            remove_wp_settings(filepath)

            with open(filepath) as f:
                result = json.load(f)

            # Should keep non-WP permissions
            assert 'Bash(git:*)' in result['permissions']['allow']
            # Should remove WP permissions
            assert 'Bash(mkdir -p ~/.claude/tmp:*)' not in result['permissions']['allow']

    def test_removes_wp_hooks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'settings.json')
            with open(filepath, 'w') as f:
                json.dump({
                    'hooks': {
                        'PreToolUse': [
                            {
                                'matcher': 'Bash',
                                'hooks': [{'command': 'echo test'}]
                            },
                            {
                                'matcher': 'Write|Edit',
                                'hooks': [{'command': 'python3 /path/wp-phase-guard.py'}]
                            }
                        ]
                    }
                }, f)

            remove_wp_settings(filepath)

            with open(filepath) as f:
                result = json.load(f)

            # Should keep non-WP hooks
            pre_tool_hooks = result['hooks']['PreToolUse']
            assert len(pre_tool_hooks) == 1
            assert pre_tool_hooks[0]['hooks'][0]['command'] == 'echo test'

    def test_removes_empty_hook_events(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'settings.json')
            with open(filepath, 'w') as f:
                json.dump({
                    'hooks': {
                        'PreToolUse': [
                            {
                                'matcher': 'Write|Edit',
                                'hooks': [{'command': 'python3 /path/wp-phase-guard.py'}]
                            }
                        ],
                        'Stop': [
                            {
                                'hooks': [{'command': 'python3 /path/wp-orchestrator.py'}]
                            }
                        ]
                    }
                }, f)

            remove_wp_settings(filepath)

            with open(filepath) as f:
                result = json.load(f)

            # Empty events should be removed
            assert 'PreToolUse' not in result['hooks']
            assert 'Stop' not in result['hooks']

    def test_preserves_other_settings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'settings.json')
            with open(filepath, 'w') as f:
                json.dump({
                    'model': 'claude-3',
                    'permissions': {'allow': []},
                    'hooks': {}
                }, f)

            remove_wp_settings(filepath)

            with open(filepath) as f:
                result = json.load(f)

            assert result['model'] == 'claude-3'

    def test_handles_missing_permissions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'settings.json')
            with open(filepath, 'w') as f:
                json.dump({'model': 'claude-3'}, f)

            # Should not raise
            remove_wp_settings(filepath)

            with open(filepath) as f:
                result = json.load(f)
            assert result['model'] == 'claude-3'

    def test_handles_missing_hooks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'settings.json')
            with open(filepath, 'w') as f:
                json.dump({'permissions': {'allow': []}}, f)

            # Should not raise
            remove_wp_settings(filepath)


class TestMainCLI:
    """Tests for the CLI interface."""

    def test_validate_command_valid_file(self, capsys):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({'valid': 'json'}, f)
            filepath = f.name

        try:
            with patch('sys.argv', ['settings_manager.py', 'validate', filepath]):
                with pytest.raises(SystemExit) as exc_info:
                    from settings_manager import main
                    main()
                # Exit code 0 means success
                assert exc_info.value.code == 0

            captured = capsys.readouterr()
            assert 'valid' in captured.out.lower()
        finally:
            os.unlink(filepath)

    def test_validate_command_invalid_file(self, capsys):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('not json')
            filepath = f.name

        try:
            with patch('sys.argv', ['settings_manager.py', 'validate', filepath]):
                with pytest.raises(SystemExit) as exc_info:
                    from settings_manager import main
                    main()
                assert exc_info.value.code == 1
        finally:
            os.unlink(filepath)

    def test_add_command(self, capsys):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'settings.json')
            with open(filepath, 'w') as f:
                json.dump({}, f)

            with patch('sys.argv', ['settings_manager.py', 'add', filepath, '/install/dir']):
                from settings_manager import main
                main()

            with open(filepath) as f:
                result = json.load(f)
            assert 'hooks' in result

    def test_remove_command(self, capsys):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, 'settings.json')
            with open(filepath, 'w') as f:
                json.dump({
                    'hooks': {
                        'Stop': [{'hooks': [{'command': 'python3 wp-orchestrator.py'}]}]
                    }
                }, f)

            with patch('sys.argv', ['settings_manager.py', 'remove', filepath]):
                from settings_manager import main
                main()

            with open(filepath) as f:
                result = json.load(f)
            assert 'Stop' not in result.get('hooks', {})

    def test_unknown_command_exits_with_error(self):
        with patch('sys.argv', ['settings_manager.py', 'unknown', '/path']):
            with pytest.raises(SystemExit) as exc_info:
                from settings_manager import main
                main()
            assert exc_info.value.code == 1

    def test_missing_args_exits_with_error(self):
        with patch('sys.argv', ['settings_manager.py']):
            with pytest.raises(SystemExit) as exc_info:
                from settings_manager import main
                main()
            assert exc_info.value.code == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
