# Current Package

Active package details. Updated when a new package starts. Archived to `docs/archive/packages/` at package close.

## P2: First LLM call

**Goal:** End-to-end slice that takes a prompt, returns a model response, and surfaces a complete trace in Langfuse. Architecture for the rest of Phase 1 locked in by D16, D17, the security baseline (D19-D27), and the deferred-decisions content before code that depends on it ships.

**Sessions in this package:**
- S4: Langfuse 3 in Compose behind Caddy (six-service deployment with subdomain serving). Charter updates: D15, D16, D17, D18, principles bounded-contexts addition, P2 current-package block. Done.
- S5: Security baseline. Charter: security posture principles section, optionality principle, D19-D27, deferred-decisions file (orchestration commitments, data-plane ownership, feature promotion process), P2 four-session current-package block. Code: platform/config/, platform/security/, platform/observability/security_events.py (the package was renamed to vadakkan/ pre-S6 per D28), contexts/audit/ scaffolding, tests/contract/tenant_isolation/ scaffolding, supply chain hardening (make scan, retroactive image digest pins for postgres/redis/caddy). Security review checklist as the per-session gate from S5 onward.
- S6: Ollama and LiteLLM in Compose. Default model (Qwen 2.5 7B per D15, reaffirmed at S6 reconciliation) pulled into a named volume that survives `make up`/`make down`. LiteLLM emits OTel-native traces (D27) — no Langfuse SDK in the callbacks list — to Langfuse 3's OTLP/HTTP ingestion endpoint, with Basic auth derived from existing Langfuse keys via ops/derive_env.py. Master key, model, OTLP endpoint, and Langfuse identifiers all read through vadakkan/config/ (D19). 10-service stack from `make up`. Images pinned to digests, scanned, exceptions documented (Categories B and C extended). `make smoke-llm` returns a valid OpenAI-format completion and the trace lands in Langfuse with full GenAI semantic-convention attributes. Done.
- S8: Vadakkan rebrand. Charter: D29 appended; D17, D18, D22 historical text restored from HEAD; current-facing prose updated. Code: pyproject distribution rename, `MeridianSettings` → `VadakkanSettings`, operational defaults in `.env.example`, comments updated in `Makefile`/`Caddyfile`/`compose.yaml`/`ops`. Done.
- S7: FastAPI skeleton with the structure mandated by D16. uv workspaces. Import-linter contracts live (structural and security). Domain event bus skeleton in vadakkan/events/. Auth middleware on every endpoint from first commit (D23). All adapters read config through vadakkan/config/ (D19). Security events emitted on auth failures (D26). One endpoint that proxies a prompt via LiteLLM, with OTel spans wrapping the gateway call so the app frame and the LLM call appear as parent-child in the trace. Browser interactive verification required for any UI-bearing acceptance criteria (lesson from S4).

**Status:** P2 in progress. S6 closed. S8 closed (charter-and-rename, executed between S6 and S7). S7 in progress.

**Notes:** P2 is the package where architectural commitments stop being abstractions and start being enforced by tooling. By package close, "production swap is configuration not refactor" is true on the inference and security paths. Trace capture is live from the first LLM call. Compliance posture is documented and architecturally enforced for SOC 2 Type II and ISO 27001, with sector frameworks additive. Orchestration architectural commitments live in deferred-decisions.md and activate in P5+.
