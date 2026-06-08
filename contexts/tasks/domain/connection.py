"""Connection value object — the tasks context's opaque provider handle (D167).

Mirrors the calendar (D148) and email (D151) Connection: the domain holds the
Nango connection id as an opaque reference (``provider_connection_ref``) plus
the integration key (``provider_config_key``) and a domain-meaningful provider
family (``provider``, e.g. ``"google_tasks"``). The domain never imports Nango
code; it carries these so the tasks port can present them to the adapter. A
vendor swap re-points the references, not domain code.

Frozen dataclass per D16 — the domain is framework-free.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Connection:
    """A tenant's connection to an external task provider (D167)."""

    id: UUID
    tenant_id: UUID
    jurisdiction: str
    provider: str
    provider_config_key: str
    provider_connection_ref: str
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.jurisdiction or not self.jurisdiction.strip():
            raise ValueError("Connection.jurisdiction must be non-empty")
        if not self.provider or not self.provider.strip():
            raise ValueError("Connection.provider must be non-empty")
        if not self.provider_config_key or not self.provider_config_key.strip():
            raise ValueError("Connection.provider_config_key must be non-empty")
        if (
            not self.provider_connection_ref
            or not self.provider_connection_ref.strip()
        ):
            raise ValueError(
                "Connection.provider_connection_ref must be non-empty "
                "(the opaque provider connection reference)"
            )
        if self.updated_at < self.created_at:
            raise ValueError("Connection.updated_at must be >= created_at")
