#!/usr/bin/env python3
"""
Waypoints Supervisor - Terminal Display

Centralized display module for rich terminal output. Uses the `rich` library
for structured elements (panels, tables, status spinners) and raw sys.stdout
for Claude's streaming text.

Falls back to plain text when rich is unavailable or NO_COLOR is set.
"""

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from typing import Dict, Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.box import HEAVY, ROUNDED, DOUBLE
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from .templates import (
    PHASE_NAMES,
    format_phase_header,
    format_workflow_header,
    format_phase_complete_banner,
    format_workflow_complete,
)

# Braille spinner frames at 80ms intervals
_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_SPINNER_INTERVAL = 0.08


class SupervisorDisplay:
    """Centralized terminal display for Waypoints supervisor mode."""

    def __init__(self) -> None:
        self._use_rich = (
            HAS_RICH
            and not os.environ.get("NO_COLOR")
            and sys.stdout.isatty()
        )
        if self._use_rich:
            self._console = Console()
        else:
            self._console = None

        self._stream_prefix_shown = False
        self._tool_spinner_task: Optional[asyncio.Task] = None
        self._tool_spinner_stop = asyncio.Event()

    # =========================================================================
    # Structured output (rich panels/tables with plain-text fallback)
    # =========================================================================

    def workflow_header(
        self,
        working_dir: str,
        workflow_id: str,
        markers_dir: str
    ) -> None:
        if self._use_rich:
            content = (
                f"[bold]Working directory:[/bold] {working_dir}\n"
                f"[bold]Workflow ID:[/bold]       {workflow_id}\n"
                f"[bold]Markers directory:[/bold] {markers_dir}"
            )
            self._console.print()
            self._console.print(Panel(
                content,
                title="[bold]Waypoints Supervisor[/bold]",
                box=HEAVY,
                style="cyan",
            ))
        else:
            print(format_workflow_header(working_dir, workflow_id, markers_dir))

    def phase_header(self, phase: int, name: str) -> None:
        if self._use_rich:
            self._console.print()
            self._console.print(Panel(
                f"[bold cyan]PHASE {phase}: {name.upper()}[/bold cyan]",
                box=HEAVY,
                style="cyan",
            ))
        else:
            print(format_phase_header(phase, name))

    def phase_complete_banner(
        self,
        phase: int,
        name: str,
        doc_path: str = ""
    ) -> None:
        if self._use_rich:
            lines = [f"[bold]Phase {phase} ({name}) Complete[/bold]"]
            if doc_path:
                lines.append("")
                lines.append(f"[dim]Review:[/dim] {doc_path}")
                lines.append("[dim]        (You can open this file in your editor)[/dim]")
            lines.append("")
            lines.append("[bold]Options:[/bold]")
            lines.append("  [green]y[/green] - Proceed to next phase")
            lines.append("  [yellow]e[/yellow] - Edit document manually, then reload")
            lines.append("  [blue]r[/blue] - Provide feedback to regenerate")
            lines.append("  [red]Ctrl+C[/red] - Abort workflow")
            self._console.print(Panel(
                "\n".join(lines),
                box=ROUNDED,
            ))
        else:
            print(format_phase_complete_banner(phase, name, doc_path))

    def workflow_complete(self) -> None:
        if self._use_rich:
            self._console.print()
            self._console.print(Panel(
                "[bold green]Waypoints Workflow Complete![/bold green]",
                box=DOUBLE,
                style="green",
            ))
        else:
            print(format_workflow_complete())

    def usage_summary(self, usage: Dict, phase_names: Dict[int, str]) -> None:
        if self._use_rich:
            table = Table(
                title="Token Usage Summary",
                box=ROUNDED,
                show_lines=True,
            )
            table.add_column("Phase", style="bold")
            table.add_column("Tokens In", justify="right")
            table.add_column("Tokens Out", justify="right")
            table.add_column("Total", justify="right", style="bold")
            table.add_column("Cost", justify="right")
            table.add_column("Duration", justify="right")
            table.add_column("Turns", justify="right")

            for phase_num in [1, 2, 3, 4]:
                phase_key = f"phase{phase_num}"
                phase_data = usage.get(phase_key, {})
                name = phase_names.get(phase_num, f"Phase {phase_num}")

                input_tokens = phase_data.get("input_tokens", 0)
                output_tokens = phase_data.get("output_tokens", 0)
                total_tokens = input_tokens + output_tokens
                cost = phase_data.get("cost_usd", 0.0)
                duration = phase_data.get("duration_ms", 0)
                turns = phase_data.get("turns", 0)

                if total_tokens > 0:
                    table.add_row(
                        f"P{phase_num} {name}",
                        f"{input_tokens:,}",
                        f"{output_tokens:,}",
                        f"{total_tokens:,}",
                        f"${cost:.4f}",
                        f"{duration / 1000.0:.1f}s",
                        str(turns),
                    )

            total = usage.get("total", {})
            total_input = total.get("input_tokens", 0)
            total_output = total.get("output_tokens", 0)
            total_tokens = total_input + total_output
            total_cost = total.get("cost_usd", 0.0)
            total_duration = total.get("duration_ms", 0)
            total_turns = total.get("turns", 0)

            table.add_row(
                "[bold]TOTAL[/bold]",
                f"[bold]{total_input:,}[/bold]",
                f"[bold]{total_output:,}[/bold]",
                f"[bold]{total_tokens:,}[/bold]",
                f"[bold]${total_cost:.4f}[/bold]",
                f"[bold]{total_duration / 1000.0:.1f}s[/bold]",
                f"[bold]{total_turns}[/bold]",
            )

            self._console.print()
            self._console.print(table)
        else:
            self._print_plain_usage(usage, phase_names)

    def _print_plain_usage(self, usage: Dict, phase_names: Dict[int, str]) -> None:
        print("\n" + "=" * 60)
        print("TOKEN USAGE SUMMARY")
        print("=" * 60)

        for phase_num in [1, 2, 3, 4]:
            phase_key = f"phase{phase_num}"
            phase_data = usage.get(phase_key, {})
            name = phase_names.get(phase_num, f"Phase {phase_num}")

            input_tokens = phase_data.get("input_tokens", 0)
            output_tokens = phase_data.get("output_tokens", 0)
            total_tokens = input_tokens + output_tokens
            cost = phase_data.get("cost_usd", 0.0)
            duration = phase_data.get("duration_ms", 0)
            turns = phase_data.get("turns", 0)

            if total_tokens > 0:
                print(f"\nPhase {phase_num} ({name}):")
                print(f"  Tokens: {input_tokens:,} in / {output_tokens:,} out ({total_tokens:,} total)")
                print(f"  Cost: ${cost:.4f}")
                print(f"  Duration: {duration / 1000.0:.1f}s | Turns: {turns}")

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

    # =========================================================================
    # Streaming Claude output (raw stdout for token-by-token streaming)
    # =========================================================================

    def stream_text(self, text: str) -> None:
        if not self._stream_prefix_shown:
            if self._use_rich:
                sys.stdout.write("\033[36m● Claude\033[0m ")
            else:
                sys.stdout.write("● Claude ")
            self._stream_prefix_shown = True
        sys.stdout.write(text)
        sys.stdout.flush()

    def stream_text_end(self) -> None:
        self._stream_prefix_shown = False

    # =========================================================================
    # Tool-use spinner (asyncio-based braille animation)
    # =========================================================================

    async def start_tool_spinner(self, tool_name: str) -> None:
        await self.stop_tool_spinner()
        self._tool_spinner_stop = asyncio.Event()

        async def _animate():
            i = 0
            while not self._tool_spinner_stop.is_set():
                frame = _SPINNER_FRAMES[i % len(_SPINNER_FRAMES)]
                if self._use_rich:
                    sys.stdout.write(f"\r\033[K\033[2m  {frame} {tool_name}\033[0m")
                else:
                    sys.stdout.write(f"\r  {frame} {tool_name}")
                sys.stdout.flush()
                i += 1
                try:
                    await asyncio.wait_for(
                        self._tool_spinner_stop.wait(),
                        timeout=_SPINNER_INTERVAL
                    )
                    break
                except asyncio.TimeoutError:
                    pass
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()

        self._tool_spinner_task = asyncio.create_task(_animate())

    async def stop_tool_spinner(self) -> None:
        if self._tool_spinner_task is not None and not self._tool_spinner_task.done():
            self._tool_spinner_stop.set()
            try:
                await self._tool_spinner_task
            except asyncio.CancelledError:
                pass
            self._tool_spinner_task = None

    # =========================================================================
    # Silent operation spinner (context manager for awaited operations)
    # =========================================================================

    @asynccontextmanager
    async def spinner(self, message: str):
        if self._use_rich:
            with self._console.status(f"[bold cyan]{message}[/bold cyan]", spinner="dots"):
                yield
        else:
            sys.stdout.write(f"  {message}...")
            sys.stdout.flush()
            yield
            sys.stdout.write(" done\n")
            sys.stdout.flush()

    # =========================================================================
    # Status messages
    # =========================================================================

    def supervisor_message(self, text: str) -> None:
        if self._use_rich:
            self._console.print(f"[dim]⚙ {text}[/dim]")
        else:
            print(f"[Supervisor] {text}")

    def supervisor_success(self, text: str) -> None:
        if self._use_rich:
            self._console.print(f"[green]✓ {text}[/green]")
        else:
            print(f"[Supervisor] {text}")

    def supervisor_error(self, text: str) -> None:
        if self._use_rich:
            self._console.print(f"[red]✗ {text}[/red]")
        else:
            print(f"[Supervisor] {text}", file=sys.stderr)

    def supervisor_warning(self, text: str) -> None:
        if self._use_rich:
            self._console.print(f"[yellow]⚠ {text}[/yellow]")
        else:
            print(f"[Supervisor] Warning: {text}")

    def tip(self, text: str) -> None:
        if self._use_rich:
            self._console.print(f"[dim italic]{text}[/dim italic]")
        else:
            print(f"[Tip: {text}]")

    def feedback_injection(self, feedback: str) -> None:
        if self._use_rich:
            self._console.print(Panel(
                feedback,
                title="[bold yellow]Reviewer Feedback[/bold yellow]",
                style="yellow",
                box=ROUNDED,
            ))
        else:
            print(f"\n{feedback}\n")

    def document_preview(self, preview: str) -> None:
        if self._use_rich:
            self._console.print(Panel(preview, title="Document Preview", box=ROUNDED, style="dim"))
        else:
            print(f"---\n{preview}\n---")

    def knowledge_summary(self, summary: str) -> None:
        if self._use_rich:
            self._console.print(f"\n[green]{summary}[/green]")
        else:
            print(f"\n{summary}")

    def print(self, text: str = "") -> None:
        """General purpose print, for messages that don't fit other categories."""
        print(text)
