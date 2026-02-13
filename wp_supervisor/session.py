#!/usr/bin/env python3
"""
Waypoints Supervisor - Session Runner

Reusable session management for streaming Claude conversations,
extracting duplicated loop logic from orchestrator.py.
"""

import asyncio
import os
import sys
from typing import Callable, Dict, List, Optional, Any, Tuple

try:
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AgentDefinition
    from claude_agent_sdk.types import AssistantMessage, ResultMessage
except ImportError:
    pass

from .markers import SupervisorMarkers
from .hooks import SupervisorHooks
from .logger import SupervisorLogger


PHASE_COMPLETE_PATTERNS = [
    "---PHASE_COMPLETE---",
    "**PHASE_COMPLETE**",
    "PHASE_COMPLETE"
]

REGENERATION_COMPLETE_PATTERNS = [
    "---REGENERATION_COMPLETE---",
    "**REGENERATION_COMPLETE**",
    "REGENERATION_COMPLETE"
]

REGENERATION_CANCELED_PATTERNS = [
    "---REGENERATION_CANCELED---",
    "**REGENERATION_CANCELED**",
    "REGENERATION_CANCELED"
]

SIGNAL_COMPLETE = 'complete'
SIGNAL_CANCELED = 'canceled'

SignalPatterns = List[str]
SignalChecker = Callable[[str], Optional[str]]
UsageRecorder = Callable[[int, "ResultMessage"], None]


def read_user_input(prompt: str = "") -> str:
    """Read user input, supporting file paths (@/path, ./path, ~/path)."""
    try:
        user_input = input(prompt)
    except (EOFError, KeyboardInterrupt):
        return ""

    file_path = None

    if user_input.startswith('@'):
        file_path = user_input[1:].strip()
    elif user_input.startswith(('/', './', '../', '~/')):
        expanded = os.path.expanduser(user_input.strip())
        if os.path.isfile(expanded):
            file_path = expanded

    if file_path:
        expanded_path = os.path.expanduser(file_path)
        try:
            with open(expanded_path, 'r') as f:
                content = f.read()
            print(f"[Loaded {len(content)} chars from {file_path}]")
            return content
        except FileNotFoundError:
            print(f"[File not found: {file_path}]")
            return ""
        except PermissionError:
            print(f"[Permission denied: {file_path}]")
            return ""
        except Exception as e:
            print(f"[Error reading file: {e}]")
            return ""

    return user_input


