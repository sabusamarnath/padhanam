"""SQLAlchemy session factory adapter for per-tenant routing (D36).

Encapsulates the SQLAlchemy import surface for the connection-
resolution layer. The adapter takes a transient ``TenantConnectionConfig``
(plaintext, function-local) and returns the matching ``AsyncEngine`` +
``async_sessionmaker`` pair. The plaintext does not persist on the
adapter — neither argument nor result keeps a reference. The AST
enforcement test in ``tests/_enforcement/test_no_plaintext_in_state.py``
walks this module and fails on any class attribute typed as
``TenantConnectionConfig``.

Pool sizing is conservative for dev: ``pool_size=2, max_overflow=3``
keeps total connections per tenant at ≤5 in steady state. Two test-set
tenants × five connections = ten peak in dev, well within the Postgres
defaults. Production sizing is a config swap.

``pool_pre_ping=True`` handles stale connections cleanly when a
Postgres instance restarts under ``make down``/``make up`` cycles —
SQLAlchemy issues a lightweight ping before each checkout and
re-establishes the connection if the ping fails. This is the right
SQLAlchemy 2.0 idiom for the per-tenant cache, where engines may
outlive a stack restart.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from contexts.tenancy.domain.tenant_connection_config import TenantConnectionConfig


def _async_url(plaintext: TenantConnectionConfig) -> str:
    return (
        f"postgresql+asyncpg://{plaintext.username}:{plaintext.password}"
        f"@{plaintext.host}:{plaintext.port}/{plaintext.database}"
    )


class SqlAlchemyTenantSessionFactory:
    """Constructs (engine, sessionmaker) pairs from plaintext credentials.

    The adapter holds no instance state related to plaintext: it is a
    pure function wrapped in a class so the routing layer's tests can
    replace it with a fake.
    """

    def create_engine_and_sessionmaker(
        self, plaintext: TenantConnectionConfig
    ) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
        engine = create_async_engine(
            _async_url(plaintext),
            pool_size=2,
            max_overflow=3,
            pool_pre_ping=True,
        )
        sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        return engine, sessionmaker
