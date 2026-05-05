# Padhanam

Padhanam (Esperanto for "studying") is a public demonstration that a senior product leader can direct the end-to-end implementation of an enterprise-grade agentic platform through Claude Code without writing code. The platform is built to enterprise standards: multi-tenant, identity-federated, audit-chained, jurisdiction-aware, OTel-instrumented. The architectural discipline is the test of whether AI-assisted development can sustain production-shaped software when directed by a product leader rather than implemented by engineers. The methodology that emerges from running the experiment is the proprietary insight; the platform is the artefact that proves it.

## How to read the charter

The charter under charter/ holds design intent. Read in this order:

1. bet.md — strategic intent, the proposition being investigated, and what success looks like
2. methodology.md — how the product-leader-and-implementer pattern is being run (pending operator authorship per D39; the gap is recorded in `current-package.md`)
3. principles.md — engineering rules, read every session
4. decisions.md — append-only architectural decisions log
5. roadmap.md — living strategic-tree artefact (bet, phases, packages, sessions) with versioned reasoning per D44; packages.md is the static reference
6. phase-1-prd.md — living phase PRD with delta capture at audit per D43
7. prfaq.md — living external-voice storytelling artefact, refreshed at every phase audit per D45
8. current-package.md — active scope and carryover items

History lives separately under [log/](log/) (sessions, packages, audits, captures) and old material is moved to [docs/archive/](docs/archive/) at audit boundaries — never deleted.

## Strategic mode and build mode

Strategic work — bets, audits, package planning, decisions assessed under Kano — produces charter edits, session prompts, and roadmap version updates. Build and test work — implementation, schema migrations, tests, commits — produces code commits and session-log entries. Both modes happen through Claude Code; mode separation is maintained by the operator declaring mode at conversation start, by distinct deliverables, and by distinct commit conventions (`docs(charter): ...` or `docs(pN/<boundary-name>): ...` for strategic; `feat(pN/sN): ...` and `docs(pN/sN): ...` for build), per D47. The charter files bridge the two modes: decisions made in strategic mode land in [decisions.md](charter/decisions.md) and become constraints in build mode; audit findings flow back through the same files. The methodology by which strategy and build are bridged is itself the artefact under investigation, to be documented in `charter/methodology.md`.

## Where new contributors look first

Start with [charter/bet.md](charter/bet.md), then [charter/principles.md](charter/principles.md). [CLAUDE.md](CLAUDE.md) describes how Claude Code is expected to operate inside the repo.

## Local HTTPS

[mkcert](https://github.com/FiloSottile/mkcert) is a host dependency: install with `brew install mkcert nss` and run `mkcert -install` once to add the local CA to the system trust store. Generate `localhost.pem` and `localhost-key.pem` into `./certs/` with `mkcert -cert-file certs/localhost.pem -key-file certs/localhost-key.pem localhost langfuse.localhost`; the directory is gitignored because the certs are host-machine-specific. The cert covers both names because UI services live on subdomains (Langfuse on `langfuse.localhost`); add new SANs as further UI services land. `make up` starts the Caddy proxy alongside the rest of the stack. Verify with `curl https://localhost/health` (returns `ok`) and `curl https://langfuse.localhost/api/public/health` (returns Langfuse JSON), both with valid TLS handshakes (no `-k` needed). `*.localhost` resolves to `127.0.0.1` on macOS without `/etc/hosts` changes.
