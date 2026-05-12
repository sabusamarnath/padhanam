"""Integration tests for the padhanam methodology CLI (S23 / D74, refactored S26a-1 / D86).

End-to-end verification of the five subcommands (create / get / list /
update / retire) via typer's CliRunner against the live control-plane
database. Skip-on-unreachable mirrors the methodology adapter
integration tests.

S26a-1 refactor: the methodology CLI now operates on ``role_refs``
rather than the prior constraint bundle. The fixture creates a role
via the role repository before each test so the methodology configs
have a valid role_id to reference. Hash-chain integrity verification
moves to the methodology revision's (template-name + description +
role_refs) content surface per D86.
"""

from __future__ import annotations

import asyncio
import json as _json
import os
import re
from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from typer.testing import CliRunner

from apps.cli.main import app
from contexts.methodology.adapters.outbound.postgres import (
    MethodologyPostgresRepository,
    RolePostgresRepository,
    methodology_revisions,
    methodology_templates,
    role_revisions,
    role_templates,
)
from contexts.methodology.domain.role import RoleRevision, RoleTemplate
from padhanam.config import ControlPlaneSettings
from padhanam.observability.security_events import file_security_event_logger
from padhanam.security.hash_chain import (
    GENESIS_REVISION_HASH,
    compute_revision_hash,
)


_TEMPLATE_ID_RE = re.compile(
    r"created methodology_template_id=([0-9a-f-]+)"
)
_REVISION_ID_RE = re.compile(r"created revision_id=([0-9a-f-]+) version=(\d+)")


@pytest.fixture(scope="module")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


def _seed_role(repo: RolePostgresRepository, event_loop: asyncio.AbstractEventLoop) -> UUID:
    """Seed a role for the methodology fixtures to reference."""
    role_template_id = uuid4()
    name = "CLITestRole"
    description = "Role for methodology CLI integration tests"
    payload = {
        "name": name,
        "description": description,
        "system_prompt": "You are a careful analyst.",
        "source_ids": [],
        "tool_allowlist": [],
        "retrieval_strategy": {"strategy": "vector_only", "params": {}},
        "filter_tree": {"node": {}},
        "top_k": 5,
        "min_score": Decimal("0.7"),
        "model_selection": "qwen2.5:7b",
    }
    initial_hash = compute_revision_hash(
        content_payload=payload, previous_hash=GENESIS_REVISION_HASH
    )
    now = datetime.now(timezone.utc)
    template = RoleTemplate(
        id=role_template_id,
        name=name,
        description=description,
        created_by_user_id="cli-test-seed",
        created_at=now,
    )
    revision = RoleRevision(
        id=uuid4(),
        role_template_id=role_template_id,
        version=1,
        system_prompt=payload["system_prompt"],
        source_ids=(),
        tool_allowlist=(),
        retrieval_strategy=payload["retrieval_strategy"],
        filter_tree=payload["filter_tree"],
        top_k=payload["top_k"],
        min_score=payload["min_score"],
        model_selection=payload["model_selection"],
        created_by_user_id="cli-test-seed",
        created_at=now,
        previous_revision_hash=GENESIS_REVISION_HASH,
        this_revision_hash=initial_hash,
    )
    event_loop.run_until_complete(repo.create_template(template, revision))
    return role_template_id


