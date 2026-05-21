"""CLI-surface tests for the ``padhanam portfolio`` subcommand (S43, D124).

These exercise the CLI layer without a database: command registration
and the ``--value`` JSON-parse guard, which runs before any wiring is
built. The use-case behaviour is covered by the application-layer unit
tests; the CLI against a live stack is exercised by the S43 smoke.
"""

from __future__ import annotations

from uuid import uuid4

from typer.testing import CliRunner

from apps.cli.main import app

runner = CliRunner()


def test_portfolio_subcommand_registered() -> None:
    result = runner.invoke(app, ["portfolio", "--help"])
    assert result.exit_code == 0
    for command in (
        "create-case",
        "create-data-point",
        "revise-data-point",
        "list-cases",
        "get-case",
    ):
        assert command in result.output


def test_create_data_point_rejects_invalid_json() -> None:
    result = runner.invoke(
        app,
        [
            "portfolio", "create-data-point",
            "--tenant-id", "a",
            "--case-id", str(uuid4()),
            "--data-point-type", "GOAL",
            "--value", "not-json",
        ],
    )
    assert result.exit_code == 2


def test_create_data_point_rejects_non_object_json() -> None:
    result = runner.invoke(
        app,
        [
            "portfolio", "create-data-point",
            "--tenant-id", "a",
            "--case-id", str(uuid4()),
            "--data-point-type", "GOAL",
            "--value", '"a bare string"',
        ],
    )
    assert result.exit_code == 2


def test_revise_data_point_rejects_invalid_json() -> None:
    result = runner.invoke(
        app,
        [
            "portfolio", "revise-data-point",
            "--tenant-id", "a",
            "--data-point-id", str(uuid4()),
            "--value", "{bad",
        ],
    )
    assert result.exit_code == 2
