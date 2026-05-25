"""CellDispatch consumer port — webhook-to-background-task seam (D133, S47).

The Twilio WhatsApp webhook returns 2xx promptly and hands the manual
entry cell run to a background task through this port. Per D133 the
port preserves Phase 2-B+ migration to an out-of-process queue
implementation as adapter swap — call sites do not change.

The port's contract carries cell-failure logging: any exception raised
by the dispatched ``cell_run`` is captured at the implementation and
logged structurally with the caller's ``context``. This closes the
bare-``except`` gap at the prior synchronous webhook shape (S46 smoke
finding at ``apps/api/routers/messaging.py``).

``cell_run`` is a zero-argument callable producing an awaitable — not an
awaitable directly — so the implementation can decide when (and on what
loop) to enter the coroutine. The caller binds its arguments at the
closure: ``lambda: _run_manual_entry_cell(messaging=..., actor=..., ...)``.

Ports layer is pure per D16 — stdlib only.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Protocol


class CellDispatch(Protocol):
    """Cell-run background-task dispatcher (D133).

    Implementations return immediately after handing the cell run off.
    """

    async def dispatch(
        self,
        cell_run: Callable[[], Awaitable[None]],
        *,
        context: dict[str, Any],
    ) -> None:
        """Dispatch ``cell_run`` to a background task; return promptly.

        The cell's *completion* happens in the background — Phase 2-A
        in-process, Phase 2-B+ out-of-process. ``dispatch`` itself
        completes quickly (in-process: ``asyncio.create_task`` then
        return; queued: enqueue then return). The method is async so
        an out-of-process implementation can await the enqueue I/O,
        and so tests can substitute a synchronous-await fake.

        ``context`` carries identifiers (``intake_id``, ``tenant_id``,
        ``external_id``) the implementation logs on cell failure so the
        failed run can be correlated to the inbound it traces to.
        """
        ...


__all__ = ["CellDispatch"]
