.PHONY: help up down derive-env logs ps psql pull-model scan sbom lint test

# .env carries the operator-edited values; .env.derived carries values
# computed from vadakkan/config/ (currently just LITELLM_OTEL_HEADERS).
# Compose loads both via repeated --env-file flags (later files override
# earlier ones for the same key). Targets that drive compose declare
# derive-env as a prerequisite so .env.derived is always fresh.
COMPOSE := docker compose --env-file .env --env-file .env.derived

help:
	@echo "Meridian — available targets:"
	@echo "  up          Start the Compose stack (10 services) in the background"
	@echo "  down        Stop the Compose stack"
	@echo "  derive-env  Recompute .env.derived from vadakkan/config/ (idempotent)"
	@echo "  logs        Follow logs from all services"
	@echo "  ps          Show service status"
	@echo "  psql        Open a psql shell against the postgres service"
	@echo "  pull-model  Pull the default Ollama model (idempotent; ~4.7GB on first run)"
	@echo "  scan        Trivy + pip-audit; gates session-closing commits (D25)"
	@echo "  sbom        Generate SBOM (stub until real Python deps land in S7)"
	@echo "  lint        Run import-linter against the architectural contracts"
	@echo "  test        Run the unit and contract test suites"

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

# Pulls the default model resolved from vadakkan/config/ (D15, D19). The
# model name flows through InferenceSettings rather than a hardcoded Make
# variable so substituting the default later (or per-profile) is a config
# change, not a Makefile edit. Idempotent: `ollama pull` on a model that
# is already current is a no-op.
pull-model: derive-env
	@model=$$(uv run python -c "from vadakkan.config import InferenceSettings; print(InferenceSettings().default_model)") && \
	echo "Pulling $$model into the ollama_data volume (idempotent)..." && \
	$(COMPOSE) exec ollama ollama pull "$$model"

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

lint:
	uv run lint-imports

test:
	uv run pytest
