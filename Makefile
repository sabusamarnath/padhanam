.PHONY: help up down derive-env logs ps psql pull-model smoke-llm scan sbom clean-pyc lint test test-live-llm migrate seed-tenants dogfood-provision dogfood-token dogfood-wipe seed-german seed-get-a-job seed-dogfood-goals pull-tasks sync-calendar dump-calendar-titles correlate-units coverage-report domain-report scheduled-check eval-run eval-report ingest-run ingest-worker neo4j-up neo4j-down neo4j-reset neo4j-shell charter-export

# .env carries the operator-edited values; .env.derived carries values
# computed from padhanam/config/ (currently just LITELLM_OTEL_HEADERS).
# Compose loads both via repeated --env-file flags (later files override
# earlier ones for the same key). Targets that drive compose declare
# derive-env as a prerequisite so .env.derived is always fresh.
COMPOSE := docker compose --env-file .env --env-file .env.derived

help:
	@echo "Padhanam — available targets:"
	@echo "  up          Start the Compose stack (15 services) in the background"
	@echo "  down        Stop the Compose stack"
	@echo "  derive-env  Recompute .env.derived from padhanam/config/ (idempotent)"
	@echo "  logs        Follow logs from all services"
	@echo "  ps          Show service status"
	@echo "  psql        Open a psql shell against the postgres service"
	@echo "  pull-model  Pull the default Ollama model (idempotent; ~4.7GB on first run)"
	@echo "  smoke-llm   End-to-end smoke through LiteLLM: completion + Langfuse trace"
	@echo "  scan        Trivy + pip-audit; gates session-closing commits (D25)"
	@echo "  sbom        Generate SBOM (stub until real Python deps land in S7)"
	@echo "  clean-pyc   Remove all __pycache__ and .pyc so enforcement runs from fresh bytecode"
	@echo "  lint        Run import-linter against the architectural contracts (clears bytecode first)"
	@echo "  test        Run the unit and contract test suites (default tier; excludes live_llm per D99)"
	@echo "  test-live-llm  Run integration tests that exercise real LLM via LiteLLM/Ollama (D99)"
	@echo "  migrate     Apply Alembic migrations: control-plane phase, then per-tenant phase against each registered tenant (D36)"
	@echo "  seed-tenants  Register the test set tenants in the registry; idempotent"
	@echo "  scheduled-check  Run scheduled supply-chain check; writes report to docs/security/scheduled-check-reports/"
	@echo "  eval-run     Run the eval CLI's 'eval run' command inside padhanam-api; pass ARGS=\"--tenant-id a --interaction-set-id <uuid> ...\""
	@echo "  eval-report  Run the eval CLI's 'eval report' command inside padhanam-api; pass ARGS=\"--tenant-id a --baseline-revision-id <uuid> ...\""
	@echo "  ingest-run   Register a source file via the ingest CLI inside padhanam-api; pass ARGS=\"<path-inside-container> --tenant-id a\""
	@echo "  ingest-worker  Run the long-running ingest worker for a tenant inside padhanam-api; pass ARGS=\"--tenant-id a [--max-iterations N]\""
	@echo "  neo4j-up    Start just the padhanam-neo4j service"
	@echo "  neo4j-down  Stop the padhanam-neo4j service (preserves the volume)"
	@echo "  neo4j-reset DESTRUCTIVE — stop padhanam-neo4j and wipe its data volume"
	@echo "  neo4j-shell Open an interactive cypher-shell against padhanam-neo4j"
	@echo "  charter-export  Build the session-close charter snapshot (dir + zip) per docs/charter-archive-manifest.md"

derive-env:
	@uv run python -m ops.derive_env > .env.derived

up: derive-env
	$(COMPOSE) up -d

down: derive-env
	$(COMPOSE) down

logs: derive-env
	$(COMPOSE) logs -f

ps: derive-env
	$(COMPOSE) ps

psql: derive-env
	$(COMPOSE) exec postgres sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

