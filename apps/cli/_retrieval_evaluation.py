"""Retrieval evaluation CLI orchestration (S39, D109).

Five subcommands at the ``padhanam gold-set`` namespace:

- ``create``: create a gold set (aggregate root + initial draft revision).
- ``append-entry``: interactive discovery-mode append. The operator
  types a query; the CLI runs vector retrieval against the tenant's
  corpus via ``PgVectorSearch`` (per D5 / D65) and renders the top-K
  candidates as a numbered list with score + content excerpt; the
  operator types a comma-separated list of indices in ranked order
  (e.g. ``3,1,5``) and the CLI converts to chunk IDs and appends one
  entry to the current draft revision.
- ``list``: paginated list of gold sets for a tenant.
- ``get``: show aggregate plus current finalized revision plus its entries.
- ``finalize``: finalize the current draft revision (computes
  hash-chain via the platform primitive, updates current_revision_id).

Tenant context resolution uses ``build_tenant_wiring`` per the dev-
only label-or-UUID convention; production tenant resolution lands at
Phase 2 per the existing carryover at charter/deferred-decisions.md.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated, Optional
from uuid import UUID

import typer

from contexts.ingestion.adapters.outbound.embedding import LiteLLMChunkEmbedder
from contexts.ingestion.adapters.outbound.retrieval import PgVectorSearch
from contexts.retrieval_evaluation.adapters.outbound.postgres.reader import (
    PostgresGoldSetReader,
)
from contexts.retrieval_evaluation.adapters.outbound.postgres.repository import (
    PostgresGoldSetRepository,
)
from contexts.retrieval_evaluation.application import (
    EmptyDraftError,
    GoldSetNotFoundError,
    NoDraftToFinalizeError,
    append_entry_to_revision,
    create_gold_set,
    finalize_revision,
    get_gold_set,
    list_gold_sets,
)
from shared_kernel import TenantId

from apps.cli._runtime import build_tenant_wiring


retrieval_evaluation_app = typer.Typer(
    name="gold-set",
    help="Retrieval evaluation gold-set authoring (S39 / D109).",
    no_args_is_help=True,
)


def _build_repository_and_reader(
    wiring,
) -> tuple[PostgresGoldSetRepository, PostgresGoldSetReader]:
    bound_tenant_id = TenantId(str(wiring.tenant_context.tenant_id))

    async def _resolver(_tid):
        return wiring.session_factory

    repo = PostgresGoldSetRepository(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=bound_tenant_id,
    )
    reader = PostgresGoldSetReader(
        per_tenant_sessionmaker_resolver=_resolver,
        bound_tenant_id=bound_tenant_id,
    )
    return repo, reader


@retrieval_evaluation_app.command("create")
def cmd_create(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label or UUID.")
    ],
    name: Annotated[str, typer.Option("--name", help="Gold-set name.")],
    created_by: Annotated[
        str, typer.Option("--created-by", help="Author user id for the audit trail.")
    ] = "cli-operator",
) -> None:
    """Create a gold set with an initial draft revision."""
    wiring = build_tenant_wiring(tenant_id)
    repo, _ = _build_repository_and_reader(wiring)

    async def _go() -> None:
        try:
            result = await create_gold_set(
                tenant_context=wiring.tenant_context,
                name=name,
                created_by_user_id=created_by,
                repository=repo,
            )
            typer.echo(f"gold_set_id={result.gold_set.id}")
            typer.echo(f"initial_revision_id={result.initial_revision.id}")
            typer.echo("status=draft revision_number=1")
        finally:
            await wiring.engine.dispose()

    asyncio.run(_go())


@retrieval_evaluation_app.command("append-entry")
def cmd_append_entry(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label or UUID.")
    ],
    gold_set_id: Annotated[
        UUID, typer.Option("--gold-set-id", help="Target gold set.")
    ],
    query: Annotated[
        str,
        typer.Option(
            "--query",
            help="Discovery-mode query against the tenant's corpus.",
        ),
    ],
    top_k: Annotated[
        int, typer.Option("--top-k", help="Number of retrieval candidates to surface.")
    ] = 10,
    correct_indices: Annotated[
        Optional[str],
        typer.Option(
            "--correct-indices",
            help=(
                "Comma-separated 1-based indices of correct chunks in ranked "
                "order (e.g. '3,1,5'). If omitted, the CLI prompts interactively."
            ),
        ),
    ] = None,
    created_by: Annotated[
        str, typer.Option("--created-by", help="Author user id for the audit trail.")
    ] = "cli-operator",
) -> None:
    """Append one entry via discovery mode (retrieve top-K, mark correct)."""
    wiring = build_tenant_wiring(tenant_id)
    repo, reader = _build_repository_and_reader(wiring)
    embedder = LiteLLMChunkEmbedder()
    search = PgVectorSearch(
        session_factory=wiring.session_factory, embedder=embedder
    )

    async def _go() -> None:
        try:
            candidates = await search.search_vector(
                query=query, scope=wiring.tenant_context, limit=top_k
            )
            if not candidates:
                typer.echo(
                    "no retrieval candidates for the query; "
                    "no entry appended."
                )
                raise typer.Exit(code=1)

            typer.echo(f"retrieved {len(candidates)} candidates:")
            for i, c in enumerate(candidates, start=1):
                excerpt = c.content[:120].replace("\n", " ")
                typer.echo(
                    f"  [{i}] chunk_id={c.chunk_id} "
                    f"score={c.similarity_score:.3f} excerpt={excerpt!r}"
                )

            if correct_indices is None:
                indices_input = typer.prompt(
                    "correct indices (1-based, comma-separated, ranked order)"
                )
            else:
                indices_input = correct_indices

            try:
                indices = [
                    int(s.strip()) for s in indices_input.split(",") if s.strip()
                ]
            except ValueError as exc:
                raise typer.BadParameter(
                    f"could not parse indices {indices_input!r}: {exc}"
                ) from exc
            if not indices:
                raise typer.BadParameter("no correct indices provided")
            if any(i < 1 or i > len(candidates) for i in indices):
                raise typer.BadParameter(
                    f"indices out of range; valid range is 1..{len(candidates)}"
                )

            expected_chunk_ids = tuple(
                candidates[i - 1].chunk_id for i in indices
            )

            result = await append_entry_to_revision(
                tenant_context=wiring.tenant_context,
                gold_set_id=gold_set_id,
                query=query,
                expected_chunk_ids=expected_chunk_ids,
                created_by_user_id=created_by,
                reader=reader,
                repository=repo,
            )
            typer.echo(f"entry_id={result.entry.id}")
            typer.echo(f"entry_index={result.entry.entry_index}")
            typer.echo(f"revision_id={result.revision.id}")
            typer.echo(
                f"opened_new_draft={result.opened_new_draft}"
            )
        except GoldSetNotFoundError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(code=2)
        finally:
            await wiring.engine.dispose()

    asyncio.run(_go())


@retrieval_evaluation_app.command("list")
def cmd_list(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label or UUID.")
    ],
    page_size: Annotated[
        int, typer.Option("--page-size", help="Rows per page (max 50).")
    ] = 20,
    cursor: Annotated[
        Optional[str], typer.Option("--cursor", help="Opaque pagination cursor.")
    ] = None,
) -> None:
    """List gold sets for the tenant (paginated)."""
    wiring = build_tenant_wiring(tenant_id)
    _, reader = _build_repository_and_reader(wiring)

    async def _go() -> None:
        try:
            page, next_cursor = await list_gold_sets(
                tenant_context=wiring.tenant_context,
                reader=reader,
                encoded_cursor=cursor,
                page_size=page_size,
            )
            if not page.gold_sets:
                typer.echo("(no gold sets)")
                return
            for gs in page.gold_sets:
                typer.echo(
                    f"{gs.id}  name={gs.name!r}  "
                    f"created_at={gs.created_at.isoformat()}  "
                    f"current_revision_id={gs.current_revision_id or '(none)'}"
                )
            if next_cursor is not None:
                typer.echo(f"next_cursor={next_cursor}")
        finally:
            await wiring.engine.dispose()

    asyncio.run(_go())


@retrieval_evaluation_app.command("get")
def cmd_get(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label or UUID.")
    ],
    gold_set_id: Annotated[
        UUID, typer.Option("--gold-set-id", help="Gold set to read.")
    ],
) -> None:
    """Show aggregate plus current finalized revision plus its entries."""
    wiring = build_tenant_wiring(tenant_id)
    _, reader = _build_repository_and_reader(wiring)

    async def _go() -> None:
        try:
            snapshot = await get_gold_set(
                tenant_context=wiring.tenant_context,
                gold_set_id=gold_set_id,
                reader=reader,
            )
            if snapshot is None:
                typer.echo("gold set not found", err=True)
                raise typer.Exit(code=2)
            gs = snapshot.gold_set
            typer.echo(f"id={gs.id}")
            typer.echo(f"name={gs.name!r}")
            typer.echo(f"jurisdiction={gs.jurisdiction}")
            typer.echo(f"created_at={gs.created_at.isoformat()}")
            typer.echo(
                f"current_revision_id={gs.current_revision_id or '(none — no finalized revision yet)'}"
            )
            if snapshot.current_revision is not None:
                rev = snapshot.current_revision
                typer.echo(
                    f"current revision: number={rev.revision_number} "
                    f"status={rev.status.value} "
                    f"finalized_at={rev.finalized_at.isoformat() if rev.finalized_at else '(none)'}"
                )
                typer.echo(f"this_event_hash={rev.this_event_hash}")
                typer.echo(f"previous_event_hash={rev.previous_event_hash}")
                typer.echo(f"entries ({len(snapshot.entries)}):")
                for entry in snapshot.entries:
                    chunks = ", ".join(str(c) for c in entry.expected_chunk_ids)
                    typer.echo(
                        f"  [{entry.entry_index}] query={entry.query!r}\n"
                        f"      expected_chunk_ids=[{chunks}]"
                    )
        finally:
            await wiring.engine.dispose()

    asyncio.run(_go())


@retrieval_evaluation_app.command("finalize")
def cmd_finalize(
    tenant_id: Annotated[
        str, typer.Option("--tenant-id", help="Tenant short label or UUID.")
    ],
    gold_set_id: Annotated[
        UUID, typer.Option("--gold-set-id", help="Gold set whose draft to finalize.")
    ],
) -> None:
    """Finalize the current draft revision (computes hash-chain)."""
    wiring = build_tenant_wiring(tenant_id)
    repo, reader = _build_repository_and_reader(wiring)

    async def _go() -> None:
        try:
            result = await finalize_revision(
                tenant_context=wiring.tenant_context,
                gold_set_id=gold_set_id,
                reader=reader,
                repository=repo,
            )
            typer.echo(f"revision_id={result.revision.id}")
            typer.echo(f"revision_number={result.revision.revision_number}")
            typer.echo(f"status={result.revision.status.value}")
            typer.echo(f"this_event_hash={result.this_event_hash}")
            typer.echo(f"previous_event_hash={result.previous_event_hash}")
            typer.echo(
                f"finalized_at={result.revision.finalized_at.isoformat()}"
            )
        except NoDraftToFinalizeError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(code=2)
        except EmptyDraftError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(code=3)
        finally:
            await wiring.engine.dispose()

    asyncio.run(_go())


__all__ = ["retrieval_evaluation_app"]
