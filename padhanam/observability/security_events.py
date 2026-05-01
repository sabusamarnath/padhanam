"""Security event logging interface (D26).

Security events log separately from application logs. Local backend writes
JSON-per-line to a path from ObservabilitySettings. Production backend ships
to a SIEM, vendor deferred until production deployment context exists.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from padhanam.config import ObservabilitySettings
from shared_kernel import TenantId


class SecurityEventCategory(StrEnum):
    AUTH_FAILURE = "auth_failure"
    AUTHZ_DENIAL = "authz_denial"
    CONFIG_CHANGE = "config_change"
    TENANT_SCOPE_VIOLATION = "tenant_scope_violation"
    PRIVILEGED_ACTION = "privileged_action"


@dataclass(frozen=True)
class SecurityEvent:
    category: SecurityEventCategory
    principal_ref: str | None
    tenant_id: TenantId | None
    action: str
    resource_ref: str | None
    outcome: str
    metadata: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_json(self) -> str:
        payload = {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "category": self.category.value,
            "principal_ref": self.principal_ref,
            "tenant_id": self.tenant_id,
            "action": self.action,
            "resource_ref": self.resource_ref,
            "outcome": self.outcome,
            "metadata": self.metadata,
        }
        return json.dumps(payload, sort_keys=True)


class SecurityEventLogger(Protocol):
    def emit(self, event: SecurityEvent) -> None: ...


@dataclass
class _FileSecurityEventLogger:
    path: Path

    def emit(self, event: SecurityEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(event.to_json())
            fh.write("\n")


def file_security_event_logger(
    path: Path | None = None,
) -> SecurityEventLogger:
    """Construct the local file backend.

    Path defaults to ObservabilitySettings.security_log_path. Production
    composition wires a SIEM-shipping logger here instead.
    """
    if path is None:
        path = ObservabilitySettings().security_log_path
    return _FileSecurityEventLogger(path=path)
