"""Port-surface tests for AuditEventReader (D102, S36).

These do not exercise an adapter implementation. They test the
Protocol's structural shape (the three method signatures resolve)
and the AuditQueryRoutingError exception class. Adapter behaviour
tests live at tests/unit/contexts/audit/test_postgres_reader.py.
"""

from __future__ import annotations

import inspect
from typing import get_type_hints

from contexts.audit.ports.reader import (
    AuditEventReader,
    AuditQueryRoutingError,
)


def test_auditeventreader_is_protocol() -> None:
    # Protocol attribute set by typing.Protocol decorator.
    assert getattr(AuditEventReader, "_is_protocol", False) is True


def test_three_methods_present() -> None:
    for method_name in (
        "get_audit_event",
        "list_audit_events_with_filters",
        "verify_chain_segment",
    ):
        assert hasattr(AuditEventReader, method_name), method_name
        method = getattr(AuditEventReader, method_name)
        assert inspect.iscoroutinefunction(method), method_name


def test_get_audit_event_signature_keyword_only_after_self() -> None:
    sig = inspect.signature(AuditEventReader.get_audit_event)
    params = [p for p in sig.parameters.values() if p.name != "self"]
    for p in params:
        assert p.kind == inspect.Parameter.KEYWORD_ONLY, p.name
    names = [p.name for p in params]
    assert names == ["destination", "event_id", "tenant_context"]


def test_list_signature_keyword_only_after_self() -> None:
    sig = inspect.signature(AuditEventReader.list_audit_events_with_filters)
    params = [p for p in sig.parameters.values() if p.name != "self"]
    for p in params:
        assert p.kind == inspect.Parameter.KEYWORD_ONLY, p.name
    names = [p.name for p in params]
    assert names == [
        "destination",
        "filters",
        "cursor",
        "page_size",
        "tenant_context",
    ]


def test_verify_chain_segment_signature() -> None:
    sig = inspect.signature(AuditEventReader.verify_chain_segment)
    params = [p for p in sig.parameters.values() if p.name != "self"]
    for p in params:
        assert p.kind == inspect.Parameter.KEYWORD_ONLY, p.name
    names = [p.name for p in params]
    assert names == ["destination", "events"]


def test_routing_error_subclass_of_exception() -> None:
    assert issubclass(AuditQueryRoutingError, Exception)
    err = AuditQueryRoutingError("per_tenant destination requires tenant_context")
    assert "per_tenant" in str(err)
