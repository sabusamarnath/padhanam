"""Connection value object — the domain's opaque handle to a provider connection (D148).

The domain holds the Nango connection id as an opaque *reference*
(``provider_connection_ref``) rather than depending on Nango's
identifiers directly. The domain never imports Nango code or interprets
these handles; it only carries them so the calendar port can present
them to the adapter. A vendor swap re-points the reference (and the
``provider_config_key``) rather than touching domain code — the
replaceability claim D148 makes honest: the OAuth client, token store,
and encryption key are ours (self-hosted Nango), so a swap is a bounded
adapter rewrite plus a token-migration script, not user re-auth.

Frozen dataclass per D16 — the domain is framework-free.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Connection:
    """A tenant's connection to an external calendar provider.

    - ``provider``: the domain-meaningful provider family (e.g.
      ``"google_calendar"``). Domain code may branch on this; it is not
      a vendor identifier.
    - ``provider_config_key``: the integration key the tool service
      (Nango) uses to select OAuth configuration (the verified
      ``"google-calendar"``). Opaque to the domain.
    - ``provider_connection_ref``: the opaque connection id the tool
      service issued (the verified ``d46195b2-...``). Opaque to the
      domain.
    """

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
            raise ValueError(
                "Connection.provider_config_key must be non-empty"
            )
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
