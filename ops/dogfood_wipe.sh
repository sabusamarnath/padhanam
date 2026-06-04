#!/usr/bin/env bash
#
# dogfood_wipe.sh — scoped wipe of the personal dogfooding tenant only.
# [dogfood-setup], D32. Drops and recreates ONLY the personal tenant's
# database, then re-migrates it.
#
# The guard is the load-bearing part. Three independent layers make it
# structurally unable to touch tenant-a, tenant-b, or the control plane:
#
#   1. Container boundary. Every destructive statement runs *inside* the
#      `postgres-tenant-personal` container via `compose exec`. That
#      container's psql can only reach its own local Postgres, so even a
#      wrong database name could not affect another tenant's instance.
#   2. Hardcoded target. SERVICE and LABEL are fixed to the personal
#      tenant; an argument is accepted only to *re-confirm* it, never to
#      redirect the wipe.
#   3. Refuse-list. The resolved service/db are checked against the
#      tenant-a/tenant-b/control-plane names; any match aborts before
#      anything runs (defends against a tampered .env).
#
# Out of scope (named, deferred with the personal-graph isolation entry
# in charter/deferred-decisions.md): the Neo4j delete-by-tenant-property
# and the Langfuse trace clear. Not needed today — the daily driver is
# Postgres-only — but a *complete* wipe will need them once personal data
# reaches the graph store and conversational cells capture prompts.
set -euo pipefail

# --- fixed target (never overridable to another tenant) ---------------
readonly SERVICE="postgres-tenant-personal"
readonly LABEL="personal"
DB="${POSTGRES_TENANT_PERSONAL_DB:-tenant_personal}"
USER="${POSTGRES_TENANT_PERSONAL_USER:-tenant_personal}"
COMPOSE="${COMPOSE:-docker compose --env-file .env --env-file .env.derived}"

# --- layer 3: refuse-list (defends against tampered env) --------------
readonly FORBIDDEN_DBS="tenant_a tenant_b control_plane postgres"
readonly FORBIDDEN_SERVICES="postgres-tenant-a postgres-tenant-b postgres-control-plane postgres"

# --- layer 2: an argument may only re-confirm the personal label ------
if [ "$#" -gt 0 ] && [ "$1" != "$LABEL" ]; then
  echo "REFUSED: dogfood_wipe only wipes the '$LABEL' tenant; got '$1'." >&2
  echo "         It cannot target tenant-a, tenant-b, or the control plane." >&2
  exit 1
fi

for f in $FORBIDDEN_SERVICES; do
  if [ "$SERVICE" = "$f" ]; then
    echo "REFUSED: target service '$SERVICE' is a protected instance." >&2
    exit 1
  fi
done
for f in $FORBIDDEN_DBS; do
  if [ "$DB" = "$f" ]; then
    echo "REFUSED: resolved personal DB name is '$DB', a protected database." >&2
    echo "         Check POSTGRES_TENANT_PERSONAL_DB in .env — it must NOT be a/b/control." >&2
    exit 1
  fi
done

# --- confirmation -----------------------------------------------------
echo "About to WIPE the personal dogfooding tenant:"
echo "    container : $SERVICE  (isolated; cannot reach a/b/control)"
echo "    database  : $DB  (DROP + CREATE)"
echo "    then      : re-migrate (per-tenant track through latest)"
echo "Tenant-a, tenant-b, and the control plane are NOT touched."
echo
if [ -t 0 ]; then
  read -r -p "Type 'wipe ${LABEL}' to proceed: " reply
  if [ "$reply" != "wipe ${LABEL}" ]; then
    echo "Aborted." >&2
    exit 1
  fi
else
  if [ "${DOGFOOD_WIPE_CONFIRM:-}" != "yes" ]; then
    echo "Non-interactive: set DOGFOOD_WIPE_CONFIRM=yes to proceed. Aborted." >&2
    exit 1
  fi
fi

# --- layer 1: destructive work runs INSIDE the personal container -----
echo "==> dropping and recreating database '$DB' inside '$SERVICE'..."
$COMPOSE exec -T "$SERVICE" psql -U "$USER" -d postgres -v ON_ERROR_STOP=1 -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB' AND pid <> pg_backend_pid();" >/dev/null
$COMPOSE exec -T "$SERVICE" psql -U "$USER" -d postgres -v ON_ERROR_STOP=1 -c \
  "DROP DATABASE IF EXISTS \"$DB\";"
$COMPOSE exec -T "$SERVICE" psql -U "$USER" -d postgres -v ON_ERROR_STOP=1 -c \
  "CREATE DATABASE \"$DB\";"

echo "==> re-migrating registered tenants (personal gets a fresh schema; a/b idempotent)..."
$COMPOSE exec -T padhanam-api python -m ops.migrate

echo "==> done. The personal tenant is wiped clean and re-migrated."
