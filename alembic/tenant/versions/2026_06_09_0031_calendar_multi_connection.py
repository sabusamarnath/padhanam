"""calendar multi-connection: connection-scoped meetings (D176)

Revision ID: 0031_calendar_multi_connection
Revises: 0030_tasks_substrate
Create Date: 2026-06-09

Resolves D159's second-calendar threshold so a second calendar account can
coexist per tenant without aging out or colliding with the first (D176).

Three coupled schema changes on the per-tenant calendar tables:

  1. ``meetings.calendar_id`` (Text, NOT NULL) — the connection-scoped calendar
     identity. Backfilled by constant-fill: every existing meeting takes its
     tenant's calendar connection id (a correlated subquery; pre-migration the
     old ``connections`` unique guaranteed exactly one google_calendar
     connection per tenant, so the fill is 1:1 and deterministic). No re-pull.
     Step 0 confirmed 0 orphan meetings (every meeting maps to a connection)
     across all tenant DBs, so NOT NULL is safe.

  2. ``meetings`` identity key extends from (tenant_id, google_event_id) to
     (tenant_id, calendar_id, google_event_id). A meeting both accounts are
     invited to shares one Google event id across calendars, so without
     calendar_id in the key a second account's pull would overwrite the first.

  3. ``connections`` unique relaxes from (tenant_id, provider,
     provider_config_key) to add provider_connection_ref, so a second calendar
     *account* (a distinct Nango connection ref) inserts a new row while
     re-connecting the same account upserts.

Per-tenant only per D32. Mirrors ``contexts/calendar/adapters/outbound/postgres/
_tables.py``, which must stay in lockstep.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0031_calendar_multi_connection"
down_revision: Union[str, None] = "0030_tasks_substrate"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add the column nullable for the backfill.
    op.add_column(
        "meetings",
        sa.Column("calendar_id", sa.Text, nullable=True),
    )
    # 2. Constant-fill backfill: each meeting takes its tenant's calendar
    #    connection id. Correlated subquery; one google_calendar connection per
    #    tenant pre-migration, so 1:1. No re-pull.
    op.execute(
        """
        UPDATE meetings AS m
        SET calendar_id = (
            SELECT c.id
            FROM connections AS c
            WHERE c.tenant_id = m.tenant_id
              AND c.provider = 'google_calendar'
            ORDER BY c.created_at
            LIMIT 1
        )
        WHERE m.calendar_id IS NULL
        """
    )
    # 3. Enforce NOT NULL (0 orphan meetings confirmed at Step 0).
    op.alter_column("meetings", "calendar_id", nullable=False)
    # 4. Swap the meetings identity key to include calendar_id.
    op.drop_constraint(
        "ux_meetings_tenant_event", "meetings", type_="unique"
    )
    op.create_unique_constraint(
        "ux_meetings_tenant_calendar_event",
        "meetings",
        ["tenant_id", "calendar_id", "google_event_id"],
    )
    # 5. Relax the connection unique to permit a second calendar account.
    op.drop_constraint(
        "ux_connections_tenant_provider_config", "connections", type_="unique"
    )
    op.create_unique_constraint(
        "ux_connections_tenant_provider_config_ref",
        "connections",
        ["tenant_id", "provider", "provider_config_key", "provider_connection_ref"],
    )


def downgrade() -> None:
    # Reverse order. Downgrade fails by design if a tenant has grown a second
    # calendar account or a cross-account event-id collision (the very states
    # this migration exists to support) — that is the honest behaviour.
    op.drop_constraint(
        "ux_connections_tenant_provider_config_ref",
        "connections",
        type_="unique",
    )
    op.create_unique_constraint(
        "ux_connections_tenant_provider_config",
        "connections",
        ["tenant_id", "provider", "provider_config_key"],
    )
    op.drop_constraint(
        "ux_meetings_tenant_calendar_event", "meetings", type_="unique"
    )
    op.create_unique_constraint(
        "ux_meetings_tenant_event",
        "meetings",
        ["tenant_id", "google_event_id"],
    )
    op.drop_column("meetings", "calendar_id")
