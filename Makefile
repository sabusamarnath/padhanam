.PHONY: help up down logs ps psql scan sbom lint test

help:
	@echo "Meridian — available targets:"
	@echo "  up    Start the Compose stack (postgres, redis, caddy, langfuse) in the background"
	@echo "  down  Stop the Compose stack"
	@echo "  logs  Follow logs from all services"
	@echo "  ps    Show service status"
	@echo "  psql  Open a psql shell against the postgres service"
	@echo "  scan  Trivy + pip-audit; gates session-closing commits (D25)"
	@echo "  sbom  Generate SBOM (stub until real Python deps land in S7)"
	@echo "  lint  Run import-linter against the architectural contracts"
	@echo "  test  Run the unit and contract test suites"

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

psql:
	docker compose exec postgres sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

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
