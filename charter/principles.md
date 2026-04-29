# Engineering Principles

Read every session. Kept tight on purpose.

## Architectural

- Hexagonal throughout. External systems behind interfaces. Domain code never imports vendor SDKs.
- Local-first. Full stack runs on the laptop. Production swap is configuration, not refactor.
- Database-per-tenant. No code path assumes a single shared database.
- LLM-provider-agnostic via LiteLLM. Default development model is Ollama.
- Hybrid retrieval. Vector via pgvector and graph via Neo4j, both behind a unified interface.
- Observability is foundation, not feature. Trace capture from the first LLM call.

## Engineering practice

- Tests are part of the build, not a follow-up.
- Schema changes update `charter/schema.md` in the same commit.
- New observability metrics require a documented decision they will inform.
- Optimization output is recommendation-shaped, not chart-shaped.
- Security as default: HTTPS via mkcert, secrets in `.env`, RLS on tenant-scoped tables, Pydantic validation on every endpoint, audit log on state changes.
- Conventional commits referencing package and session number.

## Token discipline

- Claude Code reads only what the session needs.
- Files over 200 lines are read in ranges, not whole.
- Working files (`brief.md`, `current-package.md`, session log entries) stay tight. Old content moves to archive at audit time, never deletes.
- Log entries are one line where possible. Prose only when reasoning is non-obvious.
- Strategic decisions and audits happen in Claude.ai. Build and test happen in Claude Code. Decisions written to local files bridge the two.
