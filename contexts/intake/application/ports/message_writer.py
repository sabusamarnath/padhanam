"""MessageWriter consumer port (D127 alternative (d), D129, S45).

The intake context's consumer-side port for driving a messaging
write from the inbound-message orchestration. Per the D16/D17/D28
cross-context contract the intake application layer cannot import
``contexts.messaging`` directly; it defines the shape it needs here,
and the ``apps/`` composition layer provides the adapter that
invokes ``contexts.messaging.application.record_inbound_message``.

This module imports nothing from ``contexts.messaging`` — the result
DTO is intake-context-owned and uses primitive ``str`` fields where
the producer uses its own enums (``direction``, ``channel``,
``status``). The structural duplication is the intentional cost of
the D17 boundary; the wiring adapter does field-for-field
translation. The shape follows the ``PortfolioWriter`` precedent at
``contexts/intake/application/ports/portfolio_writer.py``.

Ports layer is pure per D16 — stdlib plus shared_kernel only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from shared_kernel import ActorContext


@dataclass(frozen=True)
class MessageWriteResult:
    """Intake-owned mirror of a messaging Message write (D129).

    Carries the fields the orchestration's caller — the inbound
    webhook receiver — needs to render a response. ``direction``,
    ``channel``, and ``status`` are primitive strings mirroring the
    producer's enum values. ``intake_id`` is the IntakeRecord the
    inbound Message traces to per D128.
    """

    message_id: UUID
    direction: str
    channel: str
    body: str
    from_address: str
    to_address: str
    status: str
    external_id: str | None
    intake_id: UUID
    created_at: datetime


class MessageWriter(Protocol):
    """Consumer port: drive an inbound-message write from an orchestration.

    The single method carries the request-scoped ActorContext through
    to the messaging use case (which re-checks authorisation at its
    own decorator) and the ``intake_id`` the orchestration recorded.
    The wiring adapter at ``apps/`` implements this Protocol by
    invoking ``contexts.messaging.application.record_inbound_message``
    and translating its Message aggregate into the result DTO above.
    """

    async def record_inbound_message(
        self,
        *,
        actor: ActorContext,
        channel: str,
        from_address: str,
        to_address: str,
        body: str,
        external_id: str | None,
        intake_id: UUID,
    ) -> MessageWriteResult:
        """Persist an inbound Message carrying ``intake_id``."""
        ...


__all__ = ["MessageWriteResult", "MessageWriter"]
