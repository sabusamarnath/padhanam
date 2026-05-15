# Padhanam

Padhanam (Esperanto for "studying") is a public demonstration that a senior product leader can direct the end-to-end implementation of an enterprise-grade agentic platform through Claude Code without writing code. The platform is built to enterprise standards: multi-tenant, identity-federated, audit-chained, jurisdiction-aware, OTel-instrumented. The architectural discipline is the test of whether AI-assisted development can sustain production-shaped software when directed by a product leader rather than implemented by engineers. The methodology that emerges from running the experiment is the proprietary insight; the platform is the artefact that proves it.

## The strategic commitment

Padhanam is Apache 2.0 licensed. **The platform is the demonstration; the methodology is the proprietary insight.** Open-sourcing the platform is load-bearing for the bet: the procurement-grade architecture is verifiable by anyone reading the code, and the methodology pattern that produced it is the artefact under investigation. See [LICENSE](LICENSE) for the full text.

## What the platform does at Phase 1 close

Padhanam ships a four-context substrate plus optimization layer demonstrating the procurement-grade observability and optimization architecture an enterprise agentic platform requires. The substrate is exercisable through CLI and HTTP surfaces; the HTTP surface is documented via OpenAPI at `/openapi.json` for Phase 2 UX consumer work.

The producer contexts under [contexts/](contexts/):

- **[contexts/agent/](contexts/agent/)** — agent loop runtime with tool invocation and trace capture
- **[contexts/ingestion/](contexts/ingestion/)** — source ingestion with parse, embed, and extract stages plus hybrid vector-plus-graph retrieval through a unified strategy interface
- **[contexts/run_history/](contexts/run_history/)** — agent run records with cost and outcome aggregation per D94/D97
- **[contexts/audit/](contexts/audit/)** — hash-chained audit events with per-tenant and platform-operator chains per D102/D103
- **[contexts/retrieval_evaluation/](contexts/retrieval_evaluation/)** — gold-set authoring and retrieval evaluation runs per D109/D110
- **[contexts/optimization/](contexts/optimization/)** — rule-based recommendation generation with pluggable metric and rule abstractions per D111

The applications under [apps/](apps/):

- **[apps/cli/](apps/cli/)** — operator-grade CLI surface for substrate authoring and engine invocation
- **[apps/api/](apps/api/)** — HTTP surface for consumer UX integration with FastAPI-generated OpenAPI specification per D112

## Operating the platform

Install host dependencies: [mkcert](https://github.com/FiloSottile/mkcert) and `make` plus Docker. Run `mkcert -install` once and generate localhost certificates per the Local HTTPS section below.

Start the stack: `make up` brings up the Compose stack (Caddy proxy, Postgres, pgvector, Neo4j, Ollama for local LLM inference, LiteLLM gateway, Langfuse for trace capture, ClickHouse, Redis, MinIO, and the API container).

Apply migrations: `make migrate` runs the control-plane migrations then the per-tenant migrations against each registered tenant.

Seed the dev tenants: `make seed-tenants` registers the local test set tenants in the registry (idempotent).

Exercise the CLI surface: CLI commands run inside the API container so the Compose hostnames resolve over the network — `docker compose exec padhanam-api python -m apps.cli.main <command>`. Examples: `padhanam gold-set list --tenant-id a`, `padhanam optimization run --tenant-id a`, `padhanam evaluation-run start --tenant-id a --gold-set-id <uuid>`. Three Makefile shortcuts wrap the most common CLI flows: `make eval-run ARGS="--tenant-id a ..."`, `make ingest-run ARGS="<path> --tenant-id a"`, `make ingest-worker ARGS="--tenant-id a"`.

Exercise the HTTP surface: with the stack up, the OpenAPI specification is at `https://localhost/openapi.json`. The FastAPI Swagger UI at `https://localhost/docs` renders the specification interactively. Every route requires authentication; issue a dev JWT via `padhanam.security.auth.issue_dev_token` inside the container, then pass as `Authorization: Bearer <token>`. The S42 smoke at [docs/smoke/p11_s42_http_transport_surface.md](docs/smoke/p11_s42_http_transport_surface.md) walks the full HTTP surface end-to-end as a working example.

## How to read the charter

The charter under charter/ holds design intent. Read in this order:

1. bet.md — strategic intent, the proposition being investigated, and what success looks like
2. methodology.md — how the product-leader-and-implementer pattern is being run. The file is a **living hypothesis** revised as session data points and audit findings accumulate; treat the current state as a snapshot of the evolving discipline, not as a finished document. The hypothesis's evolution itself is the proprietary artefact under investigation; methodology.md captures the current best statement at each phase boundary.
3. principles.md — engineering rules, read every session
4. decisions.md — append-only architectural decisions log
5. schema.md — canonical database schema reference; updated in the same commit as any migration per the engineering practice principle
6. deferred-decisions.md — architectural decisions deferred to a future session with named activation triggers; reviewed at phase audits
7. roadmap.md — living strategic-tree artefact (bet, phases, packages, sessions) with versioned reasoning per D44; packages.md is the static reference
8. phase-1-prd.md — living phase PRD with delta capture at audit per D43
9. prfaq.md — living external-voice storytelling artefact, refreshed at every phase audit per D45
10. current-package.md — active scope and carryover items

History lives separately under [log/](log/) (sessions, packages, audits, captures) and old material is moved to [docs/archive/](docs/archive/) at audit boundaries — never deleted.

## Strategic mode and build mode

Strategic work — bets, audits, package planning, decisions assessed under Kano — produces charter edits, session prompts, and roadmap version updates. Build and test work — implementation, schema migrations, tests, commits — produces code commits and session-log entries. Both modes happen through Claude Code; mode separation is maintained by the operator declaring mode at conversation start, by distinct deliverables, and by distinct commit conventions (`docs(charter): ...` or `docs(pN/<boundary-name>): ...` for strategic; `feat(pN/sN): ...` and `docs(pN/sN): ...` for build), per D47. The charter files bridge the two modes: decisions made in strategic mode land in [decisions.md](charter/decisions.md) and become constraints in build mode; audit findings flow back through the same files. The methodology by which strategy and build are bridged is itself the artefact under investigation, to be documented in `charter/methodology.md`.

## Where new contributors look first

Start with [charter/bet.md](charter/bet.md), then [charter/principles.md](charter/principles.md). [CLAUDE.md](CLAUDE.md) describes how Claude Code is expected to operate inside the repo.

## Local HTTPS

[mkcert](https://github.com/FiloSottile/mkcert) is a host dependency: install with `brew install mkcert nss` and run `mkcert -install` once to add the local CA to the system trust store. Generate `localhost.pem` and `localhost-key.pem` into `./certs/` with `mkcert -cert-file certs/localhost.pem -key-file certs/localhost-key.pem localhost langfuse.localhost`; the directory is gitignored because the certs are host-machine-specific. The cert covers both names because UI services live on subdomains (Langfuse on `langfuse.localhost`); add new SANs as further UI services land. `make up` starts the Caddy proxy alongside the rest of the stack. Verify with `curl https://localhost/health` (returns `ok`) and `curl https://langfuse.localhost/api/public/health` (returns Langfuse JSON), both with valid TLS handshakes (no `-k` needed). `*.localhost` resolves to `127.0.0.1` on macOS without `/etc/hosts` changes.
