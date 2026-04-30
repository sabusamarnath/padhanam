# Current Package

Active package details. Updated when a new package starts. Archived to `docs/archive/packages/` at package close.

## Between packages

P2 closed. P2 retrospective held; archive at `docs/archive/packages/p2.md`. P3 framing pending in Claude.ai before P3 opens.

P3 will ship tenancy primitives: tenant registry, per-tenant database connections (separate Postgres instance per tenant), migration runner with control-plane and per-tenant tracks, audit log table real adapter, credential encryption from inception via `vadakkan/security/crypto.py`. Session breakdown to be settled at P3 framing.

Carryover artefacts to draft in P3 session work:
- `ops/scheduled_checks.yaml` covering monthly (Langfuse, OTel-instrumentation, LiteLLM, FastAPI/Uvicorn), quarterly (Pydantic chain), annual (import-linter) cadence buckets.
- `Vadkkan` directory housekeeping: rename to `Vadakkan`, verify compose project naming auto-corrects on next `make up`, fold into the first P3 session.