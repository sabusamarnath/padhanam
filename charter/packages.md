# Phase 1 Packages

Historical static reference per D44. The canonical living strategic-tree artefact is [charter/roadmap.md](roadmap.md), versioned with reasoning categories per change. This file is retained for direct package-list reference and is updated at phase boundaries; mid-phase content can drift from as-built reality (the P2 line drifted from S4 to 2026-05-06; corrected at the carryover-cleanup strategic session per D52, with the drift recorded as the first entry in `charter/methodology.md`'s Failure modes section). RICE scores and version log live in `roadmap.md`.

The work breakdown for Phase 1. Order reflects dependency and learning value.

- **P1: Scaffold.** Repo, charter and log structure at repo root, README, .gitignore, .env.example, Makefile, incremental Compose stack (services land per package per D11), mkcert HTTPS fronting the stack.
- **P2: First LLM call.** Langfuse 3 in Compose behind Caddy, security baseline (`padhanam/config/`, `padhanam/security/`, audit-context scaffold, supply-chain hardening), Ollama and LiteLLM in Compose with OTel-native traces, FastAPI skeleton with bounded contexts and uv workspaces, auth middleware with signed-token dev backend per D23, Quorum → Zephyr rebrand at S8. Identity foundation (Keycloak realm, OIDC, SAML SP, SCIM 2.0, federated session management) deferred to Phase 2 per D52, in supersession of D3.
- **P3: Tenancy primitives at enterprise grade.** Tenant registry on a dedicated control-plane Postgres instance, per-tenant database connections to per-tenant Postgres instances, two-phase Alembic migration runner (control-plane and per-tenant tracks), real audit context adapter with hash-chained append-only storage, credential encryption from inception via envelope encryption.
- **P4: LLM gateway.** LiteLLM-backed clients, trace capture middleware, OpenTelemetry GenAI conventions, self-hosted Langfuse wired up. Cost capture from traces lands here per D41 (pricing table in `padhanam/config/inference.py`, OTel attribute extension joining token counts to USD, per-tenant cost-attribution column added to the tenant registry as an early Alembic migration).
- **P5: Evaluation harness.** Canonical interaction set storage, replay engine, deterministic and LLM-as-judge scoring, regression reporting. Cost-per-successful-task metric implementation per D8 and D41.
- **P6: Source ingestion.** Upload, two-track pipeline (vector to pgvector, entity extraction to Neo4j), retrieval interfaces.
- **P7: Agent CRUD.** Name, system prompt, source IDs, tool allowlist, retrieval strategy, model selection.
- **P8: Agent runtime.** LangGraph orchestrator behind interface. SSE-streamed responses. Full instrumentation.
- **P9: Run history.** Replay UI, citation linking back to source chunks and graph entities.
- **P10: Audit log viewer.** Tenant-owner UI for the audit log.
- **P11: Optimization dashboard.** Trace inspection, evaluation results, active test reports. Recommendation-shaped, with cost-aware recommendations as a first-class surface per D41.
- **P12: Active testing scheduler.** Cron-driven model substitution, prompt ablation, context compression tests. Weekly per-agent reports.

Phase 1 ends after P12 with a phase audit. Phase 2 direction decided at the audit.
