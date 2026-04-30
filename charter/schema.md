# Schema

Updated whenever the database schema changes. Schema diffs at commit time check against this file.

## Tenant registry (control plane)

Lives on the dedicated `postgres-control-plane` Postgres instance per
D33. Schema lands at S10 via Alembic revision
`0001_create_tenant_registry`.

### `tenant_registry`

| Column           | Type            | Constraints                                    |
|------------------|-----------------|------------------------------------------------|
| `tenant_id`      | `uuid`          | primary key                                    |
| `display_name`   | `text`          | not null                                       |
| `jurisdiction`   | `text`          | not null; indexed (`ix_tenant_registry_jurisdiction`) |
| `status`         | `text`          | not null; default `'active'`; CHECK ∈ {`active`, `suspended`, `deprovisioned`} |
| `created_at`     | `timestamptz`   | not null; default `now()`                      |
| `wrapped_dek`    | `bytea`         | not null; envelope-encrypted DEK (D21)         |
| `dek_wrap_nonce` | `bytea`         | not null; nonce used to wrap the DEK           |
| `ciphertext`     | `bytea`         | not null; encrypted credentials                |
| `nonce`          | `bytea`         | not null; nonce used for credential encryption |
| `key_version`    | `integer`       | not null; KEK version for rotation             |
| `aad`            | `bytea`         | not null; AAD bytes (binds `tenant_id` + purpose `"tenant.credentials.v1"`) |

No plaintext credential column exists; the registry adapter at S10
encrypts on write via `vadakkan/security/crypto.py` and never decrypts
on read. Decryption flows through the operator-context-only
`reveal_connection_config` use case (D34).

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
| `tenant_id`           | `text`          | not null; the routed tenant's id (denormalised on the table for self-describing rows per D22) |
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
