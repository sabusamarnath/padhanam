"""Unit tests for the Padhanam CLI entrypoint (S18).

These tests cover argument parsing and validation through typer's
CliRunner. End-to-end coverage that exercises live composition
(replay + Langfuse + Postgres) is the integration test at
``tests/integration/evaluation/test_cli_e2e.py``.
"""

from __future__ import annotations

from typer.testing import CliRunner

from apps.cli.main import app


_runner = CliRunner()


def test_root_help_lists_eval_subcommand() -> None:
    result = _runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "eval" in result.stdout


def test_eval_help_lists_run_and_report() -> None:
    result = _runner.invoke(app, ["eval", "--help"])
    assert result.exit_code == 0
    assert "run" in result.stdout
    assert "report" in result.stdout


def test_eval_run_help_documents_required_options() -> None:
    result = _runner.invoke(app, ["eval", "run", "--help"])
    assert result.exit_code == 0
    # Required options should be documented in --help.
    assert "--tenant-id" in result.stdout
    assert "--interaction-set-id" in result.stdout
    assert "--scoring-sheet-revision-id" in result.stdout
    assert "--baseline-revision-id" in result.stdout
    assert "--output-format" in result.stdout
    assert "--output-file" in result.stdout


def test_eval_report_help_documents_required_options() -> None:
    result = _runner.invoke(app, ["eval", "report", "--help"])
    assert result.exit_code == 0
    assert "--tenant-id" in result.stdout
    assert "--baseline-revision-id" in result.stdout
    assert "--candidate-revision-id" in result.stdout
    assert "--interaction-set-id" in result.stdout
    assert "--output-format" in result.stdout


def test_eval_run_rejects_invalid_output_format() -> None:
    """--output-format must be 'text' or 'json'; other values are
    rejected before any composition wiring runs (typer.BadParameter)."""
    result = _runner.invoke(
        app,
        [
            "eval",
            "run",
            "--tenant-id",
            "a",
            "--interaction-set-id",
            "00000000-0000-4000-8000-000000000001",
            "--scoring-sheet-revision-id",
            "00000000-0000-4000-8000-000000000002",
            "--output-format",
            "xml",
        ],
    )
    assert result.exit_code != 0
    assert "output-format" in result.output.lower() or "xml" in result.output


def test_eval_report_rejects_invalid_uuid() -> None:
    """UUID typing on --baseline-revision-id is enforced by typer;
    a non-UUID argument fails parsing before any wiring runs."""
    result = _runner.invoke(
        app,
        [
            "eval",
            "report",
            "--tenant-id",
            "a",
            "--baseline-revision-id",
            "not-a-uuid",
            "--candidate-revision-id",
            "00000000-0000-4000-8000-000000000002",
            "--interaction-set-id",
            "00000000-0000-4000-8000-000000000003",
        ],
    )
    assert result.exit_code != 0