@pytest.fixture
def cli_runtime(
    event_loop: asyncio.AbstractEventLoop, tmp_path: Path,
) -> Iterator[tuple[CliRunner, Path, Path]]:
    """CliRunner plus paths to v1 and v2 config fixtures.

    Cleans the control-plane methodology + role tables at entry and
    exit so each test starts from an empty state, seeds a single role
    for the methodology to reference, then writes the v1/v2 configs
    pointing at the seeded role. Skips when the control-plane
    Postgres is unreachable.
    """
    base = ControlPlaneSettings()
    settings = ControlPlaneSettings(
        user=base.user,
        password=base.password,
        db=base.db,
        host=os.environ.get("CONTROL_PLANE_HOST_OVERRIDE", "127.0.0.1"),
        port=int(os.environ.get("CONTROL_PLANE_PORT_OVERRIDE", "5433")),
    )
    sec = file_security_event_logger()
    cleanup_repo = MethodologyPostgresRepository.from_settings(
        settings=settings, security_events=sec
    )
    cleanup_role_repo = RolePostgresRepository.from_settings(
        settings=settings, security_events=sec
    )

    async def reset() -> None:
        # Preserve migration-owned rows (e.g. 0008_create_mckinsey_7_step)
        # so cross-test ordering doesn't strip the McKinsey methodology
        # or its seven roles. Test-authored rows use distinct
        # created_by_user_id values.
        async with cleanup_repo._sessionmaker() as session:
            await session.execute(
                sa.delete(methodology_revisions).where(
                    methodology_revisions.c.created_by_user_id.notlike(
                        "migration:%"
                    )
                )
            )
            await session.execute(
                sa.delete(methodology_templates).where(
                    methodology_templates.c.created_by_user_id.notlike(
                        "migration:%"
                    )
                )
            )
            await session.execute(
                sa.delete(role_revisions).where(
                    role_revisions.c.created_by_user_id.notlike("migration:%")
                )
            )
            await session.execute(
                sa.delete(role_templates).where(
                    role_templates.c.created_by_user_id.notlike("migration:%")
                )
            )
            await session.commit()

    try:
        event_loop.run_until_complete(reset())
    except Exception as e:
        event_loop.run_until_complete(cleanup_repo.dispose())
        event_loop.run_until_complete(cleanup_role_repo.dispose())
        pytest.skip(f"control-plane Postgres unreachable: {e}")

    seeded_role_id = _seed_role(cleanup_role_repo, event_loop)

    v1 = tmp_path / "v1.yaml"
    v1.write_text(
        "name: CLITest\n"
        "description: CLI integration test fixture\n"
        "role_refs:\n"
        f"  - role_id: {seeded_role_id}\n"
        "    role_version: 1\n"
    )
    v2 = tmp_path / "v2.yaml"
    v2.write_text(
        "role_refs:\n"
        f"  - role_id: {seeded_role_id}\n"
        "    role_version: 1\n"
    )

    runner = CliRunner()
    try:
        yield runner, v1, v2
    finally:
        event_loop.run_until_complete(reset())
        event_loop.run_until_complete(cleanup_repo.dispose())
        event_loop.run_until_complete(cleanup_role_repo.dispose())


def test_methodology_create_command(cli_runtime) -> None:
    runner, v1, _ = cli_runtime
    result = runner.invoke(app, ["methodology", "create", "--config", str(v1)])
    assert result.exit_code == 0, result.output
    match = _TEMPLATE_ID_RE.search(result.output)
    assert match is not None, f"unexpected output: {result.output!r}"


def test_methodology_list_includes_created(cli_runtime) -> None:
    runner, v1, _ = cli_runtime
    create_result = runner.invoke(app, ["methodology", "create", "--config", str(v1)])
    template_id = _TEMPLATE_ID_RE.search(create_result.output).group(1)

    list_result = runner.invoke(app, ["methodology", "list"])
    assert list_result.exit_code == 0
    assert template_id in list_result.output
    assert "CLITest" in list_result.output


def test_methodology_get_returns_template_details(cli_runtime) -> None:
    runner, v1, _ = cli_runtime
    create_result = runner.invoke(app, ["methodology", "create", "--config", str(v1)])
    template_id = _TEMPLATE_ID_RE.search(create_result.output).group(1)

    get_result = runner.invoke(app, ["methodology", "get", template_id])
    assert get_result.exit_code == 0
    assert template_id in get_result.output
    assert "CLITest" in get_result.output
    assert "Revision 1" in get_result.output
    assert "role_id=" in get_result.output


def test_methodology_get_json_output(cli_runtime) -> None:
    runner, v1, _ = cli_runtime
    create_result = runner.invoke(app, ["methodology", "create", "--config", str(v1)])
    template_id = _TEMPLATE_ID_RE.search(create_result.output).group(1)

    get_result = runner.invoke(app, ["methodology", "get", template_id, "--json"])
    assert get_result.exit_code == 0
    payload = _json.loads(get_result.output)
    assert payload["id"] == template_id
    assert payload["revision"]["version"] == 1
    assert payload["revision"]["previous_revision_hash"] == GENESIS_REVISION_HASH
    assert len(payload["revision"]["role_refs"]) == 1
    assert payload["revision"]["role_refs"][0]["role_version"] == 1


