"""BroadcastDispatch consumer port — trigger-to-implementer routing (D143, S53).

Symmetric to S47's CellDispatch port. CellDispatch hands an inbound-
triggered cell run to a background task; BroadcastDispatch routes a
trigger to a registered BroadcastFlow implementer (D142). The structural
difference is deterministic routing on ``trigger_type`` rather than
classifier-driven routing.

The dispatch substrate accepts triggers from two sources at P15:
(1) scheduled triggers fire via the HTTP trigger endpoint (D145; lands
at S54); (2) event-driven triggers fire from the ThresholdEvaluator
(lands at S57) when state changes match configured rules. Both feed
``BroadcastDispatch.dispatch``; the implementation routes by
``trigger_context.trigger_type``.

The dispatch returns ``None`` because the BroadcastFlow implementer's
response is rendered and persisted as an outbound message inside the
dispatch flow (the dispatch is fire-and-forget at this layer). The
implementer's response is observable through the persisted outbound
Message plus the BROADCAST_INITIATED audit event the dispatch emits
before invoking the implementer.

A trigger_type with no registered implementer fails fast: the adapter
raises a structured error (``NoRegisteredBroadcastImplementerError``)
rather than dropping silently. The composition root is responsible for
registering every BroadcastFlow implementer the deployment may dispatch
against.

Ports layer is pure per D16 — stdlib only.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from shared_kernel.broadcast_flow import TriggerContext


class NoRegisteredBroadcastImplementerError(Exception):
    """Raised when BroadcastDispatch receives a trigger_type with no
    registered implementer. The structured message names the
    trigger_type so the operator can correlate the dispatch failure
    back to the missing composition-root registration."""

    def __init__(self, trigger_type: str) -> None:
        super().__init__(
            "BroadcastDispatch has no registered implementer for "
            f"trigger_type={trigger_type!r}; composition root must "
            "register every BroadcastTriggerType value the dispatcher "
            "may route to"
        )
        self.trigger_type = trigger_type


@runtime_checkable
class BroadcastDispatch(Protocol):
    """Trigger-driven background-task dispatcher (D143).

    The dispatch routes ``trigger_context`` to the BroadcastFlow
    implementer registered at composition root for the
    ``trigger_type``. Implementations may run the implementer
    synchronously or hand it off to a background task; either way,
    ``dispatch`` itself completes promptly so HTTP trigger endpoint
    callers and ThresholdEvaluator callers do not block on implementer
    completion.

    ``context`` carries identifiers the implementation logs on
    implementer failure (``trigger_id``, ``trigger_type``,
    ``tenant_id``, ``user_id``) so the failed broadcast can be
    correlated to the originating trigger.
    """

    async def dispatch(
        self,
        *,
        tenant_id: UUID,
        user_id: str,
        trigger_context: TriggerContext,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Route the trigger to its registered implementer; return promptly."""
        ...


__all__ = ["BroadcastDispatch", "NoRegisteredBroadcastImplementerError"]