# Pulls the default model resolved from padhanam/config/ (D15, D19). The
# model name flows through InferenceSettings rather than a hardcoded Make
# variable so substituting the default later (or per-profile) is a config
# change, not a Makefile edit. Idempotent: `ollama pull` on a model that
# is already current is a no-op.
pull-model: derive-env
	@chat_model=$$(uv run python -c "from padhanam.config import InferenceSettings; print(InferenceSettings().default_model)") && \
	embed_model=$$(uv run python -c "from padhanam.config import InferenceSettings; print(InferenceSettings().default_embedding_model)") && \
	echo "Pulling chat model $$chat_model into the ollama_data volume (idempotent)..." && \
	$(COMPOSE) exec ollama ollama pull "$$chat_model" && \
	echo "Pulling embedding model $$embed_model into the ollama_data volume (idempotent)..." && \
	$(COMPOSE) exec ollama ollama pull "$$embed_model"

# End-to-end smoke through LiteLLM. Resolves the master key, model, and
# endpoint through padhanam/config/ (D19), then sends a real chat
# completion request and prints the response. The request runs from
# inside the caddy container (which carries wget) so no host-port
# binding is needed for LiteLLM. After the response prints, the operator
# verifies in the Langfuse UI at https://langfuse.localhost/ that the
# trace appears with the GenAI semantic-convention attributes
# (gen_ai.request.model, gen_ai.usage.{input,output,total}_tokens,
# gen_ai.system, gen_ai.response.finish_reasons). Browser interactive
# verification is the acceptance signal (S4 lesson, S6 prompt §5.6).
smoke-llm: derive-env
	@eval "$$(uv run python -m ops.smoke_config | sed 's/^/export /')" && \
	body="{\"model\":\"$$SMOKE_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Say hello in five words.\"}]}" && \
	echo "Smoking LiteLLM ($$SMOKE_MODEL) via internal network..." && \
	$(COMPOSE) exec -T caddy wget -qO- \
		--header="Authorization: Bearer $$SMOKE_KEY" \
		--header="Content-Type: application/json" \
		--post-data="$$body" \
		http://litellm:4000/v1/chat/completions && \
	echo && \
	echo "OK. Verify the trace at $$SMOKE_VERIFY_URL (browser)."

scan:
	@echo "Scanning images..."
	@for img in $$(grep -E '^\s+image:' compose.yaml | awk '{print $$2}'); do \
		echo "Scanning $$img..."; \
		trivy image --scanners vuln --severity CRITICAL,HIGH --exit-code 1 $$img || exit 1; \
	done
	@echo "Scanning Python deps..."
	@if [ -f uv.lock ]; then uv run pip-audit; else echo "(no uv.lock yet, deferred to S7)"; fi

sbom:
	@echo "SBOM generation lands in S7 with first Python deps."
	@exit 0

# Clear Python bytecode before enforcement so a stale .pyc can never
# mask a red contract or carry a pre-rename co_filename into tracebacks
# (the S55a-fix finding: the host-port-binding contract read red only
# from clean bytecode). `pytest -p no:cacheprovider` additionally drops
# pytest's own cache; this target drops the interpreter's __pycache__.
clean-pyc:
	@find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name '*.pyc' -delete 2>/dev/null || true

lint: clean-pyc
	uv run lint-imports
	uv run pytest -p no:cacheprovider tests/_enforcement/

test: clean-pyc
	uv run pytest -p no:cacheprovider

# Live-LLM tier per D99. Default `make test` excludes these via the
# `addopts = -m 'not live_llm'` config in pyproject.toml; this target
# runs them explicitly. Requires the Compose stack up and Ollama
# reachable; tests that find the stack unreachable skip themselves.
test-live-llm:
	uv run pytest -m live_llm

