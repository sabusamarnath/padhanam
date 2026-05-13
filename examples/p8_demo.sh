#!/usr/bin/env bash
# P8 close demo orchestration (S30b).
#
# Drives two end-to-end agent runs against the live stack to exercise
# the S29b streaming runtime + S30b CLI substrate in product form.
#
#   1. Flowstate-McKinsey ProblemFramer on tenant alpha (label "a")
#      producing a SMART problem statement (narrow artifact).
#   2. Forgepath-LVT LVTGuide on tenant beta (label "b") producing a
#      full Lean Value Tree (broad artifact).
#
# Different tenants exercise the principal-derived tenant resolution
# path for both invocations.
#
# Pre-requisites:
#   - padhanam-api container running and rebuilt to the post-S28b image.
#   - Six Flowstate markdown files at examples/sources/flowstate/:
#     01_ceo_memo.md, 02_analyst_brief.md, 03_customer_interviews.md,
#     04_sales_sync_notes.md, 05_internal_metrics.md,
#     06_competitive_intel.md.
#   - Seven Forgepath markdown files at examples/sources/forgepath/:
#     01_ceo_pre_read.md, 02_market_landscape.md, 03_customer_segments.md,
#     04_financial_model.md, 05_org_design_notes.md, 06_prior_strategy.md,
#     07_initiative_inventory.md.
#   - McKinsey 7-Step methodology and LVT methodology authored on the
#     control plane (seeded by Alembic migrations 0007 and 0008).
#
# The script does not check in agent IDs (per-tenant database state
# varies). Outputs land at demos/p8_flowstate_output.md and
# demos/p8_forgepath_output.md (unstaged).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

mkdir -p demos

FLOWSTATE_CONFIG="$(mktemp -t flowstate-agent.json.XXXXXX)"
FORGEPATH_CONFIG="$(mktemp -t forgepath-agent.json.XXXXXX)"
trap 'rm -f "$FLOWSTATE_CONFIG" "$FORGEPATH_CONFIG"' EXIT

# --- Helpers --------------------------------------------------------

# Run a padhanam CLI command inside the padhanam-api container.
padhanam() {
    docker compose exec -T padhanam-api python -m apps.cli "$@"
}

# Look up a methodology id by exact name match.
methodology_id_by_name() {
    local name="$1"
    padhanam methodology list --json \
        | python3 -c "
import json, sys
target = sys.argv[1]
items = json.load(sys.stdin)
for item in items:
    if item['name'] == target:
        print(item['id'])
        sys.exit(0)
sys.exit('methodology not found: ' + target)
" "$name"
}

# Ingest a single source file into a tenant and emit the source UUID.
ingest_source() {
    local tenant_label="$1"
    local file_path="$2"
    padhanam ingest run "$file_path" --tenant-id "$tenant_label" \
        | tr -d '\r\n'
}

# Drain the ingest worker bounded to a few iterations so the freshly
# registered sources flow through parse → embed → extract to reach
# the indexed state retrieval gates on.
drain_ingest_worker() {
    local tenant_label="$1"
    local iterations="${2:-60}"
    padhanam ingest worker \
        --tenant-id "$tenant_label" \
        --max-iterations "$iterations" \
        --poll-interval-seconds 0.5
}

# Build a create-from-methodology config JSON from a methodology UUID,
# a display name, and a bash array of source UUIDs.
write_agent_config() {
    local config_path="$1"
    local methodology_id="$2"
    local agent_name="$3"
    shift 3
    local source_ids=("$@")
    METHODOLOGY_ID="$methodology_id" \
    AGENT_NAME="$agent_name" \
    SOURCE_IDS_JSON="$(printf '%s\n' "${source_ids[@]}" \
        | python3 -c "import json,sys; print(json.dumps([line.strip() for line in sys.stdin if line.strip()]))")" \
    python3 - <<'PY' > "$config_path"
import json
import os
print(json.dumps({
    "methodology_template_id": os.environ["METHODOLOGY_ID"],
    "name": os.environ["AGENT_NAME"],
    "source_ids": json.loads(os.environ["SOURCE_IDS_JSON"]),
}, indent=2))
PY
}

# Extract the agent_template_id UUID from a create-from-methodology
# CLI output line.
parse_agent_id() {
    grep -oE 'agent_template_id=[0-9a-f-]+' \
        | head -1 \
        | cut -d= -f2
}

# --- 1. Discover platform-managed methodology IDs -------------------

