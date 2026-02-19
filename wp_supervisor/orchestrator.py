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
from typing import Optional, Dict

try:
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AgentDefinition
except ImportError:
    print("Error: claude-agent-sdk not installed.", file=sys.stderr)
    print("Install with: pip install claude-agent-sdk", file=sys.stderr)
    sys.exit(1)

# Add hooks/lib to path for agent loading
_hooks_lib = Path(__file__).parent.parent / "hooks" / "lib"
if str(_hooks_lib) not in sys.path:
    sys.path.insert(0, str(_hooks_lib))

from wp_agents import AgentLoader
from wp_knowledge import KnowledgeManager, extract_from_text, ExtractionResult
from .markers import SupervisorMarkers
from .context import ContextBuilder
from .logger import SupervisorLogger
from .hooks import SupervisorHooks
from .templates import (
    PHASE_NAMES,
    KNOWLEDGE_EXTRACTION_PROMPT,
    format_staged_knowledge_for_prompt,
)
from .display import SupervisorDisplay
from .subagents import SubagentBuilder

from .session import (
    read_user_input,
    SessionRunner,
    PHASE_COMPLETE_PATTERNS,
    REGENERATION_COMPLETE_PATTERNS,
    REGENERATION_CANCELED_PATTERNS,
    SIGNAL_COMPLETE,
    SIGNAL_CANCELED,
)
from .review_coordinator import ReviewCoordinator, ReviewCoordinatorConfig

# Orchestrator-specific signal constants
PHASE_COMPLETE_SIGNAL = "---PHASE_COMPLETE---"
SUMMARY_VERIFIED_SIGNAL = "SUMMARY_VERIFIED"
GAPS_FOUND_SIGNAL = "GAPS_FOUND"


