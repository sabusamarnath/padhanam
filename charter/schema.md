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

### `:Outcome` nodes (S62, D163)

The typed goal layer of the whole-life goal taxonomy (D163). An Outcome is a
goal the daily driver holds; its lever is a Commitment (per-tenant Postgres
`commitments` table), connected by a `LEVER_FOR` edge. Reached only through the
`TenantScopedNeo4jSession` wrapper (the `OutcomeGraphPort` methods); no Alembic
migration — the goal is a graph node and the lever reuses the existing
`commitments` row. Lands via `migrations/neo4j/0002_outcome_goal.cypher`.

Per the **D163 clarification (S63)**, the goal-level properties — `mode`, the
`ladder`, and `current_target_level` — live on the `:Outcome` node, not the
`LEVER_FOR` edge: a goal has one mode and one target and may have many levers.
The S62 schema placed them on the edge; `migrations/neo4j/0003_outcome_props_to_node.cypher`
moves any existing instance (German) in place under the D165 mechanism.

| Property               | Type            | Notes                                                                  |
|------------------------|-----------------|-----------------------------------------------------------------------|
| `tenant_id`            | `String`        | not empty; tenant-isolation predicate at every Cypher query           |
| `jurisdiction`         | `String`        | first-class per D12                                                    |
| `outcome_id`           | `String`        | the goal's UUID                                                        |
| `name`                 | `String`        | the goal's human-readable label (e.g. "German")                       |
| `control`              | `String`        | `self` (actor's levers determine) or `other` (actor only influences)  |
| `subject`              | `String`        | `self` or `other` (whose goal it is)                                   |
| `mode`                 | `String`        | `homeostatic` / `progressive` / `sequence`                            |
| `ladder`               | `List<String>`  | ordered named levels for a progressive goal; empty otherwise          |
| `current_target_level` | `String`/`null` | the level a progressive goal currently aims at; `null` otherwise      |
| `terminal_target`      | `String`/`null` | a sequence goal's terminal — the goal reached once (e.g. "Offer accepted"); `null` otherwise |
| `terminal_state`       | `String`/`null` | `pending` / `reached` for a sequence goal's terminal; `null` otherwise. `pending` is the influence-gated part (another party decides); richer reading deferred to the influence instance |
| `created_at`           | `DateTime`      | set on initial MERGE                                                   |
| `archived_at`          | `DateTime`/absent | set when the user archives the goal (S103e, D205); absent on an active goal. The **reversible archive marker** — `list_outcomes` scopes to `archived_at IS NULL`, so an archived goal drops out of the assess surface and the matcher (both read active goals via `list_goals`) **without being deleted**: the node, its authored CDD elements, its `EVIDENCES` binds and audit history all stay intact. Removed by `unarchive_outcome`, returning the goal whole. Honors the no-auto-deletion invariant (4) + originals-never-erased: a user-initiated removal marks, never erases |

Uniqueness constraint: `outcome_unique_per_tenant` on `(tenant_id, outcome_id)`.
`current_target_level` changes only via `set_outcome_target` (the explicit
raise, never automatic — D9, the no-auto-modification invariant). `archived_at`
is set/removed only via `archive_outcome` / `unarchive_outcome` (S103e, D205) —
a schemaless property, **no migration** (the S102/S103a schemaless-prop
precedent); a never-archived goal simply lacks the property.

The `:Outcome` also carries the precision pass's **disposition counts** (S103i/D210)
— `disposition_moat` (confirmed job emails), `disposition_pipeline` (one-touch acks
routed to Pipeline-depth), `disposition_market` (board listings routed to the
Labor-market external), `disposition_parked` (un-bound by the genuine-match bar).
Set each correlate by `set_outcome_disposition` (derived state, D155), read by the
CDD lens for the Map's recommendation-shaped summary. Schemaless, **no migration**;
absent until the first correlate.

### `:Lever` nodes (S62, D163)

A thin *reference* to the Commitment that serves as a goal's lever — it carries
only the `commitment_id`, never a copy of the Postgres row (D163 Step 0 F3,
no-duplication).

| Property        | Type       | Notes                                                       |
|-----------------|------------|-------------------------------------------------------------|
| `tenant_id`     | `String`   | not empty; matches the Outcome's tenant                     |
| `jurisdiction`  | `String`   | first-class per D12                                         |
| `commitment_id` | `String`   | the Postgres `commitments.id` UUID this lever references    |
| `created_at`    | `DateTime` | set on initial MERGE                                        |

Uniqueness constraint: `lever_unique_per_tenant` on `(tenant_id, commitment_id)`.

### `LEVER_FOR` edge (S62, D163; goal-level props moved off at S63)

`(:Lever)-[:LEVER_FOR]->(:Outcome)`. Per the D163 clarification (S63) the edge
carries only **that** a lever serves the outcome — goal-level properties (mode,
ladder, current target) moved to the `:Outcome` node. The edge does carry the
lever's own **relationship-level** attributes for a sequence goal: `step_order`
and `step_state` describe how a particular lever serves the outcome (a sequence
has many ordered, individually-stateful steps), which is genuinely edge-level,
not goal-level. These are absent (`null`) for a single-lever progressive goal.

| Property      | Type            | Notes                                                                       |
|---------------|-----------------|-----------------------------------------------------------------------------|
| `tenant_id`   | `String`        | not empty; matches both endpoints                                           |
| `jurisdiction`| `String`        | matches both endpoints                                                      |
| `step_order`  | `Integer`/`null`| 1-based position in a sequence goal's lever chain; `null` for progressive   |
| `step_state`  | `String`/`null` | `ready` / `blocked` / `done` / `dropped` for a sequence step; `null` otherwise |
| `created_at`  | `DateTime`      | set on initial MERGE                                                        |

Uniqueness via the MERGE pattern keyed on `(tenant_id, commitment_id, outcome_id)`
(Community Edition has no declarative relationship-property uniqueness).

### `:Unit` nodes (S66, D168)

The anchor of a *unit of work* (D166): one thing seen from up to four facets. A
Unit is a Padhanam-native node correlated from the read-only caches — it is
*derived state* (D155), recomputed from the caches on each correlation run, never
written back to any source tool. Unit identity is deterministic
(`uuid5(tenant + anchor facet)`, anchor priority task > meeting > email) so
re-correlation is idempotent and the id stays stable for P19's goal facet. The
goal facet (a `LEVER_FOR`-style edge from a `:Unit` to an `:Outcome`) is P19;
P18 lands the first three facets.

| Property       | Type       | Notes                                                       |
|----------------|------------|-------------------------------------------------------------|
| `tenant_id`    | `String`   | not empty; D63/D64 property scoping                         |
| `jurisdiction` | `String`   | first-class per D12                                         |
| `unit_id`      | `String`   | deterministic `uuid5(tenant + anchor facet)`               |
| `created_at`   | `DateTime` | set on initial MERGE                                        |

Uniqueness constraint: `unit_unique_per_tenant` on `(tenant_id, unit_id)`.

### `:Facet` nodes (S66, D168)

A thin *reference* to a row in a read-only ingested cache — it carries only the
facet's type + id, never a copy of the cache row (the D164 thin-reference rule,
mirroring `:Lever`). `facet_type ∈ {task, meeting, email}` referencing the
Postgres `tasks.id` / `meetings.id` / `emails.id` UUID respectively.

| Property       | Type       | Notes                                                       |
|----------------|------------|-------------------------------------------------------------|
| `tenant_id`    | `String`   | not empty; matches the Unit's tenant                        |
| `jurisdiction` | `String`   | first-class per D12                                         |
| `facet_type`   | `String`   | `task` / `meeting` / `email`                                |
| `facet_id`     | `String`   | the referenced cache row's UUID                             |
| `created_at`   | `DateTime` | set on initial MERGE                                        |

Uniqueness constraint: `facet_unique_per_tenant` on `(tenant_id, facet_type, facet_id)`.

### `SAME_WORK` edge (S66, D168)

`(:Facet)-[:SAME_WORK]->(:Unit)`. The Padhanam-native correlation edge (D166):
this facet is part of this unit of work. The anchor facet links with
`status=confirmed, confidence=1.0`; additional facets carry the title-and-time
inference's confidence — `confirmed` at/above the floor, `candidate` below
(surfaced, not auto-linked). `basis` records the inference used.

| Property      | Type      | Notes                                                                  |
|---------------|-----------|------------------------------------------------------------------------|
| `tenant_id`   | `String`  | not empty; matches both endpoints                                      |
| `jurisdiction`| `String`  | matches both endpoints                                                 |
| `confidence`  | `Float`   | 0.0–1.0 inference confidence; `1.0` for the anchor                     |
| `status`      | `String`  | `confirmed` (auto-linked) / `candidate` (surfaced, below floor)        |
| `basis`       | `String`  | the inference basis, e.g. `anchor` / `title+time` / `title`           |
| `created_at`  | `DateTime`| set on initial MERGE                                                   |

Uniqueness via the MERGE pattern keyed on `(tenant_id, facet_type, facet_id, unit_id)`
(Community Edition has no declarative relationship-property uniqueness). The whole
`:Unit`/`:Facet`/`SAME_WORK` subgraph for a tenant is replaced on each correlation
run (derived state), so stale links and orphaned units do not accumulate.

### `SERVES` edge (S67, D169)

`(:Unit)-[:SERVES]->(:Outcome)`. The Padhanam-native **goal facet** of a unit of
work (D166's fourth facet): this unit serves this goal. The inference is
confidence-tiered (D169): a `confirmed` edge is a unit-facet title match against
one of the goal's lever-commitment names (the precise commitment bridge); a
`candidate` edge is a lean title-keyword match against the goal's name (recall,
surfaced recommendation-shaped). No new node label — the edge connects existing
`:Unit` (S66) and `:Outcome` (S62) nodes, so **no Neo4j migration** (the
`LEVER_FOR` precedent); idempotency comes from the MERGE pattern plus the
per-tenant replace-on-correlate.

| Property      | Type      | Notes                                                              |
|---------------|-----------|-------------------------------------------------------------------|
| `tenant_id`   | `String`  | not empty; matches both endpoints                                 |
| `jurisdiction`| `String`  | matches both endpoints                                            |
| `confidence`  | `Float`   | 0.0–1.0 inference confidence                                      |
| `status`      | `String`  | `confirmed` (commitment-bridge) / `candidate` (goal-name keyword) |
| `basis`       | `String`  | the inference basis, e.g. `commitment` / `goal-name`             |
| `created_at`  | `DateTime`| set on initial MERGE                                              |

Uniqueness via the MERGE pattern keyed on `(tenant_id, unit_id, outcome_id)`. The
tenant's `SERVES` edges are replaced on each correlation run (derived state). The
two reads are computed from the unit set, the outcome set, and these edges:
**orphan work** = a `:Unit` with no outgoing `SERVES`; **neglected goal** = an
`:Outcome` with no incoming `SERVES`.

### The authored CDD layer (S102, D200)

