"""Alembic environment for the control-plane migration track (D34).

Reads ControlPlaneSettings (D19) for connection details. Runs migrations
against the dedicated postgres-control-plane instance (D33).

Sync, not async: Alembic's async support is brittle and the migration
runner is the standard pattern for sync inside an otherwise-async stack.
The application uses asyncpg in production code (S11+); migrations
remain sync because they run on a different lifecycle (operator-driven,
not request-path).
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from vadakkan.config import ControlPlaneSettings

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False so a calling runner's loggers
    # (e.g. ops.migrate) keep their levels after fileConfig.
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def _control_plane_url() -> str:
    s = ControlPlaneSettings()
    return f"postgresql+psycopg://{s.user}:{s.password}@{s.host}:{s.port}/{s.db}"


# Target metadata is empty for the migration runner; revisions explicitly
# call `op.create_table(...)` etc. The S10 initial revision lands the
# tenant_registry table directly (no autogenerate against an ORM
# metadata, since the adapter uses SQLAlchemy Core not ORM per D34).
target_metadata = None


def run_migrations_offline() -> None:
    """Generate SQL without a live DB connection."""
    context.configure(
        url=_control_plane_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live control-plane database."""
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _control_plane_url()

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
