.PHONY: help up down logs ps psql

help:
	@echo "Meridian — available targets:"
	@echo "  up    Start the Compose stack in the background"
	@echo "  down  Stop the Compose stack"
	@echo "  logs  Follow logs from all services"
	@echo "  ps    Show service status"
	@echo "  psql  Open a psql shell against the postgres service"

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
