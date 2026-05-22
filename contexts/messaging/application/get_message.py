"""get_message use case (D129).

Single-record read behind GET ``/api/v1/messaging/messages/{id}``.
Returns the Message or ``None`` when absent or cross-tenant; the
HTTP layer translates ``None`` to a 404.
"""

from __future__ import annotations

from uuid import UUID

from contexts.messaging.domain import Message
from contexts.messaging.ports.message_repository import MessageRepository
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    MESSAGING_MESSAGE_GET,
    requires_authorisation,
)


@requires_authorisation(MESSAGING_MESSAGE_GET)
async def get_message(
    *,
    repository: MessageRepository,
    actor: ActorContext,
    message_id: UUID,
) -> Message | None:
    """Return a single Message by id, scoped to the actor's tenant."""
    return await repository.get_by_id(
        tenant_context=actor.tenant_context, message_id=message_id
    )


__all__ = ["get_message"]
