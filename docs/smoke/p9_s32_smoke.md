# P9 S32 — Live-stack smoke (2026-05-13)

End-to-end exercise of the citation-write path through
`RunHistoryWriterAdapter` against `tenant_a` per D96's
single-transaction multi-table write commitment. Image
`padhanam-api:dev@sha256:9d1aca6f6464469a716a690c7f991581df23b1ba4589cf006cc4b502722ab99b`
carries S32's full commit set (alembic 0012_revise_citation_snapshots,
ChunkCitationCandidate / EntityCitationCandidate, ToolCallCompleted
citation_candidates extension, AgentRetrievalClientAdapter
RetrievalResult envelope, invoke_agent accumulator + within-run
deduplication, RunRecord + PostgresRunHistoryAdapter single-
transaction three-table write).

## Smoke shape — direct-adapter exercise via synthetic candidates

The smoke writes one runs row plus two chunk citations plus one
entity citation against `tenant_a` via the
`RunHistoryWriterAdapter` (the same wiring adapter the SSE runtime
uses at `apps/cli/_cross_context.py`). Synthetic
`ChunkCitationCandidate` and `EntityCitationCandidate` values
reference real chunk_ids from `tenant_a`'s `chunks` table so the
FK constraint on `run_chunk_citations.chunk_id` resolves cleanly;
the synthetic candidates exercise the full write-path code (DTO →
domain record translation in the wiring adapter, the
`record_run` use case, the adapter's tenant-id defence-in-depth
checks, the `async with session.begin()` block, and the JSONB +
text[] column writes).

Variant from the brief's commit 10: the smoke does not invoke the
agent against the live SSE endpoint with a retrieval-triggering
prompt. The substitution is operationally driven: the tenant
registry got wiped between S31 close and S32 session-open
(verified at session-open by querying the empty `tenant_registry`
table on the control plane; the same `_truncate_methodology_and_role`
fixture-leak class S30b identified, now generalized to the tenant
registry's case). The `make migrate` registry-driven flow returns
"0 tenant(s) to migrate" so the SSE invocation path is non-
operational without registry recovery — out of scope for this
session's structural smoke. The direct-adapter path lands the
same acceptance criterion (one runs row + at least one citation
row on tenant_a with source_snapshot populated) by exercising the
exact production code path the SSE invocation would have taken,
minus the LLM round-trip and the agent runtime's event stream
(both of which are verified by the executor and use-case unit tests
at commits 5 and 6).

## Smoke invocation

```
docker cp scripts/smoke_p9_s32.py padhanam-padhanam-api-1:/app/scripts_smoke_p9_s32.py
docker compose exec -T padhanam-api python /app/scripts_smoke_p9_s32.py
```

Smoke output:

```
invocation_id=2e86d393-96b8-4aca-a12f-ac09d7e35355
record_run succeeded
```

## SQL verification on tenant_a

`runs` row:

```
SELECT id, termination_reason, audit_start_hash, audit_end_hash FROM runs WHERE id = '2e86d393-96b8-4aca-a12f-ac09d7e35355';
                  id                  | termination_reason |                         audit_start_hash                         |                          audit_end_hash
--------------------------------------+--------------------+------------------------------------------------------------------+------------------------------------------------------------------
 2e86d393-96b8-4aca-a12f-ac09d7e35355 | content            | aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa | bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
(1 row)
```

`run_chunk_citations` rows:

```
SELECT chunk_id, chunk_excerpt, source_snapshot FROM run_chunk_citations WHERE run_id = '2e86d393-96b8-4aca-a12f-ac09d7e35355';
               chunk_id               |                      chunk_excerpt                       |                           source_snapshot
--------------------------------------+----------------------------------------------------------+---------------------------------------------------------------------
 eda98773-76a8-41c1-9a58-d69696def123 | Customer interviews surface jobs-to-be-done patterns.    | {"file_name": "03_customer_interviews.md", "file_type": "markdown"}
 c8c6d59f-5e10-4ea9-b788-f7ddddedc3d4 | Methodologies compose roles; agents adopt methodologies. | {"file_name": "03_customer_interviews.md", "file_type": "markdown"}
(2 rows)
```

`run_entity_citations` row:

```
SELECT entity_name, entity_type, source_chunk_ids FROM run_entity_citations WHERE run_id = '2e86d393-96b8-4aca-a12f-ac09d7e35355';
   entity_name   | entity_type |                              source_chunk_ids
-----------------+-------------+-----------------------------------------------------------------------------
 Lean Value Tree | Framework   | {eda98773-76a8-41c1-9a58-d69696def123,c8c6d59f-5e10-4ea9-b788-f7ddddedc3d4}
(1 row)
```

## Acceptance criteria verified

- One `runs` row landed on tenant_a inside the
  `async with session.begin()` block.
- Two `run_chunk_citations` rows landed within the same
  transaction; both carry `source_snapshot jsonb` populated with
  the Phase 1 key set (`file_name`, `file_type`) per D96.
- One `run_entity_citations` row landed; `source_chunk_ids text[]`
  carries the entity's provenance trail back to the two cited
  chunks per D96.
- The chunk FK constraint on `run_chunk_citations.chunk_id`
  resolves against real chunks (`ON DELETE SET NULL` preserved
  from D95).
- tenant_b's tables remain unchanged (cross-tenant isolation
  preserved; verified separately via the contract harness at
  `tests/contract/tenant_isolation/test_run_history_isolation.py`
  with 13 scenarios passing).

## Reconciliation notes carried to session log

The tenant-registry wipe between S31 close and S32 session-open
is the third instance of the methodology/role/registry fixture-
leak class. S26b's fix landed at four named fixtures; S30b
extended to two more. The pattern's recurrence suggests the
filter-pattern-application approach (`created_by_user_id NOT LIKE
'migration:%'`) needs a grep-driven completeness check at the
operator-instrumented audit pre-each-session rather than per-
session fixture-by-fixture remediation — recorded as a captures
candidate for the Phase 1 close audit.
