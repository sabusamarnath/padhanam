"""Alembic environment for the per-tenant migration track (D36).

Reads the SQLAlchemy URL from the config's main options. The migration
runner at `ops/migrate.py` injects per-tenant URLs at runtime via
`cfg.set_main_option("sqlalchemy.url", url)` before invoking
`command.upgrade(cfg, "head")` once per registered tenant. Per-tenant
URLs are resolved by the routing layer (`reveal_connection_config` as
operator-context system actor) and passed through the runner; this
env.py never reads tenant credentials directly.

Sync, not async, mirroring the control-plane track. Migrations run on
a different lifecycle from request paths and the synchronous Alembic
shape is the standard pattern.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False so the runner's "ops.migrate"
    # logger keeps its INFO level after Alembic runs fileConfig per
    # tenant; otherwise per-tenant progress messages are silenced.
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def _runtime_url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError(
            "per-tenant Alembic env requires sqlalchemy.url to be set "
            "by the runner via cfg.set_main_option(...)"
        )
    return url


target_metadata = None


def run_migrations_offline() -> None:
    """Generate SQL without a live DB connection."""
    context.configure(
        url=_runtime_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live per-tenant database."""
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _runtime_url()

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
