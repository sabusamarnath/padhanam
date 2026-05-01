"""create tenant_registry

Revision ID: 0001_create_tenant_registry
Revises:
Create Date: 2026-04-30

The tenant registry is the source of truth for tenant identity,
jurisdiction, status, and the encrypted form of per-tenant database
credentials (D1, D12, D13, D21, D32, D33).

Schema notes:
- tenant_id is a UUID primary key. The domain TenantId validates
  UUID-shape; this column enforces it at the storage layer too.
- jurisdiction is plain text in P3; the architectural commitment under
  D12 is that the column exists and is queryable, not that it is yet a
  closed enum.
- status is constrained to the TenantStatus values via a CHECK; using
  text plus CHECK rather than a Postgres enum keeps Alembic migrations
  simple and avoids the enum-rename pain point.
- The credential columns (wrapped_dek, dek_wrap_nonce, ciphertext,
  nonce, key_version, aad) hold the wire-format output of
  padhanam/security/crypto.py (D21) plus the AAD bytes that bind the
  ciphertext to the tenant_id and purpose. No plaintext column exists;
  the registry adapter encrypts before insert and never decrypts on
  read (decryption flows through reveal_connection_config in the
  application layer, S11).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision: str = "0001_create_tenant_registry"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_STATUS_VALUES = ("active", "suspended", "deprovisioned")


def upgrade() -> None:
    op.create_table(
        "tenant_registry",
        sa.Column("tenant_id", pg.UUID(as_uuid=False), primary_key=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("wrapped_dek", sa.LargeBinary(), nullable=False),
        sa.Column("dek_wrap_nonce", sa.LargeBinary(), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("aad", sa.LargeBinary(), nullable=False),
        sa.CheckConstraint(
            "status IN ("
            + ", ".join(f"'{v}'" for v in _STATUS_VALUES)
            + ")",
            name="tenant_registry_status_check",
        ),
    )
    op.create_index(
        "ix_tenant_registry_jurisdiction",
        "tenant_registry",
        ["jurisdiction"],
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_registry_jurisdiction", table_name="tenant_registry")
    op.drop_table("tenant_registry")