# Apply Alembic migrations against the live control-plane Postgres
# instance (D33), then iterate over registered tenants and apply the
# per-tenant track to each (D36, S11). The orchestrator at
# ops/migrate.py runs the control-plane phase first, then the
# per-tenant phase. Per-tenant transactional: failure on tenant B
# leaves tenant A migrated, retry resumes from tenant B.
#
# Runs from inside the padhanam-api container so the migration script
# can resolve the postgres-control-plane and per-tenant hostnames
# over the Compose network (S5 rule: only Caddy binds host ports).
# The api image vendors alembic + psycopg through the root pyproject's
# runtime deps.
migrate: derive-env
	$(COMPOSE) exec padhanam-api python -m ops.migrate

# Rebuild the padhanam-api image and refresh the digest pin in
# compose.yaml so `docker compose up --force-recreate padhanam-api`
# picks up the new image (S41 methodology line 4 resolution; the
# Dockerfile uses COPY to bake source at build time, and the
# compose.yaml image-digest pin treats the image as immutable, so
# local rebuilds need the digest pin updated each time).
#
# Production-shaped path; use this when verifying against the same
# code path production would exercise. For tighter smoke iteration
# during a session, see `make sync-code`.
build-api:
	@echo "Rebuilding padhanam-api image..."
	@# docker compose build fails when the image: directive carries a
	@# digest (the digest is not a valid build tag); we drive the
	@# build directly via `docker build`, then rewrite the compose
	@# pin to the new content-addressed digest. The S37 smoke used
	@# the same docker build pattern; the S42 smoke surfaced the
	@# compose-build incompatibility in the original target.
	docker build -t padhanam-api:dev -f apps/api/Dockerfile .
	@new_digest=$$(docker image inspect padhanam-api:dev --format '{{.Id}}') && \
		echo "New image digest: $$new_digest" && \
		echo "Updating compose.yaml digest pin..." && \
		sed -i.bak -E "s|padhanam-api:dev@sha256:[a-f0-9]+|padhanam-api:dev@$$new_digest|" compose.yaml && \
		rm -f compose.yaml.bak && \
		echo "Done. Run 'docker compose up -d --force-recreate padhanam-api' to bring it up."

# Sync local source trees into the running padhanam-api container
# without rebuild (S41 methodology line 4 resolution). Dev-only
# fast-path: CLI commands invoked via `docker compose exec
# padhanam-api python -m apps.cli.main ...` create fresh Python
# processes that import from disk, so synced source is picked up
# immediately. The FastAPI server inside the container would still
# require a restart; smoke commands typically invoke CLI not server.
#
# Use this for tight smoke iteration when iterating on a session's
# code; use `make build-api` when verifying against the production-
# shaped image path.
sync-code:
	@echo "Syncing local source into padhanam-api container (dev fast-path)..."
	@$(COMPOSE) cp contexts padhanam-api:/app/
	@$(COMPOSE) cp apps padhanam-api:/app/
	@$(COMPOSE) cp padhanam padhanam-api:/app/
	@$(COMPOSE) cp shared_kernel padhanam-api:/app/
	@$(COMPOSE) cp alembic padhanam-api:/app/
	@echo "Synced. CLI commands pick up changes immediately."

# Register the test set tenants (postgres-tenant-a, postgres-tenant-b)
# in the registry. Idempotent: skips already-registered ids.
# Runs inside padhanam-api so the Compose service hostnames resolve.
seed-tenants: derive-env
	$(COMPOSE) exec padhanam-api python -m ops.seed_tenants

# --- Dogfood personal tenant ([dogfood-setup], D32) -----------------
# Provision the dedicated personal tenant: bring up its Postgres
# container, register it in the control plane (ops.dogfood_provision),
# and migrate it (ops.migrate applies the per-tenant track to every
# registered tenant, idempotent on a/b). Run after `make up`.
dogfood-provision: derive-env
	$(COMPOSE) up -d postgres-tenant-personal
	$(COMPOSE) exec padhanam-api python -m ops.dogfood_provision
	$(COMPOSE) exec padhanam-api python -m ops.migrate

