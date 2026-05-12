"""Integration tests for the padhanam tool CLI (S28b commit 8, D89).

Exercises ``padhanam tool create``, ``tool get``, ``tool list`` via
typer's CliRunner against the live control-plane DB. Skip-on-
unreachable mirrors the methodology / role CLI test pattern.

Three load-bearing scenarios:

1. ``tool create`` with a Phase-1-visible classification (read-only,
   drafting, user-affecting-with-consent) succeeds and round-trips
   via ``tool get``.

2. ``tool create`` with a Phase-1-prohibited classification
   (financial, communication, legal) exits non-zero with the
   prohibition message naming the per-invocation confirmation
   pathway deferred-decisions entry.

3. ``tool list`` returns the retrieval seed plus any test-authored
   tools.

The CLI's authoring config shape is YAML / JSON; tests use YAML
fixtures for readability.
"""

from __future__ import annotations

import asyncio
import os
import re
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
import yaml
from typer.testing import CliRunner

from apps.cli.main import app
from contexts.tools.adapters.outbound.postgres import ToolPostgresRepository
from contexts.tools.adapters.outbound.postgres.tool_repository import (
    tool_revisions,
    tools,
)
from padhanam.config import ControlPlaneSettings
from padhanam.observability.security_events import file_security_event_logger


_TEMPLATE_ID_RE = re.compile(r"id:\s+([0-9a-f-]{36})")


@pytest.fixture(scope="module")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture
def cleanup(
    event_loop: asyncio.AbstractEventLoop,
) -> Iterator[None]:
    """Truncate test-authored tool rows around each test."""
    base = ControlPlaneSettings()
    settings = ControlPlaneSettings(
        user=base.user,
        password=base.password,
        db=base.db,
        host=os.environ.get("CONTROL_PLANE_HOST_OVERRIDE", "127.0.0.1"),
        port=int(os.environ.get("CONTROL_PLANE_PORT_OVERRIDE", "5433")),
    )
    sec = file_security_event_logger()
    repo = ToolPostgresRepository.from_settings(
        settings=settings, security_events=sec,
    )

    async def truncate() -> None:
        async with repo._sessionmaker() as session:
            await session.execute(
                sa.delete(tool_revisions).where(
                    tool_revisions.c.created_by_user_id.notlike("migration:%")
                )
            )
            await session.execute(
                sa.delete(tools).where(
                    tools.c.created_by_user_id.notlike("migration:%")
                )
            )
            await session.commit()

    try:
        event_loop.run_until_complete(truncate())
    except Exception as e:
        event_loop.run_until_complete(repo.dispose())
        pytest.skip(f"control-plane Postgres unreachable: {e}")
    try:
        yield None
    finally:
        event_loop.run_until_complete(truncate())
        event_loop.run_until_complete(repo.dispose())


def _config(
    *,
    name: str,
    classification: str,
    description: str = "test tool",
) -> dict:
    return {
        "name": name,
        "description": description,
        "classification": classification,
        "parameters_schema": {
            "type": "object",
            "properties": {"q": {"type": "string"}},
            "required": ["q"],
        },
        "returns_schema": {"type": "string"},
    }


def _write_config(tmp_path: Path, payload: dict) -> Path:
    config_path = tmp_path / "tool.yaml"
    config_path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return config_path


def test_tool_create_succeeds_for_read_only_classification(
    cleanup, tmp_path: Path,
) -> None:
    runner = CliRunner()
    cfg = _write_config(
        tmp_path,
        _config(name="test-tool-A", classification="read-only"),
    )
    result = runner.invoke(app, ["tool", "create", "--config", str(cfg)])
    assert result.exit_code == 0, result.output
    assert "test-tool-A" in result.output
    assert "read-only" in result.output
    match = _TEMPLATE_ID_RE.search(result.output)
    assert match is not None
    tool_id = match.group(1)

    # Round-trip via tool get
    get_result = runner.invoke(app, ["tool", "get", "--id", tool_id])
    assert get_result.exit_code == 0
    assert "test-tool-A" in get_result.output


def test_tool_create_succeeds_for_drafting_classification(
    cleanup, tmp_path: Path,
) -> None:
    runner = CliRunner()
    cfg = _write_config(
        tmp_path,
        _config(name="test-tool-B", classification="drafting"),
    )
    result = runner.invoke(app, ["tool", "create", "--config", str(cfg)])
    assert result.exit_code == 0, result.output
    assert "drafting" in result.output


@pytest.mark.parametrize(
    "classification",
    ["financial", "communication", "legal"],
)
def test_tool_create_rejected_for_high_classifications(
    cleanup, tmp_path: Path, classification: str,
) -> None:
    runner = CliRunner()
    cfg = _write_config(
        tmp_path,
        _config(name=f"test-tool-{classification}", classification=classification),
    )
    result = runner.invoke(app, ["tool", "create", "--config", str(cfg)])
    assert result.exit_code != 0
    # The error message names the deferred-decisions entry per D89.
    assert classification in result.output
    assert "confirmation pathway" in result.output.lower()
    assert "deferred-decisions" in result.output.lower()


def test_tool_create_rejects_unknown_classification(
    cleanup, tmp_path: Path,
) -> None:
    runner = CliRunner()
    cfg = _write_config(
        tmp_path,
        _config(name="bogus", classification="nonsense"),
    )
    result = runner.invoke(app, ["tool", "create", "--config", str(cfg)])
    assert result.exit_code != 0
    assert "nonsense" in result.output


def test_tool_list_returns_retrieval_seed_plus_authored(
    cleanup, tmp_path: Path,
) -> None:
    runner = CliRunner()

    # Author one tool
    cfg = _write_config(
        tmp_path,
        _config(name="test-tool-C", classification="read-only"),
    )
    runner.invoke(app, ["tool", "create", "--config", str(cfg)])

    # list shows the retrieval seed plus test-authored entry
    list_result = runner.invoke(app, ["tool", "list"])
    assert list_result.exit_code == 0
    assert "retrieval" in list_result.output
    assert "test-tool-C" in list_result.output


def test_tool_get_returns_not_found_for_unknown_id(cleanup) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["tool", "get", "--id", str(uuid4())])
    assert result.exit_code != 0
    assert "not found" in result.output.lower()
