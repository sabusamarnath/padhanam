# Schema

Updated whenever the database schema changes. Schema diffs at commit time check against this file.

## Tenant registry (control plane)

Lives on the dedicated `postgres-control-plane` Postgres instance per
D33. Schema lands at S10 via Alembic revision
`0001_create_tenant_registry`.

### `tenant_registry`

| Column                     | Type            | Constraints                                    |
|----------------------------|-----------------|------------------------------------------------|
| `tenant_id`                | `uuid`          | primary key                                    |
| `display_name`             | `text`          | not null                                       |
| `jurisdiction`             | `text`          | not null; indexed (`ix_tenant_registry_jurisdiction`) |
| `status`                   | `text`          | not null; default `'active'`; CHECK ∈ {`active`, `suspended`, `deprovisioned`} |
| `created_at`               | `timestamptz`   | not null; default `now()`                      |
| `wrapped_dek`              | `bytea`         | not null; envelope-encrypted DEK (D21)         |
| `dek_wrap_nonce`           | `bytea`         | not null; nonce used to wrap the DEK           |
| `ciphertext`               | `bytea`         | not null; encrypted credentials                |
| `nonce`                    | `bytea`         | not null; nonce used for credential encryption |
| `key_version`              | `integer`       | not null; KEK version for rotation             |
| `aad`                      | `bytea`         | not null; AAD bytes (binds `tenant_id` + purpose `"tenant.credentials.v1"`) |
| `cost_attribution_id`      | `text`          | not null; per-tenant cost-attribution identifier (D41); S14 revision `0003_add_cost_columns` populates it for existing rows from `tenant_id::text` |
| `cost_ceiling_usd_monthly` | `numeric`       | nullable; forward-affordance per D41; not read by any code path at S14 (enforcement deferred to Phase 2) |
| `cost_ceiling_action`      | `text`          | nullable; CHECK ∈ {`block`, `throttle`, `notify`, `audit_only`} or NULL; forward-affordance per D41; not read by any code path at S14 |

No plaintext credential column exists; the registry adapter at S10
encrypts on write via `padhanam/security/crypto.py` and never decrypts
on read. Decryption flows through the operator-context-only
`reveal_connection_config` use case (D34).

The cost-attribution and cost-ceiling columns land at S14 via Alembic
revision `0003_add_cost_columns` per D41. `cost_attribution_id` is
read by the inference adapter (S15) and by future cost-rollup
queries (P9 onward). `cost_ceiling_usd_monthly` and
`cost_ceiling_action` are forward-affordance: declared at the schema
layer, constrained by CHECK on the action space, but not read by any
code path at S14. Phase 2 enforcement architecture activates them.

### `tenant_audit` (control-plane)

Lands at S12 via Alembic revision `0002_create_cp_tenant_audit`.
Holds operator-context audit events (registry mutations, control-plane
state changes) routed to this destination per D35's empty-string
sentinel for `tenant_id`. The schema mirrors the per-tenant
`tenant_audit` table column-for-column; the hash-chain helpers in
`contexts/audit/domain/events.py` operate identically against either
destination.

| Column                | Type            | Constraints                                    |
|-----------------------|-----------------|------------------------------------------------|
| `id`                  | `uuid`          | primary key; default `gen_random_uuid()`       |
| `tenant_id`           | `text`          | not null; CHECK `tenant_id = ''` (empty-string sentinel for control-plane scope per D35) |
| `actor`               | `text`          | not null                                       |
| `jurisdiction`        | `text`          | not null                                       |
| `timestamp`           | `timestamptz`   | not null; indexed (`ix_control_plane_tenant_audit_timestamp`) |
| `action_verb`         | `text`          | not null                                       |
| `resource_type`       | `text`          | not null                                       |
| `resource_id`         | `text`          | not null                                       |
| `before_state`        | `jsonb`         | not null                                       |
| `after_state`         | `jsonb`         | not null                                       |
| `correlation_id`      | `text`          | not null; indexed (`ix_control_plane_tenant_audit_correlation_id`) |
| `previous_event_hash` | `text`          | not null; genesis sentinel `"0" * 64` for the chain head |
| `this_event_hash`     | `text`          | not null; SHA-256 of the event payload + previous hash |

The CHECK constraint on `tenant_id` is symmetric to the per-tenant
table's CHECK (non-empty `tenant_id`). Accidental cross-destination
writes raise constraint violations rather than silently corrupting
the destination chain (D37).

## Per-tenant tables