# Mint a dev bearer token for the personal tenant (paste into /app).
dogfood-token: derive-env
	@$(COMPOSE) exec padhanam-api python -c "from padhanam.security.auth import issue_dev_token; print(issue_dev_token(subject='operator-001', tenant_id='00000000-0000-4000-8000-00000000d001', roles=['operator']))"

# Scoped wipe: drop + recreate ONLY the personal tenant's database,
# then re-migrate it. The guard in ops/dogfood_wipe.sh refuses any
# target other than the personal tenant and operates inside the
# postgres-tenant-personal container only (structurally unable to reach
# tenant-a/tenant-b/control-plane). See docs/ops/dogfood-runbook.md.
dogfood-wipe: derive-env
	COMPOSE="$(COMPOSE)" ./ops/dogfood_wipe.sh

# Seed German as the first progressive-cadence goal (S62, D163): a
# German-practice commitment (lever) in the personal tenant's Postgres
# plus the Outcome node + lever-to-outcome edge in the shared graph.
# Idempotent. Run after `make dogfood-provision` and `make migrate`
# (the latter applies migrations/neo4j/0002_outcome_goal.cypher).
seed-german: derive-env
	$(COMPOSE) exec padhanam-api python -m ops.seed_german_goal

# Seed get-a-job as the second goal, a sequence (S63, D163): a chain of
# lever-step commitments in the personal tenant's Postgres plus the Outcome
# node (mode sequence, control influence, subject self, a terminal target)
# + a lever edge per step in the shared graph. Idempotent. Run after
# `make dogfood-provision` and `make migrate`.
seed-get-a-job: derive-env
	$(COMPOSE) exec padhanam-api python -m ops.seed_get_a_job

# Seed the operator's remaining real dogfood goals (S69): strength, marathon,
# voice, stretch/meditate, litany — spec-driven, idempotent. Run with
# seed-german + seed-get-a-job to reach the six-plus goals the dogfood reads.
seed-dogfood-goals: derive-env
	$(COMPOSE) exec padhanam-api python -m ops.seed_dogfood_goals

# Pull Google Tasks for the personal tenant (S65, D167): ensure the
# google-tasks connection then full re-pull into the re-pullable cache.
# Operator-gated: provision the Nango google-tasks integration
# (tasks.readonly) + set TASKS_CONNECTION_REF in .env first. Idempotent.
pull-tasks: derive-env
	$(COMPOSE) exec padhanam-api python -m ops.pull_tasks

# Re-pull the personal tenant's calendar (D159 deployment smoke):
# resolves the google_calendar connection and drives the D150 refresh
# adapter (the D149 scoped full pull, sync_calendar) against live Nango.
# Read-only into the re-pullable meetings cache (D155). Idempotent.
sync-calendar: derive-env
	$(COMPOSE) exec padhanam-api python -m ops.sync_calendar

# Dump distinct calendar meeting titles per connection (S78 → S79 seed
# input): reads meetings through the decrypting MeetingReader (D21),
# groups by calendar_id. Read-only. Capture stdout to a committed artefact.
dump-calendar-titles: derive-env
	$(COMPOSE) exec padhanam-api python -m ops.dump_calendar_titles

# Correlate the personal tenant's work units (S66, D168): read the
# read-only caches (tasks/calendar/email), run the title-and-time
# inference, replace the :Unit/:Facet/SAME_WORK subgraph in Neo4j.
# Idempotent (derived state). Run the cache pulls first so it has input.
correlate-units: derive-env
	$(COMPOSE) exec padhanam-api python -m ops.correlate_units

# Assessment coverage report (S71, D174): read the live graph and print, per
# goal, linked (count + tier) or uncovered; the orphan-unit count; and a sample
# of orphan titles. Read-only — the standing instrument for judging linkage
# changes and the metric the embedding-tier decision waits on. Run after a fresh
# correlate-units.
coverage-report: derive-env
	$(COMPOSE) exec padhanam-api python -m ops.coverage_report

