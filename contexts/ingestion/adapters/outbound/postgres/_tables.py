"""SQLAlchemy Core table definitions for the ingestion schema.

Mirrors the per-tenant Alembic revision
``0005_create_sources_and_chunks``. Defined once here and imported
by the repository adapter so the ``Table`` objects are referentially
equal across reads and writes. Same Core (Table + select/insert/
update) shape S16's evaluation tables use; D34's frozen-dataclass-
plus-Core pattern keeps the domain pure and the adapter responsible
for the impedance mismatch.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


_metadata = sa.MetaData()


sources = sa.Table(
    "sources",
    _metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("tenant_id", sa.Text, nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column("file_name", sa.Text, nullable=False),
    sa.Column("file_type", sa.Text, nullable=False),
    sa.Column("file_size_bytes", sa.BigInteger, nullable=False),
    sa.Column("raw_content", sa.LargeBinary, nullable=False),
    sa.Column("state", sa.Text, nullable=False),
    sa.Column("parsing_error_text", sa.Text, nullable=True),
    sa.Column("created_by_user_id", sa.Text, nullable=False),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
    sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
)

chunks = sa.Table(
    "chunks",
    _metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("source_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("tenant_id", sa.Text, nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column("chunk_index", sa.Integer, nullable=False),
    sa.Column("content", sa.Text, nullable=False),
    sa.Column("structural_metadata", pg.JSONB, nullable=False),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
)