The per-goal Causal Decision Diagram is **authored**, not only derived (the
"graph's meaning is authored" principle, D200). The LLM drafts each goal's causal
structure — its levers, intermediaries, externals, and expected outcome — and the
user proofs it. This is distinct from the matcher's derived `SERVES`/`LEVER_FOR`
layer: the authored layer carries per-goal *meaning* (what each element is *for
this goal*), and every authored element carries a **provenance origin** and a
**proof state**. The goal-and-outcome node reuses `:Outcome` (D199's two faces, the
aim `name` and the measurable `mode`/`ladder`/`current_target_level`/
`terminal_target`, already sit on one node). Two new node types land —
`:Intermediary` and `:External` (the intermediary layer is the uniformly-absent
layer S101 rendered as a broken link; the external is the inbound the user did not
initiate, D198). Lands via `migrations/neo4j/0005_authored_cdd.cypher`. Matcher
untouched (S102 scope); the matcher rewrite from goal-linking to element-evidence
is S103.

**Provenance origin** (every authored element) is drawn from exactly three values:
`llm_drafted`, `user_authored`, `system_suggested`. D200 makes origin first-class
optimization signal, so it is present from the first migration. **Proof state** is
`pending` or `accepted`; a rejected element is **removed** (user-initiated
rejection is a delete the user asked for — allowed under the no-auto-deletion
posture, which forbids *auto*-deletion, not user-initiated removal).

#### `:Intermediary` nodes (S102, D200)

An authored intermediary factor between the levers/externals and the outcome.

| Property            | Type            | Notes                                                              |
|---------------------|-----------------|--------------------------------------------------------------------|
| `tenant_id`         | `String`        | not empty; tenant-isolation predicate at every Cypher query        |
| `jurisdiction`      | `String`        | first-class per D12                                                 |
| `element_id`        | `String`        | the intermediary's UUID (identity)                                 |
| `outcome_id`        | `String`        | the goal whose CDD this element belongs to (the authored scope)    |
| `label`             | `String`        | short human-readable label (LLM-drafted or user-authored)          |
| `provenance_origin` | `String`        | `llm_drafted` / `user_authored` / `system_suggested`               |
| `proof_state`       | `String`        | `pending` / `accepted`                                             |
| `created_at`        | `DateTime`      | set on initial MERGE                                                |

Uniqueness constraint: `intermediary_unique_per_tenant` on `(tenant_id, element_id)`; index `intermediary_tenant_id` on `tenant_id`.

#### `:External` nodes (S102, D200)

An authored external factor — another party's action that influences an
intermediary or the outcome (the inbound the user did not initiate, D198). Same
shape as `:Intermediary`. Uniqueness constraint: `external_unique_per_tenant` on
`(tenant_id, element_id)`; index `external_tenant_id` on `tenant_id`.

#### `:MeasurableOutcome` nodes (S103k, D211)

An authored **measurable outcome** — a measurable result that tells you whether the
goal is met, sitting between the intermediaries and the goal node (Pratt's
goal-versus-outcome separation). Introduced because the model had no outcome layer:
the goal `:Outcome` node *was* the only outcome, so the intermediaries fed the goal
directly and read as endpoints (D211 corrects this; it supersedes slice one's single
bundled outcome). A new node label rather than a reuse of `:Outcome`, because
`:MeasurableOutcome` is keyed by `element_id` (like `:Intermediary`/`:External`)
while the goal `:Outcome` is keyed by `outcome_id` — sharing the label would collide
with every `:Outcome {outcome_id}` match. The element kind string is
`measurable_outcome` (distinct from the `outcome` *endpoint* kind, which still
resolves to the goal node). Intermediaries `FEEDS` a `:MeasurableOutcome`; a
`:MeasurableOutcome` `FEEDS` the goal `:Outcome`. A new bindable target: the matcher
and the genuine-match bar (D209) govern its binds, so outcomes are lightly evidenced
until real offers arrive (honest, not broken). Same property shape as
`:Intermediary` (`element_id` identity, `outcome_id` scope, `label`,
`provenance_origin`, `proof_state`, optional `gate_id`). Lands via
`migrations/neo4j/0009_measurable_outcome.cypher`. Uniqueness constraint:
`measurable_outcome_unique_per_tenant` on `(tenant_id, element_id)`; index
`measurable_outcome_tenant_id` on `tenant_id`.

#### `:Gate` nodes (S103g, D207) — the process flow

A first-class process-flow gate. The framework's process layer (D198) is built as
gates: a gate is a portal into its **local CDD**, and the gate node is that CDD's
**local-outcome endpoint** (an intermediary `FEEDS` the gate, parallel to how an
intermediary `FEEDS` the `:Outcome` for the goal). Gates are a **new flow**
referencing the D163 lever-steps where one corresponds — they do not replace the
steps (the steps stay as the goal's sequence-status, D163). Lands via
`migrations/neo4j/0007_process_gates.cypher`.

| Property             | Type            | Notes                                                              |
|----------------------|-----------------|--------------------------------------------------------------------|
| `tenant_id`          | `String`        | not empty; tenant-isolation predicate at every Cypher query        |
| `jurisdiction`       | `String`        | first-class per D12                                                 |
| `gate_id`            | `String`        | the gate's UUID (identity)                                          |
| `outcome_id`         | `String`        | the goal whose flow this gate belongs to                           |
| `name`               | `String`        | the gate name (e.g. "Apply", "Screening")                          |
| `gate_order`         | `Integer`       | the gate's position in the flow sequence                           |
| `local_outcome`      | `String`        | the gate's local outcome — the CDD's measurable terminal           |
| `local_goal`         | `String`        | the gate's local goal (the decision's aim)                         |
| `provenance_origin`  | `String`        | `llm_drafted` / `user_authored` / `system_suggested`               |
| `proof_state`        | `String`        | `pending` / `accepted`                                             |
| `step_commitment_id` | `String`/absent | the D163 lever-step this gate references, or absent (e.g. Screening has no step) |
| `created_at`         | `DateTime`      | set on initial MERGE                                                |

Uniqueness constraint: `gate_unique_per_tenant` on `(tenant_id, gate_id)` (the
0005 authored-node pattern).

**The Lead gate (S103t, D221).** A **Lead gate** (`gate_order` 2, below Apply=3,
Screening=4) is the origination stage: the flow ladder now reads Lead → Apply →
Screening. A **new lead** is a `user_authored` `:Opportunity` positioned at the
Lead gate with zero touches and no correspondence thread (§2 origination, the
framework's portfolio layer). The Lead gate is seeded via the existing
`merge_gate` (idempotent MERGE — the 0007 `gate_unique_per_tenant` constraint
already covers it, **no migration**), `llm_drafted`/`pending` like Apply and
Screening. Its local CDD is not authored this session (out of scope); the fit
rubric that governs origination is a **goal-level** lever feeding Pipeline depth
(the portfolio altitude), not a Lead-gate-local element.

#### `:Opportunity` nodes (S103h, D208) — process instances / Flow items

An opportunity (one company/role) is a first-class **process instance** — a Flow
item per D198, not a CDD node. It belongs to the goal by `outcome_id`, is
positioned at its furthest-evidenced gate by `current_gate_id` (operator-
correctable), and groups its units by a `(:Unit)-[:BELONGS_TO]->(:Opportunity)`
edge. A clustered unit's gate-element binds read **per opportunity** (the
`EVIDENCES` read `OPTIONAL MATCH`es the unit's `BELONGS_TO`), so a gate element's
evidence distributes across opportunities plus an honest unclustered residual
(D171). Lands via `migrations/neo4j/0008_process_instances.cypher`.

| Property            | Type            | Notes                                                              |
|---------------------|-----------------|--------------------------------------------------------------------|
| `tenant_id`         | `String`        | not empty; tenant-isolation predicate at every Cypher query        |
| `jurisdiction`      | `String`        | first-class per D12                                                 |
| `opportunity_id`    | `String`        | the opportunity's UUID (identity)                                  |
| `outcome_id`        | `String`        | the goal this opportunity belongs to                              |
| `name`              | `String`        | the opportunity name (company/role, e.g. "Acme")                 |
| `current_gate_id`   | `String`/`null` | the furthest gate the opportunity's units evidence; operator-correctable |
| `provenance_origin` | `String`        | `system_suggested` at instantiation, `user_authored` once the operator confirms (D200) |
| `proof_state`       | `String`        | `pending` / `accepted`                                            |
| `source`            | `String`/`null` | the clustering signature (e.g. the company domain, S103o/D215). **Not** the origination channel — see `origination_source` |
| `fit_tier`          | `String`/`null` | (S103t, D221) the operator-set fit tier of a lead: `bullseye` / `strong` / `opportunistic` (below-tier is not originated). Set on a `user_authored` lead; `null` on opportunities that entered via clustering. Read by the origination Lead column's primary sort |
| `warm_access_available` | `String`/`null` | (S103t, D221) whether the lead has a warm path: `warm` / `cold`. The Lead column's secondary sort. With `fit_tier` it drives the fit-times-warm origination rule (D221) |
| `origination_source` | `String`/`null` | (S103t, D221) the origination channel: `inbound` / `outbound` (framework §2). Named `origination_source`, **not** `source`, because `source` already holds the D215 clustering signature |
| `status`            | `String`        | `live` or `closed` (S103n, D214). Absent on opportunities created before D214; the read coalesces a missing value to `live`, so the live-set filter needs no backfill. Closing sets `closed`; reopen sets `live` |
| `closed_reason`     | `String`/`null` | required when `closed` (S103n, D214): one of `won`, `declined`, `withdrawn_or_killed`, `rejected`, `went_cold`. `null` when live. With `current_gate_id` it gives the real-outcome-versus-non-start signal (closed at Apply = response problem; closed after a final round = conversion problem) |
| `closed_at`         | `DateTime`/`null` | when the opportunity was closed (S103n, D214); cleared on reopen |
| `created_at`        | `DateTime`      | set on initial MERGE                                               |

Uniqueness constraint: `opportunity_unique_per_tenant` on `(tenant_id,
opportunity_id)`. The `BELONGS_TO` edge carries `tenant_id` + `jurisdiction`, has a
range index `belongs_to_tenant_id` on `tenant_id`, and is idempotent via the MERGE
pattern (no relationship-property uniqueness in Community Edition). Units matching
no confirmed opportunity stay unclustered (no `BELONGS_TO`), reading
`opportunity_id = null` in the evidence — the honest residual, never neglect.

The **closed state** (S103n, D214) is a **schemaless property add** — no new label and
no property-existence constraint in Community Edition, so **no migration** (the
`:Outcome.archived_at` / S103j disposition precedent). Closing is **archive-not-erase**
(D114, invariant 4): `status`/`closed_reason`/`closed_at` are set, but the
opportunity node, its `BELONGS_TO` memberships, its units' binds, and its
correspondence all stay intact and reopenable — a closed process is read-only
history, never deleted. The live set is the read filtered to `coalesce(status,
'live') <> 'closed'`; closed opportunities still list, marked with their reason.

**Leads and origination (S103t, D221).** A **lead** is a `user_authored`
opportunity at the Lead gate with zero touches, carrying `fit_tier`,
`warm_access_available`, `origination_source`. It is created directly (the
create-lead path reuses `merge_opportunity`, provenance `user_authored`,
`current_gate_id` = the Lead gate, `status` `live`, no `BELONGS_TO` units) and
advanced to Apply by `set_opportunity_gate` (the apply-advance, the S103q `/stage`
write). Because a lead is origination and not yet an application, the pipeline
projection (`build_pipeline_stats`, D217) **partitions leads out** of the
engaged/applied split, the depth ladder, and the cards, surfacing them in a
dedicated leads bucket the origination Lead column renders (fit-tier primary,
warm-access secondary). Once advanced to Apply it is an ordinary process and every
downstream surface reads it unchanged. The three properties are **schemaless adds**
(the D214 precedent, read coalesces missing values), **no migration**.

#### `:Contact` nodes (S103u, D222) — the contact graph behind warm access

A **contact** is a person in the operator's network. `:Contact` is **tenant-scoped**
(a person, not a goal), keyed by `contact_id`, and **links to a company** by a
**normalized company string** — the S103o/D215 company-signature precedent, not a
`:Company` node (the model has none; `:Opportunity` carries its company as free text
in `name`). A lead reads its contacts by matching its company (its `name` before
`" — "`) against `:Contact.company`, normalized (lower-cased, trimmed). Lands via
`migrations/neo4j/0010_contact.cypher` (the 0009 `:MeasurableOutcome` precedent — a
uniqueness constraint on `(tenant_id, contact_id)` + a `tenant_id` index).

| Property             | Type            | Notes                                                              |
|----------------------|-----------------|--------------------------------------------------------------------|
| `tenant_id`          | `String`        | not empty; tenant-isolation predicate at every Cypher query        |
| `jurisdiction`       | `String`        | first-class per D12                                                 |
| `contact_id`         | `String`        | the contact's UUID (identity)                                       |
| `name`               | `String`        | the person's name (from the email display name, or operator-set)   |
| `email`              | `String`/`null` | the sender address a moat-seeded contact was extracted from (dedup key on seed); `null` for a hand-added contact |
| `company`            | `String`/`null` | the company, normalized-matched to a lead's company. Derived from the sender's real domain on seed (title-cased second-level label), `null` for a free-domain sender the operator fills |
| `degree`             | `String`/`null` | operator-set: `first` / `second`. `null` until proofed (the operator authors it, D200) |
| `strength`           | `String`/`null` | operator-set: `close` / `medium` / `weak`. `null` until proofed |
| `reachability`       | `String`/`null` | operator-set: `easy` / `hard`. `null` until proofed |
| `capture_source`     | `String`        | the capture channel: `email` (moat-seeded) / `linkedin` (manually tagged now, bulk via the S103v file adapter) / `manual` (hand-added). Named `capture_source`, **not** `source` — distinct from a lead's `origination_source` (D221) and the D215 clustering signature; lets a lead's contacts carry where each came from |
| `provenance_origin`  | `String`        | `system_suggested` on seed, `user_authored` once the operator confirms or hand-adds (D215/D200) |
| `created_at`         | `DateTime`      | set on initial MERGE                                                |

Uniqueness constraint: `contact_unique_per_tenant` on `(tenant_id, contact_id)`
(the 0009 pattern). Seeding reads the moat senders **read-only** from the encrypted
email store (D21/D148/D151 — extraction never fetches or writes) and instantiates
`system_suggested` contacts; the operator proofs (confirm → `user_authored`, enrich
`degree`/`strength`/`reachability`, or reject → delete). A contact is **usable** for
warm access when `strength in {close, medium}` or `reachability = easy` (a
`weak`+`hard` contact offers no path).

**`warm_access_available` on a lead is a derived read with a manual override
(S103u, D222).** A lead reads **warm** when at least one usable contact links to its
company, **cold** otherwise — a read-side projection, recomputed never stored
(D155). The S103t manual tag (`:Opportunity.warm_access_available`, D221) becomes
the **override**: the effective warm is the override when the operator has set one,
else the derived value (the D217 manual-over-computed precedent). The origination
column's fit×warm sort and the warming next-best-action read the effective value.

**The LinkedIn source port + the self-export adapter (S103v, D223).** LinkedIn
contacts enter through a **LinkedIn source port** whose only built adapter parses the
member's **self-export archive** (Settings → Data Privacy → "Get a copy of your
data"): `Connections.csv` (first-degree connections, name + **Company** + Position
read directly from the export — no extraction; the file carries a 3-4-line "Notes"
preamble the parser skips) and `messages.csv` (message senders, keyed on `FROM`). It
seeds `system_suggested` `:Contact` via `merge_contact` with **`capture_source` =
`linkedin`**, `degree` = `first` for connections, deduped against the email-seeded
contacts on the normalized (name, company) signature. The **DMA Member Data
Portability API** (Snapshot API, CONNECTIONS/INBOX domains) is a **deferred adapter
behind the same port, not built** — token generation is EEA/Switzerland-only and the
operator is UK-based; the port lets it slot in if UK eligibility opens. Read-only on
the archive; no vendor SDK in domain.