class SessionRunner:
    """
    Encapsulates streaming session logic for Claude conversations.

    Handles phase sessions with user interaction, regeneration sessions
    with completion/cancellation detection, and silent text extraction.
    """

    def __init__(
        self,
        working_dir: str,
        markers: SupervisorMarkers,
        hooks: SupervisorHooks,
        logger: SupervisorLogger
    ) -> None:
        self.working_dir = working_dir
        self.markers = markers
        self.hooks = hooks
        self.logger = logger

    async def _process_stream(
        self,
        client: "ClaudeSDKClient",
        phase: int,
        signal_checker: Optional[SignalChecker] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Process a message stream: print text, show work indicators, detect signals.

        Unified streaming loop used by both phase and regeneration sessions.

        Args:
            client: The SDK client to receive messages from
            phase: Current phase number for usage recording
            signal_checker: Optional callback that checks text for signals.
                           Returns signal string if detected, None otherwise.

        Returns:
            (session_id, detected_signal) tuple. session_id is from the first
            message that provides one. detected_signal is the first non-None
            return from signal_checker.
        """
        session_id: Optional[str] = None
        detected_signal: Optional[str] = None
        working_indicator_shown = False

        async for message in client.receive_response():
            if hasattr(message, 'session_id') and message.session_id:
                session_id = message.session_id

            if hasattr(message, 'content') and message.content:
                last_text = ""
                for block in message.content:
                    if hasattr(block, 'text'):
                        if working_indicator_shown:
                            print("\n", end='')
                            working_indicator_shown = False
                        print(block.text, end='', flush=True)
                        last_text = block.text
                        if signal_checker:
                            result = signal_checker(block.text)
                            if result:
                                detected_signal = result
                    elif hasattr(block, 'name'):
                        print(".", end='', flush=True)
                        working_indicator_shown = True
                if last_text and not last_text.endswith('\n'):
                    print()

            if hasattr(message, 'usage'):
                self._record_usage(phase, message)

        return session_id, detected_signal

    async def run_phase_session(
        self,
        client_context_manager: "ClaudeSDKClient",
        initial_prompt: str,
        phase: int,
        signal_patterns: SignalPatterns,
        subagents: Optional[Dict[str, "AgentDefinition"]] = None
    ) -> Optional[str]:
        """
        Run an interactive Claude session for a phase. Returns session_id.

        Streams output (text blocks + dots for tool use), detects phase completion
        signals, and runs a user input loop with /done, /complete, /next, /quit commands.
        """
        def phase_checker(text: str) -> Optional[str]:
            return SIGNAL_COMPLETE if self._check_signal(text, signal_patterns) else None

        session_id, signal = await self._process_stream(
            client_context_manager, phase, phase_checker
        )
        phase_complete = signal is not None

        first_input = True
        while not phase_complete:
            if first_input:
                print("\n[Tip: For structured input, provide a file path: @/path/to/file.md]")
                first_input = False

            user_input = read_user_input("\nYou: ").strip()

            if not user_input:
                continue

            self.logger.log_user_input(user_input)

            if user_input.lower() in ['/done', '/complete', '/next']:
                self.logger.log_user_command(user_input.lower())
                phase_complete = True
                break

            if user_input.lower() in ['/quit', '/exit', '/abort']:
                self.logger.log_user_command(user_input.lower())
                raise KeyboardInterrupt("User requested abort")

            print("\n", end='', flush=True)
            await client_context_manager.query(user_input)

            _, signal = await self._process_stream(
                client_context_manager, phase, phase_checker
            )
            if signal:
                phase_complete = True

        return session_id

    async def run_regeneration_session(
        self,
        client_context_manager: "ClaudeSDKClient",
        initial_prompt: str,
        phase: int,
        complete_patterns: SignalPatterns,
        canceled_patterns: SignalPatterns
    ) -> Tuple[bool, Optional[str]]:
        """
        Run interactive regeneration conversation.

        Returns (was_completed, session_id). Detects both completion and
        cancellation signals. User can type /done to force completion.
        """
        def regen_checker(text: str) -> Optional[str]:
            return self._check_regeneration_signal(text, complete_patterns, canceled_patterns)

        session_id, signal = await self._process_stream(
            client_context_manager, phase, regen_checker
        )
        conversation_complete = signal is not None
        was_completed = signal == SIGNAL_COMPLETE

        while not conversation_complete:
            user_input = read_user_input("\nYou: ").strip()

            if not user_input:
                continue

            self.logger.log_user_input(user_input)

            if user_input.lower() == '/done':
                self.logger.log_user_command('/done')
                was_completed = True
                break

            print("\n", end='', flush=True)
            await client_context_manager.query(user_input)

            _, signal = await self._process_stream(
                client_context_manager, phase, regen_checker
            )
            if signal:
                conversation_complete = True
                was_completed = signal == SIGNAL_COMPLETE

        return (was_completed, session_id if was_completed else None)

    async def extract_text(
        self,
        client_context_manager: "ClaudeSDKClient",
        prompt: str,
        phase: Optional[int] = None,
        session_id: Optional[str] = None,
        timeout: float = 300.0
    ) -> str:
        """Send a query and collect the text response silently. Returns partial text on timeout."""
        collected_text = ""

        async def _collect_response():
            nonlocal collected_text
            async for message in client_context_manager.receive_response():
                if hasattr(message, 'content'):
                    for block in message.content:
                        if hasattr(block, 'text'):
                            collected_text += block.text
                if hasattr(message, 'usage') and phase is not None:
                    self._record_usage(phase, message)

        try:
            await asyncio.wait_for(_collect_response(), timeout=timeout)
        except asyncio.TimeoutError:
            pass

        return collected_text

    def _check_signal(self, text: str, patterns: SignalPatterns) -> bool:
        """Check if text contains any of the given signal patterns."""
        if not text or not patterns:
            return False
        return any(pattern in text for pattern in patterns)

    def _check_regeneration_signal(
        self,
        text: str,
        complete_patterns: SignalPatterns,
        canceled_patterns: SignalPatterns
    ) -> Optional[str]:
        """Check for regeneration complete or canceled signals."""
        if self._check_signal(text, complete_patterns):
            return SIGNAL_COMPLETE
        if self._check_signal(text, canceled_patterns):
            return SIGNAL_CANCELED
        return None

    def _record_usage(self, phase: int, result: "ResultMessage") -> None:
        """Record usage data from a ResultMessage."""
        usage = getattr(result, 'usage', None) or {}
        input_tokens = usage.get('input_tokens', 0) if usage else 0
        output_tokens = usage.get('output_tokens', 0) if usage else 0
        cost_usd = getattr(result, 'total_cost_usd', None) or 0.0
        duration_ms = getattr(result, 'duration_ms', None) or 0
        turns = getattr(result, 'num_turns', None) or 0

        self.markers.add_phase_usage(
            phase=phase,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            duration_ms=duration_ms,
            turns=turns
        )
