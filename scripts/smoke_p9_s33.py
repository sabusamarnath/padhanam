"""Live-stack smoke for P9/S33 — exercises the read surface on tenant_a.

End-to-end coverage:
- PostgresRunHistoryReader.get_run returns a RunRecord aggregate with
  chunk and entity citation tuples populated for the known S32 run.
- list_runs_with_filters with no filters returns the full tenant_a
  runs list (two rows from S31 + S32).
- list_runs_with_filters with termination_reasons=("content",)
  returns both runs (both terminated content).
- Cursor pagination at page_size=1 produces a next_cursor on the
  first call; the second call with that cursor returns the next
  page with no further cursor.

Connects directly to postgres-tenant-a inside the docker network;
mirrors the S32 smoke's connection shape. The reader's adapter
construction matches the apps/cli wiring path; no tenant registry
involvement.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from contexts.run_history.adapters.outbound.postgres.reader import (
    PostgresRunHistoryReader,
)
from contexts.run_history.application.cursor import encode
from contexts.run_history.domain.query_filters import (
    RunListCursor,
    RunListFilters,
)
from shared_kernel import TenantContext, TenantId


_TENANT_A = "00000000-0000-4000-8000-00000000a001"
_KNOWN_RUN_ID = UUID("2e86d393-96b8-4aca-a12f-ac09d7e35355")  # S32 smoke run


def _jsonable(o: Any) -> Any:
    if isinstance(o, (UUID,)):
        return str(o)
    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, Decimal):
        return str(o)
    if hasattr(o, "__dataclass_fields__"):
        return {k: _jsonable(getattr(o, k)) for k in o.__dataclass_fields__}
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    return o


def _dump(label: str, value: Any) -> None:
    print(f"\n=== {label} ===")
    print(json.dumps(_jsonable(value), indent=2, default=str))


async def main() -> None:
    url = "postgresql+asyncpg://tenant_a:tenant_a@postgres-tenant-a:5432/tenant_a"
    engine = create_async_engine(url)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async def resolver(_tid: TenantId):
        return sessionmaker

    reader = PostgresRunHistoryReader(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=TenantId(_TENANT_A),
    )
    tc = TenantContext(
        tenant_id=TenantId(_TENANT_A),
        jurisdiction="eu-west",
        cost_attribution_id=_TENANT_A,
    )

    # 1) get_run on the known S32 run.
    run = await reader.get_run(tenant_context=tc, run_id=_KNOWN_RUN_ID)
    _dump("get_run(known S32 run)", run)
    if run is not None:
        print(
            f"  chunk_citations_count={len(run.chunk_citations)} "
            f"entity_citations_count={len(run.entity_citations)}"
        )

    # 2) list_runs_with_filters — no filters.
    page_all = await reader.list_runs_with_filters(
        tenant_context=tc, filters=RunListFilters(), cursor=None
    )
    _dump(
        "list_runs_with_filters(no filters)",
        {"runs_count": len(page_all.runs), "next_cursor": page_all.next_cursor},
    )
    for r in page_all.runs:
        print(
            f"  - run_id={r.id} agent_template_id={r.agent_template_id} "
            f"termination_reason={r.termination_reason} started_at={r.started_at.isoformat()}"
        )

    # 3) list_runs_with_filters — termination_reasons=("content",).
    page_content = await reader.list_runs_with_filters(
        tenant_context=tc,
        filters=RunListFilters(termination_reasons=("content",)),
        cursor=None,
    )
    _dump(
        "list_runs_with_filters(termination_reasons=('content',))",
        {"runs_count": len(page_content.runs), "next_cursor": page_content.next_cursor},
    )

    # 4) Cursor pagination at page_size=1.
    initial_cursor = RunListCursor(
        started_at=datetime(2099, 1, 1, tzinfo=__import__("datetime", fromlist=["timezone"]).timezone.utc),
        id=UUID("ffffffff-ffff-4fff-bfff-ffffffffffff"),
        page_size=1,
    )
    # First page: use the initial-cursor trick to set page_size=1 with a
    # bound that is later than any real row (so the WHERE-clause filters
    # nothing); equivalent to "first page with page_size=1".
    page1 = await reader.list_runs_with_filters(
        tenant_context=tc, filters=RunListFilters(), cursor=initial_cursor
    )
    _dump(
        "list_runs_with_filters(page_size=1, future cursor)",
        {
            "runs_count": len(page1.runs),
            "next_cursor": page1.next_cursor,
            "next_cursor_encoded": encode(page1.next_cursor) if page1.next_cursor else None,
        },
    )
    for r in page1.runs:
        print(f"  - run_id={r.id} started_at={r.started_at.isoformat()}")

    if page1.next_cursor is not None:
        page2 = await reader.list_runs_with_filters(
            tenant_context=tc, filters=RunListFilters(), cursor=page1.next_cursor
        )
        _dump(
            "list_runs_with_filters(page2, cursor from page1)",
            {
                "runs_count": len(page2.runs),
                "next_cursor": page2.next_cursor,
            },
        )
        for r in page2.runs:
            print(f"  - run_id={r.id} started_at={r.started_at.isoformat()}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
