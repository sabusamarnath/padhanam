"""In-process CellDispatch adapter — Phase 2-A (D133, S47).

Path A implementation of the ``CellDispatch`` port from
``contexts/messaging/application/ports/cell_dispatch.py``: dispatch
schedules the cell run as an ``asyncio.create_task`` on the current
event loop and returns immediately. The Twilio webhook handler at
``apps/api/routers/messaging.py`` thereby returns 2xx promptly and the
cell completes asynchronously while Twilio's connection has already
closed.

Per D133 the port preserves Phase 2-B+ migration to
``QueueCellDispatchAdapter`` (out-of-process queue) as a swap of
adapter at the composition root — no change at the call site. The
Phase 2-A trade-off (a cell run lost on container restart) is
acceptable for operator dogfooding; the customer-volume trigger
activates Phase 2-B.

The port's contract carries cell-failure logging: this adapter wraps
``cell_run`` in a try/except inside the spawned task. Any exception is
captured via ``logging.exception`` with the caller-supplied ``context``
dict surfacing as ``extra={"context": ...}`` — a structured trace that
identifies the failed run by ``intake_id`` / ``tenant_id`` /
``external_id``. This closes the bare-``except`` at the prior
synchronous webhook shape.

The strong reference set on ``self._tasks`` prevents asyncio from
garbage-collecting the task before completion (``asyncio.create_task``
only weakly references the task; without a strong reference the loop
may cancel the task at GC time, which would silently abort the cell).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

_logger = logging.getLogger("padhanam.api.cell_dispatch")


class InProcessCellDispatchAdapter:
    """Run the cell on the same event loop via ``asyncio.create_task``."""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[None]] = set()

    async def dispatch(
        self,
        cell_run: Callable[[], Awaitable[None]],
        *,
        context: dict[str, Any],
    ) -> None:
        """Schedule the cell run; return promptly.

        Exceptions raised by ``cell_run`` are caught inside the spawned
        task and logged structurally with ``context``; they never
        propagate back to the caller and the task never raises an
        unhandled exception that would emit a Python-level warning.
        """
        async def _runner() -> None:
            try:
                await cell_run()
            except Exception:
                _logger.exception(
                    "cell-run failed in background task",
                    extra={"context": dict(context)},
                )

        task = asyncio.create_task(_runner())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)


__all__ = ["InProcessCellDispatchAdapter"]
