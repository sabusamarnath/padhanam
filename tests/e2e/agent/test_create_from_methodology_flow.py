"""End-to-end test for the role-aware clone flows (S26a-2 / D86).

Exercises both clone-from-methodology and clone-from-role against the
live Compose stack so the role-first composition has end-to-end
coverage the unit and integration tests miss.

S26a-1 (D86) refactored methodology to compose roles via role_refs;
S26a-2 added the padhanam role CLI namespace plus
``padhanam agent create-from-role``. The original S25 e2e wrote a
pre-v3 methodology config that no longer parses; this file is the
full rewrite restoring the deferred integration commitment per the
brief's commit 5 scope.

Workflow exercised (numbered to match the test body):

  1. Create the LVTGuide role on the control plane via padhanam role.
  2. Create the LVT methodology on the control plane referencing the
     role via role_refs.
  3. Ingest two test markdown source files for tenant alpha.
  4. Drain the ingest worker until both sources reach indexed.
  5a. Clone an agent from the methodology; assert both lineage pairs
      populate (methodology + resolved role) and content matches the
      role's bundle.
  5b. Clone a second agent directly from the role; assert only the
      role lineage pair populates (methodology pair NULL).
  6. Update the methodology-cloned agent (top_k 8 → 12); capture
     revision 2.
  7. Assert revision 2 chains correctly from revision 1; assert the
     methodology and role templates are unchanged after the agent's
     edit (no clone-back propagation per D68).
  8. Cleanup: archive both agents; retire methodology; archive role;
     truncate sources.

The test runs CLI commands inside the padhanam-api container via
``docker compose exec`` so per-tenant Postgres hostnames resolve
over the Compose network — same pattern as the existing
tests/integration/contexts/ingestion/test_ingest_e2e.py.

Skip-on-unreachable behaviour: the test skips cleanly when Docker
is not available, when the Compose services are not running, or
when the LiteLLM / Ollama / Neo4j services needed by the worker
are not responsive.
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
_ROLE_TEMPLATE_ID_RE = re.compile(
    r"created role_template_id=([0-9a-f-]+)"
)
_GENESIS_REVISION_HASH = "0" * 64


# ---------------------------------------------------------------------
# Compose / docker helpers
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
    """Skip when the Compose services the flow depends on are not running."""
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


def _truncate_methodology_and_role() -> None:
    _exec_psql_control_plane(
        "TRUNCATE TABLE methodology_revisions, methodology_templates, "
        "role_revisions, role_templates;"
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


_LVTGUIDE_SYSTEM_PROMPT = (
    "You are an LVTGuide role: help the user place work in the "
    "bet/initiative/epic/story hierarchy, check alignment upward and "
    "decomposition downward, surface drift between strategic intent "
    "and execution. Output is recommendation-shaped: locate, assess "
    "alignment, name the gap, recommend a next step."
)


def _create_lvtguide_role() -> str:
    """Write the role config inside the container and run
    ``role create``. Returns the new role_template_id."""
    config_path = "/tmp/lvtguide-role.yaml"
    description = (
        "LVT guide role: places work in the LVT four-level hierarchy."
    )
    config = (
        "name: LVTGuide\n"
        f"description: {json.dumps(description)}\n"
        f"system_prompt: {json.dumps(_LVTGUIDE_SYSTEM_PROMPT)}\n"
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
    result = _padhanam("role", "create", "--config", config_path)
    assert result.returncode == 0, result.stderr or result.stdout
    match = _ROLE_TEMPLATE_ID_RE.search(result.stdout)
    assert match is not None, f"unexpected output: {result.stdout!r}"
    return match.group(1)


def _create_lvt_methodology(*, role_id: str) -> str:
    """Write the methodology config inside the container (referencing
    the role via role_refs) and run ``methodology create``. Returns
    the new methodology_template_id."""
    config_path = "/tmp/lvt-methodology.yaml"
    description = (
        "Lean Value Tree methodology: composes the LVTGuide role with "
        "playbook-level guidance for tree placement and alignment checks."
    )
    config = (
        "name: LVT\n"
        f"description: {json.dumps(description)}\n"
        "role_refs:\n"
        f"  - role_id: {role_id}\n"
        "    role_version: 1\n"
    )
    _write_file_in_container(config_path, config)
    result = _padhanam("methodology", "create", "--config", config_path)
    assert result.returncode == 0, result.stderr or result.stdout
    match = _METHODOLOGY_TEMPLATE_ID_RE.search(result.stdout)
    assert match is not None, f"unexpected output: {result.stdout!r}"
    return match.group(1)


def _ingest_source(*, tenant_label: str, file_path: str, body: str) -> None:
    _write_file_in_container(file_path, body)
    result = _padhanam(
        "ingest", "run", file_path, "--tenant-id", tenant_label
    )
    assert result.returncode == 0, result.stderr or result.stdout


def _drain_worker_until_indexed(*, tenant_label: str, expected_sources: int, max_iterations: int = 40) -> None:
    for _ in range(max_iterations):
        result = _padhanam(
            "ingest", "worker",
            "--tenant-id", tenant_label,
            "--max-iterations", "1",
            "--poll-interval-seconds", "0.5",
            timeout=180,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"ingest worker failed: rc={result.returncode}, "
                f"stdout={result.stdout!r}, stderr={result.stderr!r}"
            )
        count = _exec_psql_tenant(
            tenant_label,
            "SELECT count(*) FROM sources WHERE state = 'indexed';",
        )
        if int(count) >= expected_sources:
            return
        time.sleep(0.5)
    raise RuntimeError(
        f"worker did not reach indexed state for {expected_sources} sources "
        f"within {max_iterations} iterations"
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


@pytest.fixture
def clean_state(compose_running):  # noqa: ARG001
    _truncate_ingestion(_TENANT_LABEL)
    _truncate_agents(_TENANT_LABEL)
    _truncate_methodology_and_role()
    yield
    _truncate_ingestion(_TENANT_LABEL)
    _truncate_agents(_TENANT_LABEL)
    _truncate_methodology_and_role()


def test_full_role_aware_clone_and_edit_flow_against_live_stack(
    clean_state,
) -> None:  # noqa: ARG001
    """End-to-end exercise of the S26a-2 role-aware shape:

      - Role authoring via padhanam role create.
      - Methodology authoring via padhanam methodology create
        referencing the role via role_refs.
      - Source ingestion + indexing.
      - Agent cloning via both create-from-methodology (both lineage
        pairs populated) and create-from-role (only the role pair
        populated).
      - Edit one cloned agent; assert hash chain advances; assert
        methodology and role templates unchanged (D68 independence).
      - Archive both agents; retire methodology; archive role.
    """
    # 1. Create LVTGuide role on the control plane.
    role_id = _create_lvtguide_role()

    # 2. Create LVT methodology on the control plane, referencing the
    #    role via role_refs (single-role methodology per D86 Phase 1).
    methodology_id = _create_lvt_methodology(role_id=role_id)

    # 3. Ingest two markdown sources for tenant alpha.
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
            file_path=f"/tmp/s26a2-source-{i}.md",
            body=body,
        )

    # 4. Drain worker until both sources reach indexed.
    _drain_worker_until_indexed(
        tenant_label=_TENANT_LABEL,
        expected_sources=2,
        max_iterations=40,
    )

    source_ids = _get_source_ids_in_state(
        tenant_label=_TENANT_LABEL, state="indexed"
    )
    assert len(source_ids) == 2, source_ids

    # 5a. Clone an agent from the methodology (both lineage pairs
    #     populate per the S26a-2 extension).
    methodology_clone_path = "/tmp/lvt-pm-agent-clone.yaml"
    methodology_clone = (
        f"methodology_template_id: {methodology_id}\n"
        "methodology_version: null\n"
        "name: LVT PM Agent (from methodology)\n"
        "source_ids:\n"
        + "".join(f"  - {sid}\n" for sid in source_ids)
    )
    _write_file_in_container(methodology_clone_path, methodology_clone)
    methodology_clone_result = _padhanam(
        "agent", "create-from-methodology",
        "--tenant", _TENANT_LABEL,
        "--config", methodology_clone_path,
    )
    assert methodology_clone_result.returncode == 0, (
        methodology_clone_result.stderr or methodology_clone_result.stdout
    )
    methodology_agent_match = _AGENT_TEMPLATE_ID_RE.search(
        methodology_clone_result.stdout
    )
    assert methodology_agent_match is not None, methodology_clone_result.stdout
    methodology_agent_id = methodology_agent_match.group(1)

    methodology_agent_get = _padhanam(
        "agent", "get", methodology_agent_id, "--tenant", _TENANT_LABEL, "--json",
    )
    assert methodology_agent_get.returncode == 0
    methodology_agent_payload = json.loads(methodology_agent_get.stdout)

    # Both lineage pairs populated.
    assert methodology_agent_payload["source_methodology_template_id"] == methodology_id
    assert methodology_agent_payload["source_methodology_template_version"] == 1
    assert methodology_agent_payload["source_role_id"] == role_id
    assert methodology_agent_payload["source_role_version"] == 1
    assert methodology_agent_payload["name"] == "LVT PM Agent (from methodology)"

    methodology_revision = methodology_agent_payload["revision"]
    assert methodology_revision["version"] == 1
    assert methodology_revision["previous_revision_hash"] == _GENESIS_REVISION_HASH
    assert methodology_revision["system_prompt"] == _LVTGUIDE_SYSTEM_PROMPT
    assert methodology_revision["top_k"] == 8
    assert methodology_revision["min_score"] == "0.3"
    assert methodology_revision["model_selection"] == "qwen2.5:7b"
    assert sorted(methodology_revision["source_ids"]) == sorted(source_ids)
    methodology_agent_v1_hash = methodology_revision["this_revision_hash"]
    assert methodology_agent_v1_hash != _GENESIS_REVISION_HASH
    assert len(methodology_agent_v1_hash) == 64

    # 5b. Clone a second agent directly from the role; only the role
    #     pair populates (methodology pair NULL — D86 third valid state).
    role_clone_path = "/tmp/lvtguide-direct-clone.yaml"
    role_clone = (
        f"role_id: {role_id}\n"
        "role_version: null\n"
        "name: LVTGuide Direct Agent (from role)\n"
        "source_ids:\n"
        + "".join(f"  - {sid}\n" for sid in source_ids)
    )
    _write_file_in_container(role_clone_path, role_clone)
    role_clone_result = _padhanam(
        "agent", "create-from-role",
        "--tenant", _TENANT_LABEL,
        "--config", role_clone_path,
    )
    assert role_clone_result.returncode == 0, (
        role_clone_result.stderr or role_clone_result.stdout
    )
    role_agent_match = _AGENT_TEMPLATE_ID_RE.search(role_clone_result.stdout)
    assert role_agent_match is not None, role_clone_result.stdout
    role_agent_id = role_agent_match.group(1)

    role_agent_get = _padhanam(
        "agent", "get", role_agent_id, "--tenant", _TENANT_LABEL, "--json",
    )
    assert role_agent_get.returncode == 0
    role_agent_payload = json.loads(role_agent_get.stdout)

    # Methodology pair is NULL; role pair populated. Third valid state.
    assert role_agent_payload["source_methodology_template_id"] is None
    assert role_agent_payload["source_methodology_template_version"] is None
    assert role_agent_payload["source_role_id"] == role_id
    assert role_agent_payload["source_role_version"] == 1
    assert role_agent_payload["name"] == "LVTGuide Direct Agent (from role)"

    role_agent_revision = role_agent_payload["revision"]
    assert role_agent_revision["version"] == 1
    assert role_agent_revision["previous_revision_hash"] == _GENESIS_REVISION_HASH
    # The role-cloned agent inherits the same role bundle content as
    # the methodology-cloned agent because methodology-cloning resolves
    # to the same first role_ref. Hashes legitimately differ because
    # the two agents carry different names (D75 includes name in the
    # canonical hash payload); content-field equality is the audit
    # invariant.
    assert role_agent_revision["system_prompt"] == methodology_revision["system_prompt"]
    assert role_agent_revision["top_k"] == methodology_revision["top_k"]
    assert role_agent_revision["min_score"] == methodology_revision["min_score"]
    assert role_agent_revision["model_selection"] == methodology_revision["model_selection"]
    assert sorted(role_agent_revision["source_ids"]) == sorted(
        methodology_revision["source_ids"]
    )

    # 6. Update the methodology-cloned agent (top_k 8 → 12). Capture
    #    revision 2 and assert chain advances.
    update_config_path = "/tmp/lvt-pm-agent-update.yaml"
    update_config = (
        f"system_prompt: {json.dumps(_LVTGUIDE_SYSTEM_PROMPT)}\n"
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
        "agent", "update", methodology_agent_id,
        "--tenant", _TENANT_LABEL,
        "--config", update_config_path,
    )
    assert update_result.returncode == 0, update_result.stderr or update_result.stdout
    rev_match = _AGENT_REVISION_RE.search(update_result.stdout)
    assert rev_match is not None
    assert rev_match.group(2) == "2"

    # 7. Assert revision 2 chains correctly from revision 1.
    get_v2 = _padhanam(
        "agent", "get", methodology_agent_id,
        "--tenant", _TENANT_LABEL,
        "--version", "2",
        "--json",
    )
    assert get_v2.returncode == 0
    v2_payload = json.loads(get_v2.stdout)
    assert v2_payload["revision"]["version"] == 2
    assert v2_payload["revision"]["previous_revision_hash"] == methodology_agent_v1_hash
    assert v2_payload["revision"]["top_k"] == 12
    assert v2_payload["revision"]["this_revision_hash"] != methodology_agent_v1_hash

    # 7b. Assert the role template is unchanged after the agent's edit
    #     — single revision, no clone-back propagation (D68 independence).
    role_get = _padhanam("role", "get", role_id, "--json")
    assert role_get.returncode == 0
    role_payload = json.loads(role_get.stdout)
    assert role_payload["revision"]["version"] == 1
    assert role_payload["revision"]["top_k"] == 8

    # 7c. Assert the methodology template is unchanged: still references
    #     the original role at version 1; methodology revision count is 1.
    methodology_get = _padhanam(
        "methodology", "get", methodology_id, "--json",
    )
    assert methodology_get.returncode == 0
    methodology_payload = json.loads(methodology_get.stdout)
    assert methodology_payload["revision"]["version"] == 1
    role_refs = methodology_payload["revision"]["role_refs"]
    assert len(role_refs) == 1
    assert role_refs[0]["role_id"] == role_id
    assert role_refs[0]["role_version"] == 1

    # 8. Cleanup of agents + methodology + role (sources cleaned by
    #    fixture teardown).
    archive_methodology_agent = _padhanam(
        "agent", "archive", methodology_agent_id, "--tenant", _TENANT_LABEL,
    )
    assert archive_methodology_agent.returncode == 0
    archive_role_agent = _padhanam(
        "agent", "archive", role_agent_id, "--tenant", _TENANT_LABEL,
    )
    assert archive_role_agent.returncode == 0
    retire_methodology = _padhanam(
        "methodology", "retire", methodology_id,
    )
    assert retire_methodology.returncode == 0
    archive_role_result = _padhanam(
        "role", "archive", role_id,
    )
    assert archive_role_result.returncode == 0
