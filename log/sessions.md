# Session Log

One entry per session. Append-only. Old entries archive at phase audits, never delete.

Format:
```
## Session N (Package P)
- Produced: [what shipped]
- Decisions: [D-numbers from decisions.md, or "none"]
- Tests: [pass/fail summary]
- Reflection: [one or two sentences. What was learned, what should change.]
```

---

## Session 1 (Package P1)
- Produced: Repo initialized. Charter committed at /charter/. Log structure at /log/sessions.md. Archive placeholders at /docs/archive/. README, CLAUDE.md, .gitignore, .env.example, Makefile stub at root. Conventional commits configured via .gitmessage.
- Decisions: D11 (scaffold grows incrementally).
- Tests: None. No code yet.
- Reflection: Directory layout was unspecified in the prompt and got resolved mid-session — the brief referenced `/charter/` while the working tree had `docs/charter/`, reorganized to match the brief before close. `docs/session-prompt.md` was written to the repo earlier and removed at close; canonical session structure now lives in CLAUDE.md plus the Claude.ai prompt. Charter content survived intact otherwise. Next session: align `docs/README.md` with the new layout (still references the old `docs/charter/` tree).

## Session 2 (Package P1)
- Produced: compose.yaml at repo root with postgres (pgvector/pgvector:pg17) and redis (redis:7-alpine), both with healthchecks and named volumes. .env.example extended with Postgres/Redis vars; local .env seeded from it. Makefile gained up/down/logs/ps/psql targets, help updated. Stale docs/README.md removed.
- Decisions: none (D11 reaffirmed by scoping S2 to Postgres + Redis only).
- Tests: `make up` → both services `(healthy)` within ~3s. `CREATE EXTENSION vector;` succeeds, `\dx` shows vector 0.8.2. `make down` removes containers, network, and reports nothing running.
- Reflection: pgvector and healthchecks came up clean on the first try — pg_isready and redis-cli ping are well-suited to Compose's healthcheck contract, no tuning needed. The `.env.example` wiring is already showing one mild strain: POSTGRES_USER/PASSWORD/DB are duplicated between the env block and the psql target's shell expansion (`$$POSTGRES_USER`), which is fine here but will multiply when LiteLLM, Langfuse, and Keycloak each want their own DB credentials. Worth watching whether per-service `env_file:` blocks or a secrets pattern emerges before P3's database-per-tenant work, rather than letting the flat .env grow to dozens of vars.

## Session 3 (Package P1)
- Produced: mkcert localhost cert generated into `./certs/` (gitignored); Caddyfile at repo root with `auto_https off`, `admin off`, a `/health` route returning `ok`, and a 503 catch-all. compose.yaml gained a `caddy` service (caddy:2-alpine) on port 443 mounting the Caddyfile and certs read-only, plus `caddy_data`/`caddy_config` named volumes. Makefile help line updated to mention the proxy. README gained a Local HTTPS section. P1 closed.
- Decisions: none (Caddy choice was decided pre-S3 in Claude.ai; reasoning captured in the session brief, not promoted to a D-number since it is a tooling choice rather than an architectural commitment).
- Tests: `make up` → caddy + postgres + redis all up, postgres and redis `(healthy)`. `curl https://localhost/health` → `200 ok` over HTTP/2 with no `-k` (mkcert CA in system trust store, trust chain valid). `curl https://localhost/` → `503` with the catch-all message, confirming unrouted requests fail visibly. `make down` removes all three containers and the network.
- Reflection: The placeholder catch-all did its job — sending a request to `/` returns the explicit "no backends configured yet" 503 rather than a confusing 404, which is exactly the failure mode worth preserving once P2 adds Keycloak. The Caddyfile is not yet showing strain: a single `localhost` site with two `handle` blocks is well within Caddyfile's sweet spot. The first mild pressure point will be when P2 adds Keycloak as the first real upstream: the catch-all must remain (still useful for unknown paths) while a `handle /auth/*` block is inserted ahead of it, and the cert path will need to keep working after the upstream is added — neither is structural strain, just a reminder that the ordering of `handle` blocks is load-bearing in Caddy and worth a brief comment when the second block lands.