**Warming steps are append-only audit events (S103v, D224).** A warming action
(intro requested / follow-up sent / referral asked / message sent) against a
`:Contact` or `:Opportunity` is stored via `AuditPort.emit` — **not a `:WarmingStep`
node**, no migration. The event uses `action_verb` = **`warming.step`**,
`resource_type` = `contact` / `opportunity`, `resource_id` = the subject id, and the
step kind + note in `after_state`; it is read back per subject through the faceted
audit reader (`AuditEventListFilters(resource_type, resource_id, action_verbs)`, the
D203 correction precedent). The warming next-best-action reads the last step to
advance its suggestion. The compliance record and the future warming-learning signal
are the same hash-chained artefact.

**The contact network map (S103v, D225)** is a read-only List/Map toggle lens over
the contact surface (the D199 pattern): `:Contact` grouped by company, the leads at
each company, the derived-warm state (override marked), and the logged warming steps,
rendered honestly for unproofed contacts (the proofed/unproofed split visible, D171).
A projection, recomputed on read (D155); no model change.

#### The qualification + history layer (S103w, D226-D229)

**The stage ladder (S103w, D226)** is five active gates — **Lead** (`gate_order` 2),
**Application** (3, renamed from Apply), **Screening** (4), **Interviewing** (5),
**Offer** (6) — seeded via `merge_gate` (no migration). **In role** is the terminal
`won` state (closing `won`, already in `CLOSE_REASONS` — a relabel, not a new reason;
`close_opportunity` unchanged), not a gate. Onboarding folds into the
offer-accepted-to-start transition; interview-round texture lives in the qualification
(D228), not in columns. "Needs staging" stays a render-only column for
`current_gate_id = null`.

**`:Contact.process_role` (S103w, D227)** is a schemaless property: `hiring_manager`
/ `recruiter` / `hr_partner` / `champion` / `interviewer` / `decision_maker`, distinct
from job title. The qualification's champion + decision-maker fields seed from the
role-typed contacts at the opportunity's company (the normalized company match, S103o).
No migration.

**The qualification model (S103w, D228)** — `:Opportunity` gains eight
**dynamic-key schemaless** fields, each a value (`q_<field>`) plus a `last_touched`
(`q_<field>_ts`), written via `SET o[$key]` and read back as a `q_`-prefixed property
map (no migration, no `merge_opportunity` widening — a dedicated `set_qualification_field`
write). The fields (native names, MEDDPICC equivalent): `q_role_open` (pain),
`q_success_measures` (metrics), `q_selection_criteria` (decision criteria),
`q_interview_process` (decision process), `q_champion`, `q_decision_maker`,
`q_competing_candidates` (competition), `q_vetting_checks` (paperwork). An authored
**stage-activation map** (a domain-level default this session, operator-tunable
deferred) assigns each field its active stage(s): Lead → role_open + success_measures;
Application → selection_criteria; Screening → champion + decision_maker; Interviewing
→ interview_process; Offer → competing_candidates + vetting_checks. Activation is
**soft** (all visible, active highlighted, rest dimmed). Seed-and-proof (D200).

**Activity history + stage-relative freshness (S103w, D229)** — a per-opportunity
append-only **activity stream** over the D224 audit route: `warming.step` (D224,
retained) plus a general **`opportunity.activity`** verb, read as the **union** per
opportunity (`resource_type=opportunity` / `resource_id` / both verbs). An entry may
name a qualification field it touched, bumping that field's `q_<field>_ts`.
**Freshness** reuses `staleness.py` (D187, `is_overdue`/`days_elapsed` over
`last_touched`) and is **stage-relative**: computed always, surfaced as a risk badge
only when the field is active at the current stage per the activation map. No new node
type, no migration.

#### `gate_id` on authored elements (S103g, D207) — the dual rollup

A `:Lever` / `:Intermediary` / `:External` carries an optional **`gate_id`** when
it belongs to a gate's local CDD; a goal-level (portfolio) element simply lacks
the property (schemaless, no constraint — the `outcome_id`-on-elements precedent).
A gate-scoped element carries **both** `outcome_id` (so gate work still rolls up
to the goal — coverage stays honest, D171) **and** `gate_id` (so it rolls up to
its gate). The intra-gate Pratt edges reuse the existing `FEEDS` / `INFLUENCES`
authored edge types (no new edge type): lever `FEEDS` intermediary, external
`INFLUENCES` intermediary, intermediary `FEEDS` gate (the local-outcome endpoint).
The `EVIDENCES` read returns the target element's `gate_id`, so a unit's evidence
is attributable to a gate as well as the goal.

#### Authored outcome stance on `:Outcome` (S102, D200; proofable at S103a)

The goal's authored expected outcome — the measurable result that means the goal
is met — is a stance stored on the existing `:Outcome` node (D199's two faces, no
separate node), not an authored element node. S102 stored only the text; **S103a
makes it a proofable terminal element** with the same accept / edit / reject the
other elements carry, so the outcome stops being a static header. Three properties
carry it (all schemaless — no constraint, so no migration; the eight S102-drafted
outcomes carry the text alone and the read coalesces a missing proof_state to
`pending` and a missing origin to `llm_drafted`, since they were LLM-drafted):

| Property                        | Type            | Notes                                                              |
|---------------------------------|-----------------|--------------------------------------------------------------------|
| `authored_expected_outcome`     | `String`/absent | the measurable result (LLM-drafted or user-authored); reject clears it |
| `authored_outcome_origin`       | `String`/absent | `llm_drafted` / `user_authored` / `system_suggested`; absent ⇒ `llm_drafted` |
| `authored_outcome_proof_state`  | `String`/absent | `pending` / `accepted`; absent ⇒ `pending`                         |

Accept sets `authored_outcome_proof_state = accepted`; edit sets the text and flips
the origin to `user_authored`; reject clears the text and its proof/origin (the
`:Outcome` node itself is the goal and is never deleted). The outcome is **not** a
reclassify target (D201): it is the goal's single terminal, not one of the
lever/intermediary/external types.

#### `:Lever` extension (S102, D200)

The authored layer **extends** the existing `:Lever` rather than forking a
parallel authored-lever concept — the lever is the one element that already binds
to its evidence (`commitment_id`), and forking would force the S103 matcher to
reconcile two lever concepts. A stable `lever_id` carries identity so an
LLM-drafted lever can exist before it binds to a commitment, so **`commitment_id`
becomes nullable**, and the authored properties are added:

| Property            | Type            | Notes                                                                          |
|---------------------|-----------------|--------------------------------------------------------------------------------|
| `lever_id`          | `String`/absent | stable identity for an authored lever; absent on a legacy matcher lever        |
| `commitment_id`     | `String`/absent | **now nullable** — the Postgres `commitments.id`; absent on an LLM-drafted lever with no commitment yet |
| `outcome_id`        | `String`        | the goal whose CDD this authored lever belongs to (authored levers only)       |
| `label`             | `String`/absent | the authored lever's display text; absent when commitment-backed (the matcher lever reads its name from the commitment) |
| `provenance_origin` | `String`/absent | `llm_drafted` / `user_authored` / `system_suggested`; absent on a legacy lever |
| `proof_state`       | `String`/absent | `pending` / `accepted`; absent on a legacy lever                               |

**Constraint reconciliation (brief-altitude per D200).** A new uniqueness
constraint `lever_id_unique_per_tenant` on `(tenant_id, lever_id)` carries authored
identity. The existing `lever_unique_per_tenant` on `(tenant_id, commitment_id)`
**stays** and continues to govern commitment-backed levers: Neo4j node uniqueness
constraints exempt nodes missing a constraint property, so an LLM-drafted lever
with no `commitment_id` is exempt from the commitment constraint, and a legacy
matcher lever with no `lever_id` is exempt from the authored constraint. The two
identities coexist without collision; no constraint is dropped.

#### `FEEDS` and `INFLUENCES` edges (S102, D200)

Authored causal edges, distinct from the matcher's `SERVES` and the existing
`LEVER_FOR`. `FEEDS`: `(:Lever)-[:FEEDS]->(:Intermediary)` and
`(:Intermediary)-[:FEEDS]->(:Outcome)` (a controllable action feeds an
intermediary feeds the outcome). `INFLUENCES`:
`(:External)-[:INFLUENCES]->(:Intermediary)` or `(:External)-[:INFLUENCES]->(:Outcome)`
(an external influences but is not controlled). Each carries `tenant_id`,
`jurisdiction`, and `created_at` matching both endpoints.

| Property      | Type      | Notes                                          |
|---------------|-----------|------------------------------------------------|
| `tenant_id`   | `String`  | not empty; matches both endpoints              |
| `jurisdiction`| `String`  | matches both endpoints                         |
| `created_at`  | `DateTime`| set on initial MERGE                           |
| `needs_review`| `Bool`/absent | set `true` when a reclassify (D201, S103a) makes the edge ungrammatical for the new source kind; absent ⇒ valid. Schemaless, no constraint, no migration. Surfaced on the proof read; never auto-cleared, never auto-deleted |

Uniqueness via the MERGE pattern keyed on `(tenant_id, source, target)` (Community
Edition has no declarative relationship-property uniqueness), the `SERVES`/
`LEVER_FOR` precedent. References D200 (the authored-CDD pivot), D198 (the
process-versus-CDD boundary the authored levers/intermediaries/externals
instantiate), D199 (the read-only slice whose dogfood surfaced the pivot), and the
"graph's meaning is authored" principle.

#### Authoring completion (S103a, D201)

S102 drafted and proofed; **S103a closes the authoring loop** so the model is fully
authorable — all over the `0005` shapes, no migration (the only new persisted state
is the schemaless outcome-stance proof/origin properties and the edge `needs_review`
flag documented above). Three write paths land, all behind `DAILY_DRIVER_CDD_WRITE`
(D126), tenant-scoped through the wrapper:

- **Add** a user-authored element of any of the four types. A lever / intermediary /
  external is a fresh node (`provenance_origin = user_authored`, `proof_state =
  accepted` — authored is proofed by the act) wired with a default edge to the
  outcome (lever/intermediary `FEEDS`, external `INFLUENCES`, the drafter's fallback
  shape) so it joins the causal chain; this is how externals enter the model at all,
  given the zero-externals draft. An "outcome" add sets the authored outcome stance
  above (`user_authored` / `accepted`).
- **Reclassify** an element across the lever/intermediary/external boundary per
  **D201**: preserve the node and its stable id (moving the id value between
  `lever_id` and `element_id` as the kind requires), flip the origin to
  `user_authored`, and flag — never drop — any incident edge the new kind makes
  ungrammatical (`needs_review = true`).
- **Surface the outcome** as a proofable terminal element (accept / edit / reject the
  authored outcome stance).

### The element-evidence layer (S103b, D202) — `EVIDENCES` edge (migration 0006)

D202 binds ingested work to the **authored element** it serves, not the goal as a
whole. A `(:Unit)-[:EVIDENCES]->(authored element)` edge is the primary evidence
write, replacing the goal-level `(:Unit)-[:SERVES]->(:Outcome)` write (which is
**retired** — no longer written; the goal level is **derived on read** from element
evidence to prevent drift, D155). The edge target is a `:Lever` (by `lever_id`),
`:Intermediary` / `:External` (by `element_id`), or the `:Outcome` goal node (by
`outcome_id`) — the same authored-endpoint whitelist as the `FEEDS`/`INFLUENCES`
edges. A unit may carry `EVIDENCES` edges to **more than one** element (multi-attach).

Lands via `migrations/neo4j/0006_element_evidence.cypher`. Like `SERVES`/`FEEDS`,
the edge has **no declarative constraint** (Community Edition has no
relationship-property uniqueness); idempotency comes from the MERGE pattern keyed
on `(tenant_id, unit, element)`, and the matcher replaces the tenant's `EVIDENCES`
set each run (derived state). 0006 carries a relationship range index on
`EVIDENCES(tenant_id)` for the tenant-scoped reads (idempotent, `IF NOT EXISTS`).

| Property      | Type      | Notes                                                              |
|---------------|-----------|-------------------------------------------------------------------|
| `tenant_id`   | `String`  | not empty; matches both endpoints; the tenant-isolation predicate |
| `jurisdiction`| `String`  | first-class per D12; matches both endpoints                       |
| `tier`        | `String`  | the match tier: `lexical_exact` / `lexical_keyword` / `alias`     |
| `status`      | `String`  | `confirmed` / `candidate` — derived from the tier                 |
| `basis`       | `String`  | the matcher basis string (e.g. `element-exact`, `element-keyword`, `alias`) |
| `created_at`  | `DateTime`| set on initial MERGE                                              |

**No direction property** this session: the lever-vs-external orientation (email
sender/recipient, calendar organiser/attendee) needs a user-identity reference the
system does not store and whose only consumer is the emergent loop, so direction
and its `EVIDENCES.direction` property land at **S104** (D203, reserved). **No
embedding tier** (the live matcher is lexical-and-alias only; S100's empty
email-embedding corpus keeps it out of scope).

