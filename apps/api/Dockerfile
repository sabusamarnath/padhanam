# syntax=docker/dockerfile:1.7
#
# Padhanam FastAPI image. Multi-stage so the final image carries only
# the runtime venv + source, not the build toolchain. Pinned upstream
# digest is enforced in compose.yaml; the FROM here uses the floating
# tag so the digest pin lives in one place (S5 pattern).
#
# Build: docker build -f apps/api/Dockerfile -t padhanam-api:dev .
# (run from the repo root; uv.lock and pyproject.toml live there)

FROM python:3.14-slim AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# Install uv from its official image; pinning the version here keeps
# the build reproducible across rebuilds within a session.
COPY --from=ghcr.io/astral-sh/uv:0.5.0 /uv /usr/local/bin/uv

WORKDIR /app

# Copy lockfile and pyprojects first so dependency layers cache across
# source changes. The workspace topology (D30) means uv resolves the
# whole graph from these files alone.
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml ./apps/api/
COPY contexts/inference/pyproject.toml ./contexts/inference/
COPY contexts/observability/pyproject.toml ./contexts/observability/
COPY contexts/audit/pyproject.toml ./contexts/audit/
COPY contexts/tenancy/pyproject.toml ./contexts/tenancy/

RUN uv sync --frozen --no-dev --no-install-project

# Copy the source and finalise the install. --no-dev ships a runtime
# venv only; tests and lint tooling stay out of the image.
COPY padhanam ./padhanam
COPY shared_kernel ./shared_kernel
COPY contexts ./contexts
COPY apps ./apps
# Alembic config + migration scripts (D34). Operator invokes the
# control-plane track via `docker compose exec`; the binary and the
# script tree both need to be inside the image because the Postgres
# instances only resolve on the Compose network (S5 host-port-binding
# rule). S11 grows the per-tenant track here too (D36).
COPY alembic.ini ./
COPY alembic ./alembic
# ops/ scripts. S11 (D36) introduces ops.seed_tenants and ops.migrate
# which `make seed-tenants` and `make migrate` invoke as `python -m
# ops.<name>` inside this container so per-tenant Compose hostnames
# resolve.
COPY ops ./ops
RUN uv sync --frozen --no-dev


FROM python:3.14-slim AS runtime

# Run as a non-root user. UID 1000 is the conventional first non-root
# UID and matches the image's expectation when bind-mounting a volume.
RUN useradd --create-home --uid 1000 padhanam

WORKDIR /app

COPY --from=builder --chown=padhanam:padhanam /opt/venv /opt/venv
COPY --from=builder --chown=padhanam:padhanam /app /app

# logs/ is the default directory for security_events.py. Pre-create it
# with the right ownership so the non-root user can write
# logs/security.jsonl (D26) at runtime.
RUN mkdir -p /app/logs && chown padhanam:padhanam /app/logs

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER padhanam

EXPOSE 8000

# Healthcheck via the public /health route that bypasses auth. urllib
# is in the stdlib so no extra package needed in the image.
HEALTHCHECK --interval=10s --timeout=5s --retries=6 --start-period=15s \
    CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8000/health'); sys.exit(0)" || exit 1

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
