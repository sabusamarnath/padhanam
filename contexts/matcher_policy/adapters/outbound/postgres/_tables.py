"""SQLAlchemy Core table for the matcher_policy per-tenant table (D186/S91b).

One row per tenant — the active matcher policy. ``tenant_id`` is the primary key
(a tenant has exactly one policy; apply upserts it). **No content** — a boolean
flag and a timestamp only. Migration:
``alembic/tenant/versions/2026_06_12_0035_matcher_policies``.

Shared between the repository (writer) and reader adapters. SQLAlchemy 2.0 Core —
no ORM, per the ``matcher_evaluation`` / ``retrieval_evaluation`` precedent.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

metadata = sa.MetaData()


matcher_policies = sa.Table(
    "matcher_policies",
    metadata,
    sa.Column("tenant_id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column(
        "suppress_single_signal",
        sa.Boolean,
        nullable=False,
        server_default=sa.text("false"),
    ),
    sa.Column(
        "updated_at",
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
)


__all__ = ["matcher_policies", "metadata"]
