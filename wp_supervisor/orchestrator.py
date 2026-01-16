#!/usr/bin/env python3
"""
Waypoints Supervisor - Main Orchestrator

Orchestrates Waypoints workflow across multiple Claude sessions,
managing context transfer between phases.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional, List

try:
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
    from claude_agent_sdk.types import AssistantMessage, ResultMessage
except ImportError:
    print("Error: claude-agent-sdk not installed.", file=sys.stderr)
    print("Install with: pip install claude-agent-sdk", file=sys.stderr)
    sys.exit(1)

# Add hooks/lib to path for agent loading
_hooks_lib = Path(__file__).parent.parent / "hooks" / "lib"
if str(_hooks_lib) not in sys.path:
    sys.path.insert(0, str(_hooks_lib))

from wp_agents import AgentLoader
from .markers import SupervisorMarkers
from .context import ContextBuilder
from .logger import SupervisorLogger
from .hooks import SupervisorHooks
from .templates import (
    PHASE_NAMES,
    format_phase_header,
    format_workflow_header,
    format_phase_complete_banner,
    format_workflow_complete,
)


def read_user_input(prompt: str = "") -> str:
    """
    Read user input, supporting both direct text and file paths.

    For complex features, users can write structured requirements in a file
    and provide the path. The file content will be read and returned.

    File input methods:
    - @/path/to/file.md  - Explicit file prefix
    - /absolute/path.md  - Auto-detected absolute path
    - ./relative/path.md - Auto-detected relative path
    - ~/home/path.md     - Auto-detected home path

    Args:
        prompt: The prompt to display

    Returns:
        User input text or file contents
    """
    try:
        user_input = input(prompt)
    except (EOFError, KeyboardInterrupt):
        return ""

    # Check if input is a file reference
    file_path = None

    if user_input.startswith('@'):
        # Explicit file reference: @/path/to/file
        file_path = user_input[1:].strip()
    elif user_input.startswith(('/', './', '../', '~/')):
        # Potential file path - check if it exists
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


class WPOrchestrator:
    """
    Orchestrates Waypoints workflow across multiple Claude sessions.

    Each phase runs in its own session with clean context.
    Context is passed between phases via summaries.
    """

    # Signals must be on their own line to avoid false positives
    PHASE_COMPLETE_SIGNAL = "---PHASE_COMPLETE---"
    # Also accept markdown bold variant (Claude sometimes uses this)
    PHASE_COMPLETE_PATTERNS = ["---PHASE_COMPLETE---", "**PHASE_COMPLETE**", "PHASE_COMPLETE"]
    SUMMARY_VERIFIED_SIGNAL = "SUMMARY_VERIFIED"
    GAPS_FOUND_SIGNAL = "GAPS_FOUND"

    def __init__(self, working_dir: Optional[str] = None):
        """
        Initialize the Waypoints orchestrator.

        Args:
            working_dir: Project working directory (defaults to cwd)
        """
        self.working_dir = Path(working_dir or os.getcwd()).resolve()
        self.markers = SupervisorMarkers()
        self.logger = SupervisorLogger(
            workflow_dir=self.markers.markers_dir,
            workflow_id=self.markers.workflow_id
        )
        self.agent_loader = AgentLoader()
        self.hooks = SupervisorHooks(
            markers=self.markers,
            logger=self.logger,
            working_dir=str(self.working_dir)
        )

        # Validate working directory
        if not self.working_dir.is_dir():
            raise ValueError(f"Working directory does not exist: {self.working_dir}")

    async def run(self, initial_task: Optional[str] = None) -> None:
        """
        Run the complete Waypoints workflow.

        Args:
            initial_task: Optional initial task description
        """
        print(format_workflow_header(
            working_dir=str(self.working_dir),
            workflow_id=self.markers.workflow_id,
            markers_dir=str(self.markers.get_marker_dir())
        ))

        try:
            # Initialize markers and log start
            self.markers.initialize()
            self.logger.log_workflow_start(initial_task or "")

            # Run all 4 phases
            await self._run_phase(1, initial_task)
            await self._run_phase(2)
            await self._run_phase(3)
            await self._run_phase(4)

            # Log completion with usage summary
            self.logger.log_workflow_complete(self.markers.get_usage_summary_text())
            self.logger.log_usage_summary(
                total_tokens=self.markers.get_total_tokens(),
                total_cost=self.markers.get_total_cost(),
                duration_sec=self.markers.get_total_duration_sec()
            )

            print(format_workflow_complete())

        except KeyboardInterrupt:
            print("\n\nWorkflow interrupted by user.")
            self.logger.log_workflow_aborted("User interrupted")
            self.markers.cleanup()
            print("Markers cleaned up.")
        except Exception as e:
            print(f"\n\nWorkflow error: {e}", file=sys.stderr)
            self.logger.log_error("Workflow failed", e)
            self.logger.log_workflow_aborted(str(e))
            self.markers.cleanup()
            raise

    def _build_phase_context(self, phase: int, initial_task: Optional[str] = None) -> str:
        """Build context for a specific phase, including phase-bound agents."""
        # Build base context from templates
        if phase == 1:
            context = ContextBuilder.build_phase1_context(initial_task)
        elif phase == 2:
            context = ContextBuilder.build_phase2_context(
                self.markers.get_requirements_summary()
            )
        elif phase == 3:
            context = ContextBuilder.build_phase3_context(
                self.markers.get_requirements_summary(),
                self.markers.get_interfaces_list()
            )
        elif phase == 4:
            context = ContextBuilder.build_phase4_context(
                self.markers.get_requirements_summary(),
                self.markers.get_interfaces_list(),
                self.markers.get_tests_list()
            )
        else:
            raise ValueError(f"Invalid phase: {phase}")

        # Load and append phase-bound agents
        agent_content = self.agent_loader.load_phase_agents(phase, logger=self.logger)
        if agent_content:
            context += f"\n\n# Phase Agents\n{agent_content}"

        return context

    async def _run_phase(self, phase: int, initial_task: Optional[str] = None) -> None:
        """
        Run a single Waypoints phase.

        Args:
            phase: Phase number (1-4)
            initial_task: Initial task description (phase 1 only)
        """
        phase_name = PHASE_NAMES[phase]
        print(format_phase_header(phase, phase_name))
        self.markers.set_phase(phase)
        self.logger.log_phase_start(phase, phase_name)

        # Build and save context
        context = self._build_phase_context(phase, initial_task)
        context_path = self.markers.save_phase_context(phase, context)
        if context_path:
            self.logger.log_phase_context_saved(phase, context_path)

        # Run the phase session
        session_id = await self._run_phase_session(context, phase)

        if phase < 4:
            # Generate summary and save as document
            summary = await self._generate_and_verify_summary(phase, session_id)
            doc_path = self.markers.save_phase_document(phase, summary)
            if doc_path:
                self.logger.log_phase_summary_saved(phase, doc_path)
                print(f"\n[Supervisor] {phase_name} document saved: {doc_path}")

            # Confirmation loop with edit/regenerate options
            while True:
                action = await self._confirm_phase_completion(phase, doc_path, session_id)

                if action == 'proceed':
                    break
                elif action == 'edit':
                    # Verify the edited document can be read
                    edited_content = self.markers.get_phase_document(phase)
                    if edited_content:
                        # Show preview of edited content
                        preview_lines = edited_content.strip().split('\n')[:5]
                        preview = '\n'.join(preview_lines)
                        if len(edited_content.strip().split('\n')) > 5:
                            preview += '\n...'
                        print(f"\n[Supervisor] Document updated. Preview:")
                        print(f"---")
                        print(preview)
                        print(f"---")
                        self.logger.log_event("USER", f"Phase {phase} document edited manually")
                    else:
                        print(f"[Supervisor] Warning: Could not read document at {doc_path}")
                elif action == 'regenerate':
                    # Regenerate summary with user feedback
                    summary = await self._regenerate_summary(phase, session_id)
                    doc_path = self.markers.save_phase_document(phase, summary)
                    if doc_path:
                        self.logger.log_phase_summary_saved(phase, doc_path)
                        print(f"[Supervisor] Updated document saved: {doc_path}")
        else:
            print(f"\n[Supervisor] Implementation complete - all tests passing!")
            self.logger.log_phase_complete(phase, phase_name)
            self._display_usage_summary()
            # Keep documents for reference, only remove state.json
            self.markers.cleanup(keep_documents=True)
            print(f"\n[Supervisor] Documents preserved in: {self.markers.get_marker_dir()}")

    async def _run_phase_session(self, initial_context: str, phase: int) -> Optional[str]:
        """
        Run an interactive Claude session for a phase using ClaudeSDKClient.

        Uses ClaudeSDKClient for proper bidirectional streaming with hooks support.

        Args:
            initial_context: Initial context/prompt for the phase
            phase: Current phase number

        Returns:
            Session ID for resuming conversation (e.g., for summary generation)
        """
        env_vars = self.markers.get_env_vars()

        # First message to Claude with phase context
        print(f"\n[Starting Phase {phase} session...]\n")

        session_id = None
        phase_complete = False
        working_indicator_shown = False

        # Use async context manager for proper streaming mode
        # This connects with empty stream, allowing us to use query() for messages
        async with ClaudeSDKClient(
            options=ClaudeAgentOptions(
                cwd=str(self.working_dir),
                env=env_vars,
                permission_mode="bypassPermissions",
                hooks=self.hooks.get_hooks_config(),
            )
        ) as client:
            # Send initial context as first query
            await client.query(initial_context)

            # Process initial response
            async for message in client.receive_response():
                # Capture session ID
                if hasattr(message, 'session_id') and message.session_id:
                    session_id = message.session_id

                # Print AssistantMessage content (text and tool usage)
                if isinstance(message, AssistantMessage) and message.content:
                    last_text = ""
                    for block in message.content:
                        if hasattr(block, 'text'):
                            if working_indicator_shown:
                                print("\n", end='')  # New line after dots
                                working_indicator_shown = False
                            print(block.text, end='', flush=True)
                            last_text = block.text
                            if any(p in block.text for p in self.PHASE_COMPLETE_PATTERNS):
                                phase_complete = True
                        elif hasattr(block, 'name'):
                            # Tool use - show dot as progress indicator
                            print(".", end='', flush=True)
                            working_indicator_shown = True
                    # Ensure message ends with newline for readability
                    if last_text and not last_text.endswith('\n'):
                        print()

                # Capture usage from ResultMessage
                if isinstance(message, ResultMessage):
                    self._record_usage(phase, message)

            # If phase not complete, continue interactive loop
            first_input = True
            while not phase_complete:
                # Show hint on first input prompt
                if first_input:
                    print("\n[Tip: For structured input, provide a file path: @/path/to/file.md]")
                    first_input = False

                user_input = read_user_input("\nYou: ").strip()

                if not user_input:
                    continue

                # Log user input
                self.logger.log_user_input(user_input)

                # Check for user commands
                if user_input.lower() in ['/done', '/complete', '/next']:
                    self.logger.log_user_command(user_input.lower())
                    phase_complete = True
                    break

                if user_input.lower() in ['/quit', '/exit', '/abort']:
                    self.logger.log_user_command(user_input.lower())
                    raise KeyboardInterrupt("User requested abort")

                # Continue conversation
                print("\n", end='', flush=True)
                working_indicator_shown = False
                await client.query(user_input)

                async for message in client.receive_response():
                    # Print AssistantMessage content (text and tool usage)
                    if isinstance(message, AssistantMessage) and message.content:
                        last_text = ""
                        for block in message.content:
                            if hasattr(block, 'text'):
                                if working_indicator_shown:
                                    print("\n", end='')  # New line after progress dots
                                    working_indicator_shown = False
                                print(block.text, end='', flush=True)
                                last_text = block.text
                                if any(p in block.text for p in self.PHASE_COMPLETE_PATTERNS):
                                    phase_complete = True
                            elif hasattr(block, 'name'):
                                # Tool use - show dot as progress indicator
                                print(".", end='', flush=True)
                                working_indicator_shown = True
                        # Ensure message ends with newline for readability
                        if last_text and not last_text.endswith('\n'):
                            print()

                    # Capture usage from ResultMessage
                    if isinstance(message, ResultMessage):
                        self._record_usage(phase, message)

        return session_id

    def _record_usage(self, phase: int, result: ResultMessage) -> None:
        """
        Record usage data from a ResultMessage.

        Args:
            phase: Phase number (1-4)
            result: ResultMessage from query()
        """
        usage = result.usage or {}
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cost_usd = result.total_cost_usd or 0.0
        duration_ms = result.duration_ms or 0
        turns = result.num_turns or 0

        self.markers.add_phase_usage(
            phase=phase,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            duration_ms=duration_ms,
            turns=turns
        )

    def _display_usage_summary(self) -> None:
        """Display token usage summary at end of workflow."""
        usage = self.markers.get_all_usage()

        print("\n" + "=" * 60)
        print("TOKEN USAGE SUMMARY")
        print("=" * 60)

        for phase_num in [1, 2, 3, 4]:
            phase_key = f"phase{phase_num}"
            phase_data = usage.get(phase_key, {})
            phase_name = PHASE_NAMES.get(phase_num, f"Phase {phase_num}")

            input_tokens = phase_data.get("input_tokens", 0)
            output_tokens = phase_data.get("output_tokens", 0)
            total_tokens = input_tokens + output_tokens
            cost = phase_data.get("cost_usd", 0.0)
            duration = phase_data.get("duration_ms", 0)
            turns = phase_data.get("turns", 0)

            if total_tokens > 0:
                duration_sec = duration / 1000.0
                print(f"\nPhase {phase_num} ({phase_name}):")
                print(f"  Tokens: {input_tokens:,} in / {output_tokens:,} out ({total_tokens:,} total)")
                print(f"  Cost: ${cost:.4f}")
                print(f"  Duration: {duration_sec:.1f}s | Turns: {turns}")

        # Total
        total = usage.get("total", {})
        total_input = total.get("input_tokens", 0)
        total_output = total.get("output_tokens", 0)
        total_tokens = total_input + total_output
        total_cost = total.get("cost_usd", 0.0)
        total_duration = total.get("duration_ms", 0)
        total_turns = total.get("turns", 0)

        print("\n" + "-" * 60)
        print("TOTAL:")
        print(f"  Tokens: {total_input:,} in / {total_output:,} out ({total_tokens:,} total)")
        print(f"  Cost: ${total_cost:.4f}")
        print(f"  Duration: {total_duration / 1000.0:.1f}s | Turns: {total_turns}")
        print("=" * 60)

    async def _confirm_phase_completion(
        self,
        phase: int,
        doc_path: str = "",
        session_id: Optional[str] = None
    ) -> str:
        """
        Ask user to confirm phase completion with edit/regenerate options.

        Args:
            phase: Phase number
            doc_path: Path to the phase document
            session_id: Session ID for regeneration queries

        Returns:
            Action to take: 'proceed', 'edit', or 'regenerate'
        """
        name = PHASE_NAMES.get(phase, f"Phase {phase}")

        print(format_phase_complete_banner(phase, name, doc_path))

        while True:
            response = input("\nYour choice [y/e/r]: ").strip().lower()

            if response in ['y', 'yes', '']:
                self.logger.log_user_confirmation(phase)
                self.logger.log_phase_complete(phase, name)
                return 'proceed'
            elif response == 'e':
                print(f"\n[Supervisor] Edit the document, then press Enter to continue...")
                print(f"             File: {doc_path}")
                input("\nPress Enter when done editing: ")
                return 'edit'
            elif response == 'r':
                return 'regenerate'
            else:
                print("\nOptions:")
                print("  y - Proceed to next phase")
                print("  e - Edit document manually, then reload")
                print("  r - Provide feedback to regenerate")
                print("  Ctrl+C - Abort workflow")

    async def _generate_and_verify_summary(self, phase: int, session_id: Optional[str] = None) -> str:
        """
        Generate a summary for the phase with self-review verification.

        This is a two-step process:
        1. Generate initial summary
        2. Ask Claude to self-review and fill any gaps

        Args:
            phase: Phase number to summarize
            session_id: Session ID to resume (uses same context as phase session)

        Returns:
            Verified summary text
        """
        # Step 1: Generate initial summary
        summary_prompt = ContextBuilder.get_summary_prompt(phase)
        if not summary_prompt:
            return ""

        print(f"\n[Supervisor] Generating phase {phase} summary...")

        initial_summary = await self._query_for_text(summary_prompt, session_id=session_id, phase=phase)

        # Step 2: Self-review
        review_prompt = ContextBuilder.get_review_prompt(phase)
        if not review_prompt:
            return initial_summary

        print(f"[Supervisor] Verifying summary completeness...")

        review_response = await self._query_for_text(review_prompt, session_id=session_id, phase=phase)

        # Parse review response
        if review_response.startswith(self.GAPS_FOUND_SIGNAL):
            # Extract updated summary (everything after the signal line)
            lines = review_response.split('\n', 1)
            if len(lines) > 1:
                updated_summary = lines[1].strip()
                print(f"[Supervisor] Summary updated with missing items.")
                return updated_summary
            else:
                # Fallback to initial if parsing fails
                return initial_summary
        elif review_response.startswith(self.SUMMARY_VERIFIED_SIGNAL):
            # Extract verified summary
            lines = review_response.split('\n', 1)
            if len(lines) > 1:
                print(f"[Supervisor] Summary verified complete.")
                return lines[1].strip()
            else:
                return initial_summary
        else:
            # If response doesn't follow format, use as-is
            # (Claude might have just output the summary directly)
            print(f"[Supervisor] Summary captured.")
            return review_response if review_response else initial_summary

    async def _regenerate_summary(
        self,
        phase: int,
        session_id: Optional[str] = None
    ) -> str:
        """
        Regenerate summary based on user feedback.

        Args:
            phase: Phase number
            session_id: Session ID to resume (maintains conversation context)

        Returns:
            Regenerated summary text
        """
        # Get current summary for reference
        current_summary = self.markers.get_phase_document(phase)

        # Get user feedback
        print("\n[Supervisor] What changes would you like to make?")
        print("             (Describe what to add, remove, or modify)")
        feedback = read_user_input("\nYour feedback: ").strip()

        if not feedback:
            print("[Supervisor] No feedback provided, keeping current summary.")
            return current_summary

        self.logger.log_user_input(f"Regenerate feedback: {feedback}")

        # Build regeneration prompt
        regenerate_prompt = f"""
