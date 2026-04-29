# Phase 1 Packages

The work breakdown for Phase 1. Order reflects dependency and learning value.

- **P1: Scaffold.** Repo, Docker Compose, Make targets, mkcert HTTPS, .env.example, README, `/docs` structure committed.
- **P2: Identity foundation.** Keycloak realm, OIDC integration, SAML SP, SCIM 2.0 endpoint, session management.
- **P3: Tenancy primitives.** Tenant registry, per-tenant database connections, migration runner, audit log table.
- **P4: LLM gateway.** LiteLLM-backed clients, trace capture middleware, OpenTelemetry GenAI conventions, self-hosted Langfuse wired up.
- **P5: Evaluation harness.** Canonical interaction set storage, replay engine, deterministic and LLM-as-judge scoring, regression reporting.
- **P6: Source ingestion.** Upload, two-track pipeline (vector to pgvector, entity extraction to Neo4j), retrieval interfaces.
- **P7: Agent CRUD.** Name, system prompt, source IDs, tool allowlist, retrieval strategy, model selection.
- **P8: Agent runtime.** LangGraph orchestrator behind interface. SSE-streamed responses. Full instrumentation.
- **P9: Run history.** Replay UI, citation linking back to source chunks and graph entities.
- **P10: Audit log viewer.** Tenant-owner UI for the audit log.
- **P11: Optimization dashboard.** Trace inspection, evaluation results, active test reports. Recommendation-shaped.
- **P12: Active testing scheduler.** Cron-driven model substitution, prompt ablation, context compression tests. Weekly per-agent reports.

Phase 1 ends after P12 with a phase audit. Phase 2 direction decided at the audit.
