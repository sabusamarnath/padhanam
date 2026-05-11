"""End-to-end test for the clone-from-methodology flow (S25 / D79).

Exercises the full operator workflow against the live Compose stack:

  1. Create LVT methodology on control-plane Postgres.
  2. Ingest two test markdown source files for tenant alpha.
  3. Drain the ingest worker until both sources reach indexed state.
  4. Create a PM agent cloned from LVT with the indexed sources
     attached.
  5. Assert lineage fields populate paired (template_id + version);
     revision 1 content matches LVT defaults; source_ids match.
  6. Update the agent (top_k 8 → 12) and capture revision 2.
  7. Assert revision 2's hash chains correctly from revision 1.
  8. Assert the methodology template is unchanged after the agent's
     edits (single revision; no clone-back propagation per D68).
  9. Cleanup: archive agent, retire methodology, drop test sources.

The test runs CLI commands inside the padhanam-api container via
``docker compose exec`` so per-tenant Postgres hostnames resolve
over the Compose network — same pattern as the existing
tests/integration/contexts/ingestion/test_ingest_e2e.py.

Skip-on-unreachable behaviour: the test skips cleanly when Docker
is not available, when the Compose services are not running, or
when the LiteLLM / Ollama / Neo4j services needed by the worker
are not responsive. The worker drain step is the most failure-
sensitive step because it depends on the full pipeline (parse +
embed + extract); the test reports a precise skip reason rather
than failing on infrastructure absence.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time

import pytest


_TENANT_LABEL = "a"
_AGENT_TEMPLATE_ID_RE = re.compile(
    r"created agent_template_id=([0-9a-f-]+)"
)
_AGENT_REVISION_RE = re.compile(
    r"revision_id=([0-9a-f-]+) version=(\d+)"
)
_METHODOLOGY_TEMPLATE_ID_RE = re.compile(
    r"created methodology_template_id=([0-9a-f-]+)"
)
_GENESIS_REVISION_HASH = "0" * 64


# ---------------------------------------------------------------------
# Compose / docker helpers (mirrors test_ingest_e2e.py conventions)
# ---------------------------------------------------------------------


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        subprocess.run(
            ["docker", "compose", "ps", "-q"],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return False
    return True


@pytest.fixture(scope="module")
def compose_running() -> None:
    """Skip when the Compose services the flow depends on are not running.

    The flow needs:
      - padhanam-api (host for the CLI invocations)
      - postgres-control-plane (methodology storage)
      - postgres-tenant-a (sources, chunks, agent storage)
      - litellm + ollama (embedding stage)
      - padhanam-neo4j (extraction stage)
    """
    if not _docker_available():
        pytest.skip("docker compose not reachable from test environment")
    services = subprocess.run(
        ["docker", "compose", "ps", "--services", "--filter", "status=running"],
        capture_output=True,
        text=True,
        check=False,
    )
    running = set(services.stdout.split())
    needed = {
        "padhanam-api",
        "postgres-control-plane",
        "postgres-tenant-a",
        "litellm",
        "ollama",
        "padhanam-neo4j",
    }
    missing = needed - running
    if missing:
        pytest.skip(f"compose services not running: {sorted(missing)}")


def _exec(*cmd: str, check: bool = True, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    full = ["docker", "compose", "exec", "-T", *cmd]
    return subprocess.run(
        full, capture_output=True, text=True, timeout=timeout, check=check
    )


def _exec_psql_tenant(label: str, query: str) -> str:
    cmd = (
        'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "'
        + query.replace('"', '\\"')
        + '"'
    )
    result = _exec("postgres-tenant-" + label, "sh", "-c", cmd)
    return result.stdout.strip()


def _exec_psql_control_plane(query: str) -> str:
    cmd = (
        'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "'
        + query.replace('"', '\\"')
        + '"'
    )
    result = _exec("postgres-control-plane", "sh", "-c", cmd)
    return result.stdout.strip()


def _truncate_ingestion(label: str) -> None:
    _exec_psql_tenant(label, "TRUNCATE TABLE chunks, sources;")


def _truncate_agents(label: str) -> None:
    _exec_psql_tenant(
        label, "TRUNCATE TABLE agent_revisions, agent_templates;"
    )


def _truncate_methodology() -> None:
    _exec_psql_control_plane(
        "TRUNCATE TABLE methodology_revisions, methodology_templates;"
    )


def _write_file_in_container(path: str, content: str) -> None:
    proc = subprocess.Popen(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "padhanam-api",
            "sh",
            "-c",
            f"cat > {path}",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out, err = proc.communicate(input=content.encode("utf-8"), timeout=10)
    if proc.returncode != 0:
        raise RuntimeError(
            f"failed to write {path} in container: stderr={err!r} stdout={out!r}"
        )


# ---------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------


def _padhanam(*args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    """Invoke ``python -m apps.cli.main`` inside padhanam-api."""
    return _exec("padhanam-api", "python", "-m", "apps.cli.main", *args, timeout=timeout)


def _create_lvt_methodology(*, system_prompt: str) -> str:
    """Write the LVT methodology config inside the container and run
    `methodology create`. Returns the new template_id."""
    config_path = "/tmp/lvt-methodology.yaml"
    description = (
        "Lean Value Tree methodology assistant: locates work in the "
        "bet->initiative->epic->story hierarchy, checks alignment "
        "upward and decomposition downward, surfaces drift between "
        "strategic intent and execution."
    )
    config = (
        "name: LVT\n"
        f"description: {json.dumps(description)}\n"
        f"system_prompt: {json.dumps(system_prompt)}\n"
        "source_ids: []\n"
        "tool_allowlist: []\n"
        "retrieval_strategy:\n"
        "  strategy: hybrid\n"
        "  params: {}\n"
        "filter_tree:\n"
        "  node: {}\n"
        "top_k: 8\n"
        "min_score: 0.3\n"
        "model_selection: qwen2.5:7b\n"
    )
    _write_file_in_container(config_path, config)
    result = _padhanam("methodology", "create", "--config", config_path)
    assert result.returncode == 0, result.stderr or result.stdout
    match = _METHODOLOGY_TEMPLATE_ID_RE.search(result.stdout)
    assert match is not None, f"unexpected output: {result.stdout!r}"
    return match.group(1)


def _ingest_source(*, tenant_label: str, file_path: str, body: str) -> None:
    """Write a markdown file inside the container and register it."""
    _write_file_in_container(file_path, body)
    result = _padhanam(
        "ingest", "run", file_path, "--tenant-id", tenant_label
    )
    assert result.returncode == 0, result.stderr or result.stdout


def _drain_worker_until_indexed(*, tenant_label: str, expected_sources: int, max_iterations: int = 40) -> None:
    """Run the worker repeatedly until all sources reach 'indexed' state.

    Each ingest worker invocation processes a single stage transition
    per claimed source; the full pipeline needs three transitions per
    source (parse → embed → extract). For two sources that's six
    transitions; the iteration bound allows margin for retries.
    """
    deadline_iterations = max_iterations
    for _ in range(deadline_iterations):
        result = _padhanam(
            "ingest", "worker",
            "--tenant-id", tenant_label,
            "--max-iterations", "1",
            "--poll-interval-seconds", "0.5",
            timeout=180,
        )
        # The worker exits 0 normally; a non-zero exit suggests
        # infrastructure failure.
        if result.returncode != 0:
            raise RuntimeError(
                f"ingest worker failed: rc={result.returncode}, "
                f"stdout={result.stdout!r}, stderr={result.stderr!r}"
            )
        # Check progress via direct SQL.
        count = _exec_psql_tenant(
            tenant_label,
            "SELECT count(*) FROM sources WHERE state = 'indexed';",
        )
        if int(count) >= expected_sources:
            return
        time.sleep(0.5)
    raise RuntimeError(
        f"worker did not reach indexed state for {expected_sources} sources "
        f"within {deadline_iterations} iterations"
    )


def _get_source_ids_in_state(*, tenant_label: str, state: str) -> list[str]:
    result = _exec_psql_tenant(
        tenant_label, f"SELECT id FROM sources WHERE state = '{state}' ORDER BY created_at;"
    )
    if not result:
        return []
    return [line.strip() for line in result.splitlines() if line.strip()]


# ---------------------------------------------------------------------
# The e2e flow
# ---------------------------------------------------------------------


_LVT_SYSTEM_PROMPT = (
    "You are an LVT (Lean Value Tree) methodology assistant. LVT structures "
    "product strategy as a four-level hierarchy: bet, initiative, epic, story. "
    "Each level cascades strategic intent downward and aggregates evidence upward.\n\n"
    "Your role is to help users place work in the right level of the tree, "
    "identify when a level is misaligned with the level above, and surface drift "
    "between strategic intent and execution.\n\n"
    "When a user describes work, locate it in the tree first.\n\n"
    "A bet is a load-bearing strategic claim with named test conditions and "
    "falsifiable success criteria. Bets answer \\\"what proposition are we testing "
    "in the market?\\\"\n\n"
    "An initiative is a coherent body of work aligned with one bet's success "
    "criteria. Initiatives answer \\\"what concrete arc do we ship to test the "
    "bet?\\\"\n\n"
    "An epic is a shippable scope within an initiative that produces measurable "
    "outcomes. Epics answer \\\"what ships, and how do we know it worked?\\\"\n\n"
    "A story is the smallest unit of value within an epic. Stories answer \\\"what "
    "does the team do this week?\\\"\n\n"
    "When asked to assess work, locate it first, then check alignment upward "
    "(does this epic actually serve its initiative? does this initiative actually "
    "test its bet?) and decomposition downward (does this initiative break into "
    "shippable epics? do the stories aggregate to the epic's outcomes?).\n\n"
    "Push back on weak placements. A bet without falsifiable success criteria is "
    "a vision statement. An initiative without measurable outcomes is a roadmap "
    "header. An epic without shippable scope is a wish. A story without "
    "acceptance criteria is a task.\n\n"
    "Use the source materials attached to this agent for the user's specific "
    "bet, initiatives, epics, and stories. Cite specific source content when "
    "grounding assessments. When source materials contradict each other, surface "
    "the contradiction rather than papering over it.\n\n"
    "Your output is recommendation-shaped: name the placement, name the alignment "
    "status, name the gap, recommend a next step. End with a position, not a menu."
)


@pytest.fixture
def clean_state(compose_running):  # noqa: ARG001
    _truncate_ingestion(_TENANT_LABEL)
    _truncate_agents(_TENANT_LABEL)
    _truncate_methodology()
    yield
    _truncate_ingestion(_TENANT_LABEL)
    _truncate_agents(_TENANT_LABEL)
    _truncate_methodology()


@pytest.mark.skip(
    reason=(
        "S26a-1 (D86) refactored methodology to role_refs; methodology CLI "
        "no longer accepts the constraint bundle directly. Restoring this "
        "full clone-and-edit e2e against the new shape requires the "
        "`padhanam role` CLI namespace (S26a-2) so an operator can author "
        "a role via CLI before authoring the methodology that references it. "
        "S26a-1 commit 4 lands a focused LVT round-trip e2e that exercises "
        "the methodology→role resolution end-to-end via the agent flow."
    )
)
def test_full_clone_and_edit_flow_against_live_stack(clean_state, tmp_path) -> None:  # noqa: ARG001
    """End-to-end exercise: methodology create → sources ingest →
    sources drain to indexed → clone agent → assert lineage and
    content → update agent → assert hash chain advances → assert
    methodology unchanged → cleanup.

    Each step uses the production CLI surface so the test catches
    drift between the unit/integration tests' in-memory fakes and
    the real adapter behaviour against the live data planes.
    """
    # 1. Create LVT methodology on control plane.
    methodology_id = _create_lvt_methodology(system_prompt=_LVT_SYSTEM_PROMPT)

    # 2. Ingest two markdown sources for tenant alpha.
    bodies = [
        (
            "# Bet 1\n\n"
            "We bet that procurement-grade architectural discipline is "
            "demonstrable through AI-assisted implementation.\n"
        ),
        (
            "# Initiative A\n\n"
            "Phase 1 ships the substrate that proves the bet. Twelve "
            "packages, each with measurable outcomes.\n"
        ),
    ]
    for i, body in enumerate(bodies):
        _ingest_source(
            tenant_label=_TENANT_LABEL,
            file_path=f"/tmp/s25-source-{i}.md",
            body=body,
        )

    # 3. Drain worker until both sources reach indexed.
    _drain_worker_until_indexed(
        tenant_label=_TENANT_LABEL,
        expected_sources=2,
        max_iterations=40,
    )

    # 4. Pull the indexed source ids.
    source_ids = _get_source_ids_in_state(
        tenant_label=_TENANT_LABEL, state="indexed"
    )
    assert len(source_ids) == 2, source_ids

    # 5. Clone the agent.
    clone_config_path = "/tmp/lvt-pm-agent-clone.yaml"
    clone_config = (
        f"methodology_template_id: {methodology_id}\n"
        "methodology_version: null\n"
        "name: LVT PM Agent\n"
        "source_ids:\n"
        + "".join(f"  - {sid}\n" for sid in source_ids)
    )
    _write_file_in_container(clone_config_path, clone_config)
    clone_result = _padhanam(
        "agent", "create-from-methodology",
        "--tenant", _TENANT_LABEL,
        "--config", clone_config_path,
    )
    assert clone_result.returncode == 0, clone_result.stderr or clone_result.stdout
    agent_match = _AGENT_TEMPLATE_ID_RE.search(clone_result.stdout)
    assert agent_match is not None, clone_result.stdout
    agent_id = agent_match.group(1)

    # 6. Read the agent back and assert lineage + content match.
    get_result = _padhanam(
        "agent", "get", agent_id, "--tenant", _TENANT_LABEL, "--json",
    )
    assert get_result.returncode == 0, get_result.stderr or get_result.stdout
    payload = json.loads(get_result.stdout)

    assert payload["source_methodology_template_id"] == methodology_id
    assert payload["source_methodology_template_version"] == 1
    assert payload["name"] == "LVT PM Agent"

    revision = payload["revision"]
    assert revision["version"] == 1
    assert revision["previous_revision_hash"] == _GENESIS_REVISION_HASH
    assert revision["system_prompt"] == _LVT_SYSTEM_PROMPT
    assert revision["retrieval_strategy"] == {"strategy": "hybrid", "params": {}}
    assert revision["filter_tree"] == {"node": {}}
    assert revision["top_k"] == 8
    # Decimal round-trips through the CLI as a string per the
    # _render_template_json convention.
    assert revision["min_score"] == "0.3"
    assert revision["model_selection"] == "qwen2.5:7b"
    assert revision["tool_allowlist"] == []
    assert sorted(revision["source_ids"]) == sorted(source_ids)
    revision_1_hash = revision["this_revision_hash"]
    assert revision_1_hash != _GENESIS_REVISION_HASH
    assert len(revision_1_hash) == 64

    # 7. Update the agent (top_k 8 → 12). The CLI's update command
    # takes the same shape as agent create but without name; we feed
    # all the revision content fields per the existing update schema.
    update_config_path = "/tmp/lvt-pm-agent-update.yaml"
    update_config = (
        f"system_prompt: {json.dumps(_LVT_SYSTEM_PROMPT)}\n"
        "source_ids:\n"
        + "".join(f"  - {sid}\n" for sid in source_ids)
        + "tool_allowlist: []\n"
        "retrieval_strategy:\n"
        "  strategy: hybrid\n"
        "  params: {}\n"
        "filter_tree:\n"
        "  node: {}\n"
        "top_k: 12\n"
        "min_score: 0.3\n"
        "model_selection: qwen2.5:7b\n"
    )
    _write_file_in_container(update_config_path, update_config)
    update_result = _padhanam(
        "agent", "update", agent_id,
        "--tenant", _TENANT_LABEL,
        "--config", update_config_path,
    )
    assert update_result.returncode == 0, update_result.stderr or update_result.stdout
    rev_match = _AGENT_REVISION_RE.search(update_result.stdout)
    assert rev_match is not None
    assert rev_match.group(2) == "2"

    # 8. Assert revision 2 chains correctly.
    get_v2 = _padhanam(
        "agent", "get", agent_id,
        "--tenant", _TENANT_LABEL,
        "--version", "2",
        "--json",
    )
    assert get_v2.returncode == 0
    v2_payload = json.loads(get_v2.stdout)
    assert v2_payload["revision"]["version"] == 2
    assert v2_payload["revision"]["previous_revision_hash"] == revision_1_hash
    assert v2_payload["revision"]["top_k"] == 12
    assert v2_payload["revision"]["this_revision_hash"] != revision_1_hash

    # 9. Assert the methodology template is unchanged after the
    # agent's edits — single revision, no clone-back propagation.
    methodology_get = _padhanam(
        "methodology", "get", methodology_id, "--json",
    )
    assert methodology_get.returncode == 0
    methodology_payload = json.loads(methodology_get.stdout)
    assert methodology_payload["revision"]["version"] == 1
    assert methodology_payload["revision"]["system_prompt"] == _LVT_SYSTEM_PROMPT
    # The methodology's top_k is the LVT default; the agent's edit
    # did not propagate back.
    assert methodology_payload["revision"]["top_k"] == 8

    # 10. Cleanup of agent + methodology (sources cleaned by fixture
    # teardown via _truncate_ingestion).
    archive_result = _padhanam(
        "agent", "archive", agent_id, "--tenant", _TENANT_LABEL,
    )
    assert archive_result.returncode == 0
    retire_result = _padhanam(
        "methodology", "retire", methodology_id,
    )
    assert retire_result.returncode == 0
