#!/usr/bin/env python3
"""
Waypoints Supervisor - Hook Callbacks

Provides hook callback functions for SDK-spawned Claude sessions.
Reuses logic from hooks/lib/ (WPConfig for pattern matching).
"""

import sys
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

# Add hooks/lib to path for imports
_hooks_lib = Path(__file__).parent.parent / "hooks" / "lib"
if str(_hooks_lib) not in sys.path:
    sys.path.insert(0, str(_hooks_lib))

from wp_config import WPConfig
from .hook_messages import (
    get_phase_block_reason,
    get_log_reason,
    format_compile_error,
    format_test_failure,
)

if TYPE_CHECKING:
    from .logger import SupervisorLogger
    from .markers import SupervisorMarkers


class SupervisorHooks:
    """
    Hook callbacks for supervisor-spawned Claude sessions.

    Replicates CLI hook behavior:
    - Phase guard: blocks writes that don't match current phase
    - Logging: logs tool uses to workflow.log
    """

    def __init__(
        self,
        markers: "SupervisorMarkers",
        logger: "SupervisorLogger",
        working_dir: str
    ):
        self.markers = markers
        self.logger = logger
        self.config = WPConfig(working_dir)

    # --- Response Helpers ---

    def _get_file_path(self, input_data: Dict[str, Any]) -> Optional[str]:
        """Extract file path from tool input."""
        tool_input = input_data.get("tool_input", {})
        return tool_input.get("file_path") if isinstance(tool_input, dict) else None

    def _deny(self, hook_event_name: str, reason: str) -> Dict[str, Any]:
        """Create a deny response."""
        return {
            "hookSpecificOutput": {
                "hookEventName": hook_event_name,
                "permissionDecision": "deny",
                "permissionDecisionReason": reason
            }
        }

    def _allow(self) -> Dict[str, Any]:
        """Create an allow response (empty dict)."""
        return {}

    # --- Hook Callbacks ---

    async def phase_guard(
        self,
        input_data: Dict[str, Any],
        tool_use_id: Optional[str],
        context: Any
    ) -> Dict[str, Any]:
        """
        Phase guard - blocks file edits that don't match current phase.

        Phase rules:
        - Phase 1: Block all source edits
        - Phase 2: Block test edits
        - Phase 3: Block main source edits (allow tests)
        - Phase 4: Allow all

        Note: Uses run_in_executor for blocking I/O to avoid blocking event loop.
        """
        import asyncio

        try:
            tool_name = input_data.get("tool_name", "")
            if tool_name not in ("Write", "Edit"):
                return self._allow()

            file_path = self._get_file_path(input_data)
            if not file_path:
                return self._allow()

            # Run blocking I/O in executor to avoid blocking event loop
            loop = asyncio.get_running_loop()

            phase = await loop.run_in_executor(None, self.markers.get_phase)
            hook_event = input_data.get("hook_event_name", "PreToolUse")

            is_main = await loop.run_in_executor(None, self.config.is_main_source, file_path)
            is_test = await loop.run_in_executor(None, self.config.is_test_source, file_path)
            is_config = await loop.run_in_executor(None, self.config.is_config_file, file_path)

            should_block = False

            if phase == 1 and (is_main or is_test):
                should_block = True
            elif phase == 2 and is_test:
                should_block = True
            elif phase == 3 and is_main and not is_test and not is_config:
                should_block = True

            if should_block:
                log_reason = get_log_reason(phase)
                # Log in executor too
                await loop.run_in_executor(
                    None,
                    self.logger.log_wp,
                    f"Phase {phase}: Blocked {file_path} - {log_reason}"
                )
                return self._deny(hook_event, get_phase_block_reason(phase))

            return self._allow()
        except Exception as e:
            try:
                self.logger.log_event("HOOK_ERROR", f"phase_guard exception: {e}")
            except:
                pass
            return self._allow()  # Allow on error to not break workflow

    async def log_tool_use(
        self,
        input_data: Dict[str, Any],
        tool_use_id: Optional[str],
        context: Any
    ) -> Dict[str, Any]:
        """
        Logging hook - logs tool uses to workflow.log.

        Note: Uses run_in_executor for blocking I/O to avoid blocking event loop.
        """
        import asyncio

        try:
            hook_event = input_data.get("hook_event_name", "")
            tool_name = input_data.get("tool_name", "")

            if hook_event == "PreToolUse":
                loop = asyncio.get_running_loop()
                file_path = self._get_file_path(input_data)
                if file_path:
                    await loop.run_in_executor(
                        None,
                        self.logger.log_event,
                        "TOOL",
                        f"{tool_name}: {file_path}"
                    )
                else:
                    tool_input = input_data.get("tool_input", {})
                    if isinstance(tool_input, dict):
                        cmd = tool_input.get("command", "")
                        if cmd:
                            preview = (cmd[:50] + "...") if len(cmd) > 50 else cmd
                            await loop.run_in_executor(
                                None,
                                self.logger.log_event,
                                "TOOL",
                                f"{tool_name}: {preview}"
                            )
                        else:
                            await loop.run_in_executor(
                                None,
                                self.logger.log_event,
                                "TOOL",
                                tool_name
                            )

            return self._allow()
        except Exception as e:
            # Log error but don't break workflow
            try:
                self.logger.log_event("HOOK_ERROR", f"log_tool_use exception: {e}")
            except:
                pass
            return self._allow()

    # --- Build Verification Hook ---

    def _run_command(self, cmd: str, cwd: str, timeout: int = 120) -> tuple:
        """Run a shell command and return (exit_code, output)."""
        import subprocess
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=cwd
            )
            return result.returncode, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return 1, f"Command timed out after {timeout} seconds"
        except Exception as e:
            return 1, f"Command error: {e}"

    def _has_placeholder(self, cmd: str) -> bool:
        """Check if command has unreplaced placeholders."""
        placeholders = ["{file}", "{testClass}", "{testName}", "{testFile}"]
        return any(p in cmd for p in placeholders)

    async def build_verify(
        self,
        input_data: Dict[str, Any],
        tool_use_id: Optional[str],
        context: Any
    ) -> Dict[str, Any]:
        """
        Build verification hook (Stop) - runs compile/test before phase completion.

        Phase behavior:
        - Phase 1: No verification
        - Phase 2: Run compile command
        - Phase 3: Run test compile command
        - Phase 4: Run compile + full test suite
        """
        import asyncio

        try:
            if input_data.get("stop_hook_active"):
                return self._allow()

            loop = asyncio.get_running_loop()
            phase = await loop.run_in_executor(None, self.markers.get_phase)

            if phase == 1:
                return self._allow()

            cwd = input_data.get("cwd", "")
            if not cwd:
                return self._allow()

            profile = await loop.run_in_executor(None, self.config.get_profile_name)
            compile_cmd = await loop.run_in_executor(None, self.config.get_command, "compile")
            test_compile_cmd = await loop.run_in_executor(None, self.config.get_command, "testCompile")
            test_cmd = await loop.run_in_executor(None, self.config.get_command, "test")

            await loop.run_in_executor(
                None, self.logger.log_event, "BUILD",
                f"Phase {phase} stop hook triggered (profile: {profile})"
            )

            # Phase 2: Verify interfaces compile
            if phase == 2 and compile_cmd and not self._has_placeholder(compile_cmd):
                await loop.run_in_executor(None, self.logger.log_event, "BUILD", f"Running: {compile_cmd}")
                code, out = await loop.run_in_executor(None, self._run_command, compile_cmd, cwd)
                if code != 0:
                    await loop.run_in_executor(None, self.logger.log_wp, "Phase 2: Compile FAILED")
                    return {"continue": False, "stopReason": format_compile_error(out, profile, compile_cmd)}
                await loop.run_in_executor(None, self.logger.log_wp, "Phase 2: Compile OK")

            # Phase 3: Verify tests compile
            if phase == 3:
                cmd = test_compile_cmd or compile_cmd
                if cmd and not self._has_placeholder(cmd):
                    await loop.run_in_executor(None, self.logger.log_event, "BUILD", f"Running: {cmd}")
                    code, out = await loop.run_in_executor(None, self._run_command, cmd, cwd)
                    if code != 0:
                        await loop.run_in_executor(None, self.logger.log_wp, "Phase 3: Test compile FAILED")
                        return {"continue": False, "stopReason": format_compile_error(out, profile, cmd)}
                    await loop.run_in_executor(None, self.logger.log_wp, "Phase 3: Test compile OK")

            # Phase 4: Verify compile + tests pass
            if phase == 4:
                if compile_cmd and not self._has_placeholder(compile_cmd):
                    await loop.run_in_executor(None, self.logger.log_event, "BUILD", f"Running: {compile_cmd}")
                    code, out = await loop.run_in_executor(None, self._run_command, compile_cmd, cwd)
                    if code != 0:
                        await loop.run_in_executor(None, self.logger.log_wp, "Phase 4: Compile FAILED")
                        return {"continue": False, "stopReason": format_compile_error(out, profile, compile_cmd)}
                    await loop.run_in_executor(None, self.logger.log_wp, "Phase 4: Compile OK")

                if test_cmd and not self._has_placeholder(test_cmd):
                    await loop.run_in_executor(None, self.logger.log_event, "BUILD", f"Running: {test_cmd}")
                    code, out = await loop.run_in_executor(None, self._run_command, test_cmd, cwd, 300)
                    if code != 0:
                        await loop.run_in_executor(None, self.logger.log_wp, "Phase 4: Tests FAILED")
                        return {"continue": False, "stopReason": format_test_failure(out, profile)}
                    await loop.run_in_executor(None, self.logger.log_wp, "Phase 4: Tests OK")

                await loop.run_in_executor(None, self.logger.log_wp, "Phase 4 COMPLETE: All builds and tests passing")

            return self._allow()

        except Exception as e:
            try:
                self.logger.log_event("HOOK_ERROR", f"build_verify exception: {e}")
            except:
                pass
            return self._allow()

    # --- Hook Config ---

    def get_hooks_config(self) -> Dict[str, Any]:
        """Get hooks config for ClaudeAgentOptions."""
        import os

        # Allow disabling hooks via environment variable for debugging
        if os.environ.get("WP_DISABLE_HOOKS") == "1":
            self.logger.log_event("HOOK", "Hooks DISABLED via WP_DISABLE_HOOKS=1")
            return {}

        try:
            from claude_agent_sdk import HookMatcher
        except ImportError:
            self.logger.log_event("HOOK", "HookMatcher import FAILED - no hooks registered")
            return {}

        # Full hooks: phase guard, logging, and build verification
        self.logger.log_event("HOOK", "Registering hooks (phase_guard, log_tool_use, build_verify)")
        return {
            "PreToolUse": [
                HookMatcher(matcher="Write|Edit", hooks=[self.phase_guard]),
                HookMatcher(hooks=[self.log_tool_use]),
            ],
            "Stop": [
                HookMatcher(hooks=[self.build_verify]),
            ],
        }

    def get_extraction_hooks_config(self) -> Dict[str, Any]:
        """
        Get lightweight hooks config for internal queries (summary, review, knowledge extraction).

        Excludes build_verify Stop hook to avoid unnecessary compilation
        when Claude is only generating text summaries.
        """
        import os

        if os.environ.get("WP_DISABLE_HOOKS") == "1":
            return {}

        try:
            from claude_agent_sdk import HookMatcher
        except ImportError:
            return {}

        self.logger.log_event("HOOK", "Registering hooks (log_tool_use only)")
        return {
            "PreToolUse": [
                HookMatcher(hooks=[self.log_tool_use]),
            ],
        }
