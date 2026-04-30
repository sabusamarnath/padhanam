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

(Empty until P3 ships.)

## Vector store

(Empty until P6 ships.)

## Graph store

(Empty until P6 ships.)
