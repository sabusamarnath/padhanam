"""Connection — the email tenant's Nango connection identity (D151).

Mirrors the calendar Connection (D148): identity only — the opaque Nango
connection id (`provider_connection_ref`) plus provider and
provider_config_key. The domain never imports Nango identifiers directly;
a vendor swap re-points the reference rather than touching domain code.
Email keeps its own Connection (not calendar's) per bounded-context
independence (D16/D17/D28). Framework-free per D16.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Connection:
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
        if not self.provider_connection_ref or not self.provider_connection_ref.strip():
            raise ValueError("Connection.provider_connection_ref must be non-empty")
