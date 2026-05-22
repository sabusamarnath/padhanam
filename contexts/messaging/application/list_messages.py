"""list_messages use case (D129).

Paginated read behind GET ``/api/v1/messaging/messages`` with
optional direction and channel filters. Returns a ``MessageListPage``
ordered newest-first; the HTTP layer encodes ``next_cursor`` with
the messaging cursor codec.
"""

from __future__ import annotations

from contexts.messaging.domain.query_filters import (
    MessageListCursor,
    MessageListFilters,
)
from contexts.messaging.ports.message_repository import (
    MessageListPage,
    MessageRepository,
)
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    MESSAGING_MESSAGE_LIST,
    requires_authorisation,
)


@requires_authorisation(MESSAGING_MESSAGE_LIST)
async def list_messages(
    *,
    repository: MessageRepository,
    actor: ActorContext,
    filters: MessageListFilters | None = None,
    cursor: MessageListCursor | None = None,
    page_size: int = 20,
) -> MessageListPage:
    """List a tenant's messages, paginated newest-first."""
    return await repository.list_for_tenant(
        tenant_context=actor.tenant_context,
        filters=filters,
        cursor=cursor,
        page_size=page_size,
    )


__all__ = ["list_messages"]
