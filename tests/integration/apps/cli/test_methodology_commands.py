"""Integration tests for the padhanam methodology CLI (S23 / D74).

End-to-end verification of the five subcommands (create / get / list /
update / retire) via typer's CliRunner against the live control-plane
database. Skip-on-unreachable mirrors the methodology adapter
integration tests.

The e2e sequence test exercises the full CLI flow: create → list →
get → update → retire, with assertions on revision count, hash chain
integrity, and archive semantics.
"""

from __future__ import annotations

import asyncio
import json as _json
import os
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
import sqlalchemy as sa
from typer.testing import CliRunner

from apps.cli.main import app
from contexts.methodology.adapters.outbound.postgres import (
    MethodologyPostgresRepository,
    methodology_revisions,
    methodology_templates,
)
from padhanam.security.hash_chain import GENESIS_REVISION_HASH
from padhanam.config import ControlPlaneSettings
from padhanam.observability.security_events import file_security_event_logger


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


@pytest.fixture
def cli_runtime(
    event_loop: asyncio.AbstractEventLoop, tmp_path: Path,
) -> Iterator[tuple[CliRunner, Path, Path]]:
    """CliRunner plus paths to v1 and v2 config fixtures.

    Cleans the control-plane methodology tables at entry and exit so
    each test starts from an empty state. Skips when the control-plane
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

    async def reset() -> None:
        async with cleanup_repo._sessionmaker() as session:
            await session.execute(sa.delete(methodology_revisions))
            await session.execute(sa.delete(methodology_templates))
            await session.commit()

    try:
        event_loop.run_until_complete(reset())
    except Exception as e:
        event_loop.run_until_complete(cleanup_repo.dispose())
        pytest.skip(f"control-plane Postgres unreachable: {e}")

    # Write fixture configs to tmp_path so each test owns its inputs.
    v1 = tmp_path / "v1.yaml"
    v1.write_text(
        "name: CLITest\n"
        "description: CLI integration test fixture\n"
        "system_prompt: You are a careful analyst.\n"
        "source_ids: []\n"
        "tool_allowlist: []\n"
        "retrieval_strategy:\n"
        "  strategy: vector_only\n"
        "  params: {}\n"
        "filter_tree:\n"
        "  node: {}\n"
        "top_k: 5\n"
        "min_score: 0.7\n"
        "model_selection: qwen2.5:7b\n"
    )
    v2 = tmp_path / "v2.yaml"
    v2.write_text(
        "system_prompt: You are an even more careful analyst (v2).\n"
        "source_ids: []\n"
        "tool_allowlist: []\n"
        "retrieval_strategy:\n"
        "  strategy: vector_only\n"
        "  params: {}\n"
        "filter_tree:\n"
        "  node: {}\n"
        "top_k: 8\n"
        "min_score: 0.85\n"
        "model_selection: qwen2.5:7b\n"
    )

    runner = CliRunner()
    try:
        yield runner, v1, v2
    finally:
        event_loop.run_until_complete(reset())
        event_loop.run_until_complete(cleanup_repo.dispose())


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

    # list excludes retired by default.
    list_result = runner.invoke(app, ["methodology", "list"])
    assert template_id not in list_result.output


def test_methodology_e2e_full_sequence_chain_intact(
    event_loop, cli_runtime,
) -> None:
    """End-to-end create → list → get → update → retire with chain assertion.

    Verifies revision 2's previous_revision_hash equals revision 1's
    this_revision_hash; revision 1's previous_revision_hash equals the
    genesis sentinel; archive marks archived_at; retired template
    drops out of list.
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
    incomplete.write_text(
        "name: BadFixture\n"
        "system_prompt: missing other required fields\n"
    )
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
