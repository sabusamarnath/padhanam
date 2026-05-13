"""Live-stack smoke for P9/S32 — exercises the citation-write path on tenant_a.

Writes a synthetic AgentRunRecord with two ChunkCitationCandidate
and one EntityCitationCandidate via the RunHistoryWriterAdapter
(the same wiring adapter the SSE runtime uses) so the test
exercises the full single-transaction multi-table write per D96
plus the source_snapshot JSONB population path.

End-to-end coverage:
- Migration 0012 already applied to tenant_a (verified at session-open).
- RunHistoryWriterAdapter translates agent-context AgentRunRecord
  into run-history-context RunRecord with mirrored citation records.
- PostgresRunHistoryAdapter.persist opens `async with session.begin()`
  and writes runs + run_chunk_citations + run_entity_citations
  atomically.
- The source_snapshot JSONB column on run_chunk_citations is
  populated with the Phase 1 key set (file_name, file_type).
- The source_chunk_ids text[] column on run_entity_citations is
  populated with the entity's provenance trail.

Variant from brief commit 10: this smoke is a direct adapter-path
exercise rather than an SSE-driven end-to-end agent invocation
because the tenant registry got wiped between S31 close and S32
session-open (the S30b-identified fixture-leak class). The structural
acceptance criterion (one runs row + at least one citation row on
tenant_a with source_snapshot populated) lands identically.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from contexts.agent.application.ports import AgentRunRecord
from contexts.agent.domain.citation_candidates import (
    ChunkCitationCandidate,
    EntityCitationCandidate,
)
from apps.cli._cross_context import RunHistoryWriterAdapter
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventLogger,
)


class _StdoutSecurityEventLogger:
    def emit(self, event: SecurityEvent) -> None:
        print(f"security_event: {event.category} action={event.action} outcome={event.outcome}")
from padhanam.security import OPERATOR_ROLE, Principal
from shared_kernel import TenantContext, TenantId


async def main() -> None:
    tenant_id = "00000000-0000-4000-8000-00000000a001"
    jurisdiction = "eu-west"
    url = "postgresql+asyncpg://tenant_a:tenant_a@postgres-tenant-a:5432/tenant_a"
    engine = create_async_engine(url)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def session_factory_for_tenant(ctx: TenantContext):
        return sessionmaker

    sec_log: SecurityEventLogger = _StdoutSecurityEventLogger()
    writer = RunHistoryWriterAdapter(
        session_factory_for_tenant=session_factory_for_tenant,
        security_events=sec_log,
    )

    invocation_id = uuid4()
    started_at = datetime(2026, 5, 13, 23, 0, 0, tzinfo=timezone.utc)
    completed_at = datetime(2026, 5, 13, 23, 0, 30, tzinfo=timezone.utc)
    # Real chunk_ids from tenant_a's chunks table so the FK constraint
    # on run_chunk_citations.chunk_id resolves; the source-level fields
    # match what the JOIN at retrieval time would produce.
    chunk_a = ChunkCitationCandidate(
        chunk_id=UUID("eda98773-76a8-41c1-9a58-d69696def123"),
        source_id=UUID("36a507ca-af09-4d94-86d0-4a41084a9cab"),
        chunk_index=0,
        content_snapshot="Customer interviews surface jobs-to-be-done patterns.",
        source_snapshot={
            "file_name": "03_customer_interviews.md",
            "file_type": "markdown",
        },
        tenant_id=tenant_id,
        jurisdiction=jurisdiction,
    )
    chunk_b = ChunkCitationCandidate(
        chunk_id=UUID("c8c6d59f-5e10-4ea9-b788-f7ddddedc3d4"),
        source_id=UUID("36a507ca-af09-4d94-86d0-4a41084a9cab"),
        chunk_index=1,
        content_snapshot="Methodologies compose roles; agents adopt methodologies.",
        source_snapshot={
            "file_name": "03_customer_interviews.md",
            "file_type": "markdown",
        },
        tenant_id=tenant_id,
        jurisdiction=jurisdiction,
    )
    entity = EntityCitationCandidate(
        entity_tenant_id=tenant_id,
        entity_name="Lean Value Tree",
        entity_type="Framework",
        source_chunk_ids=(chunk_a.chunk_id, chunk_b.chunk_id),
        tenant_id=tenant_id,
        jurisdiction=jurisdiction,
    )

    record = AgentRunRecord(
        id=invocation_id,
        tenant_id=tenant_id,
        jurisdiction=jurisdiction,
        agent_template_id=uuid4(),
        agent_template_version=1,
        input_message="What is LVT?",
        output_content="LVT is a Lean Value Tree, a methodology used by senior product leaders.",
        started_at=started_at,
        completed_at=completed_at,
        termination_reason="content",
        iteration_count=2,
        total_cost_usd=Decimal("0.00123"),
        trace_id=None,
        audit_start_hash="a" * 64,
        audit_end_hash="b" * 64,
        created_at=completed_at,
        chunk_citations=(chunk_a, chunk_b),
        entity_citations=(entity,),
    )

    principal = Principal(
        subject="cli-operator",
        tenant_id=TenantId("operator"),
        roles=frozenset({OPERATOR_ROLE}),
        credential_ref="dev-token-op",
    )

    print(f"invocation_id={invocation_id}")
    await writer.record_run(record, principal=principal)
    print("record_run succeeded")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
