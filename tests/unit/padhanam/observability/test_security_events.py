from __future__ import annotations

import json
from pathlib import Path

import pytest

from padhanam.observability import (
    SecurityEvent,
    SecurityEventCategory,
    file_security_event_logger,
)
from shared_kernel import TenantId


def test_emit_round_trip(tmp_path: Path) -> None:
    log_path = tmp_path / "security.jsonl"
    logger = file_security_event_logger(log_path)
    event = SecurityEvent(
        category=SecurityEventCategory.AUTH_FAILURE,
        principal_ref="dev-token...",
        tenant_id=TenantId("tenant-a"),
        action="login",
        resource_ref="auth/session",
        outcome="denied",
        metadata={"reason": "invalid_signature"},
    )
    logger.emit(event)

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["category"] == "auth_failure"
    assert parsed["tenant_id"] == "tenant-a"
    assert parsed["metadata"]["reason"] == "invalid_signature"
    assert "event_id" in parsed
    assert "timestamp" in parsed


def test_emit_appends_multiple_events(tmp_path: Path) -> None:
    log_path = tmp_path / "security.jsonl"
    logger = file_security_event_logger(log_path)
    for i in range(3):
        logger.emit(
            SecurityEvent(
                category=SecurityEventCategory.AUTHZ_DENIAL,
                principal_ref=f"p{i}",
                tenant_id=TenantId("tenant-a"),
                action="audit.read",
                resource_ref=f"event/{i}",
                outcome="deny",
            )
        )
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3


def test_emit_creates_parent_directory(tmp_path: Path) -> None:
    log_path = tmp_path / "nested" / "subdir" / "security.jsonl"
    logger = file_security_event_logger(log_path)
    logger.emit(
        SecurityEvent(
            category=SecurityEventCategory.CONFIG_CHANGE,
            principal_ref="system",
            tenant_id=None,
            action="settings.update",
            resource_ref="padhanam.observability",
            outcome="success",
        )
    )
    assert log_path.exists()


def test_categories_cover_charter_set() -> None:
    expected = {
        "auth_failure",
        "authz_denial",
        "config_change",
        "tenant_scope_violation",
        "privileged_action",
    }
    assert {c.value for c in SecurityEventCategory} == expected
