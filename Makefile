.PHONY: help up down derive-env logs ps psql pull-model smoke-llm scan sbom lint test

# .env carries the operator-edited values; .env.derived carries values
# computed from vadakkan/config/ (currently just LITELLM_OTEL_HEADERS).
# Compose loads both via repeated --env-file flags (later files override
# earlier ones for the same key). Targets that drive compose declare
# derive-env as a prerequisite so .env.derived is always fresh.
COMPOSE := docker compose --env-file .env --env-file .env.derived

help:
	@echo "Vadakkan — available targets:"
	@echo "  up          Start the Compose stack (10 services) in the background"
	@echo "  down        Stop the Compose stack"
	@echo "  derive-env  Recompute .env.derived from vadakkan/config/ (idempotent)"
	@echo "  logs        Follow logs from all services"
	@echo "  ps          Show service status"
	@echo "  psql        Open a psql shell against the postgres service"
	@echo "  pull-model  Pull the default Ollama model (idempotent; ~4.7GB on first run)"
	@echo "  smoke-llm   End-to-end smoke through LiteLLM: completion + Langfuse trace"
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

# End-to-end smoke through LiteLLM. Resolves the master key, model, and
# endpoint through vadakkan/config/ (D19), then sends a real chat
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

lint:
	uv run lint-imports

test:
	uv run pytest
