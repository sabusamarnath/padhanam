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

## Vector store

(Empty until P6 ships.)

## Graph store

(Empty until P6 ships.)
