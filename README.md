# Padhanam

Padhanam (Esperanto for "studying") is a public demonstration that a senior product leader can direct the end-to-end implementation of an enterprise-grade agentic platform through Claude Code without writing code. The platform is built to enterprise standards: multi-tenant, identity-federated, audit-chained, jurisdiction-aware, OTel-instrumented. The architectural discipline is the test of whether AI-assisted development can sustain production-shaped software when directed by a product leader rather than implemented by engineers. The methodology that emerges from running the experiment is the proprietary insight; the platform is the artefact that proves it.

## How to read the charter

The charter under charter/ holds design intent. Read in this order:

1. bet.md — strategic intent, the proposition being investigated, and what success looks like
2. methodology.md — how the product-leader-and-implementer pattern is being run, descriptive at this stage and growing as sessions surface new patterns
3. principles.md — engineering rules, read every session
4. decisions.md — append-only architectural decisions log
5. packages.md — Phase 1 work breakdown, then current-package.md for active scope

History lives separately under [log/](log/) (sessions, packages, audits) and old material is moved to [docs/archive/](docs/archive/) at audit boundaries — never deleted.

## Claude.ai vs Claude Code

Strategic work — bets, audits, package planning, decisions framed against Kano — happens in Claude.ai, where breadth of context and reasoning matter more than tool access. Build and test work — implementation, schema migrations, tests, commits — happens in Claude Code against this repo. The two surfaces meet through the local files: decisions written in Claude.ai land in [decisions.md](charter/decisions.md), and Claude Code reads them as constraints. Audit findings flow back the same way. The methodology by which strategy and build are bridged is itself the artefact under investigation; it is documented in charter/methodology.md.

## Where new contributors look first

Start with [charter/bet.md](charter/bet.md), then [charter/principles.md](charter/principles.md). [CLAUDE.md](CLAUDE.md) describes how Claude Code is expected to operate inside the repo.

## Local HTTPS

[mkcert](https://github.com/FiloSottile/mkcert) is a host dependency: install with `brew install mkcert nss` and run `mkcert -install` once to add the local CA to the system trust store. Generate `localhost.pem` and `localhost-key.pem` into `./certs/` with `mkcert -cert-file certs/localhost.pem -key-file certs/localhost-key.pem localhost langfuse.localhost`; the directory is gitignored because the certs are host-machine-specific. The cert covers both names because UI services live on subdomains (Langfuse on `langfuse.localhost`); add new SANs as further UI services land. `make up` starts the Caddy proxy alongside the rest of the stack. Verify with `curl https://localhost/health` (returns `ok`) and `curl https://langfuse.localhost/api/public/health` (returns Langfuse JSON), both with valid TLS handshakes (no `-k` needed). `*.localhost` resolves to `127.0.0.1` on macOS without `/etc/hosts` changes.