Live on each tenant's dedicated Postgres instance per D32. Schema is
identical across tenants in S11 (D36); tenant-specific configuration
(classification policy, retention) lives in tenant-configuration
tables, not in schema variations. Initial revision lands at S11 via
the per-tenant Alembic track at `alembic/tenant/`
(`0001_create_tenant_audit`), applied to each registered tenant by
`make migrate`'s per-tenant phase.

### `tenant_audit`

| Column                | Type            | Constraints                                    |
|-----------------------|-----------------|------------------------------------------------|
| `id`                  | `uuid`          | primary key; default `gen_random_uuid()`       |
| `tenant_id`           | `text`          | not null; the routed tenant's id (denormalised on the table for self-describing rows per D22); CHECK `tenant_id <> ''` (S12 revision `0002_audit_sentinel_check`, symmetric to the control-plane CHECK) |
| `actor`               | `text`          | not null                                       |
| `jurisdiction`        | `text`          | not null                                       |
| `timestamp`           | `timestamptz`   | not null; indexed (`ix_tenant_audit_timestamp`) |
| `action_verb`         | `text`          | not null                                       |
| `resource_type`       | `text`          | not null                                       |
| `resource_id`         | `text`          | not null                                       |
| `before_state`        | `jsonb`         | not null                                       |
| `after_state`         | `jsonb`         | not null                                       |
| `correlation_id`      | `text`          | not null; indexed (`ix_tenant_audit_correlation_id`) |
| `previous_event_hash` | `text`          | not null; genesis sentinel `"0" * 64` for the chain head |
| `this_event_hash`     | `text`          | not null; SHA-256 of the event payload + previous hash |

The hash chain is per-tenant (D35). Per-destination chains are
independent: each tenant's database holds one chain, the control
plane holds a separate chain (schema lands at S12). The audit
adapter at S12 routes by the `tenant_id` sentinel: empty string
indicates control-plane scope; non-empty indicates this per-tenant
table on the routed tenant's data plane.

## Evaluation tables

Per-tenant track, lands at S16 via Alembic revision
`0003_create_evaluation_tables`. Seven tables comprise the eval
harness data model: `scoring_sheets` (the named primitive),
`scoring_sheet_revisions` (immutable per-version), `scoring_sheet_criteria`
(per revision), `appliers` (per criterion), `interaction_sets`,
`interactions` (per set), and `rubric_applications` (the score-result
records). `appliers` lives in its own table rather than collapsed into
`scoring_sheet_criteria` so that D53's appliers-as-data framing is
preserved structurally and so that multi-applier-per-criterion (e.g.,
cross-validation pairing a deterministic check with an LLM-as-judge
on the same criterion) lands as a row addition rather than a schema
migration. The `applier_type` column uses a CHECK constraint to pin
valid values; cross-column NULL invariants (e.g.,
`deterministic_function_name` non-null iff
`applier_type='deterministic'`) are enforced at the domain layer
rather than via schema CHECK clauses, with the type-tag-plus-nullable-
columns shape as a watch-item: if S17's prompt applier addition or
future applier types strain the shape, single-table inheritance
promotes to class-table inheritance (`deterministic_appliers`,
`prompt_appliers`) at that point.

### `scoring_sheets`

| Column                | Type            | Constraints                                    |
|-----------------------|-----------------|------------------------------------------------|
| `id`                  | `uuid`          | primary key; default `gen_random_uuid()`       |
| `name`                | `text`          | not null                                       |
| `description`         | `text`          | nullable                                       |
| `created_by_user_id`  | `text`          | not null                                       |
| `created_at`          | `timestamptz`   | not null; default `now()`                      |
| `archived_at`         | `timestamptz`   | nullable                                       |

### `scoring_sheet_revisions`

| Column                | Type            | Constraints                                    |
|-----------------------|-----------------|------------------------------------------------|
| `id`                  | `uuid`          | primary key; default `gen_random_uuid()`       |
| `scoring_sheet_id`    | `uuid`          | not null; FK → `scoring_sheets.id`             |
| `version`             | `integer`       | not null                                       |
| `description`         | `text`          | nullable                                       |
| `created_by_user_id`  | `text`          | not null                                       |
| `created_at`          | `timestamptz`   | not null; default `now()`                      |

`UNIQUE(scoring_sheet_id, version)` —
`scoring_sheet_revisions_sheet_version_unique`. Revisions are
immutable per D53: updates create new revision rows, never edit
existing ones.

### `scoring_sheet_criteria`

| Column                       | Type            | Constraints                                    |
|------------------------------|-----------------|------------------------------------------------|
| `id`                         | `uuid`          | primary key; default `gen_random_uuid()`       |
| `scoring_sheet_revision_id`  | `uuid`          | not null; FK → `scoring_sheet_revisions.id`    |
| `name`                       | `text`          | not null                                       |
| `description`                | `text`          | nullable                                       |
| `levels`                     | `jsonb`         | not null; structured array of `{label, definition}` objects |
| `ordering`                   | `integer`       | not null                                       |