echo "[discover] methodology IDs"
MCKINSEY_ID="$(methodology_id_by_name 'McKinsey 7-Step')"
LVT_ID="$(methodology_id_by_name 'LVT')"
echo "  McKinsey 7-Step: $MCKINSEY_ID"
echo "  LVT:             $LVT_ID"

# --- 2. Ingest Flowstate pack into tenant alpha ---------------------

echo
echo "[ingest] Flowstate pack into tenant alpha (label 'a')"
FLOWSTATE_SOURCE_IDS=()
for file in \
    examples/sources/flowstate/01_ceo_memo.md \
    examples/sources/flowstate/02_analyst_brief.md \
    examples/sources/flowstate/03_customer_interviews.md \
    examples/sources/flowstate/04_sales_sync_notes.md \
    examples/sources/flowstate/05_internal_metrics.md \
    examples/sources/flowstate/06_competitive_intel.md
do
    source_id="$(ingest_source a "$file")"
    FLOWSTATE_SOURCE_IDS+=("$source_id")
    echo "  $file -> $source_id"
done

echo
echo "[drain] tenant alpha worker to indexed state"
drain_ingest_worker a 60

# --- 3. Ingest Forgepath pack into tenant beta ----------------------

echo
echo "[ingest] Forgepath pack into tenant beta (label 'b')"
FORGEPATH_SOURCE_IDS=()
for file in \
    examples/sources/forgepath/01_ceo_pre_read.md \
    examples/sources/forgepath/02_market_landscape.md \
    examples/sources/forgepath/03_customer_segments.md \
    examples/sources/forgepath/04_financial_model.md \
    examples/sources/forgepath/05_org_design_notes.md \
    examples/sources/forgepath/06_prior_strategy.md \
    examples/sources/forgepath/07_initiative_inventory.md
do
    source_id="$(ingest_source b "$file")"
    FORGEPATH_SOURCE_IDS+=("$source_id")
    echo "  $file -> $source_id"
done

echo
echo "[drain] tenant beta worker to indexed state"
drain_ingest_worker b 70

# --- 4. Create the Flowstate-McKinsey agent on tenant alpha ---------
# create-from-methodology picks role_refs[0] (ProblemFramer) per the
# Phase-1 single-role-per-methodology commitment in D88.

echo
echo "[create] Flowstate-McKinsey ProblemFramer agent on tenant alpha"
write_agent_config \
    "$FLOWSTATE_CONFIG" \
    "$MCKINSEY_ID" \
    "Flowstate ProblemFramer (S30b demo)" \
    "${FLOWSTATE_SOURCE_IDS[@]}"
FLOWSTATE_AGENT_ID="$(padhanam agent create-from-methodology \
    --tenant a \
    --config "$FLOWSTATE_CONFIG" | tee /dev/stderr | parse_agent_id)"
echo "  agent_id: $FLOWSTATE_AGENT_ID"

# --- 5. Create the Forgepath-LVT agent on tenant beta ---------------

echo
echo "[create] Forgepath-LVT LVTGuide agent on tenant beta"
write_agent_config \
    "$FORGEPATH_CONFIG" \
    "$LVT_ID" \
    "Forgepath LVTGuide (S30b demo)" \
    "${FORGEPATH_SOURCE_IDS[@]}"
FORGEPATH_AGENT_ID="$(padhanam agent create-from-methodology \
    --tenant b \
    --config "$FORGEPATH_CONFIG" | tee /dev/stderr | parse_agent_id)"
echo "  agent_id: $FORGEPATH_AGENT_ID"

# --- 6. Run the Flowstate demo --------------------------------------

echo
echo "[run] Flowstate-McKinsey ProblemFramer demo"
FLOWSTATE_INPUT="$(cat examples/sources/flowstate/_input.txt)"
padhanam agent run \
    --tenant a \
    --agent "$FLOWSTATE_AGENT_ID" \
    --input "$FLOWSTATE_INPUT" \
    --output-file demos/p8_flowstate_output.md
echo "  output: demos/p8_flowstate_output.md"

# --- 7. Run the Forgepath demo --------------------------------------

echo
echo "[run] Forgepath-LVT LVTGuide demo"
FORGEPATH_INPUT="$(cat examples/sources/forgepath/_input.txt)"
padhanam agent run \
    --tenant b \
    --agent "$FORGEPATH_AGENT_ID" \
    --input "$FORGEPATH_INPUT" \
    --output-file demos/p8_forgepath_output.md
echo "  output: demos/p8_forgepath_output.md"

echo
echo "[done] demo outputs captured at demos/p8_flowstate_output.md and demos/p8_forgepath_output.md"