**Unbound** is not a node type: a unit carrying **no** `EVIDENCES` edge is unbound,
surfaced by query (the existing unlinked/coverage read, now meaning "matched no
element"), parked as the emergent loop's queue (S104), never dropped.

**The correction record** (each relink/unlink stored with provenance as the
learning signal) lands at **S103c** with the audit-event path, not this migration —
S103b captures no corrections (it has no relink/unlink yet; the display is
read-only).

#### User-ownership + correction capture (S103c, D203) — no migration

S103c makes the bindings correctable and the re-match re-runnable, all schemaless
over the `0005`/`0006` shapes — **no migration**.

- **`:Unit.user_owned`** (`Bool` / absent) — set `true` on a `:Unit` the first time
  the user relinks or unlinks any of its evidence (unit-level ownership grain,
  D203). The re-runnable re-match **skips** user-owned units: `replace_element_evidence`
  deletes only `EVIDENCES` from non-user-owned units, and the matcher excludes
  user-owned units from the inference, so a correction is never overwritten and
  authoring a new goal recovers coverage only on the non-owned remainder. Absent ⇒
  matcher-owned. Survives `correlate_units` (the `:Unit` MERGE by deterministic id
  preserves the property). Per-element ownership is the named refinement (deferred).
- **A relinked/unlinked `EVIDENCES` edge** carries `tier = user`, `status = confirmed`,
  `basis = user-corrected` (the user's binding outranks the matcher's tiers).
- **The correction record is an audit event** (`AuditPort.emit`, the canonical
  hash-chained append-only store — the Step-0 audit-versus-dedicated decision,
  settled for audit). `resource_type = cdd_element_evidence`; `action_verb`
  `cdd.relink` / `cdd.unlink`; `before_state` the prior binding (unit + element),
  `after_state` the new binding (the relink target, or removed for unlink); `actor`
  + `timestamp` from the event. The labelled (prior → new) pair is the learning
  signal a later session reads back through the audit reader's faceted query; S103c
  captures, it does not consume.

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
| `category`                      | `text`           | not null; CHECK ∈ {`retrieval_strategy`, `model_choice`, `prompt_revision`, `cost_optimization`, `matcher_suppression`} (matcher_suppression added 0036, D185/D186) |
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

## Intake context substrate

Per-tenant substrate for `contexts/intake/` per D127. One table on
each tenant's dedicated Postgres data plane per D32, landing the
Phase 2-A canonical-entry record. IntakeRecord is the aggregate
root: a record captured when work enters the system, ahead of any
downstream portfolio write. Every table carries `tenant_id` and
`jurisdiction` per D12. Tamper-evidence follows D110 commitment 7:
every intake write through the application layer emits an audit
event; no parallel hash chain on the intake table.

Migration `alembic/tenant/versions/0017_intake_substrate` ships the
`intakes` table; migration `0018_intake_id_columns` adds the
nullable `intake_id` foreign-key column to `cases` and `assertions`.

### `intakes`

| Column                | Type          | Constraints                                                          |
|-----------------------|---------------|----------------------------------------------------------------------|
| `id`                  | `uuid`        | primary key; default `gen_random_uuid()`                             |
| `tenant_id`           | `uuid`        | not null; jurisdiction-bearing per D12                               |
| `jurisdiction`        | `text`        | not null; CHECK `jurisdiction <> ''`                                 |
| `intake_source`       | `text`        | not null; CHECK ∈ {`MANUAL_ENTRY`, `WHATSAPP_INBOUND`}               |
| `payload`             | `jsonb`       | not null; the serialised IntakePayload variant                       |
| `authored_by_user_id` | `text`        | not null; CHECK `<> ''`; ActorReference persisted identity per D126  |
| `created_at`          | `timestamptz` | not null; default `now()`                                            |

The aggregate root. `intake_source` carries `MANUAL_ENTRY` at
S44b; migration `0020_intake_source_whatsapp` (S45, D129) extends
the CHECK with `WHATSAPP_INBOUND` for inbound WhatsApp messages,
and `CALENDAR_READ` / `EMAIL_READ` land at P14. `payload`
is the JSONB-serialised IntakePayload — the single
ManualEntryPayload variant, reused for `WHATSAPP_INBOUND` intakes
with `raw_text` carrying the message body so the `IntakePayload`
type alias stays single-variant per D127's build-at-second-instance
discipline. IntakeRecords are immutable: never
updated or deleted, per the "Originals never erased" principle.
Index `ix_intakes_tenant_created_at` on `(tenant_id, created_at
DESC)` and `ix_intakes_tenant_source` on `(tenant_id,
intake_source)` support the list surface.

### `intake_id` on `cases` and `assertions` (migration 0018)

Migration `0018_intake_id_columns` adds a nullable `intake_id`
column to `cases` and to `assertions`, each a foreign key to
`intakes(id)` ON DELETE RESTRICT. The column is nullable at the
persistence layer for migration safety and is nullable at the
domain layer per D128: the intake-canonical orchestration paths
populate it (a Case from `record_intake_and_create_case`, an
INITIAL Assertion from `record_intake_and_create_data_point`, a
REVISION Assertion from `record_intake_and_revise_data_point`),
while direct domain construction outside an orchestration leaves it
null. D128 commits the intake-canonical posture: every persisted
state change at the platform's write surfaces traces to an
IntakeRecord via this field.

### IntakeRecord (intake aggregate root)

| Field           | Type             | Constraints                                                              |
|-----------------|------------------|--------------------------------------------------------------------------|
| `intake_id`     | `UUID`           | not null; the aggregate identity                                         |
| `tenant_id`     | `UUID`           | not null; jurisdiction-bearing per D12                                   |
| `jurisdiction`  | `str`            | not null; non-empty                                                      |
| `intake_source` | `IntakeSource`   | not null; Phase 2-A `MANUAL_ENTRY`                                       |
| `payload`       | `IntakePayload`  | not null; the source-specific payload value object                       |
| `authored_by`   | `ActorReference` | not null; the persisted authoring identity, derived from ActorContext    |
| `created_at`    | `datetime`       | not null; timezone-aware                                                 |

A frozen dataclass; `__post_init__` enforces non-empty invariants.
`IntakeSource` is a string enum. `IntakePayload` is a type alias —
at S44b the single `ManualEntryPayload` variant; it widens to a
Union when `CALENDAR_READ` / `EMAIL_READ` payload variants land at
P14.

### ManualEntryPayload (intake payload value object)

| Field             | Type                | Constraints                                          |
|-------------------|---------------------|------------------------------------------------------|
| `raw_text`        | `str`               | not null; non-empty; the operator's manual input     |
| `intent_hint`     | `str | None`        | nullable; an optional free-text intent annotation    |
| `linked_case_ids` | `tuple[UUID, ...]`  | not null; default empty; optional case associations  |

A frozen dataclass, framework-free per D16. The Phase 2-A
`IntakePayload` variant. The `linked_case_ids` data structure
lands at S44b; the linking-heuristics UX surface defers to P14.

## Messaging context substrate

Per-tenant substrate for `contexts/messaging/` per D129. One table
on each tenant's dedicated Postgres data plane per D32, landing the
Phase 2-A Wave 1 communication substrate — the channel through
which all three product modes (attentional, workflow,
observation-and-suggestion) reach the user. Message is the
aggregate root: one inbound or outbound message on a channel.
Every table carries `tenant_id` and `jurisdiction` per D12.
Tamper-evidence follows D110 commitment 7: every messaging write
through the application layer emits an audit event; no parallel
hash chain on the messaging table. The channel and vendor
commitment (WhatsApp via the Twilio Sandbox) is D119; D129 commits
the bounded-context substrate that operates on that commitment.

Migration `alembic/tenant/versions/0019_messaging_substrate` ships
the `messages` table on every per-tenant database.

### `messages`

| Column         | Type          | Constraints                                                                  |
|----------------|---------------|------------------------------------------------------------------------------|
| `id`           | `uuid`        | primary key; default `gen_random_uuid()`                                     |
| `tenant_id`    | `uuid`        | not null; jurisdiction-bearing per D12                                       |
| `jurisdiction` | `text`        | not null; CHECK `jurisdiction <> ''`                                         |
| `direction`    | `text`        | not null; CHECK ∈ {`INBOUND`, `OUTBOUND`}                                    |
| `channel`      | `text`        | not null; CHECK ∈ {`WHATSAPP`}                                               |
| `body`         | `text`        | not null; CHECK `body <> ''`                                                 |
| `from_address` | `text`        | not null; CHECK `<> ''`; channel-addressed (an E.164 number for WhatsApp)     |
| `to_address`   | `text`        | not null; CHECK `<> ''`; channel-addressed                                   |
| `status`       | `text`        | not null; CHECK ∈ {`QUEUED`, `SENT`, `DELIVERED`, `FAILED`, `RECEIVED`}       |
| `external_id`  | `text`        | nullable; the vendor message identifier (the Twilio MessageSid)              |
| `intake_id`    | `uuid`        | nullable; FK → `intakes.id` ON DELETE RESTRICT; populated on inbound per D128 |
| `actor_id`     | `text`        | not null; CHECK `<> ''`; the acting actor's identity                         |
| `created_at`   | `timestamptz` | not null; default `now()`                                                    |
| `cell_payload` | `jsonb`       | nullable; default null; outbound implementer-specific shape per D141         |

The aggregate root. `channel` carries the single Phase 2-A value
`WHATSAPP`; the CHECK widens as SMS, voice, and email channels
land at P14+ per the channel-enum extension trigger. `status`
moves QUEUED → SENT → DELIVERED for an outbound message and is
RECEIVED for an inbound one; FAILED is terminal for a rejected
send. `external_id` is null until the vendor assigns an
identifier — synthesised by the LocalEcho adapter, the Twilio
MessageSid under the Twilio adapter. `intake_id` is non-null on
inbound messages (the IntakeRecord the `record_intake_and_record_inbound_message`
orchestration recorded per D128) and null on outbound messages.
Messages are immutable once persisted, per the "Originals never
erased" principle; a status change on an outbound message is
out of scope at S45 (delivery-status callbacks defer to P14+).
Index `ix_messages_tenant_created_at` on `(tenant_id, created_at
DESC)` and `ix_messages_tenant_direction_channel` on `(tenant_id,
direction, channel)` support the list surface.

### Message (messaging aggregate root)

| Field          | Type               | Constraints                                                  |
|----------------|--------------------|--------------------------------------------------------------|
| `id`           | `UUID`             | not null; the aggregate identity                             |
| `tenant_id`    | `UUID`             | not null; jurisdiction-bearing per D12                       |
| `jurisdiction` | `str`              | not null; non-empty                                          |
| `direction`    | `MessageDirection` | not null; INBOUND or OUTBOUND                                |
| `channel`      | `MessageChannel`   | not null; Phase 2-A `WHATSAPP`                               |
| `body`         | `str`              | not null; non-empty                                          |
| `from_address` | `str`              | not null; non-empty; channel-addressed                       |
| `to_address`   | `str`              | not null; non-empty; channel-addressed                       |
| `status`       | `MessageStatus`    | not null                                                     |
| `external_id`  | `str \| None`      | nullable; the vendor message identifier                      |
| `intake_id`    | `UUID \| None`     | nullable; the IntakeRecord an inbound message traces to      |
| `actor_id`     | `str`              | not null; non-empty                                          |
| `created_at`   | `datetime`         | not null; timezone-aware                                     |
| `cell_payload` | `dict \| None`     | nullable; per-implementer payload per D141; INBOUND must be null |

A frozen dataclass; `__post_init__` enforces the non-empty and
not-null invariants plus the pairing rule that an INBOUND message
may carry an `intake_id` while an OUTBOUND message must not, plus
the pairing rule per D141 that an INBOUND message must not carry a
`cell_payload`. `MessageDirection`, `MessageChannel`, and
`MessageStatus` are string enums. Domain code is framework-free per
D16.

The `cell_payload` field carries per-implementer state for
cross-turn extraction per D141. Each ConversationFlow implementer
is responsible for validating the shape on read; mismatched or
absent payload routes through D139 to D134 clarification per the
implementer's cell-flow commitment. Mirror-conversation at S52 is
the first user: it persists `current_focus_artefact` (as
`{"current_focus_artefact": {"artefact_id": str(uuid),
"artefact_type": "case"|"data_point"}}`) for drill-down anchor
extraction on the next turn. Audit-conversation and manual_entry
do not populate the column; CellResponse / AuditConversationResponse
do not carry implementer-specific extension fields.

### `pending_clarifications`

| Column                       | Type           | Constraints                                                                                                          |
|------------------------------|----------------|----------------------------------------------------------------------------------------------------------------------|
| `id`                         | `uuid`         | primary key                                                                                                          |
| `tenant_id`                  | `uuid`         | not null; jurisdiction-bearing per D12                                                                               |
| `jurisdiction`               | `text`         | not null; CHECK `jurisdiction <> ''`                                                                                 |
| `user_id`                    | `text`         | not null; CHECK `user_id <> ''`                                                                                      |
| `originating_channel`        | `text`         | not null; CHECK `originating_channel <> ''`                                                                          |
| `originating_user_address`   | `text`         | not null; CHECK `originating_user_address <> ''`                                                                     |
| `originating_intake_id`      | `uuid`         | not null; FK → `intakes.id` ON DELETE RESTRICT                                                                       |
| `proposed_intent`            | `jsonb`        | not null; the cell's structured best-guess intent                                                                    |
| `proposed_action_summary`    | `text`         | not null; CHECK `proposed_action_summary <> ''`                                                                      |
| `status`                     | `text`         | not null; CHECK ∈ {`PENDING`, `RESOLVED`, `EXPIRED`}                                                                 |
| `target_cell`                | `text`         | not null after Alembic 0023 backfill; CHECK ∈ {`manual_entry`, `audit_conversation`, `mirror_conversation`, `calendar_conversation`, `email_conversation`, `dispatch_clarification`, `checkin`} (widened at 0032, then 0038) |
| `created_at`                 | `timestamptz`  | not null                                                                                                             |
| `expires_at`                 | `timestamptz`  | not null; CHECK `expires_at > created_at`                                                                            |
| `resolved_at`                | `timestamptz`  | nullable; CHECK `(status = 'PENDING' AND resolved_at IS NULL) OR (status <> 'PENDING' AND resolved_at IS NOT NULL)`  |

D134's multi-turn conversation state — at medium-confidence
classification the cell renders a shape-aware clarification and
persists the proposed action; the operator's confirming reply
resolves the pending and executes the proposed action; a correcting
reply resolves as cancelled; silence times out at 24 hours per
D119's WhatsApp Sandbox conversation window. The D134 invariant
("at most one PENDING per `(tenant_id, user_id)`") is enforced
structurally by a partial unique index
`ux_pending_clar_one_pending_per_user` on `(tenant_id, user_id)
WHERE status = 'PENDING'`; the create use case respects it
operationally by expiring any prior PENDING before inserting the
new one. Index `ix_pending_clar_tenant_user` on `(tenant_id,
user_id)` supports active-pending lookup. `proposed_intent` rides
as JSONB; a resolution-ambiguity sub-case carries a
`resolution_candidates` sidecar that the cell's intent re-parser
ignores per D139.

Migrations `0021_pending_clarification` (S47) created the table;
`0023_pending_clar_target_cell` (S52, D140) adds the `target_cell`
column. The `target_cell` field identifies which ConversationFlow
implementer owns the pending. The `dispatch_inbound` use case
consults this field on active-pending routing per D140's dispatch
flow Step 2. The meta-classification PendingClarification created
at low-confidence dispatch carries `target_cell='dispatch_clarification'`
for implementer-side handling at the dispatch layer.
`0032_pending_clar_target_cell_calendar_email` (S60/S56) widened the
CHECK to admit the calendar and email cells; `0038_pending_clar_target_cell_checkin`
(S97b, D194) widened it to admit the **pending-only** `checkin` cell —
outbound-initiated (the DAILY_SCHEDULED composer creates its pending),
so it owns a `target_cell` but is never meta-routed. The allowed set is
kept in lockstep with `CellIdentifier` by the constraint-sync tripwire
(`test_cell_identifier_constraint_sync`).

### PendingClarification (messaging multi-turn state)

| Field                       | Type                            | Constraints                                                                |
|-----------------------------|---------------------------------|----------------------------------------------------------------------------|
| `id`                        | `UUID`                          | not null                                                                   |
| `tenant_id`                 | `UUID`                          | not null; jurisdiction-bearing per D12                                     |
| `jurisdiction`              | `str`                           | not null; non-empty                                                        |
| `user_id`                   | `str`                           | not null; non-empty                                                        |
| `originating_channel`       | `str`                           | not null; non-empty                                                        |
| `originating_user_address`  | `str`                           | not null; non-empty                                                        |
| `originating_intake_id`     | `UUID`                          | not null                                                                   |
| `proposed_intent`           | `dict[str, Any]`                | not null; cell's structured best-guess intent                              |
| `proposed_action_summary`   | `str`                           | not null; non-empty                                                        |
| `status`                    | `PendingClarificationStatus`    | not null; PENDING / RESOLVED / EXPIRED                                     |
| `target_cell`               | `str`                           | not null; identifies the owning ConversationFlow implementer per D140      |
| `created_at`                | `datetime`                      | not null; timezone-aware                                                   |
| `expires_at`                | `datetime`                      | not null; strictly after `created_at`                                      |
| `resolved_at`               | `datetime \| None`              | nullable; non-null iff `status` is terminal                                |

A frozen dataclass; `__post_init__` enforces non-empty text fields,
the `expires_at > created_at` ordering, and the status / resolved_at
pairing invariant. `resolve(at)` and `expire(at)` return new
instances with updated status and `resolved_at` per the "Originals
never erased" principle. `target_cell` lands at S52 (D140) carrying
one of the four known identifiers (`manual_entry`, `audit_conversation`,
`mirror_conversation`, `dispatch_clarification`); future
ConversationFlow implementers at P15+ extend the accepted set as
they register.

### `fired_triggers`

| Column            | Type           | Constraints                                                                                                          |
|-------------------|----------------|----------------------------------------------------------------------------------------------------------------------|
| `id`              | `uuid`         | primary key; default `gen_random_uuid()`                                                                             |
| `tenant_id`       | `uuid`         | not null                                                                                                             |
| `user_id`         | `text`         | not null; CHECK `user_id <> ''`                                                                                      |
| `trigger_type`    | `text`         | not null; CHECK ∈ {`daily_scheduled`, `threshold_crossed`, `calendar_event`, `email_received`, `manual`}             |
| `idempotency_key` | `text`         | nullable; semantics differ per `trigger_type` per D147                                                               |
| `fired_at`        | `timestamptz`  | not null; default `now()`                                                                                            |
| UNIQUE            | composite      | UNIQUE on `(tenant_id, user_id, trigger_type, idempotency_key)`                                                      |

The fired_triggers table provides race-safe idempotency for
platform-initiated broadcasts per D147. The HTTP trigger endpoint
use case (FireTrigger) consults this table via INSERT with
`ON CONFLICT DO NOTHING` before BROADCAST_INITIATED audit event
emission. Idempotency key semantics vary per `trigger_type`:
DAILY_SCHEDULED uses the date string in operator timezone (one row
per tenant+user+day); MANUAL uses null (Postgres UNIQUE permits
multiple null rows per construction); THRESHOLD_CROSSED at S57 keys
on the derived-state crossing identity per D153: a cancellation is
`rule_id:google_event_id`; a conflict is `rule_id:eventA|eventB`
(sorted). The identity excludes `cancelled_at`. No
`matched_audit_event_id`. Future
trigger types commit semantics at activation sessions. Index
`ix_fired_triggers_tenant_user_type` on `(tenant_id, user_id,
trigger_type)` supports diagnostic lookups for the last firing per
user per trigger type. Migration `0025_fired_triggers` (S54) ships
the table on every per-tenant database.

### FiredTrigger (messaging value object)

| Field            | Type        | Constraints                                                          |
|------------------|-------------|----------------------------------------------------------------------|
| `id`             | `UUID`      | not null                                                             |
| `tenant_id`      | `UUID`      | not null                                                             |
| `user_id`        | `str`       | not null; non-empty                                                  |
| `trigger_type`   | `str`       | not null; one of the BroadcastTriggerType enum values                |
| `idempotency_key`| `str \| None`| nullable per D147 semantics                                          |
| `fired_at`       | `datetime`  | not null; timezone-aware                                             |

A frozen dataclass representing a successful trigger fire. The
read shape is informational (diagnostic reads); the write path is
through the FiredTriggersRepository's `insert_or_skip` method that
returns the boolean fresh-vs-conflict outcome per D147.

## Calendar context tables (per-tenant)

Migration `0026_calendar_substrate` (S55a, D148) ships these on every
per-tenant database. Per-tenant only per D32; the control plane has no
calendar tables.

### `connections`

| Column                    | Type          | Constraints                                                              |
|---------------------------|---------------|--------------------------------------------------------------------------|
| `id`                      | `uuid`        | primary key                                                              |
| `tenant_id`               | `uuid`        | not null                                                                 |
| `jurisdiction`            | `text`        | not null                                                                 |
| `provider`                | `text`        | not null (domain-meaningful provider family, e.g. `google_calendar`)     |
| `provider_config_key`     | `text`        | not null (opaque Nango integration key, e.g. `google-calendar`)          |
| `provider_connection_ref` | `text`        | not null (opaque Nango connection id)                                    |
| `sync_token`              | `text`        | nullable; per-connection incremental-sync state; cleared on 410 resync   |
| `created_at`              | `timestamptz` | not null; default `now()`                                                |
| `updated_at`              | `timestamptz` | not null; default `now()`                                                |
| UNIQUE                    | composite     | UNIQUE on `(tenant_id, provider, provider_config_key)`                   |

The domain `Connection` value object holds the Nango handles as opaque
references (the domain never imports Nango identifiers); a vendor swap
re-points `provider_config_key`/`provider_connection_ref` rather than
touching domain code. The `sync_token` is sync *state* accessed through
dedicated repository get/set methods, kept off the identity-only
Connection value object.

### `meetings`

| Column               | Type          | Constraints                                                                 |
|----------------------|---------------|-----------------------------------------------------------------------------|
| `id`                 | `uuid`        | primary key                                                                 |
| `tenant_id`          | `uuid`        | not null                                                                    |
| `jurisdiction`       | `text`        | not null                                                                    |
| `google_event_id`    | `text`        | not null (the stable key)                                                   |
| `status`             | `text`        | not null; CHECK ∈ {`confirmed`, `tentative`, `cancelled`}                   |
| `start_at`           | `timestamptz` | nullable (best-effort parse of the source start)                            |
| `end_at`             | `timestamptz` | nullable                                                                    |
| `start_raw`          | `text`        | nullable (raw RFC3339/date string as returned)                              |
| `end_raw`            | `text`        | nullable                                                                    |
| `source_updated_at`  | `timestamptz` | nullable (Google's last-modified)                                           |
| `recurring_event_id` | `text`        | nullable                                                                    |
| `html_link`          | `text`        | nullable                                                                    |
| `content_hash`       | `text`        | nullable (digest of synthesised content text; NULL when tombstoned)         |
| `enc_wrapped_dek`    | `bytea`       | nullable (P3 envelope encryption, D21; NULL when tombstoned)                |
| `enc_dek_wrap_nonce` | `bytea`       | nullable                                                                    |
| `enc_ciphertext`     | `bytea`       | nullable (encrypted JSON: title/description/location/attendees/organizer)   |
| `enc_nonce`          | `bytea`       | nullable                                                                    |
| `enc_key_version`    | `integer`     | nullable                                                                    |
| `embedding`          | `vector(768)` | nullable; HNSW cosine index `meetings_embedding_hnsw_idx`; raw-SQL column   |
| `created_at`         | `timestamptz` | not null; default `now()`                                                   |
| `updated_at`         | `timestamptz` | not null; default `now()`                                                   |
| `cancelled_at`       | `timestamptz` | nullable (set when tombstoned)                                              |
| UNIQUE               | composite     | UNIQUE on `(tenant_id, google_event_id)`                                    |

The `meetings` table is the event-id-keyed mutable search cache (D148): a
delta upserts a modified event and tombstones a cancelled one. The
tombstone path sets `status='cancelled'`, sets `cancelled_at`, and purges
the content (`content_hash`, the five `enc_*` columns, and `embedding`
all NULL) so cancelled events leave search while the row is retained so a
re-appearing event id is recognised. Content (title/description/location/
attendees/organizer) is field-level encrypted via P3 envelope encryption
into the `enc_*` columns; structural columns stay plaintext for querying.
The `embedding` column mirrors ingestion's `chunks.embedding`
(`vector(768)`, HNSW cosine, raw-SQL declaration) — the embedding
capability is inherited per the substrate-inheritance survey, the storage
and similarity search are calendar's own. Index `ix_meetings_tenant_start`
on `(tenant_id, start_at)` supports time-windowed reads. The immutable
evidence record for citation is the audit-event payload snapshot, not this
mutable row.

### Meeting / Connection (calendar domain value objects)

`Meeting` is a frozen dataclass carrying the structured event fields plus
`content_hash` and the tombstone marker; `to_search_text()` synthesises
the content for embedding and the hash. `Connection` is a frozen dataclass
carrying identity and the opaque provider references. Both are
framework-free per D16.

## Email context tables (per-tenant)

Migration `0027_email_substrate` (S56a, D151) ships these on every
per-tenant database. Per-tenant only per D32. Table names carry the
`email_` prefix so they do not collide with calendar's `connections`/
`meetings` on the same per-tenant database.

### `email_connections`

| Column                    | Type          | Constraints                                                          |
|---------------------------|---------------|----------------------------------------------------------------------|
| `id`                      | `uuid`        | primary key                                                          |
| `tenant_id`               | `uuid`        | not null                                                             |
| `jurisdiction`            | `text`        | not null                                                             |
| `provider`                | `text`        | not null (e.g. `google_mail`)                                        |
| `provider_config_key`     | `text`        | not null (opaque Nango integration key, e.g. `google-mail`)          |
| `provider_connection_ref` | `text`        | not null (opaque Nango connection id)                                |
| `history_id`              | `text`        | nullable; dormant mailbox incremental anchor (getProfile; D151)      |
| `created_at` / `updated_at` | `timestamptz` | not null; default `now()`                                          |
| UNIQUE                    | composite     | UNIQUE on `(tenant_id, provider, provider_config_key)`              |

### `emails`

| Column                | Type          | Constraints                                                                 |
|-----------------------|---------------|-----------------------------------------------------------------------------|
| `id`                  | `uuid`        | primary key                                                                 |
| `tenant_id`           | `uuid`        | not null                                                                    |
| `jurisdiction`        | `text`        | not null                                                                    |
| `message_id`          | `text`        | not null (stable Gmail message id)                                          |
| `thread_id`           | `text`        | nullable                                                                    |
| `received_at`         | `timestamptz` | nullable (internalDate); the set-diff window scope                          |
| `labels`              | `jsonb`       | not null; default `'[]'` (Gmail label ids — non-sensitive metadata)         |
| `history_id`          | `text`        | nullable; per-message history id (metadata)                                 |
| `content_hash`        | `text`        | nullable; digest of subject+body; NULL when tombstoned                      |
| `enc_*` (5 columns)   | `bytea`/`int` | P3 envelope-encrypted content (subject/body/addresses/snippet; D21); NULL when tombstoned |
| `created_at` / `updated_at` | `timestamptz` | not null; default `now()`                                             |
| `deleted_at`          | `timestamptz` | nullable; set-diff soft-delete tombstone (row retained)                     |
| UNIQUE                | composite     | UNIQUE on `(tenant_id, message_id)`; index on `(tenant_id, received_at)`    |

Subject, body, from/to/cc addresses, and snippet are field-level encrypted
via P3 envelope encryption (D21) into the five `enc_*` columns; structural
metadata stays plaintext for querying. Deletion is set-diff (D151): Gmail's
bounded query excludes Trash, so a message present last pull and absent
this pull is tombstoned (`deleted_at` set; `enc_*`, `content_hash`, and the
message's chunk rows purged; row retained). Email content is immutable
once received, so an Email cites directly with no citation-time snapshot.

### `email_chunks`

| Column                | Type          | Constraints                                                          |
|-----------------------|---------------|----------------------------------------------------------------------|
| `id`                  | `uuid`        | primary key                                                          |
| `tenant_id`           | `uuid`        | not null                                                             |
| `jurisdiction`        | `text`        | not null                                                             |
| `email_id`            | `uuid`        | not null (the parent Email)                                          |
| `message_id`          | `text`        | not null                                                             |
| `chunk_index`         | `integer`     | not null                                                             |
| `enc_*` (5 columns)   | `bytea`/`int` | P3 envelope-encrypted chunk text (D21)                               |
| `embedding`           | `vector(768)` | per-chunk embedding; HNSW cosine index `email_chunks_embedding_hnsw_idx` |
| `created_at`          | `timestamptz` | not null; default `now()`                                            |
| UNIQUE                | composite     | UNIQUE on `(tenant_id, message_id, chunk_index)`; index on `(tenant_id, message_id)` |

The email-local body-chunk store (D151) — the largest divergence from
calendar, since email bodies are long. Bodies are chunked (an email-local
chunker) and each chunk embedded via ingestion's inherited
`ChunkEmbedderPort.embed(chunks)` (the embedder is a port; ingestion's
parsers are not reused). `replace_chunks` is the unit of write (delete +
re-insert per message); the `embedding vector(768)` column is added in raw
SQL with an HNSW cosine index, mirroring calendar/ingestion.

## Daily-driver context substrate (per-tenant)

Per-tenant substrate for `contexts/daily_driver/` per D157 (the P16/S58
daily-driver first slice). Three tables on each tenant's dedicated
Postgres data plane per D32. The slice's load-bearing discipline is
*compute-at-render*: status and overdue are never stored — they are
computed from the completion log against the commitment interval at read
time — so no status or overdue column exists on any of these tables.
Every table carries `tenant_id` and `jurisdiction` per D12. Migration
`alembic/tenant/versions/0028_daily_driver_substrate` ships these tables.
Tamper-evidence (audit-chain coverage) is not added at S58: the Day
ordering/done churn is per-day UI state, not canonical tenant-authored
state, consistent with D155's reasoning that not every mutation is
canonical; commitment create/complete audit emission is a named
carryover if procurement review demands it.

### `commitments`

| Column                   | Type          | Constraints                                          |
|--------------------------|---------------|------------------------------------------------------|
| `id`                     | `uuid`        | primary key; default `gen_random_uuid()`             |
| `tenant_id`              | `uuid`        | not null; jurisdiction-bearing per D12               |
| `jurisdiction`           | `text`        | not null; CHECK `jurisdiction <> ''`                 |
| `name`                   | `text`        | not null; CHECK `name <> ''`                         |
| `expected_interval_days` | `integer`     | not null; CHECK `expected_interval_days > 0`         |
| `authored_by_user_id`    | `text`        | not null; the user-authored cadence's author         |
| `created_at`             | `timestamptz` | not null; default `now()`                            |
| `expected_outcome`       | `text`        | nullable; free-text expectation captured at creation (D162) |
| `observed_outcome`       | `text`        | nullable; free-text observation captured after (D162)       |
| `outcome_status`         | `text`        | nullable; CHECK `outcome_status IS NULL OR outcome_status IN ('met','partial','missed','changed','dropped')` (D162) |
| `observed_at`            | `timestamptz` | nullable; timestamp of the observation capture (D162)       |

The minimal user-authored cadence: a name plus an expected interval in
days. S61 (D162) adds the minimal expected-versus-observed loop as
record-level fields (not completion-log rows, which are the cadence-tick
history): a free-text `expected_outcome` captured forward at creation, a
free-text `observed_outcome` + coarse `outcome_status` captured after, and
the `observed_at` timestamp of that capture. `observed_at` is the only new
progress signal — the drop-candidate query's `last_progress_at` is
otherwise derived from the completion log at render, so no progress column
exists. `outcome_status` is nullable (absence is the not-yet-observed
state); `dropped` is the user-initiated status the operator sets to act on
a drop-candidate recommendation (no auto-delete). Outcomes are plaintext,
consistent with the store's existing posture (the context is not
D21-classified). Migration `0029_commitment_outcome` ALTERs this table to
add these columns and the `commitments_outcome_status_check` constraint.
The full cadence-with-staleness primitive (threshold-engine integration
per D153, multiple cadence types, richer completion semantics) defers to
Phase 2-B per the deferred-decisions "Cadence-with-staleness primitive
(full)" entry; the LLM-computed gap, graph causal edges, and longitudinal
optimisation defer with D162 behind the dogfooding verdict. Index
`ix_commitments_tenant_id` on `(tenant_id)`.

### `commitment_completions`

| Column          | Type          | Constraints                                                |
|-----------------|---------------|------------------------------------------------------------|
| `id`            | `uuid`        | primary key; default `gen_random_uuid()`                   |
| `commitment_id` | `uuid`        | not null; FK → `commitments.id` ON DELETE CASCADE          |
| `tenant_id`     | `uuid`        | not null; jurisdiction-bearing per D12                     |
| `jurisdiction`  | `text`        | not null                                                   |
| `completed_at`  | `timestamptz` | not null; default `now()`                                  |

The append-only completion log. The latest `completed_at` per commitment
is the staleness rule's last-activity input (falling back to the
commitment's `created_at` when the log is empty). Indexes
`ix_commitment_completions_commitment_id` on `(commitment_id)` and
`ix_commitment_completions_tenant_id` on `(tenant_id)`.

This is the **single authoritative did-source** under the Option-B did-source
decision (D192): the cadence read consults `MAX(completed_at)` here for a
commitment's last completion; reported-not-done negatives live in
`commitment_checkin_responses` and are never read as dids.

### `commitment_checkin_responses`

| Column          | Type          | Constraints                                                |
|-----------------|---------------|------------------------------------------------------------|
| `id`            | `uuid`        | primary key; default `gen_random_uuid()`                   |
| `commitment_id` | `uuid`        | not null; FK → `commitments.id` ON DELETE CASCADE          |
| `tenant_id`     | `uuid`        | not null; jurisdiction-bearing per D12                     |
| `jurisdiction`  | `text`        | not null                                                   |
| `beat_date`     | `date`        | not null; the day the outcome refers to (backfillable)     |
| `outcome`       | `text`        | not null; CHECK in (`did`, `reported_didnt`)               |
| `recorded_at`   | `timestamptz` | not null; default `now()`                                  |

The check-in negative sibling store (D192, migration 0037). Makes Padhanam's
daily completion **three-state**: a `reported_didnt` row is a tracked negative
(the beat is missed *with evidence*); silence writes no row. The cadence read
sources `last_reported_didnt` as `MAX(beat_date)` per commitment WHERE
`outcome = 'reported_didnt'`. Under Option B (D192), dids stay in
`commitment_completions`; the `outcome` CHECK admits `did` for S97b write-path
flexibility, but S97a reads dids only from the completion log, so no outcome is
read from two stores. Indexes
`ix_commitment_checkin_responses_commitment_id` on `(commitment_id)` and
`ix_commitment_checkin_responses_tenant_id` on `(tenant_id)`.

### `day_item_states`

| Column         | Type          | Constraints                                                |
|----------------|---------------|------------------------------------------------------------|
| `id`           | `uuid`        | primary key; default `gen_random_uuid()`                   |
| `tenant_id`    | `uuid`        | not null; jurisdiction-bearing per D12                     |
| `jurisdiction` | `text`        | not null                                                   |
| `user_id`      | `text`        | not null                                                   |
| `day_date`     | `date`        | not null                                                   |
| `item_kind`    | `text`        | not null; CHECK ∈ {`CASE`, `COMMITMENT`}                   |
| `item_id`      | `uuid`        | not null; the Case id or Commitment id                     |
| `position`     | `integer`     | nullable; the user's explicit ordering, 0-based            |
| `done`         | `boolean`     | not null; default `false`; the done-for-today mark         |
| `updated_at`   | `timestamptz` | not null; default `now()`                                  |

The minimal Day concept: the only state that persists is the user's
per-day ordering (`position`) and done-for-today mark (`done`). UNIQUE
`ux_day_item_states_tenant_user_day_item` on
`(tenant_id, user_id, day_date, item_kind, item_id)` makes ordering and
done independent upserts (reordering does not clobber a done mark and
vice versa). Index `ix_day_item_states_tenant_user_day` on
`(tenant_id, user_id, day_date)` supports the per-day read.

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

### ActorContext (shared-kernel value object)

The request-scoped actor-identity-and-authorisation envelope
introduced at S44a per D126. ActorContext composes the existing
TenantContext as a field and adds the acting actor's identity
plus the authorisation surface the use-case-boundary decorator
checks. It lives at `shared_kernel/actor_context.py`; it is the
value object that flows into every portfolio use case from S44a
onward. ActorContext is distinct from `ActorReference`:
ActorReference is the minimal *persisted* authoring-identity
value object stamped onto `DataPoint.authored_by` and
`Assertion.authored_by`, whereas ActorContext is the
*request-scoped* envelope carrying capability — D126 supersedes
D124's forward commitment that `authored_by` would become
ActorContext, because a persisted record cannot honestly carry a
request-time authorisation snapshot.

| Field               | Type             | Constraints                                                                                  |
|---------------------|------------------|----------------------------------------------------------------------------------------------|
| `tenant_context`    | `TenantContext`  | not null; wraps the shared-kernel TenantContext value object per D126's compose shape         |
| `actor_id`          | `str`            | not null; non-empty; UUID-shaped from the Principal at the HTTP path, a label at the CLI path |
| `role_list`         | `frozenset[str]` | not null; non-empty; Phase 2-A populates `{"operator"}`                                       |
| `authorisation_set` | `frozenset[str]` | not null; Phase 2-A populates from the hardcoded role-to-authorisation lookup; may be empty   |

The shape is a frozen dataclass: Pydantic is forbidden in
`shared_kernel/` by the import-linter `shared-kernel-policed`
contract per D16, so the choice is structurally pre-empted,
consistent with TenantContext. `__post_init__` enforces the
non-empty invariant on `actor_id` and `role_list` and the
not-null invariant on `tenant_context` and `authorisation_set`.
The object is constructed alongside (not replacing) the existing
TenantContext extraction: the HTTP `get_actor_context` dependency
composes the registry-resolved TenantContext with the
Principal-derived `actor_id`, and the CLI synthesises ActorContext
directly from the dev tenant wiring. The authorisation decorator
`requires_authorisation` at `shared_kernel/authorisation.py`
checks a required permission string against `authorisation_set`
and raises `AuthorisationDenied` on failure; the HTTP layer
translates that to 403 with the `ErrorResponse` shape above per
D98, registered at `apps/api/_auth_errors.py` per D104.

### Structured-output discipline (shared-kernel value objects plus Protocol)

Per D130, the structured-output primitive at
`shared_kernel/structured_output.py` is the cross-cutting
discipline for LLM calls that must return a schema-conforming
structured value rather than free text. Three shapes — two
frozen dataclasses and one Protocol:

```python
@dataclass(frozen=True)
class StructuredOutputRequest:
    prompt: str
    schema: dict[str, Any]          # a JSON Schema object
    temperature: float | None = None
    model_hint: str | None = None

@dataclass(frozen=True)
class StructuredOutputResponse(Generic[T]):
    value: T                        # the schema-conforming result
    confidence: float | None        # optional self-reported confidence
    provider_metadata: dict[str, Any]

@runtime_checkable
class StructuredOutputPort(Protocol):
    async def generate_structured(
        self, request: StructuredOutputRequest
    ) -> StructuredOutputResponse[dict[str, Any]]: ...
```

`StructuredOutputRequest.schema` is a JSON Schema object held as
a `dict` — vendor-neutral and framework-free, which
`shared_kernel/` requires (Pydantic is forbidden there by the
`shared-kernel-policed` import-linter contract per D16). The
adapter maps the JSON Schema dict to the vendor's
`response_format` parameter. `StructuredOutputResponse[T]` is
generic over the parsed value type: `value` is the
schema-conforming result, `confidence` is null unless the schema
itself carries a confidence field, `provider_metadata` carries
model name, token usage, and finish reason. `StructuredOutputPort`
exposes one async method, `generate_structured`, returning a
`StructuredOutputResponse[dict[str, Any]]` (the parsed JSON
object). The inference adapter implements the port additively at
S45 per D130; per-context structured-output shapes live at each
context's domain layer conforming to this primitive.

### ConversationFlow Protocol (cross-context behavioural contract)

Per D115, ConversationFlow is the cross-context standard
interface for multi-turn interactions that resolve revisions and
clarifications. D115 committed the primitive; S45 lands the shape
at `shared_kernel/conversation_flow.py` directly under D115 — no
separate shape D-entry, because the shape carries no contested
alternatives (unlike the Revisable shape, which warranted D125).
Like the Revisable Protocol above, this sub-section formalises a
behavioural contract, not a value-object schema. The Protocol
exposes three async methods over five frozen-dataclass value
objects:

```python
@dataclass(frozen=True)
class ConversationInvocation:    # opens a conversation
    purpose: str
    actor_id: str
    parameters: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ConversationState:         # carried across turns
    conversation_id: str
    purpose: str
    turn_count: int              # 0 at open
    is_open: bool
    payload: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ConversationInput:         # a single user turn
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ConversationClosure:       # the instruction to close
    reason: str

@dataclass(frozen=True)
class ConversationOutcome:       # the terminal result
    conversation_id: str
    turn_count: int
    resolution: str
    payload: dict[str, Any] = field(default_factory=dict)

@runtime_checkable
class ConversationFlow(Protocol):
    async def open(
        self, invocation: ConversationInvocation
    ) -> ConversationState: ...

    async def turn(
        self, state: ConversationState, user_input: ConversationInput
    ) -> ConversationState: ...

    async def close(
        self, state: ConversationState, closure: ConversationClosure
    ) -> ConversationOutcome: ...
```

`open` starts a conversation from a `ConversationInvocation` and
returns the initial `ConversationState`; `turn` advances the
conversation by one `ConversationInput` and returns the next
`ConversationState`; `close` terminates it from a
`ConversationClosure` and returns the terminal
`ConversationOutcome`. The five value objects are framework-free
per D16. Conformance is CI-enforceable via the contract harness
at `tests/contract/conversation_flow/`; the first implementer —
the manual entry cell — registers at S46 (see "Manual entry cell"
below), and audit-conversation (5.1) and portfolio
mirror-conversation (4.1) implementers land at P14+.

### Latency tier and four-layer model ontology (shared-kernel value objects)

Per D122 and D132, `shared_kernel/inference.py` carries the
latency-tier and model-identification primitives for the inference
port. Framework-free per D16 — stdlib only.

```python
class LatencyTier(StrEnum):
    REAL_TIME_REQUIRED = "real_time_required"   # user-invoked surfaces
    ASYNC_TOLERANT = "async_tolerant"           # substrate / background

class Provider(StrEnum):
    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"

@dataclass(frozen=True)
class ModelConfiguration:        # the Configuration layer
    latency_tier: LatencyTier
    temperature: float | None = None
    max_tokens: int | None = None
    structured_output_schema: dict[str, Any] | None = None

@dataclass(frozen=True)
class ModelIdentifier:           # the four-layer identification
    provider: Provider
    account: str
    version: str
    configuration: ModelConfiguration
```

`LatencyTier` is the D122 hint a call site declares; the
`InferencePort` / `StructuredOutputPort` surface carries it as a
defaulted parameter (`REAL_TIME_REQUIRED` default — Path A, D122's
preserve-current-behaviour commitment). `ModelIdentifier` is the
D132 four-layer identification — Provider, Account, Version,
Configuration. It composes at the LiteLLM adapter boundary, not at
the public call signature (D132 Finding C), and the adapter's
per-call OTel span captures all four dimensions as
`gen_ai.model.provider` / `.account` / `.version` /
`.configuration`. Phase 2-A operates single-account-per-provider;
the Account field is `"default"` until Phase 2-B+ customer
deployments make it load-bearing.

## Manual entry cell (messaging context)

Per D129 (messaging substrate) and D131 (provenance-aware response
composition). The manual entry cell is the first ConversationFlow
implementer (D115). It lives at the messaging *application* layer —
`contexts/messaging/application/manual_entry_cell.py` — because it
holds ports and orchestrates (S46 pre-write reconciliation Finding
B: a cell holding ports cannot sit at the pure-domain layer per the
`layers-messaging` hexagonal contract). The intent value objects it
dispatches on are pure-domain.

### Intent value objects (messaging domain)

`contexts/messaging/domain/intent.py` carries the discriminated
intent union the cell extracts from an inbound message via
structured output. Four frozen-dataclass variants plus the
schema-level discriminant enum:

```python
class IntentType(StrEnum):
    CREATE_CASE = "create_case"
    ADD_DATA_POINT = "add_data_point"
    REVISE_DATA_POINT = "revise_data_point"
    UNCLEAR = "unclear"

@dataclass(frozen=True)
class CreateCaseIntent:
    title: str

@dataclass(frozen=True)
class AddDataPointIntent:
    case_reference: str       # natural-language reference (Path B)
    data_point_type: str      # GOAL / STATUS / METHODOLOGY_APPLICATION
    value_text: str

@dataclass(frozen=True)
class ReviseDataPointIntent:
    data_point_reference: str # natural-language reference (Path B)
    value_text: str

@dataclass(frozen=True)
class UnclearIntent:
    clarification: str        # the question to ask the operator

Intent = (
    CreateCaseIntent | AddDataPointIntent
    | ReviseDataPointIntent | UnclearIntent
)
```

`IntentType` is the discriminant in the structured-output JSON
Schema; `parse_intent(raw: dict) -> Intent` maps the LLM's parsed
object to the typed variant. The cell dispatches on the variant
type. `AddDataPointIntent.case_reference` and
`ReviseDataPointIntent.data_point_reference` are natural-language
references (Path B target identifier resolution); the cell resolves
them against portfolio state before driving a write. Each variant's
`__post_init__` enforces non-empty string invariants. DropCaseIntent
and QueryStateIntent defer to the second-instance trigger per the
build-at-second-instance discipline.

### Target resolution outcomes (messaging application)

`resolve_target` searches portfolio state for the case or data
point a natural-language reference names, returning a
`ResolutionOutcome`:

```python
class ResolutionStatus(StrEnum):
    MATCHED_SINGLE = "matched_single"
    AMBIGUOUS = "ambiguous"
    NO_MATCH = "no_match"

@dataclass(frozen=True)
class ResolutionOutcome:
    status: ResolutionStatus
    matched_id: UUID | None             # set when MATCHED_SINGLE
    candidate_labels: tuple[str, ...]   # human labels when AMBIGUOUS
```

### CellResponse and citation discipline (D131 first instance)

The cell composes a `CellResponse` carrying the operator-facing
text plus the D131 citation fields:

```python
@dataclass(frozen=True)
class CellResponse:
    text: str
    cited_intake_records: tuple[UUID, ...]
    cited_audit_events: tuple[UUID, ...]
    cited_artefacts: tuple[UUID, ...]
```

D131 first-instance exercise: `cited_intake_records` and
`cited_artefacts` populate from the IDs the cell holds in scope
after a successful orchestration (the IntakeRecord id and the
Case / DataPoint id). `cited_audit_events` stays empty at S46 — the
intake-owned write-result DTOs do not surface audit-event IDs, and
extending them is out of proportion for the first-instance exercise
(recorded at `charter/captures.md`). The WhatsApp surface renders
citations in compact textual form (Shape 1:
short-hex-prefix-plus-timestamp).

### ManualEntryCell ConversationFlow registration

The cell implements the ConversationFlow Protocol (D115) — `open` /
`turn` / `close`. It is the first implementer registered with the
contract harness at `tests/contract/conversation_flow/` via
`tests/contract/conversation_flow/test_manual_entry_cell_conversation_flow.py`
(the harness globs `test_*_conversation_flow.py` for registration
modules); the harness's five conformance scenarios run against it. `turn`
processes one inbound message: structured-output intent extraction
→ target resolution → intake-canonical portfolio orchestration →
`CellResponse` composition. The cell holds the `StructuredOutputPort`
and a single `PortfolioGateway` consumer port (read for resolution,
write for orchestration); the composed response is embedded in the
returned `ConversationState.payload`.

