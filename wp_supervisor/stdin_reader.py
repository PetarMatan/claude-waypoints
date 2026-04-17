#!/usr/bin/env python3
"""
Background stdin reader for developer interrupt-during-streaming.

Reads stdin on a daemon thread while Claude is streaming, queuing typed
lines for injection at the next natural break point (after _process_stream).
"""

import logging
import queue
import select
import sys
import threading
from typing import Optional


logger = logging.getLogger(__name__)


class StdinInterruptReader:
    """
    Thread-based stdin reader that captures input during streaming.

    Lifecycle:
    - start(): Begin reading stdin on a background daemon thread.
    - stop(): Signal the reader to stop. Blocks briefly for thread cleanup.
    - drain(): Return all queued input as a single concatenated string,
               clearing the queue. Returns None if queue is empty or
               contains only whitespace.

    Thread safety: The internal queue.Queue is thread-safe. start/stop/drain
    are called from the main asyncio thread; the background thread only
    writes to the queue.

    Must be stopped before read_user_input() is called, so stdin returns
    to normal blocking read behavior.
    """

    def __init__(self) -> None:
        self._queue: queue.Queue[str] = queue.Queue()
        self._stop_event: threading.Event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """
        Start the background stdin reader thread.

        Spawns a daemon thread that reads lines from stdin and enqueues them.
        No-op if already running.

        The thread exits when stop() sets the stop event OR when stdin
        produces EOF. Uses select/poll on stdin to allow periodic stop checks
        rather than blocking indefinitely on readline().
        """
        if self.is_running:
            return

        self._stop_event.clear()

        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """
        Signal the background reader to stop and wait for thread exit.

        After stop(), stdin is no longer being read by this class —
        safe to call read_user_input().

        No-op if not running. Waits up to a short timeout for thread join.
        """
        if self._thread is None:
            return

        self._stop_event.set()
        self._thread.join(timeout=0.5)
        self._thread = None

    def drain(self) -> Optional[str]:
        """
        Drain all queued lines into a single string.

        Returns:
            Concatenated queued input (newline-joined), or None if the queue
            is empty or contains only whitespace [EDGE-4, REQ-7].

        Clears the queue regardless of return value.
        """
        lines = []
        while not self._queue.empty():
            try:
                lines.append(self._queue.get_nowait())
            except queue.Empty:
                break

        if not lines:
            return None

        result = "\n".join(lines)
        if not result.strip():
            return None

        return result

    def _reader_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                readable, _, _ = select.select([sys.stdin], [], [], 0.1)
                if readable:
                    line = sys.stdin.readline()
                    if not line:  # EOF
                        break
                    self._queue.put(line.rstrip('\n'))
            except Exception:
                logger.warning("stdin reader error", exc_info=True)
                break

    @property
    def is_running(self) -> bool:
        """Whether the background reader thread is currently active."""
        return self._thread is not None and self._thread.is_alive()