`levels` carries the criterion's score-interpretation contract per
D55: each entry pairs a score label (numeric like `"4"`,
categorical like `"pass"`, or continuous like `"0.85"`) with a
human-readable definition of what produces that label. The criterion
is the architectural authority on what its scores mean.

### `appliers`

| Column                          | Type    | Constraints                                                     |
|---------------------------------|---------|-----------------------------------------------------------------|
| `id`                            | `uuid`  | primary key; default `gen_random_uuid()`                        |
| `scoring_sheet_revision_id`     | `uuid`  | not null; FK → `scoring_sheet_revisions.id`                     |
| `criterion_id`                  | `uuid`  | not null; FK → `scoring_sheet_criteria.id`                      |
| `applier_type`                  | `text`  | not null; CHECK ∈ {`deterministic`, `prompt`, `human`}          |
| `deterministic_function_name`   | `text`  | nullable                                                        |
| `prompt_template`               | `text`  | nullable                                                        |
| `judge_model`                   | `text`  | nullable                                                        |

Cross-column NULL invariants enforced at the domain layer per the
section rationale above; no schema-level CHECKs on the cross-column
shape at S16. The `applier_type` CHECK pins the type-tag space so
unknown applier_types cannot land.

### `interaction_sets`

| Column                | Type            | Constraints                                    |
|-----------------------|-----------------|------------------------------------------------|
| `id`                  | `uuid`          | primary key; default `gen_random_uuid()`       |
| `name`                | `text`          | not null                                       |
| `description`         | `text`          | nullable                                       |
| `created_by_user_id`  | `text`          | not null                                       |
| `created_at`          | `timestamptz`   | not null; default `now()`                      |

### `interactions`

| Column                | Type            | Constraints                                    |
|-----------------------|-----------------|------------------------------------------------|
| `id`                  | `uuid`          | primary key; default `gen_random_uuid()`       |
| `interaction_set_id`  | `uuid`          | not null; FK → `interaction_sets.id`           |
| `input`               | `jsonb`         | not null                                       |
| `expected_output`     | `jsonb`         | nullable                                       |
| `ordering`            | `integer`       | not null                                       |
| `created_at`          | `timestamptz`   | not null; default `now()`                      |

`input` and `expected_output` are jsonb so the interaction model
carries text prompts, structured payloads, and future
agent-trajectory inputs without schema variation.

### `rubric_applications`

| Column                       | Type            | Constraints                                    |
|------------------------------|-----------------|------------------------------------------------|
| `id`                         | `uuid`          | primary key; default `gen_random_uuid()`       |
| `scoring_sheet_revision_id`  | `uuid`          | not null; FK → `scoring_sheet_revisions.id`    |
| `criterion_id`               | `uuid`          | not null; FK → `scoring_sheet_criteria.id`     |
| `interaction_id`             | `uuid`          | not null; FK → `interactions.id`               |
| `applier_id`                 | `uuid`          | not null; FK → `appliers.id`                   |
| `automated_score`            | `text`          | nullable; populated by deterministic and prompt appliers per D53 |
| `human_score`                | `text`          | nullable; data-substrate for the deferred human-review path per D53 |
| `reviewed_by_user_id`        | `text`          | nullable; data-substrate for the deferred human-review path per D53 |
| `confirmed_at`               | `timestamptz`   | nullable; data-substrate for the deferred human-review path per D53 |
| `trace_id`                   | `text`          | nullable; lands at S17a via revision `0004_add_rubric_apps_trace_id` alongside the replay engine; links each rubric application to the trace that produced its scored output |
| `created_at`                 | `timestamptz`   | not null; default `now()`                      |

Score columns are `text` per D55. Score interpretation is
criterion-level: each criterion's `levels` jsonb defines what its
score values mean. SQL aggregation across `rubric_applications`
requires criterion-level filtering and explicit casting; direct
`AVG(automated_score)` is foreclosed and is not the intended access
pattern. The reading and write surfaces consume the criterion's
level definitions to determine pass/fail, threshold breaches, or
continuous aggregation.

`trace_id` lands at S17a alongside the replay engine via revision
`0004_add_rubric_apps_trace_id`; the column links each rubric
application to the trace that produced its scored output,
enabling cost-per-successful-task computation at S17b without
coupling evaluation to a specific trace store implementation per
D27. The column is nullable so that rubric_applications produced by
paths that do not pass through the replay engine (deterministic
applier invoked from a flow that does not run a model) leave
trace_id null; downstream cost queries skip those rows. The S16
forward-affordance discipline held — the column landed at the
session that introduced its proximate consumer rather than at S16
speculatively.

