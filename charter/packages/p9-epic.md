# P9 Epic — Run history (backend-only)

## Goal

P9 ships the run-history backend substrate that closes Phase 1's substrate-completeness story per D92 and that Phase 2 UX consumes directly per D93. At P9 close, every agent invocation through the P8 streaming runtime persists a structured run record and citation surface on the tenant's data plane, the audit chain from S29b links cleanly to the run record via shared hashes, the citation surface preserves what the agent saw at run time even if underlying sources later change, and Phase 2 UX can consume a consumer-defined query port that renders runs, lists runs with filters, and surfaces citations without back-joining to the trace store or Neo4j.

## Scope at P9 close

A new `contexts/run_history/` bounded context owns the run-history surface. The substrate is three per-tenant Postgres tables per D94: `runs` (the structured run record), `run_chunk_citations` (run-to-chunk linkage via real foreign key plus rendering-grade snapshot columns), `run_entity_citations` (run-to-Neo4j-entity linkage via composite key plus rendering-grade snapshot columns). All three tables sit on the tenant's data plane per D32.

The write path triggers at invocation completion in `contexts/agent/`. The executor derives the run record plus citation rows from the in-flight event stream from S29b and writes them in a single transaction. The cross-context call from agent to run-history follows the consumer-port-plus-wiring-adapter pattern reinforced across S26a through S29b.

The read-side surface is one consumer-defined query port shaped to Phase 2 UX consumption: get_run, list_runs_with_filters, get_citations_for_run. The Postgres adapter implements it against the new tables. P11's aggregation-shaped read port is explicitly out of scope at P9 and lands at P11 framing per the consumer-defined-ports precedent.

The HTTP API for ingestion management absorbed from the P6 deferred carryover lands inside P9. The API surface exposes existing ingestion use cases at `contexts/ingestion/application/` over FastAPI routes following the principal-derived tenant context convention from S29b's agent SSE endpoint.

Tenant-isolation contract tests extend the existing `tests/contract/tenant_isolation/` harness per D24 to cover the new per-tenant tables. Cross-tenant read and write access through the query port and the write path must fail.

The trace store (Langfuse via OTel) stays as operational observability per D27. The run record's `trace_id` column is the join key for ops deep-dives; product surfaces do not query the trace store directly.

## Sessions forecast

Four sessions most likely, possibly five. P9 inherits substantial substrate from P8 (the eleven-event vocabulary, the streaming runtime, the audit chain, the nested OTel span hierarchy) and adds storage and query surface rather than new architectural primitives. Session boundaries settle session-by-session per the established discipline. Indicative shape:

