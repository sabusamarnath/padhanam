from __future__ import annotations

from dataclasses import dataclass

from padhanam.events import DomainEvent, SynchronousEventBus


@dataclass(frozen=True)
class _Alpha(DomainEvent):
    payload: str = ""


@dataclass(frozen=True)
class _Beta(DomainEvent):
    count: int = 0


def test_subscriber_receives_published_event() -> None:
    bus = SynchronousEventBus()
    received: list[_Alpha] = []
    bus.subscribe(_Alpha, received.append)

    event = _Alpha(payload="hello")
    bus.publish(event)

    assert received == [event]


def test_subscribers_for_other_types_are_not_called() -> None:
    bus = SynchronousEventBus()
    alpha_received: list[_Alpha] = []
    beta_received: list[_Beta] = []
    bus.subscribe(_Alpha, alpha_received.append)
    bus.subscribe(_Beta, beta_received.append)

    bus.publish(_Alpha(payload="x"))

    assert len(alpha_received) == 1
    assert beta_received == []


def test_handlers_run_in_subscription_order() -> None:
    bus = SynchronousEventBus()
    order: list[str] = []
    bus.subscribe(_Alpha, lambda _: order.append("first"))
    bus.subscribe(_Alpha, lambda _: order.append("second"))
    bus.subscribe(_Alpha, lambda _: order.append("third"))

    bus.publish(_Alpha())

    assert order == ["first", "second", "third"]


def test_handler_exception_propagates() -> None:
    bus = SynchronousEventBus()

    def boom(_: DomainEvent) -> None:
        raise RuntimeError("subscriber failure")

    bus.subscribe(_Alpha, boom)

    try:
        bus.publish(_Alpha())
    except RuntimeError as e:
        assert str(e) == "subscriber failure"
    else:  # pragma: no cover - we expect the raise above
        raise AssertionError("expected RuntimeError to propagate")


def test_event_id_and_timestamp_are_populated() -> None:
    event = _Alpha(payload="x")
    assert event.event_id
    assert event.occurred_at
    assert "T" in event.occurred_at
