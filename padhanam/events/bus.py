"""Domain event bus (D17).

Contexts publish domain events from their domain or application layer;
subscriptions wire in apps/. The synchronous in-process implementation
dispatches publications immediately, on the publisher's thread, in the
order subscriptions were registered. The interface is broker-ready: a
future RedisStreamsAdapter (or NATS, Kafka, etc.) implements the same
EventBus protocol with no change to publishers or subscribers.

Phase 1 commits to the synchronous bus only. The interface shape is
deliberate so the production swap is configuration, not refactor — the
broker-backed adapter takes the same publish/subscribe surface.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Protocol
from uuid import uuid4


@dataclass(frozen=True)
class DomainEvent:
    """Base for every domain event.

    Subclasses extend this with event-specific fields. The base carries the
    metadata every subscriber needs regardless of event type: a stable
    event_id, the emission timestamp, and the tenant_id (D12 jurisdiction
    flows alongside, but lives in subclasses that need it because some
    cross-tenant platform events do not carry one).
    """

    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


EventHandler = Callable[[DomainEvent], None]


class EventBus(Protocol):
    """Publish/subscribe surface every implementation honours.

    publish() is fire-and-forget from the caller's perspective: synchronous
    implementations dispatch on the calling thread and return after every
    handler runs; broker-backed implementations enqueue the event and return
    immediately. Handlers cannot signal failure back to the publisher —
    the bus is for fan-out, not for request/response.
    """

    def publish(self, event: DomainEvent) -> None: ...

    def subscribe(
        self, event_type: type[DomainEvent], handler: EventHandler
    ) -> None: ...


class SynchronousEventBus:
    """In-process synchronous bus. Dispatches in subscription order.

    Handler exceptions propagate. Publisher contexts are responsible for
    wrapping publish() if they want the bus to be best-effort. Phase 1
    deliberately does not catch — silent failures here would mean
    subscribers (audit, observability) drop events without surfacing.
    """

    def __init__(self) -> None:
        self._subscribers: dict[type[DomainEvent], list[EventHandler]] = (
            defaultdict(list)
        )

    def publish(self, event: DomainEvent) -> None:
        for event_type, handlers in self._subscribers.items():
            if isinstance(event, event_type):
                for handler in handlers:
                    handler(event)

    def subscribe(
        self, event_type: type[DomainEvent], handler: EventHandler
    ) -> None:
        self._subscribers[event_type].append(handler)
