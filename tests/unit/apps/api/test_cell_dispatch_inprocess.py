"""InProcessCellDispatchAdapter unit tests (D133, S47).

Exercises the Phase 2-A in-process implementation of the CellDispatch
port: dispatch returns promptly, the cell runs in a background task on
the event loop, and exceptions raised by the cell are captured at the
port and logged structurally with the caller-supplied context.

Tests drive async code via ``asyncio.run`` per the codebase convention
(no pytest-asyncio dependency, mirroring the S45 messaging-application
test idiom).
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from apps.api.adapters.cell_dispatch_inprocess import (
    InProcessCellDispatchAdapter,
)


def test_dispatch_runs_cell_in_background_task() -> None:
    async def _scenario() -> None:
        adapter = InProcessCellDispatchAdapter()
        ran = asyncio.Event()

        async def _cell() -> None:
            ran.set()

        await adapter.dispatch(_cell, context={"intake_id": "i1"})
        await asyncio.wait_for(ran.wait(), timeout=1.0)

    asyncio.run(_scenario())


def test_dispatch_returns_quickly_when_cell_is_slow() -> None:
    """``dispatch`` does not await the cell; the cell completes after."""
    async def _scenario() -> None:
        adapter = InProcessCellDispatchAdapter()
        cell_done = asyncio.Event()

        async def _slow_cell() -> None:
            await asyncio.sleep(0.05)
            cell_done.set()

        loop = asyncio.get_event_loop()
        start = loop.time()
        await adapter.dispatch(_slow_cell, context={"intake_id": "i2"})
        elapsed = loop.time() - start
        assert elapsed < 0.04, (
            f"dispatch should return before the cell completes; "
            f"took {elapsed:.3f}s"
        )
        await asyncio.wait_for(cell_done.wait(), timeout=1.0)

    asyncio.run(_scenario())


def test_dispatch_captures_cell_exception_and_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A cell exception is captured at the port and surfaces in logs.

    The port's contract carries cell-failure logging — exceptions do
    not propagate to the caller and never leave the task unhandled.
    """
    async def _scenario() -> asyncio.Task[None]:
        adapter = InProcessCellDispatchAdapter()
        finished = asyncio.Event()

        async def _failing_cell() -> None:
            try:
                raise RuntimeError("boom")
            finally:
                finished.set()

        # The caller does not see the exception:
        await adapter.dispatch(
            _failing_cell,
            context={"intake_id": "i3", "tenant_id": "t1"},
        )
        await asyncio.wait_for(finished.wait(), timeout=1.0)
        # Yield once so the task's exception handler runs.
        await asyncio.sleep(0)
        # Return a sentinel; the adapter retains the task ref internally
        # so the logging callback has time to fire.
        return None  # type: ignore[return-value]

    with caplog.at_level(
        logging.ERROR, logger="padhanam.api.cell_dispatch"
    ):
        asyncio.run(_scenario())

    failure_records = [
        r for r in caplog.records
        if "cell-run failed" in r.getMessage()
    ]
    assert failure_records, "structured failure log missing"
    rec = failure_records[0]
    assert rec.levelno == logging.ERROR
    # The context dict surfaces via ``extra`` so downstream observers
    # can correlate the failure to the inbound it traces to.
    assert getattr(rec, "context", None) == {
        "intake_id": "i3",
        "tenant_id": "t1",
    }


def test_dispatch_independent_calls_do_not_interfere() -> None:
    """Concurrent dispatches each run to completion independently."""
    async def _scenario() -> None:
        adapter = InProcessCellDispatchAdapter()
        counter = {"a": 0, "b": 0}
        done = asyncio.Event()

        async def _cell_a() -> None:
            await asyncio.sleep(0.01)
            counter["a"] += 1
            if counter["a"] and counter["b"]:
                done.set()

        async def _cell_b() -> None:
            counter["b"] += 1
            if counter["a"] and counter["b"]:
                done.set()

        await adapter.dispatch(_cell_a, context={"id": "a"})
        await adapter.dispatch(_cell_b, context={"id": "b"})
        await asyncio.wait_for(done.wait(), timeout=1.0)
        assert counter == {"a": 1, "b": 1}

    asyncio.run(_scenario())