def test_methodology_update_creates_revision_two(cli_runtime) -> None:
    runner, v1, v2 = cli_runtime
    create_result = runner.invoke(app, ["methodology", "create", "--config", str(v1)])
    template_id = _TEMPLATE_ID_RE.search(create_result.output).group(1)

    update_result = runner.invoke(
        app, ["methodology", "update", template_id, "--config", str(v2)]
    )
    assert update_result.exit_code == 0, update_result.output
    rev_match = _REVISION_ID_RE.search(update_result.output)
    assert rev_match is not None
    assert rev_match.group(2) == "2"


def test_methodology_retire_marks_archived(cli_runtime) -> None:
    runner, v1, _ = cli_runtime
    create_result = runner.invoke(app, ["methodology", "create", "--config", str(v1)])
    template_id = _TEMPLATE_ID_RE.search(create_result.output).group(1)

    retire_result = runner.invoke(app, ["methodology", "retire", template_id])
    assert retire_result.exit_code == 0
    assert "archived_at=" in retire_result.output

    list_result = runner.invoke(app, ["methodology", "list"])
    assert template_id not in list_result.output


def test_methodology_e2e_full_sequence_chain_intact(
    event_loop, cli_runtime,
) -> None:
    """End-to-end create → list → get → update → retire with chain assertion.

    The chain assertion is shape-equivalent to the pre-S26a-1 test:
    revision 1's previous_revision_hash is the genesis sentinel;
    revision 2's previous_revision_hash equals revision 1's
    this_revision_hash. The hash content surface is now
    (name, description, role_refs) per D86; the chain structure is
    unchanged.
    """
    runner, v1, v2 = cli_runtime

    create_result = runner.invoke(app, ["methodology", "create", "--config", str(v1)])
    assert create_result.exit_code == 0
    template_id = _TEMPLATE_ID_RE.search(create_result.output).group(1)

    list_result = runner.invoke(app, ["methodology", "list"])
    assert template_id in list_result.output

    get_v1 = runner.invoke(app, ["methodology", "get", template_id, "--json"])
    v1_payload = _json.loads(get_v1.output)
    assert v1_payload["revision"]["version"] == 1
    assert v1_payload["revision"]["previous_revision_hash"] == GENESIS_REVISION_HASH
    rev1_this_hash = v1_payload["revision"]["this_revision_hash"]

    update_result = runner.invoke(
        app, ["methodology", "update", template_id, "--config", str(v2)]
    )
    assert update_result.exit_code == 0
    assert _REVISION_ID_RE.search(update_result.output).group(2) == "2"

    get_v2 = runner.invoke(
        app, ["methodology", "get", template_id, "--version", "2", "--json"]
    )
    v2_payload = _json.loads(get_v2.output)
    assert v2_payload["revision"]["version"] == 2
    assert v2_payload["revision"]["previous_revision_hash"] == rev1_this_hash

    retire_result = runner.invoke(app, ["methodology", "retire", template_id])
    assert retire_result.exit_code == 0

    final_list = runner.invoke(app, ["methodology", "list"])
    assert template_id not in final_list.output


def test_methodology_create_missing_config_field_raises(cli_runtime, tmp_path) -> None:
    runner, _, _ = cli_runtime
    incomplete = tmp_path / "incomplete.yaml"
    incomplete.write_text("name: BadFixture\n")  # missing role_refs
    result = runner.invoke(
        app, ["methodology", "create", "--config", str(incomplete)]
    )
    assert result.exit_code != 0


def test_methodology_create_unsupported_extension_raises(
    cli_runtime, tmp_path,
) -> None:
    runner, _, _ = cli_runtime
    bad = tmp_path / "config.txt"
    bad.write_text("not a real config")
    result = runner.invoke(
        app, ["methodology", "create", "--config", str(bad)]
    )
    assert result.exit_code != 0