The user has reviewed the summary and wants changes.

## Current Summary
{current_summary}

## User Feedback
{feedback}

## Your Task
Update the summary based on the user's feedback. Keep the same format but incorporate
their requested changes. Output ONLY the updated summary, no explanations.
"""

        print(f"\n[Supervisor] Regenerating summary with your feedback...")

        new_summary = await self._query_for_text(
            regenerate_prompt,
            session_id=session_id,
            phase=phase
        )

        if new_summary:
            print(f"[Supervisor] Summary regenerated.")
            return new_summary
        else:
            print(f"[Supervisor] Regeneration failed, keeping current summary.")
            return current_summary

    async def _query_for_text(
        self,
        prompt: str,
        timeout: float = 300.0,
        session_id: Optional[str] = None,
        phase: Optional[int] = None
    ) -> str:
        """
        Send a query and collect the text response using ClaudeSDKClient.

        Args:
            prompt: The prompt to send
            timeout: Maximum time to wait in seconds (default 5 minutes)
            session_id: Optional session ID to resume conversation
            phase: Optional phase number for usage tracking

        Returns:
            Collected text response
        """
        text_parts: List[str] = []
        env_vars = self.markers.get_env_vars()

        async def collect_response() -> None:
            # Use async context manager for proper streaming mode
            async with ClaudeSDKClient(
                options=ClaudeAgentOptions(
                    cwd=str(self.working_dir),
                    env=env_vars,
                    resume=session_id,
                    permission_mode="bypassPermissions",
                    hooks=self.hooks.get_hooks_config(),
                )
            ) as client:
                # Send prompt via query
                await client.query(prompt)

                # Collect response
                async for message in client.receive_response():
                    if isinstance(message, AssistantMessage) and message.content:
                        for block in message.content:
                            if hasattr(block, 'text'):
                                text_parts.append(block.text)

                    # Capture usage from ResultMessage
                    if isinstance(message, ResultMessage) and phase:
                        self._record_usage(phase, message)

        try:
            await asyncio.wait_for(collect_response(), timeout=timeout)
        except asyncio.TimeoutError:
            print(f"\n[Supervisor] Query timed out after {timeout}s", file=sys.stderr)

        return ''.join(text_parts)


async def run_supervisor(
    working_dir: Optional[str] = None,
    task: Optional[str] = None,
) -> None:
    """
    Run the Waypoints supervisor.

    Args:
        working_dir: Project working directory
        task: Initial task description
    """
    orchestrator = WPOrchestrator(working_dir=working_dir)
    await orchestrator.run(initial_task=task)
