"""In-process BroadcastDispatch adapter — Phase 2-A (D143, S53).

Symmetric to ``apps/api/adapters/cell_dispatch_inprocess.py``: the
adapter implements both the registry surface
(``BroadcastFlowRegistry``) and the dispatch surface
(``BroadcastDispatch``) in one composite. The single object holds the
trigger-type → implementer mapping the composition root registers and
the dispatch consults.

Per D143 the dispatch invokes the registered implementer's ``fire``
method synchronously inside an ``asyncio.create_task`` and returns
promptly. The Phase 2-A trade-off (a broadcast lost on container
restart between trigger receipt and implementer completion) mirrors
the CellDispatch trade-off; the Phase 2-B+ swap is a different adapter
(out-of-process queue) at composition root with no call-site change.

Per Finding 6 at S53 pre-write reconciliation the dispatch is symmetric
to CellDispatch but routing is deterministic on ``trigger_type`` rather
than classifier-driven. A trigger type with no registered implementer
raises ``NoRegisteredBroadcastImplementerError`` (no silent drop).

Implementer ``fire`` exceptions are caught inside the spawned task and
logged structurally with the trigger context dict surfacing as
``extra={"context": ...}`` — mirrors the CellDispatch failure-logging
discipline.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from contexts.messaging.application.ports.broadcast_dispatch import (
    NoRegisteredBroadcastImplementerError,
)
from shared_kernel.broadcast_flow import (
    BroadcastFlow,
    BroadcastTriggerType,
    TriggerContext,
)

_logger = logging.getLogger("padhanam.messaging.broadcast_dispatch")


class InProcessBroadcastDispatchAdapter:
    """In-process implementation of BroadcastDispatch plus BroadcastFlowRegistry.

    A single composite object: the composition root constructs one
    instance, registers every BroadcastFlow implementer it knows about,
    and passes the same instance to any caller that needs the dispatch
    surface. The class satisfies both Protocols structurally; tests can
    inject either surface independently.
    """

    def __init__(self) -> None:
        self._implementers: dict[BroadcastTriggerType, BroadcastFlow] = {}
        self._tasks: set[asyncio.Task[None]] = set()

    # ------------------------------------------------------------------ registry surface

    def register(
        self,
        *,
        trigger_type: BroadcastTriggerType,
        implementer: BroadcastFlow,
    ) -> None:
        """Register ``implementer`` as the BroadcastFlow for ``trigger_type``."""
        self._implementers[trigger_type] = implementer

    def get(
        self, trigger_type: BroadcastTriggerType
    ) -> BroadcastFlow | None:
        """Return the registered implementer for ``trigger_type`` or None."""
        return self._implementers.get(trigger_type)

    def registered_types(self) -> frozenset[BroadcastTriggerType]:
        """Return the set of currently-registered trigger types."""
        return frozenset(self._implementers.keys())

    # ------------------------------------------------------------------ dispatch surface

    async def dispatch(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        trigger_context: TriggerContext,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Route the trigger to its registered implementer; return promptly.

        Raises ``NoRegisteredBroadcastImplementerError`` synchronously
        when no implementer is registered for the trigger type — the
        caller (HTTP trigger endpoint at S54; ThresholdEvaluator at
        S57) maps the error to its surface-appropriate failure
        signal.
        """
        implementer = self._implementers.get(trigger_context.trigger_type)
        if implementer is None:
            raise NoRegisteredBroadcastImplementerError(
                trigger_type=trigger_context.trigger_type.value
            )

        log_context: dict[str, Any] = {
            "trigger_id": str(trigger_context.trigger_id),
            "trigger_type": trigger_context.trigger_type.value,
            "tenant_id": str(tenant_id),
            "user_id": user_id,
        }
        if context:
            log_context.update(context)

        async def _runner() -> None:
            try:
                await implementer.fire(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    trigger_context=trigger_context,
                )
            except Exception:
                _logger.exception(
                    "broadcast implementer fire failed in background task",
                    extra={"context": dict(log_context)},
                )

        task = asyncio.create_task(_runner())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)


__all__ = ["InProcessBroadcastDispatchAdapter"]
