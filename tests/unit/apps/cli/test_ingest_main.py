"""Unit tests for the CLI ``ingest`` subcommand surface (S19).

Argument parsing and validation through typer's CliRunner. The
end-to-end path that exercises live composition (Postgres + the
worker loop) is the integration test at
``tests/integration/contexts/ingestion/test_ingest_e2e.py``.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from apps.cli.main import app


_runner = CliRunner()


def test_root_help_lists_ingest_subcommand() -> None:
    result = _runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "ingest" in result.stdout


def test_ingest_help_lists_run_command() -> None:
    result = _runner.invoke(app, ["ingest", "--help"])
    assert result.exit_code == 0
    assert "run" in result.stdout


def test_ingest_run_help_documents_arguments() -> None:
    result = _runner.invoke(app, ["ingest", "run", "--help"])
    assert result.exit_code == 0
    assert "FILE_PATH" in result.stdout or "file_path" in result.stdout.lower()
    assert "--tenant-id" in result.stdout
    assert "--user-id" in result.stdout


def test_ingest_run_rejects_missing_file(tmp_path: Path) -> None:
    """A non-existent path surfaces as exit code 2 with a clear
    error before any database or composition wiring runs."""
    missing = tmp_path / "does_not_exist.md"
    result = _runner.invoke(
        app,
        ["ingest", "run", str(missing), "--tenant-id", "a"],
    )
    assert result.exit_code == 2
    assert "file not found" in result.output


def test_ingest_run_rejects_unsupported_extension(tmp_path: Path) -> None:
    """A .pdf upload is rejected at the CLI surface before the
    worker pulls the source per the brief's acceptance criterion 7.
    """
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake content")
    result = _runner.invoke(
        app,
        ["ingest", "run", str(pdf), "--tenant-id", "a"],
    )
    assert result.exit_code == 2
    assert "unsupported" in result.output.lower()
    assert ".pdf" in result.output


def test_ingest_run_rejects_directory(tmp_path: Path) -> None:
    """Directories aren't regular files; the error message names
    the case clearly so the operator knows what went wrong."""
    result = _runner.invoke(
        app,
        ["ingest", "run", str(tmp_path), "--tenant-id", "a"],
    )
    assert result.exit_code == 2
    assert (
        "regular file" in result.output.lower()
        or "directory" in result.output.lower()
    )
