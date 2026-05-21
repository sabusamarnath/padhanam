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
| `created_by_user_id`       | `text`          | not null; actor provenance per D101; lands at S35a via Alembic revision `0011_tenant_actor_provenance`; existing rows backfill with sentinel `'migration:0001'`; seed script uses `'migration:ops/seed_tenants'` so wipe-guard pattern `NOT LIKE 'migration:%'` works symmetrically with methodology/role/tool tables |

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

## Methodology templates (control plane)

Lives on the dedicated `postgres-control-plane` Postgres instance per
D33. Schema initially lands at S23 via Alembic revision
`0004_methodology_tables`. Refactored to the role-first v3 shape per
D86 at S26a-1 via revisions `0006_methodology_role_refs` (constraint
bundle moves to the role aggregate; methodology revisions gain
`role_refs jsonb`) and `0007_lvt_split` (data-only migration renaming
the auto-migrated role to `LVTGuide`).

### `methodology_templates`

| Column                | Type            | Constraints                                    |
|-----------------------|-----------------|------------------------------------------------|
| `id`                  | `uuid`          | primary key; default `gen_random_uuid()`       |
| `name`                | `text`          | not null; UNIQUE among non-archived templates per partial index `ix_methodology_templates_name_unique_active` |
| `description`         | `text`          | nullable                                       |
| `created_by_user_id`  | `text`          | not null                                       |
| `created_at`          | `timestamptz`   | not null; default `now()`                      |
| `archived_at`         | `timestamptz`   | nullable                                       |

The partial-unique-index on `name` where `archived_at IS NULL` enforces
unique active template names across the platform; archived templates
retain their name without conflict for audit purposes per D31's
append-only-at-version-level discipline.

### `methodology_revisions`

| Column                    | Type            | Constraints                                    |
|---------------------------|-----------------|------------------------------------------------|
| `id`                      | `uuid`          | primary key; default `gen_random_uuid()`       |
| `methodology_template_id` | `uuid`          | not null; FK → `methodology_templates.id`      |
| `version`                 | `integer`       | not null                                       |
| `role_refs`               | `jsonb`         | not null; array of `{role_id, role_version, overrides}` entries per D86; lands at S26a-1 via revision `0006_methodology_role_refs` replacing the prior constraint bundle; D87 commits `overrides` to the structured `{<field>: {"mode", "value"}}` shape |
| `created_by_user_id`      | `text`          | not null                                       |
| `created_at`              | `timestamptz`   | not null; default `now()`                      |
| `previous_revision_hash`  | `text`          | not null; genesis sentinel `"0" * 64` for the chain head |
| `this_revision_hash`      | `text`          | not null; SHA-256 of canonical JSON of content fields plus previous hash per D74 |

`UNIQUE(methodology_template_id, version)` —
`methodology_revisions_template_version_unique`. Revisions are immutable
per D31; updates create new revision rows.

Per D86's role-first refinement (Phase 1 methodology v3, skipping the
never-built v2 from D81), revision `0006_methodology_role_refs` at
S26a-1 drops the prior constraint bundle columns (`system_prompt`,
`source_ids`, `tool_allowlist`, `retrieval_strategy`, `filter_tree`,
`top_k`, `min_score`, `model_selection`) from this table; the bundle
moves to the role aggregate per `## Role aggregate (control plane)`
below. Each entry in `role_refs` carries `role_id` (UUID string
referencing a `role_templates.id`), `role_version` (integer referencing
a `role_revisions.version` of that role), and `overrides` (JSON object
carrying methodology-context-specific field overrides per D86's per-role
overrides commitment, refined by D87).