# Commitment-domain resolution report (S82, D179): per-goal domain + the
# corpus before/after + a mis-domain check. Grouped by goal so no medication
# commitment name is printed. Read-only.
domain-report: derive-env
	$(COMPOSE) exec padhanam-api python -m ops.domain_report

# Run the scheduled supply-chain check (D25). Reads
# ops/scheduled_checks.yaml, queries upstream registries (PyPI online,
# Docker Hub manual), writes a Markdown report under
# docs/security/scheduled-check-reports/<today>.md. The operator
# reviews the report and opens digest-bump PRs manually; no auto-PR.
scheduled-check:
	uv run python -m ops.run_scheduled_checks

# S18 eval CLI. Runs from inside the padhanam-api container so per-
# tenant Postgres hostnames resolve over the Compose network and the
# OTel exporter reaches Langfuse on the in-network address. Pass the
# CLI arguments via ARGS, e.g.
#   make eval-run ARGS="--tenant-id a --interaction-set-id <uuid> \
#                       --scoring-sheet-revision-id <uuid>"
eval-run: derive-env
	$(COMPOSE) exec padhanam-api python -m apps.cli eval run $(ARGS)

eval-report: derive-env
	$(COMPOSE) exec padhanam-api python -m apps.cli eval report $(ARGS)

# S19 ingest CLI. Same in-container invocation pattern as the eval
# commands: per-tenant Postgres hostnames resolve over the Compose
# network. ingest-run registers a source file (the file path is
# inside the container — usually a /tmp/... path the test fixture
# wrote, or /app/... for source-tree files). ingest-worker drains
# the tenant's pending-source queue. Pass the CLI arguments via ARGS,
# e.g.
#   make ingest-run ARGS="/tmp/sample.md --tenant-id a"
#   make ingest-worker ARGS="--tenant-id a --max-iterations 5"
ingest-run: derive-env
	$(COMPOSE) exec padhanam-api python -m apps.cli ingest run $(ARGS)

ingest-worker: derive-env
	$(COMPOSE) exec padhanam-api python -m apps.cli ingest worker $(ARGS)

# S21 Neo4j convenience targets (D63). The shared Neo4j 5 Community
# instance is part of the standard `make up` flow; these targets are
# for the operator who wants to bring just the graph store up/down or
# wipe its data volume during dev iteration.
neo4j-up: derive-env
	$(COMPOSE) up -d padhanam-neo4j

neo4j-down: derive-env
	$(COMPOSE) stop padhanam-neo4j

# DESTRUCTIVE: wipes the named volume. Use only when the dev graph
# state is actually wrong; operator-affirmative-action target.
neo4j-reset: derive-env
	$(COMPOSE) stop padhanam-neo4j
	$(COMPOSE) rm -f padhanam-neo4j
	docker volume rm $$(docker compose --env-file .env --env-file .env.derived ls --format json | python -c "import json,sys; sys.stdout.write(json.load(sys.stdin)[0]['Name'])")_neo4j_data || true
	$(COMPOSE) up -d padhanam-neo4j

# Interactive cypher-shell against the running padhanam-neo4j
# container. The credentials resolve from the host .env (loaded into
# the shell via the existing Compose env-file plumbing on COMPOSE).
neo4j-shell: derive-env
	$(COMPOSE) exec padhanam-neo4j cypher-shell -u $${NEO4J_USER:-neo4j} -p $${NEO4J_PASSWORD}

# Session-close charter snapshot. Flattens the allowlisted charter surface
# into charter-YYYYMMDD-HHMM/ plus the matching .zip at the repo root (both
# git-ignored). The file set is governed by docs/charter-archive-manifest.md
# — the script reads that manifest as its single source of truth and never
# globs. The operator uploads the zip to the Claude.ai project mirror so
# strategic-mode conversations have the charter as searchable knowledge.
# Run `uv run python scripts/charter-export.py --dry-run` to preview the
# source -> snapshot mapping without writing anything.
charter-export:
	uv run python scripts/charter-export.py