class WPOrchestrator:
    """Orchestrates Waypoints workflow across multiple Claude sessions."""

    def __init__(self, working_dir: Optional[str] = None):
        self.working_dir = Path(working_dir or os.getcwd()).resolve()
        self.markers = SupervisorMarkers()
        self.logger = SupervisorLogger(
            workflow_dir=self.markers.markers_dir,
            workflow_id=self.markers.workflow_id
        )
        self.display = SupervisorDisplay()
        self.agent_loader = AgentLoader()
        self.hooks = SupervisorHooks(
            markers=self.markers,
            logger=self.logger,
            working_dir=str(self.working_dir),
            display=self.display,
        )
        self._session_runner = SessionRunner(
            working_dir=str(self.working_dir),
            markers=self.markers,
            hooks=self.hooks,
            logger=self.logger,
            display=self.display,
        )
        self._knowledge_manager = KnowledgeManager(project_dir=str(self.working_dir))
        self._knowledge_context: str = ""
        self._review_coordinator: Optional[ReviewCoordinator] = None

        if not self.working_dir.is_dir():
            raise ValueError(f"Working directory does not exist: {self.working_dir}")

    async def run(self, initial_task: Optional[str] = None) -> None:
        """Run the complete Waypoints workflow."""
        self.display.workflow_header(
            working_dir=str(self.working_dir),
            workflow_id=self.markers.workflow_id,
            markers_dir=str(self.markers.get_marker_dir())
        )

        try:
            self.markers.initialize()
            self.logger.log_workflow_start(initial_task or "")
            self._knowledge_context = self._load_knowledge_context()

            await self._run_phase(1, initial_task)
            await self._run_phase(2)
            await self._run_phase(3)
            await self._run_phase(4)

            self._apply_knowledge_at_workflow_end()
            self.logger.log_workflow_complete(self.markers.get_usage_summary_text())
            self.logger.log_usage_summary(
                total_tokens=self.markers.get_total_tokens(),
                total_cost=self.markers.get_total_cost(),
                duration_sec=self.markers.get_total_duration_sec()
            )

            self.display.workflow_complete()

        except KeyboardInterrupt:
            self.display.supervisor_warning("Workflow interrupted by user.")
            self.logger.log_workflow_aborted("User interrupted")
            self.markers.clear_staged_knowledge()
            self.markers.cleanup()
            self.display.supervisor_message("Markers cleaned up.")
        except Exception as e:
            self.display.supervisor_error(f"Workflow error: {e}")
            self.logger.log_error("Workflow failed", e)
            self.logger.log_workflow_aborted(str(e))
            self.markers.clear_staged_knowledge()
            self.markers.cleanup()
            raise

    def _load_knowledge_context(self) -> str:
        """Load project knowledge for injection into phase contexts."""
        return KnowledgeManager(str(self.working_dir)).load_knowledge_context()

    async def _extract_and_stage_knowledge(
        self,
        phase: int,
        session_id: Optional[str] = None
    ) -> None:
        """Extract knowledge from phase and stage for later application. Fails silently."""
        self.logger.log_event("KNOWLEDGE", f"Starting knowledge extraction for phase {phase}")
        try:
            staged = self.markers.get_staged_knowledge()
            staged_str = format_staged_knowledge_for_prompt(staged)

            prompt = KNOWLEDGE_EXTRACTION_PROMPT.format(
                existing_knowledge=self._knowledge_context or "No existing knowledge.",
                staged_this_session=staged_str
            )
            self.logger.log_event("KNOWLEDGE", "Prompt built, querying Claude...")
            response = await self._extract_text_response(
                prompt,
                session_id=session_id,
                phase=phase
            )
            self.logger.log_event("KNOWLEDGE", f"Got response: {len(response)} chars")
            result = extract_from_text(response)
            self.logger.log_event("KNOWLEDGE", f"Parsed: had_content={result.had_content}, is_empty={result.knowledge.is_empty() if result.knowledge else 'N/A'}")

            if result.parse_error:
                self.logger.log_error(f"Knowledge extraction parse error: {result.parse_error}")
                return

            if result.had_content and not result.knowledge.is_empty():
                self.markers.stage_knowledge(result.knowledge)
                self.logger.log_event("KNOWLEDGE", "Knowledge staged successfully")
            else:
                self.logger.log_event("KNOWLEDGE", "No knowledge to stage")

        except Exception as e:
            self.logger.log_error(f"Knowledge extraction failed: {e}")
            import traceback
            self.logger.log_error(f"Traceback: {traceback.format_exc()}")

    def _apply_knowledge_at_workflow_end(self) -> None:
        """Apply staged knowledge to permanent files after Phase 4."""
        if not self.markers.has_staged_knowledge():
            return

        try:
            counts = self.markers.apply_staged_knowledge(str(self.working_dir))
            if counts:
                summary = KnowledgeManager(str(self.working_dir)).get_updated_files_summary(counts)
                self.display.knowledge_summary(summary)
            self.markers.clear_staged_knowledge()
        except Exception as e:
            self.logger.log_error(f"Failed to apply staged knowledge: {e}")
            self.markers.clear_staged_knowledge()

    def _build_phase_context(
        self,
        phase: int,
        initial_task: Optional[str] = None,
        delegate_exploration: bool = True
    ) -> str:
        """Build context for a phase, including agents and knowledge."""
        if phase == 1:
            context = ContextBuilder.build_phase1_context(
                initial_task,
                knowledge_context=self._knowledge_context,
                supervisor_mode=delegate_exploration
            )
        elif phase == 2:
            context = ContextBuilder.build_phase2_context(
                self.markers.get_requirements_summary(),
                knowledge_context=self._knowledge_context
            )
        elif phase == 3:
            context = ContextBuilder.build_phase3_context(
                self.markers.get_requirements_summary(),
                self.markers.get_interfaces_list(),
                knowledge_context=self._knowledge_context
            )
        elif phase == 4:
            context = ContextBuilder.build_phase4_context(
                self.markers.get_requirements_summary(),
                self.markers.get_interfaces_list(),
                self.markers.get_tests_list(),
                knowledge_context=self._knowledge_context
            )
        else:
            raise ValueError(f"Invalid phase: {phase}")

        agent_content = self.agent_loader.load_phase_agents(phase, logger=self.logger)
        if agent_content:
            context += f"\n\n# Phase Agents\n{agent_content}"

        return context

    def _build_exploration_subagents(self) -> Dict[str, AgentDefinition]:
        """Build Phase 1 exploration subagent definitions."""
        return SubagentBuilder.build_exploration_agents(
            knowledge_context=self._knowledge_context
        )

    async def _run_phase(self, phase: int, initial_task: Optional[str] = None) -> None:
        """Run a single Waypoints phase."""
        phase_name = PHASE_NAMES[phase]
        self.display.phase_header(phase, phase_name)
        self.markers.set_phase(phase)
        self.logger.log_phase_start(phase, phase_name)

        # Build subagents before context so we can fall back on failure
        subagents: Optional[Dict[str, AgentDefinition]] = None
        delegate_exploration = True
        if phase == 1:
            try:
                subagents = self._build_exploration_subagents()
            except Exception as e:
                self.logger.log_event(
                    "SUBAGENTS",
                    f"Failed to build exploration subagents, "
                    f"falling back to standard exploration: {e}"
                )
                subagents = None
                delegate_exploration = False

        context = self._build_phase_context(phase, initial_task, delegate_exploration=delegate_exploration)
        context_path = self.markers.save_phase_context(phase, context)
        if context_path:
            self.logger.log_phase_context_saved(phase, context_path)

        if phase == 4:
            async with self.display.spinner("Starting code reviewer"):
                await self._start_review_coordinator()

        try:
            session_id = await self._run_phase_session(context, phase, subagents=subagents)
        finally:
            if phase == 4:
                await self._stop_review_coordinator()

        if phase < 4:
            summary = await self._generate_and_verify_summary(phase, session_id)
            doc_path = self.markers.save_phase_document(phase, summary)
            if doc_path:
                self.logger.log_phase_summary_saved(phase, doc_path)
                self.display.supervisor_success(f"{phase_name} document saved: {doc_path}")

            async with self.display.spinner("Extracting knowledge"):
                await self._extract_and_stage_knowledge(phase, session_id)

            while True:
                action = await self._confirm_phase_completion(phase, doc_path, session_id)

                if action == 'proceed':
                    break
                elif action == 'edit':
                    edited_content = self.markers.get_phase_document(phase)
                    if edited_content:
                        preview_lines = edited_content.strip().split('\n')[:5]
                        preview = '\n'.join(preview_lines)
                        if len(edited_content.strip().split('\n')) > 5:
                            preview += '\n...'
                        self.display.supervisor_message("Document updated. Preview:")
                        self.display.document_preview(preview)
                        self.logger.log_event("USER", f"Phase {phase} document edited manually")
                    else:
                        self.display.supervisor_warning(f"Could not read document at {doc_path}")
                elif action == 'regenerate':
                    summary = await self._regenerate_summary(phase, session_id)
                    doc_path = self.markers.save_phase_document(phase, summary)
                    if doc_path:
                        self.logger.log_phase_summary_saved(phase, doc_path)
                        self.display.supervisor_success(f"Updated document saved: {doc_path}")
        else:
            self.display.supervisor_success("Implementation complete - all tests passing!")
            self.logger.log_phase_complete(phase, phase_name)
            self._mark_phase_complete(phase)
            async with self.display.spinner("Extracting knowledge"):
                await self._extract_and_stage_knowledge(phase, session_id)
            self._display_usage_summary()
            self.display.supervisor_message(f"Documents preserved in: {self.markers.get_marker_dir()}")

    async def _run_phase_session(
        self,
        initial_context: str,
        phase: int,
        subagents: Optional[Dict[str, AgentDefinition]] = None
    ) -> Optional[str]:
        """Run an interactive Claude session for a phase. Returns session ID."""
        env_vars = self.markers.get_env_vars()
        self.display.supervisor_message(f"Initializing Phase {phase} session...")

        agent_options = ClaudeAgentOptions(
            cwd=str(self.working_dir),
            env=env_vars,
            permission_mode="bypassPermissions",
            hooks=self.hooks.get_hooks_config(),
        )

        if subagents:
            agent_options.agents = subagents
            self.logger.log_event(
                "SUBAGENTS",
                f"Configured {len(subagents)} exploration subagents: {list(subagents.keys())}"
            )

        async with ClaudeSDKClient(options=agent_options) as client:
            await client.query(initial_context)
            return await self._session_runner.run_phase_session(
                client_context_manager=client,
                initial_prompt=initial_context,
                phase=phase,
                signal_patterns=PHASE_COMPLETE_PATTERNS,
                review_coordinator=self._review_coordinator,
            )

    def _mark_phase_complete(self, phase: int) -> None:
        if phase == 1:
            self.markers.mark_requirements_complete()
        elif phase == 2:
            self.markers.mark_interfaces_complete()
        elif phase == 3:
            self.markers.mark_tests_complete()
        elif phase == 4:
            self.markers.mark_implementation_complete()

    def _display_usage_summary(self) -> None:
        usage = self.markers.get_all_usage()
        self.display.usage_summary(usage, PHASE_NAMES)

    async def _confirm_phase_completion(
        self,
        phase: int,
        doc_path: str = "",
        session_id: Optional[str] = None
    ) -> str:
        """Ask user to confirm phase completion. Returns 'proceed', 'edit', or 'regenerate'."""
        name = PHASE_NAMES.get(phase, f"Phase {phase}")

        self.display.phase_complete_banner(phase, name, doc_path)

        while True:
            response = input("\nYour choice [y/e/r]: ").strip().lower()

            if response in ['y', 'yes', '']:
                self.logger.log_user_confirmation(phase)
                self.logger.log_phase_complete(phase, name)
                # Mark phase complete in state.json
                self._mark_phase_complete(phase)
                return 'proceed'
            elif response == 'e':
                self.display.supervisor_message("Edit the document, then press Enter to continue...")
                self.display.supervisor_message(f"File: {doc_path}")
                input("\nPress Enter when done editing: ")
                return 'edit'
            elif response == 'r':
                return 'regenerate'
            else:
                self.display.print("\nOptions:")
                self.display.print("  y - Proceed to next phase")
                self.display.print("  e - Edit document manually, then reload")
                self.display.print("  r - Provide feedback to regenerate")
                self.display.print("  Ctrl+C - Abort workflow")

    async def _generate_and_verify_summary(self, phase: int, session_id: Optional[str] = None) -> str:
        """Generate summary with self-review verification."""
        summary_prompt = ContextBuilder.get_summary_prompt(phase)
        if not summary_prompt:
            return ""

        async with self.display.spinner(f"Generating Phase {phase} summary"):
            initial_summary = await self._extract_text_response(summary_prompt, session_id=session_id, phase=phase)

        review_prompt = ContextBuilder.get_review_prompt(phase)
        if not review_prompt:
            return initial_summary

        async with self.display.spinner("Verifying summary completeness"):
            review_response = await self._extract_text_response(review_prompt, session_id=session_id, phase=phase)

        if review_response.startswith(GAPS_FOUND_SIGNAL):
            lines = review_response.split('\n', 1)
            if len(lines) > 1:
                updated_summary = lines[1].strip()
                self.display.supervisor_message("Summary updated with missing items.")
                return updated_summary
            else:
                return initial_summary
        elif review_response.startswith(SUMMARY_VERIFIED_SIGNAL):
            lines = review_response.split('\n', 1)
            if len(lines) > 1:
                self.display.supervisor_success("Summary verified complete.")
                return lines[1].strip()
            else:
                return initial_summary
        else:
            self.display.supervisor_message("Summary captured.")
            return review_response if review_response else initial_summary

    async def _run_regeneration_conversation(
        self,
        phase: int,
        current_summary: str,
        initial_feedback: str
    ) -> tuple:
        """Run interactive regeneration conversation. Returns (was_completed, session_id)."""
        env_vars = self.markers.get_env_vars()
        context = ContextBuilder.build_regeneration_context(
            phase=phase,
            current_summary=current_summary,
            initial_feedback=initial_feedback
        )

        hooks_config = (
            self.hooks.get_extraction_hooks_config() if phase == 1
            else self.hooks.get_hooks_config()
        )

        async with ClaudeSDKClient(
            options=ClaudeAgentOptions(
                cwd=str(self.working_dir),
                env=env_vars,
                permission_mode="bypassPermissions",
                hooks=hooks_config,
            )
        ) as client:
            await client.query(context)
            return await self._session_runner.run_regeneration_session(
                client_context_manager=client,
                initial_prompt=context,
                phase=phase,
                complete_patterns=REGENERATION_COMPLETE_PATTERNS,
                canceled_patterns=REGENERATION_CANCELED_PATTERNS
            )

    async def _regenerate_summary(
        self,
        phase: int,
        session_id: Optional[str] = None
    ) -> str:
        """Regenerate summary via interactive conversation. Returns original if canceled."""
        _ = session_id  # Kept for API compatibility

        current_summary = self.markers.get_phase_document(phase)

        self.display.supervisor_message("What changes would you like to make?")
        self.display.supervisor_message("(Describe what to add, remove, or modify)")
        feedback = read_user_input("\nYour feedback: ").strip()

        if not feedback:
            self.display.supervisor_message("No feedback provided, keeping current summary.")
            return current_summary

        self.logger.log_user_input(f"Regenerate feedback: {feedback}")

        self.display.supervisor_message("Starting revision discussion...")

        was_completed, conversation_session_id = await self._run_regeneration_conversation(
            phase=phase,
            current_summary=current_summary,
            initial_feedback=feedback
        )

        if not was_completed:
            self.display.supervisor_message("Keeping original summary.")
            return current_summary

        async with self.display.spinner("Generating final summary"):
            final_summary_prompt = ContextBuilder.get_regeneration_summary_prompt()
            new_summary = await self._extract_text_response(
                final_summary_prompt,
                session_id=conversation_session_id,
                phase=phase
            )

        if new_summary:
            self.display.supervisor_success("Summary regenerated.")
            return new_summary
        else:
            self.display.supervisor_warning("Regeneration failed, keeping current summary.")
            return current_summary

    async def _start_review_coordinator(self) -> None:
        """Start the concurrent reviewer for Phase 4."""
        try:
            self.logger.log_event("ORCHESTRATOR", "Starting review coordinator for Phase 4")

            self._review_coordinator = self._create_review_coordinator()
            await self._review_coordinator.start()

            self.hooks.set_review_coordinator(self._review_coordinator)

            if self._review_coordinator.is_degraded:
                self.logger.log_event(
                    "ORCHESTRATOR",
                    "Review coordinator started in degraded mode"
                )
            else:
                self.logger.log_event(
                    "ORCHESTRATOR",
                    "Review coordinator ready"
                )

        except Exception as e:
            self.logger.log_event("ORCHESTRATOR", f"Review coordinator failed to start: {e}")
            self._review_coordinator = None

    async def _stop_review_coordinator(self) -> None:
        """Stop the review coordinator and clean up resources."""
        try:
            if self._review_coordinator is not None:
                self.logger.log_event("ORCHESTRATOR", "Stopping review coordinator")
                await self._review_coordinator.stop()
                self._review_coordinator = None

            self.hooks.set_review_coordinator(None)

        except Exception as e:
            self.logger.log_event("ORCHESTRATOR", f"Error stopping review coordinator: {e}")
            self._review_coordinator = None

    def _create_review_coordinator(self) -> ReviewCoordinator:
        """Create a new ReviewCoordinator for Phase 4."""
        requirements_summary = self.markers.get_phase_document(1) or "# Requirements\n(Not available)"
        interfaces_summary = self.markers.get_phase_document(2) or ""
        tests_summary = self.markers.get_phase_document(3) or ""

        config = ReviewCoordinatorConfig(
            file_threshold=1,
            enabled=True
        )

        return ReviewCoordinator(
            logger=self.logger,
            working_dir=str(self.working_dir),
            requirements_summary=requirements_summary,
            interfaces_summary=interfaces_summary,
            tests_summary=tests_summary,
            config=config
        )

    async def _extract_text_response(
        self,
        prompt: str,
        timeout: float = 300.0,
        session_id: Optional[str] = None,
        phase: Optional[int] = None
    ) -> str:
        """Send a query and collect the text response."""
        env_vars = self.markers.get_env_vars()

        async with ClaudeSDKClient(
            options=ClaudeAgentOptions(
                cwd=str(self.working_dir),
                env=env_vars,
                resume=session_id,
                permission_mode="bypassPermissions",
                hooks=self.hooks.get_extraction_hooks_config(),
            )
        ) as client:
            await client.query(prompt)
            return await self._session_runner.extract_text(
                client_context_manager=client,
                prompt=prompt,
                phase=phase,
                session_id=session_id,
                timeout=timeout
            )


async def run_supervisor(
    working_dir: Optional[str] = None,
    task: Optional[str] = None,
) -> None:
    """Entry point for the Waypoints supervisor."""
    orchestrator = WPOrchestrator(working_dir=working_dir)
    await orchestrator.run(initial_task=task)