- **S31:** `contexts/run_history/` bounded context opens with the hexagonal-layer convention plus import-linter coverage. Alembic revision `0011_create_run_history` lands the three per-tenant tables per D95 (15-column `runs` with `audit_end_hash` nullable under `termination_reason='failed'` for the 1-hash `InvocationFailed` case from the executor, 8-column `run_chunk_citations` with ON DELETE SET NULL on `chunk_id`, 8-column `run_entity_citations` with `(entity_tenant_id, entity_name, entity_type)` composite join key back to Neo4j). The `RunHistoryWriter` consumer port at the agent context, the `record_run` use case at the run-history context, and the `PostgresRunHistoryAdapter` complete the producer side. `invoke_agent` extends to accumulate run-record-shaped state from the event stream and write the runs row after the terminal event yields per D95's write-timing commitment (shape B); `InvocationFailed` events with empty `partial_audit_chain_state` skip the writer call per the projection-over-recorded-activity framing. Citation tables exist but no citation rows get written at S31; citation population and the single-transaction completion seam land at S32. Tenant-isolation contract harness extends per D24 with five cross-tenant red-team scenarios for the new tables. Live-stack smoke verifies one runs row written through the SSE endpoint against `tenant_a`.
- **S32:** Citation surface lands end-to-end from retrieval through to per-tenant Postgres rows. `ChunkCitationCandidate` and `EntityCitationCandidate` value objects at `contexts/agent/domain/citation_candidates.py` carry chunk identity, content snapshot, structured source-level attribution snapshot, and the Neo4j composite key with `source_chunk_ids` provenance per D96. `ToolCallCompleted` extends with `citation_candidates: tuple[CitationCandidate, ...] = ()`. The retrieval adapter at `apps/cli/_cross_context.py` translates ingestion `ChunkResult` and `EntityResult` to agent-context candidates; the `AgentRetrievalClient` port grows a `RetrievalResult` envelope carrying both chunks and citation candidates. The accumulator at `invoke_agent` deduplicates within the run by `(chunk_id, run_id)` and `(entity_tenant_id, entity_name, entity_type, run_id)` first-seen-wins and passes citation lists to `writer.record_run`. Schema revision `0012_revise_citation_snapshots` drops `source_citation text` for `source_snapshot jsonb` and drops `entity_display_label text` for `source_chunk_ids text[]`. The `PostgresRunHistoryAdapter` writes all three tables within `async with session.begin()`; partial failure rolls all three back. Tenant-isolation contract harness extends for citation rows. Live-stack smoke verifies one runs row plus at least one citation row on `tenant_a` with `source_snapshot` populated.
- **S33** lands the UX-shaped query port and the Postgres adapter implementing it. `RunHistoryReader` port at `contexts/run_history/ports/reader.py` with two methods: `get_run` returning `RunRecord | None` as the aggregate (run + chunk citations + entity citations attached) per D97's RunRecord-as-aggregate shape; `list_runs_with_filters` returning `RunListPage` (runs + next cursor) under cursor pagination on `(started_at, id)` with sort fixed at `started_at DESC, id DESC`. Four-filter vocabulary via `RunListFilters`: `agent_template_ids`, `agent_template_versions`, `started_at_range`, `termination_reasons`. Domain types pass straight through per the storage-versus-render discipline; the consumer projects render shape. `PostgresRunHistoryReader` adapter at `contexts/run_history/adapters/outbound/postgres/reader.py` implements the port against the per-tenant Postgres tables; bound-tenant-id defence-in-depth at both read methods. Reader wired at `apps/cli/_cross_context.py` (`RunHistoryReaderAdapter`) and `apps/api/_agent_runtime_wiring.py` (`build_run_history_reader` factory) symmetrically with the writer. Tenant-isolation contract harness extends to 16 scenarios. Live-stack smoke exercises `get_run` and `list_runs_with_filters` including pagination. D97 lands at S33 commit 1.
- **S34** lands the HTTP API for ingestion management. Could fold into S33 if light enough.
- **S35** if needed lands P9 close with an end-to-end demonstration exercising the full path: agent invocation through streaming runtime, run completion writes record and citations, query port retrieves the rendered surface.

## D-entries forecast

Two to four D-entries beyond D94, depending on what implementation surfaces. Forecast at framing:

- Concrete schema (column lists, indexes, constraints, foreign-key deletion behaviors) for the three per-tenant tables. The schema-discipline norm puts this at the implementing session.
- The UX-shaped query port surface (method signatures, DTO shapes, filtering vocabulary). Consumer-defined per D5; specifics settle at S33.
- HTTP API endpoint shape for ingestion management at S34 (or wherever the carryover lands). Endpoint shape was deferred at D60's framing for the implementing session.
- Possibly: any architectural commitment that surfaces at build per the framing-prompt-as-recommendation pattern.

## Out of scope

- **P11's aggregation-shaped read port.** Lands at P11 framing per the consumer-defined-ports precedent. P11 reads the same per-tenant tables through its own adapter.
- **Replay UI.** Deferred to Phase 2 per D92.
- **Eager projection of run records into Neo4j.** Phase 2 forward-affordance per D94 alternative (h); activates if Phase 2 UX surfaces a real traversal query requirement.
- **HTTP API for evaluation management.** Lands at P10 or P11 per the existing carryover.
- **Browser-based authentication, frontend stack decision.** Phase 1 close substrate-completion territory.

## Open questions surfaced at framing

- Concrete column lists across the three tables. Framing settles the shape; implementation settles the schema per the project's discipline.
- Snapshot field choices on each citation table (chunk excerpt verbatim versus summary; whether `run_entity_citations` snapshots the entity's `source_chunk_ids` array as well as the display label). Settle at S32.
- HTTP API endpoint shape for ingestion management. Settle at the session that lands the carryover.
- Query port filtering vocabulary (which run fields are filterable, which sort orders, which pagination shape). Settle at S33 with Phase 2 UX needs as the consumer reference.
