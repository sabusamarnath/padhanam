"""BroadcastFlowRegistry consumer port — implementer-registration surface (D143, S53).

The dispatch substrate consults a registry mapping
``BroadcastTriggerType`` to the BroadcastFlow implementer registered
for that trigger type. The registry mechanism mirrors S45's
ConversationFlow registry pattern at the contract harness; this
registry is the composition-root surface (the harness is at
``tests/contract/broadcast_flow/``).

A trigger type with no registered implementer surfaces at dispatch
time via ``NoRegisteredBroadcastImplementerError`` from the dispatch
port. The registry's ``register``/``get`` interface is the seam the
composition root populates and the dispatch consults.

Ports layer is pure per D16 — stdlib only.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from shared_kernel.broadcast_flow import BroadcastFlow, BroadcastTriggerType


@runtime_checkable
class BroadcastFlowRegistry(Protocol):
    """The composition-root surface for BroadcastFlow implementer registration.

    ``register`` adds an implementer for a trigger type. ``get``
    returns the registered implementer or ``None``. ``registered_types``
    returns the set of trigger types currently registered (for
    diagnostic surfaces).
    """

    def register(
        self,
        *,
        trigger_type: BroadcastTriggerType,
        implementer: BroadcastFlow,
    ) -> None:
        """Register ``implementer`` as the BroadcastFlow for ``trigger_type``.

        Re-registration for an already-registered trigger type replaces
        the prior implementer (composition root may swap during tests).
        """
        ...

    def get(
        self, trigger_type: BroadcastTriggerType
    ) -> BroadcastFlow | None:
        """Return the registered implementer for ``trigger_type`` or None."""
        ...

    def registered_types(self) -> frozenset[BroadcastTriggerType]:
        """Return the set of currently-registered trigger types."""
        ...


__all__ = ["BroadcastFlowRegistry"]
