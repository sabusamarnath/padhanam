"""RunHistoryRepositoryPort — persistence Protocol for the run-history context (D17, D95, S31).

The producer-side port for the ``record_run`` use case. The
Postgres adapter at
``contexts/run_history/adapters/outbound/postgres/repository.py``
implements this Protocol (lands at S31 commit 4).

Tenant scoping is the caller's responsibility: the session
factory the adapter is constructed with at composition time is
already tenant-bound per D36's per-tenant migration runner and
D34's connection routing. The repository surface is intentionally
small at S31 (one method: ``persist``); the read-side query port
shaped to Phase 2 UX consumption lands as a separate port at S33
per the consumer-defined-ports precedent.

At S31 commit 3 the port is the write-only surface. Commit 4
adds the citation-row persistence shape to the same adapter when
the alembic migration lands the citation tables; commit 4's
adapter implementation continues to surface only ``persist`` at
S31 (citation rows themselves do not get written until S32 per
the p9-epic forecast).
"""

from __future__ import annotations

from typing import Protocol

from contexts.run_history.domain.run_record import RunRecord


class RunHistoryRepositoryPort(Protocol):
    """Persistence port for the run-history context (D95).

    ``persist`` writes one ``RunRecord`` into the per-tenant
    ``runs`` table. Returns ``None`` on success; raises on
    persistence failure (asyncpg IntegrityError surfaced through
    SQLAlchemy, connection errors, etc.). The caller (the
    ``record_run`` use case) lets failures propagate so the
    consumer-side ``RunHistoryWriter`` port's caller (the agent
    runtime's ``invoke_agent``) can surface failure as a
    generator-level exception per D95's write-timing reasoning.

    Tenant scoping is implicit in the bound session factory the
    adapter was constructed with. The ``RunRecord.tenant_id``
    field is the denormalised value per D22; the routing key is
    the session factory binding, not the field. The adapter
    verifies the field matches the bound tenant as defence-in-
    depth (D32).
    """

    async def persist(self, record: RunRecord) -> None: ...
