# P6 Epic — Source ingestion

## Goal

Source ingestion is the agent runtime's data substrate. Ship the upload-to-retrieval pipeline so that at P6 close, a tenant can submit a source file through the CLI, the platform parses it, embeds chunks into pgvector on the tenant's data plane, extracts entities and relationships into Neo4j, and exposes the indexed content through a unified retrieval interface ready for the agent runtime at P8 to consume.

## Scope at P6 close

A single `contexts/ingestion/` bounded context owns the full vertical from upload through retrieval. The pipeline runs asynchronously: upload returns a source identifier immediately, background workers move sources through parse, embed, extract, and index stages, and a per-stage status on the source row drives reentrancy. Worker writes are idempotent so retries are safe. The queue mechanism is Postgres `SELECT ... FOR UPDATE SKIP LOCKED` against pending source rows.

Two destination tracks coordinate: pgvector indexing on the tenant's per-tenant Postgres instance (per D32) and graph indexing into Neo4j. A source becomes queryable only when both tracks report success for that source.

A `RetrievalClient` port per D5 exposes the read surface; method shape settles at the implementing session per D56's interface-segregation posture. Tenant isolation extends through the existing `tests/contract/tenant_isolation/` harness per D24 to cover both pgvector and Neo4j paths.

The CLI gains `padhanam ingest` subcommands at `apps/cli/` per the workspace-member precedent from S18. The OTel TracerProvider initialisation pattern reaches its third-instance promotion threshold (per the carryover from S18 reflection) and lifts to a shared helper at `padhanam/observability/init_tracing.py` if the P6 CLI surface is the consumer that justifies the lift.

## Sessions forecast

Three to four sessions. P6 has more vendor surface than P5 (Neo4j enters the codebase, embedding model, extraction model) and the pipeline coordination machinery, so the upper end is more likely than the lower. Session boundaries settle at the session-by-session framing per the established discipline. Indicative shape:

- **S19** lands the bounded context skeleton, source upload, parsing, the status-driven worker pattern, and the queue mechanism. No vendor surface beyond what already exists.
- **S20** lands embedding through LiteLLM (model default settled at the session) and pgvector indexing. First track complete.
- **S21** lands graph extraction (model default settled at the session) and Neo4j writes. Neo4j topology D-entry lands here. Second track complete.
- **S22** if needed lands the retrieval interface and the cross-track readiness semantics, plus P6 close.

## D-entries forecast

Three to five D-entries beyond D60. Forecast at framing:
- Embedding model default per the D15 shape.
- Extraction model default and graph extraction prompt strategy.
- Neo4j topology per the deferred-decisions entry.
- RetrievalClient method surface per D56's interface-segregation principle.
- Possibly: parsing scope at P6 close (file types supported), if the choice surfaces architectural commitments worth recording.

The framing-prompt-as-recommendation pattern (observed four times across P5) holds: framing names options and the strongest recommendation; build sessions commit with whatever refinements the implementation surfaces.

## Out of scope

- **Within-tenant segmentation primitive** (use case, business unit, or other). Defers to the package whose consumer drives the choice (likely P8 agent runtime).
- **Platform-level corpora** (cross-tenant reference content like regulatory text). Defers to a session with a real consumer or to Phase 2 framing alongside the data-plane-ownership entry already in `deferred-decisions.md`.
- **Re-indexing on parsing or embedding-model changes.** Defers to a session that has evidence the cost matters.
- **Diff-aware re-ingestion of updated sources.** Source updates at P6 close are full-replace.
- **Multi-modal sources** (images, audio, video). Phase 2 territory.
- **Citation linking infrastructure beyond what P9 needs.** P9 owns the run-history-to-citation surface.
- **HTTP API for ingestion management.** CLI is the user surface at P6; API ships when a UI consumer arrives.

## Open questions surfaced at framing

- Embedding model default. Likely Ollama-served (consistent with D15's local-default posture) but specific model defers to S20 framing or its prompt.
- Extraction model and prompt strategy. Whether the same default model handles extraction with different prompting, or a smaller specialised model carries the load.
- Parsing scope at P6 close. Markdown is trivial; PDF is meaningful work; DOCX adds another dependency. The cost-benefit settles at S19 framing or in its prompt.
- Source schema specifics, including how many source-lifecycle statuses the per-stage column tracks.