## Source ingestion tables

Per-tenant track, lands at S19 via Alembic revision
`0005_create_sources_and_chunks` per D60 / D61. Two tables comprise
the S19 surface: `sources` (the upload primitive plus pipeline-state
column) and `chunks` (the parsed-content rows that pgvector
embeddings will reference at S20). The `state` column on `sources`
is the per-stage status field D60 commits to as the worker
reentrancy seam; at S19 it tracks only the parsing stage
(`{received, parsing, parsed, failed}`). S20 extends the state
space with the embedding stage and S21 with the extraction stage.

### `sources`

| Column                | Type            | Constraints                                                                                                                                       |
|-----------------------|-----------------|---------------------------------------------------------------------------------------------------------------------------------------------------|
| `id`                  | `uuid`          | primary key; default `gen_random_uuid()`                                                                                                          |
| `tenant_id`           | `text`          | not null; CHECK `tenant_id <> ''` (denormalised on the row for self-describing audit per D22)                                                     |
| `jurisdiction`        | `text`          | not null                                                                                                                                          |
| `file_name`           | `text`          | not null                                                                                                                                          |
| `file_type`           | `text`          | not null; CHECK ∈ {`markdown`, `text`} per D61 (extends incrementally as parsers ship)                                                             |
| `file_size_bytes`     | `bigint`        | not null                                                                                                                                          |
| `raw_content`         | `bytea`         | not null at S19; the dev shape stores raw bytes on the row. Production object-store URI deferred until production deployment context arrives      |
| `state`               | `text`          | not null; CHECK ∈ {`received`, `parsing`, `parsed`, `failed`}; default `'received'`                                                               |
| `parsing_error_text`  | `text`          | nullable; populated when `state = 'failed'` so the operator can see why parsing failed without trawling logs                                      |
| `created_by_user_id`  | `text`          | not null                                                                                                                                          |
| `created_at`          | `timestamptz`   | not null; default `now()`                                                                                                                         |
| `updated_at`          | `timestamptz`   | not null; default `now()`; the worker bumps this on each state transition                                                                         |

Indices: `ix_sources_tenant_state` on `(tenant_id, state)` for the
worker poll (the `claim_pending_for_parse` query filters by
`state = 'received'` and the index keeps the planner from a full
scan).

The state column drives reentrancy per D60: `received` rows are
claimed by the worker via `SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1`,
transitioned to `parsing` while the parser runs, and transitioned to
`parsed` on success or `failed` on parser exception. Re-running the
worker against an already-`parsed` source is a no-op (the claim
query returns no rows for that source). Re-running against a
`failed` source by manually transitioning back to `received` is the
operator surface for retry at S19; richer retry semantics defer to
production-deployment context.

### `chunks`

| Column                  | Type            | Constraints                                                                                                                |
|-------------------------|-----------------|----------------------------------------------------------------------------------------------------------------------------|
| `id`                    | `uuid`          | primary key; default `gen_random_uuid()`                                                                                   |
| `source_id`             | `uuid`          | not null; FK → `sources.id`                                                                                                |
| `tenant_id`             | `text`          | not null; CHECK `tenant_id <> ''`                                                                                          |
| `jurisdiction`          | `text`          | not null                                                                                                                   |
| `chunk_index`           | `integer`       | not null; ordering within the source                                                                                       |
| `content`               | `text`          | not null                                                                                                                   |
| `structural_metadata`   | `jsonb`         | not null; default `'{}'::jsonb`; carries parser-emitted structure (e.g., heading hierarchy for markdown, paragraph index for plain text) |
| `created_at`            | `timestamptz`   | not null; default `now()`                                                                                                  |

Indices: `ix_chunks_source_id` on `source_id`; UNIQUE
`(source_id, chunk_index)` so re-running the parser against an
already-parsed source produces an integrity violation rather than
duplicate rows (the worker's idempotency contract per D60 means
the parser write only happens once per source-index pair; the
constraint is the structural backstop).

S19 lands no embedding columns on `chunks`. The embedding column
lands at S20 via the next per-tenant migration alongside the
embedding adapter; the column name and type settle at S20 framing
per the framing-prompt-as-recommendation pattern.

## Vector store

(Empty until S20 ships the embedding column on `chunks` and the
pgvector index.)

## Graph store

(Empty until S21 ships Neo4j writes per the deferred-decisions entry.)