Per D87 (S26b), the `overrides` shape is `{<field>: {"mode": <str>,
"value": <any>}}` with the mode drawn from `{augment, replace, tighten}`.
Each entry in `overrides` keys by the underlying role field (e.g.
`system_prompt`, `tool_allowlist`, `retrieval_strategy`) and carries the
canonical mode-and-value pair the agent runtime at S27b consumes. Empty
or absent `overrides` (e.g. the LVT methodology's single `role_ref`) is
the trivial no-op: the JSONB stores `{}` and canonical serialisation
remains byte-stable. The authoring projection at the methodology config
parser layer accepts a flat value per field and expands to the
structured form using the per-field default mode committed in D87
(`system_prompt` → augment; soft fields → replace; hard fields →
tighten); structured input passes through; inadmissible (field, mode)
pairs raise at parse time. The on-disk JSONB always carries the
structured form so hash determinism stays byte-stable across authoring
paths.

The hash-chain content surface updates at the same revision: the
spanned fields become `name` (denormalised from the parent template at
hash-compute time per D74's chain-self-containment pattern),
`description` (denormalised likewise), `role_refs` (sorted by
`role_id` for determinism), plus `previous_revision_hash`. The
constraint bundle no longer spans the methodology hash; the bundle's
content surface is now spanned by each role revision's own chain. The
migration script at `0006_methodology_role_refs` recomputes existing
methodology revision hashes against the new content surface, anchoring
chain integrity at the migration boundary; the LVT methodology
revision 1 from S23 is the only existing row at migration time. Down-
migration re-adds the bundle columns and re-derives them from
`role_refs`; lossy when methodology revisions reference multiple roles
(Phase 1 has single-role methodologies only, so the down-migration
loss surface is structurally bounded).

`0007_lvt_split` (also at S26a-1) renames the auto-migrated role row
to `LVTGuide` per D86's LVT methodology + LVTGuide role split
commitment; no schema change, data-only migration.

## Role aggregate (control plane)

Lives on the dedicated `postgres-control-plane` Postgres instance per
D33. Schema lands at S26a-1 via Alembic revision `0005_role_tables`.
Roles are independently authored and identified per D86 Y2 sub-choice:
hosted within `contexts/methodology/` bounded context but with their
own aggregate, repository, and use cases. Promotion to a separate
`contexts/roles/` bounded context defers to Phase 2 if evidence
demands per D86.

### `role_templates`

| Column                | Type            | Constraints                                    |
|-----------------------|-----------------|------------------------------------------------|
| `id`                  | `uuid`          | primary key; default `gen_random_uuid()`       |
| `name`                | `text`          | not null; UNIQUE among non-archived templates per partial index `ix_role_templates_name_unique_active` |
| `description`         | `text`          | nullable                                       |
| `created_by_user_id`  | `text`          | not null                                       |
| `created_at`          | `timestamptz`   | not null; default `now()`                      |
| `archived_at`         | `timestamptz`   | nullable                                       |

The partial-unique-index on `name` where `archived_at IS NULL` mirrors
the methodology_templates pattern: unique active role names across the
platform; archived rows retain their name for audit per D31.

### `role_revisions`

| Column                    | Type            | Constraints                                    |
|---------------------------|-----------------|------------------------------------------------|
| `id`                      | `uuid`          | primary key; default `gen_random_uuid()`       |
| `role_template_id`        | `uuid`          | not null; FK → `role_templates.id`             |
| `version`                 | `integer`       | not null                                       |
| `system_prompt`           | `text`          | not null                                       |
| `source_ids`              | `jsonb`         | not null; array of UUID strings; typically empty for platform-managed roles per D68 |
| `tool_allowlist`          | `jsonb`         | not null; pre-D89 shape was an array of opaque name strings; post-S28b commit 4 the shape is an array of `{tool_id, revision_id}` objects pinning to specific tool revisions per D89 |
| `retrieval_strategy`      | `jsonb`         | not null; strategy-name-plus-params shape per D66 |
| `filter_tree`             | `jsonb`         | not null; typed Boolean tree per D67           |
| `top_k`                   | `integer`       | not null                                       |
| `min_score`               | `numeric`       | not null                                       |
| `model_selection`         | `text`          | not null                                       |
| `created_by_user_id`      | `text`          | not null                                       |
| `created_at`              | `timestamptz`   | not null; default `now()`                      |
| `previous_revision_hash`  | `text`          | not null; genesis sentinel `"0" * 64` for the chain head |
| `this_revision_hash`      | `text`          | not null; SHA-256 of canonical JSON of content fields plus previous hash per D74 |

`UNIQUE(role_template_id, version)` —
`role_revisions_template_version_unique`. Revisions are immutable per
D31; updates create new revision rows. Hash-chain content surface
mirrors the methodology revision pattern from D74: the hash spans
`name` (denormalised from the parent template at hash-compute time),
`description` (denormalised likewise), `system_prompt`, `source_ids`
(sorted), `tool_allowlist` (sorted by `(tool_id, revision_id)` per
D89 commit 4; the on-disk shape is an array of
`{"tool_id": "<uuid>", "revision_id": "<uuid>"}` objects),
`retrieval_strategy`,
`filter_tree`, `top_k`, `min_score`, `model_selection`, plus
`previous_revision_hash`. Chain metadata (template_id, version,
timestamps) is excluded from the hash. Each role template has its own
independent chain rooted at the genesis sentinel.

D86's idealization names `source_filter` and `cost_ceiling` on the
role bundle. S26a-1 implements with existing field names (`source_ids`
matching `methodology_revisions`' prior shape; no `cost_ceiling`
column at the role layer) to avoid introducing schema concepts without
consumers — cost-ceiling forward-affordance already lives at the
tenant-registry level per D41 and is unread until Phase 2 enforcement.
The drift between D86's idealized field set and implementation reality
is intentional per the brief's pre-write reconciliation and is logged
in S26a-1's reflection.

## Tool registry (control plane)

Lives on the dedicated `postgres-control-plane` Postgres instance per
D33. Schema lands at S28b via Alembic revision
`0009_create_tools_tables`. Storage location resolves per D89's
storage-location section: alongside `methodology_templates`,
`methodology_revisions`, `role_templates`, `role_revisions` rather
than per-tenant per the P8 epic note's initial framing. Per-tenant
tool authoring lifts at Phase 2 per the deferred-decisions entry on
customer-deployment evidence.

### `tools`

| Column                | Type            | Constraints                                    |
|-----------------------|-----------------|------------------------------------------------|
| `id`                  | `uuid`          | primary key; default `gen_random_uuid()`       |
| `name`                | `text`          | not null; UNIQUE among non-archived templates per partial index `ix_tools_name_unique_active` |
| `description`         | `text`          | nullable                                       |
| `classification`      | `text`          | not null; CHECK ∈ {`read-only`, `drafting`, `user-affecting-with-consent`, `financial`, `communication`, `legal`} per `tools_classification_check` (the six-category D89 taxonomy) |
| `created_by_user_id`  | `text`          | not null                                       |
| `created_at`          | `timestamptz`   | not null; default `now()`                      |
| `archived_at`         | `timestamptz`   | nullable                                       |

Classification is on the template per D89 alternative (g):
classification is a property of what the tool does, not what role
uses it. Reclassifying mid-revision would semantically be a different
tool; the template owns classification, revisions evolve the
parameters and returns schemas.

The partial-unique-index on `name` where `archived_at IS NULL` mirrors
the methodology / role pattern: unique active tool names across the
platform; archived rows retain their name for audit per D31.

The retrieval tool seeds as part of revision `0009_create_tools_tables`
with the well-known UUID `00000000-0000-0000-0000-000000000001`. The
fixed UUID is the durable anchor that lets platform-managed role
allowlists reference retrieval across the role allowlist tuple-shape
migration at S28b commit 4 (`0010_role_tool_allowlist_pin`).
Classification is `read-only`.

### `tool_revisions`

| Column                    | Type            | Constraints                                    |
|---------------------------|-----------------|------------------------------------------------|
| `id`                      | `uuid`          | primary key; default `gen_random_uuid()`       |
| `tool_id`                 | `uuid`          | not null; FK → `tools.id`                      |
| `version`                 | `integer`       | not null                                       |
| `parameters_schema`       | `jsonb`         | not null; JSON-schema payload describing the tool's argument shape |
| `returns_schema`          | `jsonb`         | not null; JSON-schema payload describing the tool's result shape; used by the BC stub at commit 6 |
| `bc_result`               | `jsonb`         | not null; default `'{}'::jsonb`; populated by `create_tool_revision` at commit 6 with the schema-diff outcome per D89 (forward-affordance column at the table-create migration) |
| `created_by_user_id`      | `text`          | not null                                       |
| `created_at`              | `timestamptz`   | not null; default `now()`                      |
| `previous_revision_hash`  | `text`          | not null; genesis sentinel `"0" * 64` for the chain head |
| `this_revision_hash`      | `text`          | not null; SHA-256 of canonical JSON of content fields plus previous hash per D74 |

`UNIQUE(tool_id, version)` —
`tool_revisions_tool_version_unique`. Revisions are immutable per
D31; updates create new revision rows. Hash-chain content surface
mirrors the methodology / role revision patterns from D74:
the hash spans `name` (denormalised from the parent template at
hash-compute time), `description` (denormalised likewise),
`classification` (denormalised likewise; classification is on the
template per D89 alternative (g)), `parameters_schema`,
`returns_schema`, plus `previous_revision_hash`. Chain metadata
(template_id, version, timestamps, bc_result) is excluded from the
hash. Each tool has its own independent chain rooted at the
genesis sentinel.

The retrieval revision-1 seeds with the well-known UUID
`00000000-0000-0000-0000-000000000002` and a `previous_revision_hash`
of the genesis sentinel; `parameters_schema` matches the prior
hardcoded `_RETRIEVAL_TOOL_DEFINITION.parameters` in S27b's
`AgentLoopExecutor` verbatim; `returns_schema` describes the single-
string result shape produced by `_format_chunks_as_tool_result`. The
retrieval seed lands at the table-create migration so the role
allowlist tuple-shape migration at commit 4 has a stable target
revision to pin against.

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
`0005_create_sources_and_chunks` per D60 / D61, extended at S20 via
revision `0006_add_chunk_embedding` per D62. Two tables comprise
the surface: `sources` (the upload primitive plus pipeline-state
column) and `chunks` (the parsed-content rows plus per-chunk
embedding vector). The `state` column on `sources` is the per-stage
status field D60 commits to as the worker reentrancy seam; S19
tracked the parsing stage (`{received, parsing, parsed, failed}`),
S20 extends with the embedding stage (`{embedding, embedded,
embedding_failed}`); S21 extends with the extraction stage. S22
adds retrieval methods (vector cosine search via pgvector and
graph traversal via Neo4j) that read the existing schema without
schema changes — the per-source state filter at retrieval time is
a `state = 'indexed'` predicate against `sources` per D65, not a
new column.

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
| `state`               | `text`          | not null; CHECK ∈ {`received`, `parsing`, `parsed`, `failed`, `embedding`, `embedded`, `embedding_failed`}; default `'received'`. S19 lands the parsing-stage values; S20 extends with the embedding-stage values per D62 via revision `0006_add_chunk_embedding` |
| `parsing_error_text`  | `text`          | nullable; populated when `state = 'failed'` so the operator can see why parsing failed without trawling logs                                      |
| `embedding_error_text` | `text`         | nullable; populated when `state = 'embedding_failed'` so the operator can see why embedding failed without trawling logs. Lands at S20 per D62    |
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
`parsed` on success or `failed` on parser exception. The S20
embedding stage extends the same pattern: `parsed` rows are claimed
by `claim_pending_for_embed`, transitioned to `embedding` while the
embedder runs, and transitioned to `embedded` on success or
`embedding_failed` on embedder exception. Re-running the worker
against an already-`embedded` source is a no-op (the claim query
returns no rows for that source). Re-running against a `failed` or
`embedding_failed` source by manually transitioning back to
`received` or `parsed` is the operator surface for retry at S19/S20;
richer retry semantics defer to production-deployment context.

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
| `embedding`             | `vector(768)`   | nullable; populated by the S20 embedding worker stage per D62. Dimension matches `nomic-embed-text:v1.5` native output. Lands at S20 via revision `0006_add_chunk_embedding` |
| `created_at`            | `timestamptz`   | not null; default `now()`                                                                                                  |

Indices: `ix_chunks_source_id` on `source_id`; UNIQUE
`(source_id, chunk_index)` so re-running the parser against an
already-parsed source produces an integrity violation rather than
duplicate rows (the worker's idempotency contract per D60 means
the parser write only happens once per source-index pair; the
constraint is the structural backstop). `chunks_embedding_hnsw_idx`
on `(embedding vector_cosine_ops)` `USING hnsw` with pgvector
defaults `(m=16, ef_construction=64)` per D62; lands at S20 via
revision `0006_add_chunk_embedding`. Cosine matches
`nomic-embed-text:v1.5`'s recommended distance metric.

## Vector store

The S20 embedding column on `chunks` plus the
`chunks_embedding_hnsw_idx` HNSW index over `vector_cosine_ops` is
the vector store at P6. Per-tenant per D32 — each tenant's
embeddings live on the tenant's own data plane; cross-tenant
retrieval is structurally prevented by the per-tenant Postgres
instance topology. The embedding worker writes via UPSERT on
`chunks.id` for idempotent re-embed per D62 (re-running the
embedding stage against the same chunk replaces the vector rather
than producing a duplicate row; the column nullability lets the
embedded vs not-yet-embedded shape stay observable on the row).

## Graph store (Neo4j 5, shared instance, tenant-property scoping)

Lands at S21 per D63 and D64 via Cypher migration
`migrations/neo4j/0001_base_constraints.cypher`. Single Neo4j 5
Community instance (`padhanam-neo4j` Compose service, pinned per
D10) shared across all tenants. Tenant isolation is enforced at
the property level on both nodes and relationships, structurally
gated by the `TenantScopedNeo4jSession` wrapper at
`contexts/ingestion/adapters/outbound/neo4j/` per D63 (raw
`neo4j` driver imports forbidden outside the wrapper module by the
`neo4j-confined` import-linter contract and by AST enforcement
test `tests/_enforcement/test_no_raw_neo4j_session.py`). Contract
tests under `tests/contract/tenant_isolation/` verify cross-tenant
read and write access fails on both directions.

### `:Entity` nodes

| Property            | Type             | Notes                                                                                            |
|---------------------|------------------|--------------------------------------------------------------------------------------------------|
| `tenant_id`         | `String`         | not empty; constrained by tenant-isolation predicate at every Cypher query                       |
| `jurisdiction`      | `String`         | first-class per D12; matches the source's jurisdiction                                           |
| `name`              | `String`         | extracted from chunks; the human-readable label of the entity                                    |
| `entity_type`       | `String`         | free-form per D64; no taxonomy commitment at S21                                                 |
| `source_chunk_ids`  | `List<String>`   | provenance back to per-tenant Postgres `chunks.id` rows; appended on re-extraction MERGE         |
| `created_at`        | `DateTime`       | set on initial MERGE; not updated on subsequent MERGEs against the same composite key            |

Uniqueness constraint: `entity_unique_per_tenant` on
`(tenant_id, name, entity_type)`. The constraint doubles as the
composite-key index for tenant-scoped entity lookup. Cypher
MERGE on this composite key produces idempotent re-extraction:
the second MERGE with the same `(tenant_id, name, entity_type)`
matches the existing node and updates the mutable
`source_chunk_ids` array additively.

### Relationships

Typed Neo4j edges. The relationship type comes from the
extraction prompt at runtime; no taxonomy commitment per D64.
Properties on every relationship:

| Property            | Type        | Notes                                                                                            |
|---------------------|-------------|--------------------------------------------------------------------------------------------------|
| `tenant_id`         | `String`    | not empty; matches both endpoint nodes' `tenant_id`                                              |
| `jurisdiction`      | `String`    | matches both endpoint nodes' `jurisdiction`                                                      |
| `source_chunk_id`   | `String`    | provenance to the per-tenant Postgres `chunks.id` row that produced the relationship             |
| `created_at`        | `DateTime`  | set on initial MERGE                                                                             |

Uniqueness: composite key
`(tenant_id, source_id, target_id, relationship_type, source_chunk_id)`.
Neo4j Community Edition does not support relationship-property
uniqueness constraints declaratively; uniqueness is enforced
through the MERGE pattern in the GraphRepository adapter (Cypher
`MERGE (a)-[r:RELTYPE {tenant_id: ..., source_chunk_id: ...}]->(b)`
keyed on the five-component composite). The same chunk re-extracted
produces no duplicate edges; different chunks producing the same
endpoint pair and relationship type produce distinct edges keyed
on `source_chunk_id`, preserving provenance.

## Agent tables (per-tenant)

Live on each tenant's dedicated Postgres instance per D32. Schema lands at S24 via Alembic revision `0008_agent_tables` on the per-tenant track at `alembic/tenant/`. S26a-2 extends `agent_templates` with role lineage fields via Alembic revision `0009_agent_role_lineage` per D86's role-first refinement.

### `agent_templates`

| Column                              | Type            | Constraints                                    |
|-------------------------------------|-----------------|------------------------------------------------|
| `id`                                | `uuid`          | primary key; default `gen_random_uuid()`       |
| `name`                              | `text`          | not null; UNIQUE among non-archived templates per partial index `ix_agent_templates_name_unique_active` |
| `description`                       | `text`          | nullable; immutable after creation per D75     |
| `source_methodology_template_id`    | `uuid`          | nullable for blank-created agents; immutable after construction per D75 |
| `source_methodology_template_version` | `integer`     | nullable for blank-created agents; immutable after construction per D75 |
| `source_role_id`                    | `uuid`          | nullable for blank-created agents; immutable after construction per D86 |
| `source_role_version`               | `integer`       | nullable for blank-created agents; immutable after construction per D86 |
| `created_by_user_id`                | `text`          | not null                                       |
| `created_at`                        | `timestamptz`   | not null; default `now()`                      |
| `archived_at`                       | `timestamptz`   | nullable                                       |

Lineage fields move as paired-NULL pairs: D75's paired-null invariant on `(source_methodology_template_id, source_methodology_template_version)` is enforced by CHECK constraint `agent_templates_lineage_paired_null`; D86's paired-null invariant on `(source_role_id, source_role_version)` is enforced independently by CHECK constraint `agent_templates_role_lineage_paired_null` (`CHECK ((source_role_id IS NULL) = (source_role_version IS NULL))`).

The two pairs are independent. Three valid combinations:

- Both pairs NULL — blank-created agent at S24's `create_blank_agent`.
- Both pairs populated — methodology-created agent at S25's `create_agent_from_methodology` flow per D79; the methodology lineage pair carries the methodology origin and the role lineage pair carries the resolved first `role_ref` from the methodology's revision, persisted at agent creation time so the role-aware constraint stack from D86 has its origin attribution available.
- Only the role pair populated, methodology pair NULL — role-created agent at S26a-2's `create_agent_from_role` flow; an agent occupies a role directly without a methodology playbook above it, per D86's first-class-role posture.

The fourth combination (methodology populated, role NULL) is structurally invalid because methodology-based creation always resolves at least one role per D86; it is not separately CHECK-constrained because the role-pair invariant alone is sufficient to keep the schema honest about populated-role agents.

The partial-unique-index on `name` where `archived_at IS NULL` enforces unique active agent names per tenant.

### `agent_revisions`

| Column                    | Type            | Constraints                                    |
|---------------------------|-----------------|------------------------------------------------|
| `id`                      | `uuid`          | primary key; default `gen_random_uuid()`       |
| `agent_template_id`       | `uuid`          | not null; FK → `agent_templates.id`            |
| `version`                 | `integer`       | not null                                       |
| `system_prompt`           | `text`          | not null                                       |
| `source_ids`              | `jsonb`         | not null; array of UUID strings                |
| `tool_allowlist`          | `jsonb`         | not null; pre-D89 shape was an array of opaque name strings; post-S28b commit 4 the per-tenant shape is an array of `{tool_id, revision_id}` objects pinning to specific tool revisions per D89 (Alembic per-tenant `0010_agent_tool_allowlist_pin`) |
| `retrieval_strategy`      | `jsonb`         | not null; strategy-name-plus-params per D66    |
| `filter_tree`             | `jsonb`         | not null; typed Boolean tree per D67           |
| `top_k`                   | `integer`       | not null                                       |
| `min_score`               | `numeric`       | not null                                       |
| `model_selection`         | `text`          | not null                                       |
| `created_by_user_id`      | `text`          | not null                                       |
| `created_at`              | `timestamptz`   | not null; default `now()`                      |
| `previous_revision_hash`  | `text`          | not null; genesis sentinel `"0" * 64` for chain head |
| `this_revision_hash`      | `text`          | not null; SHA-256 per D75's content surface specification |

Name and description are read from the parent `agent_templates` row at hash-compute time per D75 and are not persisted as columns on `agent_revisions`; the canonical-JSON payload pulls them from the template, mirroring the methodology context's actual implementation from S23.

`UNIQUE(agent_template_id, version)` — `agent_revisions_template_version_unique`. Revisions are immutable per D31; updates create new revision rows. Hash chain is per template; chains are independent per agent template, mirroring the methodology revision pattern from D74.

## Run history tables

Per-tenant track, lands at S31 via Alembic revision
`0011_create_run_history` per D95. Three tables comprise the
surface: `runs` (the structured run record), `run_chunk_citations`
(run-to-chunk linkage), `run_entity_citations` (run-to-Neo4j-entity
linkage). All three live on the tenant's data plane per D32.

### `runs`

| Column                    | Type            | Constraints                                                                                                                                          |
|---------------------------|-----------------|------------------------------------------------------------------------------------------------------------------------------------------------------|
| `id`                      | `uuid`          | primary key; default `gen_random_uuid()`                                                                                                             |
| `tenant_id`               | `text`          | not null; CHECK `tenant_id <> ''` (denormalised per D22)                                                                                             |
| `jurisdiction`            | `text`          | not null                                                                                                                                             |
| `agent_template_id`       | `uuid`          | not null; FK-equivalent to `agent_templates.id` (no enforced FK because `agent_templates` is append-only per D75; references survive archived state) |
| `agent_template_version`  | `integer`       | not null                                                                                                                                             |
| `input_message`           | `text`          | not null; the user-supplied input echoed for audit and rendering                                                                                     |
| `output_content`          | `text`          | not null; the agent's final content; empty string for `InvocationFailed` and `InvariantBlocked` terminations                                          |
| `started_at`              | `timestamptz`   | not null                                                                                                                                             |
| `completed_at`            | `timestamptz`   | not null                                                                                                                                             |
| `termination_reason`      | `text`          | not null; CHECK ∈ {`content`, `max_iterations`, `tool_not_registered`, `error`, `invariant_blocked`, `failed`} (the five `TerminationReason` enum values plus synthesised `failed` for the `InvocationFailed` terminal event class per D95) |
| `iteration_count`         | `integer`       | not null; CHECK `>= 0`                                                                                                                               |
| `total_cost_usd`          | `numeric`       | not null; CHECK `>= 0`                                                                                                                               |
| `trace_id`                | `text`          | nullable; OTel trace identifier per D27; join key to the trace store                                                                                  |
| `audit_start_hash`        | `text`          | not null; CHECK length 64; `this_event_hash` from the audit row at `InvocationStarted` per S29b                                                       |
| `audit_end_hash`          | `text`          | nullable; CHECK `audit_end_hash IS NULL OR length(audit_end_hash) = 64`; additional CHECK `(termination_reason = 'failed') OR (audit_end_hash IS NOT NULL)`; NULL only for `InvocationFailed` events with 1-hash `partial_audit_chain_state` (start audit landed, end audit did not) per D95 |
| `created_at`              | `timestamptz`   | not null; default `now()`                                                                                                                            |

Indices: `ix_runs_agent_template_id` on `agent_template_id`;
`ix_runs_started_at` on `started_at`; partial index
`ix_runs_trace_id` on `trace_id WHERE trace_id IS NOT NULL`.

The runs row is the rendering projection over the canonical audit
chain per D94 and D95's write-timing commitment. `invoke_agent`
yields the terminal event before calling `writer.record_run`, so
writer-failure post-yield leaves a missing-row condition
reconcilable from the audit chain via `audit_end_hash` rather than
collapsing the audit-versus-projection asymmetry into the
runtime's terminal-event contract. `InvocationFailed` events with
empty `partial_audit_chain_state` (pre-start-audit failure) skip
the writer call entirely so no runs row exists for invocations
with no audit evidence per D95.

### `run_chunk_citations`

| Column           | Type            | Constraints                                                                            |
|------------------|-----------------|----------------------------------------------------------------------------------------|
| `id`             | `uuid`          | primary key; default `gen_random_uuid()`                                               |
| `run_id`         | `uuid`          | not null; FK → `runs.id` ON DELETE CASCADE                                             |
| `chunk_id`       | `uuid`          | nullable; FK → `chunks.id` ON DELETE SET NULL (snapshot survives source removal per D94) |
| `tenant_id`      | `text`          | not null; CHECK `tenant_id <> ''`                                                      |
| `jurisdiction`   | `text`          | not null                                                                               |
| `chunk_excerpt`  | `text`          | not null; snapshot of chunk content for rendering per D96                              |
| `source_snapshot`| `jsonb`         | not null; default `'{}'::jsonb`; structured snapshot of source-level metadata available at retrieval time (Phase 1 carries `file_name` and `file_type`; grows additively with ingestion enrichment per D96) |
| `created_at`     | `timestamptz`   | not null; default `now()`                                                              |

Indices: `ix_run_chunk_citations_run_id` on `run_id`.

S32 revision per D96 (Alembic `0012_revise_citation_snapshots`):
drops `source_citation text NOT NULL` and adds `source_snapshot
jsonb NOT NULL DEFAULT '{}'::jsonb` so render shape (Harvard,
footnote, hover card, et al.) stays a Phase 2 read-time concern
over a structured input snapshot. Citation rows accumulate at
write time through `invoke_agent`'s within-run deduplication
(`(chunk_id, run_id)` first-seen-wins) and land alongside the
runs row within `async with session.begin()` per D96's single-
transaction multi-table write commitment.

### `run_entity_citations`

| Column                  | Type            | Constraints                                                                                                              |
|-------------------------|-----------------|--------------------------------------------------------------------------------------------------------------------------|
| `id`                    | `uuid`          | primary key; default `gen_random_uuid()`                                                                                 |
| `run_id`                | `uuid`          | not null; FK → `runs.id` ON DELETE CASCADE                                                                               |
| `entity_tenant_id`      | `text`          | not null; CHECK `entity_tenant_id <> ''`; matches Neo4j entity's `tenant_id` property per D63                            |
| `entity_name`           | `text`          | not null; matches Neo4j entity's `name` property                                                                          |
| `entity_type`           | `text`          | not null; matches Neo4j entity's `entity_type` property; free-form per D64                                                |
| `tenant_id`             | `text`          | not null; CHECK `tenant_id <> ''`; denormalised on the row per D22                                                       |
| `source_chunk_ids`      | `text[]`        | not null; default `'{}'::text[]`; snapshot of the Neo4j entity's `source_chunk_ids` array preserving provenance back to per-tenant Postgres chunks per D96 |
| `created_at`            | `timestamptz`   | not null; default `now()`                                                                                                |

Indices: `ix_run_entity_citations_run_id` on `run_id`.

The `(entity_tenant_id, entity_name, entity_type)` composite is
the join key back to the Neo4j entity per D64's uniqueness
commitment. No Postgres foreign key to Neo4j is possible; the
snapshot columns carry the rendering payload that survives entity
merge or removal per D94's audit-evidence claim.

S32 revision per D96 (Alembic `0012_revise_citation_snapshots`):
drops `entity_display_label text NOT NULL` (display label
synthesised from name plus type at render time) and adds
`source_chunk_ids text[] NOT NULL DEFAULT '{}'::text[]` so the
entity provenance trail back to per-tenant Postgres chunks is
load-bearing audit evidence rather than a pre-rendered display
field. The audit-evidence-fidelity claim from D94 holds for entity
provenance the same way it holds for chunk content. Citation rows
land within the same single transaction as the runs row per D96.

## Retrieval evaluation tables (per-tenant)

Substrate for `contexts/retrieval_evaluation/` per D109. The gold-set
aggregate root carries the tenant-authored named container; revisions
are append-only with status (draft or finalized) and hash-chain audit
on finalized revisions per D26 chain-self-containment; entries carry
an ordered chunk-id list encoding ranked relevance per D105.

### `gold_sets`

| Column                | Type            | Constraints                                                                                |
|-----------------------|-----------------|--------------------------------------------------------------------------------------------|
| `id`                  | `uuid`          | primary key; default `gen_random_uuid()`                                                   |
| `tenant_id`           | `uuid`          | not null; jurisdiction-bearing per D12; denormalised per D22                               |
| `jurisdiction`        | `text`          | not null; CHECK `jurisdiction <> ''`                                                       |
| `name`                | `text`          | not null                                                                                   |
| `created_by_user_id`  | `text`          | not null                                                                                   |
| `created_at`          | `timestamptz`   | not null; default `now()`                                                                  |
| `current_revision_id` | `uuid`          | nullable; FK → `gold_set_revisions.id` DEFERRABLE INITIALLY DEFERRED per the circular FK   |

`UNIQUE(tenant_id, name)` — `gold_sets_tenant_name_unique`. The
`current_revision_id` FK is deferrable so the create-gold-set use
case can insert the aggregate row plus the initial draft revision
row in a single transaction with the FK check fired at commit time
rather than at row-insert time.

### `gold_set_revisions`

| Column                | Type            | Constraints                                                                                |
|-----------------------|-----------------|--------------------------------------------------------------------------------------------|
| `id`                  | `uuid`          | primary key; default `gen_random_uuid()`                                                   |
| `gold_set_id`         | `uuid`          | not null; FK → `gold_sets.id` ON DELETE RESTRICT                                           |
| `revision_number`     | `integer`       | not null; monotonic per `gold_set_id` starting at 1                                        |
| `status`              | `text`          | not null; CHECK ∈ {`draft`, `finalized`}                                                   |
| `created_by_user_id`  | `text`          | not null                                                                                   |
| `created_at`          | `timestamptz`   | not null; default `now()`                                                                  |
| `finalized_at`        | `timestamptz`   | nullable; populated when status transitions to `finalized`                                 |
| `this_event_hash`     | `text`          | nullable; populated at finalization via `compute_revision_hash` per D109 commitment 4      |
| `previous_event_hash` | `text`          | nullable; `GENESIS_HASH` for revision_number=1 or the prior finalized revision's hash      |

`UNIQUE(gold_set_id, revision_number)` —
`gold_set_revisions_gold_set_revision_unique`. Finalized revisions
are immutable per D31 (no UPDATE path on rows where `status =
'finalized'`); the application layer enforces this; corrections land
as new draft revisions opened by `finalize_revision` or by the next
authoring action.

### `gold_set_entries`

| Column                  | Type            | Constraints                                                                                |
|-------------------------|-----------------|--------------------------------------------------------------------------------------------|
| `id`                    | `uuid`          | primary key; default `gen_random_uuid()`                                                   |
| `gold_set_revision_id`  | `uuid`          | not null; FK → `gold_set_revisions.id` ON DELETE RESTRICT                                  |
| `entry_index`           | `integer`       | not null; monotonic position within revision starting at 0                                 |
| `query`                 | `text`          | not null                                                                                   |
| `expected_chunk_ids`    | `uuid[]`        | not null; ordered array; order encodes ranked relevance per D105                           |

`UNIQUE(gold_set_revision_id, entry_index)` —
`gold_set_entries_revision_entry_unique`. The `expected_chunk_ids`
array references the per-tenant `chunks` table from
`contexts/ingestion/` per D109 commitment 3; no foreign key
constraint to `chunks.id` is enforced at the database level because
chunk lifecycle is independent of gold-set authoring (chunks may
delete or re-ingest while gold-set entries persist as historical
record). Recall@k, precision@k, and MRR computation at S40 handles
missing-chunk cases at metric-computation time.

Chain integrity verification reuses the audit context's primitive
shape per D109 commitment 4: the gold-set-revision payload (the
revision's canonical JSON shape with entries sorted by `entry_index`
and `expected_chunk_ids` rendered as lowercase canonical UUID
strings) feeds `compute_chained_payload_hash` from
`contexts/audit/domain/events.py` along with `previous_event_hash`;
the result is the row's `this_event_hash`. On-read verification
mirrors the S36 page-granularity verifier pattern: read the
revision and its entries, reconstruct the canonical payload,
recompute the hash, compare against the stored value.

## `contexts/retrieval_evaluation/` runner substrate (per-tenant database, P11 S40, D110)

Three additional tables on each tenant's dedicated Postgres data
plane per D32, capturing the retrieval-evaluation runner's
per-query records, per-strategy aggregates, and run-level
lifecycle. Tamper-evidence on these platform-computed records is
absorbed by the audit context at the event level per D110
commitment 7 (every write to the three tables emits an audit
event); no parallel hash chain on the runner records themselves.

### `evaluation_runs`

| Column                  | Type             | Constraints                                                                                |
|-------------------------|------------------|--------------------------------------------------------------------------------------------|
| `id`                    | `uuid`           | primary key; default `gen_random_uuid()`                                                   |
| `tenant_id`             | `uuid`           | not null; jurisdiction-bearing per D12                                                     |
| `jurisdiction`          | `text`           | not null                                                                                   |
| `gold_set_id`           | `uuid`           | not null; FK → `gold_sets.id` ON DELETE RESTRICT                                           |
| `gold_set_revision_id`  | `uuid`           | not null; FK → `gold_set_revisions.id` ON DELETE RESTRICT; the revision exercised          |
| `invoked_by_user_id`    | `text`           | not null                                                                                   |
| `invoked_at`            | `timestamptz`    | not null; default `now()`                                                                  |
| `completed_at`          | `timestamptz`    | nullable until status transitions to `completed` or `failed`                               |
| `status`                | `text`           | not null; CHECK constraint pins {`running`, `completed`, `failed`}                         |

The aggregate is mutable for status transitions per D110
commitment 2 (`running` → `completed` or `failed`); the child rows
in `evaluation_results` and `evaluation_aggregates` are append-only
and immutable.

### `evaluation_results`

| Column                  | Type             | Constraints                                                                                |
|-------------------------|------------------|--------------------------------------------------------------------------------------------|
| `id`                    | `uuid`           | primary key; default `gen_random_uuid()`                                                   |
| `evaluation_run_id`     | `uuid`           | not null; FK → `evaluation_runs.id` ON DELETE RESTRICT                                     |
| `gold_set_entry_id`     | `uuid`           | not null; FK → `gold_set_entries.id` ON DELETE RESTRICT                                    |
| `retrieval_strategy`    | `text`           | not null; canonical identifier per D110 commitment 6 (`vector_only`, `graph_only`)         |
| `returned_chunk_ids`    | `uuid[]`         | not null; ordered array; ranked by retrieval at runner time                                |
| `recall_at_k`           | `jsonb`          | not null; `{"1": float, "3": float, "5": float, "10": float}`                              |
| `precision_at_k`        | `jsonb`          | not null; same shape                                                                       |
| `mrr`                   | `numeric(6,4)`   | not null; 0.0000 to 1.0000                                                                 |
| `latency_ms`            | `integer`        | not null; wall-clock retrieval-client-invocation-start to result-return                    |

`UNIQUE(evaluation_run_id, gold_set_entry_id, retrieval_strategy)`
— `evaluation_results_run_entry_strategy_unique`. The
`returned_chunk_ids` array captures retrieval-time provenance; no
FK to `chunks.id` per the same lifecycle-independence reasoning
that applies to `gold_set_entries.expected_chunk_ids` at D109
commitment 3.

### `evaluation_aggregates`

| Column                  | Type             | Constraints                                                                                |
|-------------------------|------------------|--------------------------------------------------------------------------------------------|
| `id`                    | `uuid`           | primary key; default `gen_random_uuid()`                                                   |
| `evaluation_run_id`     | `uuid`           | not null; FK → `evaluation_runs.id` ON DELETE RESTRICT                                     |
| `retrieval_strategy`    | `text`           | not null; canonical identifier per D110 commitment 6                                       |
| `recall_at_k_mean`      | `jsonb`          | not null; mean across the run's per-query records for this strategy                        |
| `precision_at_k_mean`   | `jsonb`          | not null; same shape                                                                       |
| `mrr_mean`              | `numeric(6,4)`   | not null                                                                                   |
| `latency_ms_p50`        | `integer`        | not null                                                                                   |
| `latency_ms_p95`        | `integer`        | not null                                                                                   |
| `latency_ms_mean`       | `integer`        | not null                                                                                   |

`UNIQUE(evaluation_run_id, retrieval_strategy)` —
`evaluation_aggregates_run_strategy_unique`. Per-strategy aggregates
compute at run-completion time from the per-query
`evaluation_results` rows; the aggregation formula lives at
`contexts/retrieval_evaluation/domain/metrics.py` per D110
commitment 4 so on-read computation is unnecessary and the
aggregation surface is stable across reads. The runner produces
one aggregate row per executing strategy per the D110 commitment 6
strategy-set (two at S40: `vector_only`, `graph_only`; the
deferred `parallel_rrf` per `charter/deferred-decisions.md`
activates a third row when fusion implementation lands).

## Optimization tables (per-tenant)

Substrate for `contexts/optimization/` per D111. Two aggregate roots
(`OptimizationRun` and `Recommendation`) plus the
`recommendation_status_transitions` audit table. Tamper-evidence on
both aggregates is absorbed by the audit context at the event level
per D110 commitment 7's regime extended at D111 commitment 8;
every write to `optimization_runs` (insert + status transitions),
every write to `recommendations` (generation), and every row in
`recommendation_status_transitions` emits an audit event.

### `optimization_runs`

| Column                  | Type             | Constraints                                                                                |
|-------------------------|------------------|--------------------------------------------------------------------------------------------|
| `id`                    | `uuid`           | primary key; default `gen_random_uuid()`                                                   |
| `tenant_id`             | `uuid`           | not null; jurisdiction-bearing per D12                                                     |
| `jurisdiction`          | `text`           | not null; CHECK `jurisdiction <> ''`                                                       |
| `invoked_by_user_id`    | `text`           | not null                                                                                   |
| `invoked_at`            | `timestamptz`    | not null; default `now()`                                                                  |
| `completed_at`          | `timestamptz`    | nullable until status transitions to `completed` or `failed`                               |
| `status`                | `text`           | not null; CHECK constraint pins {`running`, `completed`, `failed`}                         |
| `skipped_categories`    | `jsonb`          | not null; default `'{}'::jsonb`; `{category: {reason_code, reason_text}}` per D111 cmt 2   |

The aggregate is mutable for status transitions per D111
commitment 2 (`running` → `completed` or `failed`); the engine
captures rule skip-reasons on `skipped_categories` at status-
transition time so the run's persisted snapshot carries the full
invocation context including which categories were skipped and
why. Phase 1 populates `skipped_categories` for `model_choice` and
`prompt_revision` since their substrate (scoring-sheet evaluation
runs from `contexts/evaluation/`) is Phase 2 territory.

### `recommendations`

| Column                          | Type             | Constraints                                                                                |
|---------------------------------|------------------|--------------------------------------------------------------------------------------------|
| `id`                            | `uuid`           | primary key; default `gen_random_uuid()`                                                   |
| `tenant_id`                     | `uuid`           | not null; jurisdiction-bearing per D12                                                     |
| `jurisdiction`                  | `text`           | not null; CHECK `jurisdiction <> ''`                                                       |
| `category`                      | `text`           | not null; CHECK ∈ {`retrieval_strategy`, `model_choice`, `prompt_revision`, `cost_optimization`} |
| `subject`                       | `text`           | not null                                                                                   |
| `text`                          | `text`           | not null                                                                                   |
| `evidence_citations`            | `jsonb`          | not null; discriminated union by category per D111 commitment 7                            |
| `status`                        | `text`           | not null; CHECK ∈ {`generated`, `acknowledged`, `applied`, `rejected`}                     |
| `generated_at`                  | `timestamptz`    | not null; default `now()`                                                                  |
| `generated_by_run_id`           | `uuid`           | not null; FK → `optimization_runs.id` ON DELETE RESTRICT                                   |
| `last_transition_at`            | `timestamptz`    | not null; default `now()`                                                                  |
| `last_transition_by_user_id`    | `text`           | nullable; populated when status transitions away from `generated`                          |

The aggregate is mutable for status transitions; `text` and
`evidence_citations` are append-only per D111 alternative (g) (no
UPDATE path on those columns; corrections happen as new
recommendations in a new optimization run). The
`last_transition_at` / `last_transition_by_user_id` fields mirror
the most-recent transition row in `recommendation_status_transitions`
for read-time convenience; the transitions table is canonical for
any audit drill-down.

Index `recommendations_tenant_status_category_idx` on `(tenant_id,
status, category)` supports list filtering at the read surface.

### `recommendation_status_transitions`

| Column                          | Type             | Constraints                                                                                |
|---------------------------------|------------------|--------------------------------------------------------------------------------------------|
| `id`                            | `uuid`           | primary key; default `gen_random_uuid()`                                                   |
| `recommendation_id`             | `uuid`           | not null; FK → `recommendations.id` ON DELETE RESTRICT                                     |
| `from_status`                   | `text`           | not null                                                                                   |
| `to_status`                     | `text`           | not null                                                                                   |
| `transitioned_by_user_id`       | `text`           | not null                                                                                   |
| `transitioned_at`               | `timestamptz`    | not null; default `now()`                                                                  |

Append-only; no UPDATE or DELETE on rows. Provides the full
status-history audit trail at the recommendation level without
mutating the parent aggregate's lifecycle fields. Index
`recommendation_status_transitions_recommendation_idx` on
`(recommendation_id, transitioned_at)` supports per-recommendation
chronological reads.

## Portfolio context substrate

Per-tenant substrate for `contexts/portfolio/` per D124. Three
tables on each tenant's dedicated Postgres data plane per D32,
landing the Phase 2-A Wave 1 foundational domain entities all
three product modes share: Case (the aggregate root), DataPoint
(an entity within the Case aggregate boundary), and Assertion
(the append-only revision unit). FK cascade runs Case → DataPoint
→ Assertion. Every table carries `tenant_id` and `jurisdiction`
per D12. Tamper-evidence follows D110 commitment 7: every write
through the application layer emits an audit event and the audit
context's hash chain transitively covers the portfolio records;
no parallel hash chain on these tables.

Migration `alembic/tenant/versions/0016_portfolio_substrate`
ships these tables on every per-tenant database.

### `cases`

| Column         | Type          | Constraints                                                |
|----------------|---------------|------------------------------------------------------------|
| `id`           | `uuid`        | primary key; default `gen_random_uuid()`                   |
| `tenant_id`    | `uuid`        | not null; jurisdiction-bearing per D12                     |
| `jurisdiction` | `text`        | not null; CHECK `jurisdiction <> ''`                       |
| `title`        | `text`        | not null; CHECK `title <> ''`                              |
| `case_type`    | `text`        | not null; CHECK ∈ {`PORTFOLIO_ITEM`}                       |
| `status`       | `text`        | not null; CHECK ∈ {`OPEN`, `CLOSED`, `ARCHIVED`}           |
| `created_at`   | `timestamptz` | not null; default `now()`                                  |
| `updated_at`   | `timestamptz` | not null; default `now()`; advances on status transitions  |

The aggregate root. `case_type` carries the single Phase 2-A
value `PORTFOLIO_ITEM`; the CHECK accepts that value only at S43
and widens as new case types land. `status` is mutable — OPEN →
CLOSED or OPEN → ARCHIVED — and `updated_at` advances on each
transition; per the "Originals never erased" principle a Case is
archived, never deleted, in normal operation. Index
`ix_cases_tenant_status` on `(tenant_id, status)` and
`ix_cases_tenant_created_at` on `(tenant_id, created_at DESC)`
support the list surface.

### `data_points`

| Column                | Type               | Constraints                                                      |
|-----------------------|--------------------|------------------------------------------------------------------|
| `id`                  | `uuid`             | primary key; default `gen_random_uuid()`                         |
| `case_id`             | `uuid`             | not null; FK → `cases.id` ON DELETE CASCADE                      |
| `tenant_id`           | `uuid`             | not null; jurisdiction-bearing per D12                           |
| `jurisdiction`        | `text`             | not null; CHECK `jurisdiction <> ''`                             |
| `data_point_type`     | `text`             | not null; CHECK ∈ {`GOAL`, `STATUS`, `METHODOLOGY_APPLICATION`}  |
| `value`               | `jsonb`            | not null; the structured payload at DataPoint creation           |
| `authored_by_user_id` | `text`             | not null; CHECK `<> ''`; ActorReference placeholder per D124     |
| `certainty`           | `double precision` | nullable; CHECK `certainty >= 0 AND certainty <= 1`; D117 reserve |
| `created_at`          | `timestamptz`      | not null; default `now()`                                        |

An entity within the Case aggregate. `value` is the structured
payload captured at DataPoint creation; the current state is the
latest Assertion in the revision history (Revisable Protocol per
D125). `certainty` is nullable and unset at Phase 2-A — the
column lands now so the D117 tiered-by-salience implementation at
P15 is a pure write-path addition. `authored_by_user_id` persists
the `ActorReference` placeholder. Index `ix_data_points_case_id`
on `(case_id)` and `ix_data_points_tenant_id` on `(tenant_id)`.

### `assertions`

| Column                 | Type          | Constraints                                                  |
|------------------------|---------------|--------------------------------------------------------------|
| `id`                   | `uuid`        | primary key; default `gen_random_uuid()`                     |
| `data_point_id`        | `uuid`        | not null; FK → `data_points.id` ON DELETE CASCADE            |
| `tenant_id`            | `uuid`        | not null; jurisdiction-bearing per D12                       |
| `jurisdiction`         | `text`        | not null; CHECK `jurisdiction <> ''`                         |
| `assertion_type`       | `text`        | not null; CHECK ∈ {`INITIAL`, `REVISION`}                    |
| `revises_assertion_id` | `uuid`        | nullable; FK → `assertions.id` ON DELETE RESTRICT            |
| `value`                | `jsonb`       | not null; the revision payload                               |
| `authored_by_user_id`  | `text`        | not null; CHECK `<> ''`; ActorReference placeholder per D124  |
| `created_at`           | `timestamptz` | not null; default `now()`                                    |

The append-only revision unit implementing the Revisable
Protocol's revision-history surface. Each DataPoint opens with
one `INITIAL` assertion; every `revise` call appends a `REVISION`
assertion. A pairing CHECK `assertions_type_revises_pairing_check`
pins the shape: an `INITIAL` assertion has `revises_assertion_id`
null; a `REVISION` assertion has it not null (the self-referential
FK points at the prior assertion in the chain). Assertions are
never updated or deleted. Index
`ix_assertions_data_point_created_at` on `(data_point_id,
created_at)` orders revision history; `ix_assertions_tenant_id`
on `(tenant_id)`.

## Cross-cutting binding shapes

This section formalises non-table binding shapes — value objects,
HTTP-layer DTOs, application-layer codecs — that cross multiple
bounded contexts and ship to procurement-grade consumer surfaces.
The shapes exist in code; this section gives them a place on the
binding-specification surface. The section's audit-trail role is
the same as the database-table sections above: schema diffs at
commit time reconcile against this surface for cross-cutting
shape additions just as they do for table additions.

### TenantContext (shared-kernel value object)

The frozen value object carried via auth-middleware extraction
per D34's credential-encryption integration and D50's
TenantContext shape commitment. It cross-cuts every per-tenant
context — the inference adapter and the audit adapter both
consume TenantContext-shaped values — which is why it lives in
`shared_kernel/tenant_context.py` rather than in any single
context.

| Field                 | Type  | Constraints                                                                  |
|-----------------------|-------|------------------------------------------------------------------------------|
| `tenant_id`           | `str` | not null; non-empty; UUID-shaped per registry resolution; primary identifier |
| `jurisdiction`        | `str` | not null; non-empty                                                          |
| `cost_attribution_id` | `str` | not null; non-empty; D41 cost-attribution surface                            |

The shape is a frozen dataclass: Pydantic is forbidden in
`shared_kernel/` by the import-linter `shared-kernel-policed`
contract per D16, and the `Tenant` aggregate's `frozen=True`
precedent makes the choice consistent with the rest of the
domain. `__post_init__` enforces the non-empty invariant on all
three fields. The object propagates via the auth middleware's
principal-derived extraction pattern per D98.

### ErrorResponse (HTTP-layer DTO)

The Pydantic model rendered by the OpenAPI specification as the
canonical error wire format across HTTP error paths per the D98
narrative. Lives at `apps/api/_errors.py`. Structurally
consistent across the S34, S37, S38, and S42 HTTP transports.

| Field            | Type   | Constraints                                                                                        |
|------------------|--------|----------------------------------------------------------------------------------------------------|
| `error_code`     | `str`  | not null; machine-readable discriminator across error paths; canonical identifier per route family |
| `message`        | `str`  | not null; human-readable error message                                                             |
| `correlation_id` | `str`  | not null; UUID4-shaped; propagated from request context for cross-system tracing                   |
| `details`        | `dict` | nullable; default null; per-error-code structured detail payload (field-level validation errors)   |

The `error_code` field is the machine-readable discriminator
that distinguishes error families and is canonical per route
family; the model itself is a flat `BaseModel`, not a Pydantic
discriminated union. HTTP contract tests at
`tests/contract/http/` enforce error-response shape consistency
per S42.

### Canonical cursor codec (application-layer pagination)

The base64-encoded-JSON codec for paged-list cursors, the S33
vintage per D97. Four implementing sites carry a structurally
identical shape: a URL-safe base64 envelope over compact JSON,
with decode raising `MalformedCursorError` on base64, JSON,
schema, type, or range errors. Module naming carries a
hygiene-tolerated drift — three sites use the singular
`cursor.py` and one (`contexts/optimization/`) uses the plural
`cursors.py` — flagged at P12 audit Finding B5 with a non-action
disposition.

| Module path                                           | Originating session |
|-------------------------------------------------------|---------------------|
| `contexts/run_history/application/cursor.py`          | S33                 |
| `contexts/audit/application/cursor.py`                | S36                 |
| `contexts/retrieval_evaluation/application/cursor.py` | S39 (P11)           |
| `contexts/optimization/application/cursors.py`        | S41 (P11)           |

The cursor payload carries the cursor-position identifier — a
timestamp field plus the row `id` — plus `page_size`; the
encoded string is opaque to consumers, who receive it at
`next_cursor` time and pass it back verbatim on the next
request. The codec is application-layer: it is imported by the
HTTP read surface but defined inside each context's
`application/` package alongside the use cases it serves.

### Revisable Protocol (cross-context behavioural contract)

This sub-section formalises a *Protocol shape* — a behavioural
contract — rather than a value-object schema; the field-table
style of the three sub-sections above does not apply. Per D125,
`Revisable` is the cross-context standard interface for entities
that carry an append-only revision history (the D114
revision-with-lineage primitive). It lives at
`shared_kernel/revisable.py` as a generic `Protocol`:

```python
class Revisable(Protocol[RevisionT]):
    def revise(
        self, change: AssertionChange, actor: ActorReference
    ) -> "Revisable[RevisionT]": ...

    def revision_history(self) -> list[RevisionT]: ...
```

Contract semantics: `revise` appends a new revision rather than
overwriting — it returns a `Revisable` carrying the extended
history; the latest revision is the entity's current state;
`revision_history` returns the full revision list in
chronological order. The protocol is generic over `RevisionT` so
it imports no bounded-context type — `shared_kernel/` cannot
import `contexts/` per D16. `contexts/portfolio/`'s `DataPoint`
implements `Revisable[Assertion]` at S43; methodology-application
revision and Case-level revision are future implementers.
Conformance is CI-enforceable via contract tests per D114.

### AssertionChange (revision-input value object)

The value object passed to `Revisable.revise` describing the
change to apply. Lives at `shared_kernel/revisable.py` alongside
the protocol. Frozen dataclass, framework-free per D16.

| Field   | Type   | Constraints                                          |
|---------|--------|------------------------------------------------------|
| `value` | `dict` | not null; the structured payload of the new revision |

`revise` consumes an `AssertionChange` plus an `ActorReference`
and appends an `Assertion` carrying the change's `value`,
`assertion_type = REVISION`, and `revises_assertion_id` pointing
at the prior head of the revision chain.

