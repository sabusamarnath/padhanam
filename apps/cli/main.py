"""Padhanam CLI entrypoint (S18 / S19).

Commands at S19:

  - ``padhanam eval run`` (S18) — orchestrates replay →
    cost-aggregate → render report end-to-end.

  - ``padhanam eval report`` (S18) — re-renders an existing
    comparison from stored rubric_applications without re-running
    replay.

  - ``padhanam ingest run <file>`` (S19) — register a source file
    for ingestion into the tenant's data plane. Returns a source
    id; the worker loop picks it up for parsing within seconds.

  - ``padhanam ingest worker`` (S19) — long-running worker that
    polls the tenant's pending-source queue and parses each source
    into chunks. Exits gracefully on SIGINT / SIGTERM.

Invocation: ``python -m apps.cli ingest run path/to/file.md
--tenant-id a`` (Phase 1 dev). The CLI runs from inside the
padhanam-api container so per-tenant Postgres hostnames resolve
over the Compose network — the same shape ``make migrate`` and
``make seed-tenants`` use.

The CLI calls into application-layer use cases (replay_and_score,
cost_per_successful_task, compare_runs, render functions for eval;
register_source for ingest run; parse_source for ingest worker).
No business logic in the CLI layer; the commands are thin
orchestrators wiring composition.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Annotated, Optional
from uuid import UUID

import typer

from apps.cli._eval import run_eval, run_report
from apps.cli._ingest import CLIIngestError, run_ingest_run, run_ingest_worker

app = typer.Typer(
    name="padhanam",
    help="Padhanam CLI runner (S18 eval; S19 ingest).",
    no_args_is_help=True,
    add_completion=False,
)

eval_app = typer.Typer(
    name="eval",
    help="Evaluation harness commands.",
    no_args_is_help=True,
)
app.add_typer(eval_app, name="eval")

ingest_app = typer.Typer(
    name="ingest",
    help="Source ingestion commands (S19).",
    no_args_is_help=True,
)
app.add_typer(ingest_app, name="ingest")


_OUTPUT_FORMAT_TEXT = "text"
_OUTPUT_FORMAT_JSON = "json"
_VALID_OUTPUT_FORMATS = (_OUTPUT_FORMAT_TEXT, _OUTPUT_FORMAT_JSON)


@eval_app.command("run")
def eval_run(
    tenant_id: Annotated[
        str,
        typer.Option("--tenant-id", help="Tenant short label ('a', 'b') or UUID."),
    ],
    interaction_set_id: Annotated[
        UUID,
        typer.Option("--interaction-set-id", help="Interaction set to run against."),
    ],
    scoring_sheet_revision_id: Annotated[
        UUID,
        typer.Option(
            "--scoring-sheet-revision-id",
            help="Candidate scoring sheet revision (the run under test).",
        ),
    ],
    model_name: Annotated[
        str,
        typer.Option(
            "--model",
            help="Model name for replay; defaults to the dev posture model.",
        ),
    ] = "qwen2.5:7b",
    baseline_revision_id: Annotated[
        Optional[UUID],
        typer.Option(
            "--baseline-revision-id",
            help=(
                "If provided, replay both baseline and candidate revisions "
                "and produce a regression report comparing the two."
            ),
        ),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option(
            "--output-format",
            help=f"One of {_VALID_OUTPUT_FORMATS}.",
        ),
    ] = _OUTPUT_FORMAT_TEXT,
    output_file: Annotated[
        Optional[Path],
        typer.Option(
            "--output-file",
            help="Write output to this file instead of stdout.",
        ),
    ] = None,
    poll_timeout_seconds: Annotated[
        float,
        typer.Option(
            "--poll-timeout-seconds",
            help="Per-trace polling timeout for cost-query availability (D59).",
        ),
    ] = 30.0,
) -> None:
    """Run replay → score → cost-aggregate → render report."""
    _validate_output_format(output_format)
    rendered = asyncio.run(
        run_eval(
            tenant_id=tenant_id,
            interaction_set_id=interaction_set_id,
            candidate_revision_id=scoring_sheet_revision_id,
            model_name=model_name,
            baseline_revision_id=baseline_revision_id,
            output_format=output_format,
            poll_timeout_seconds=poll_timeout_seconds,
        )
    )
    _emit(rendered, output_file)


@eval_app.command("report")
def eval_report(
    tenant_id: Annotated[
        str,
        typer.Option("--tenant-id", help="Tenant short label ('a', 'b') or UUID."),
    ],
    baseline_revision_id: Annotated[
        UUID,
        typer.Option(
            "--baseline-revision-id",
            help="Baseline scoring sheet revision id.",
        ),
    ],
    candidate_revision_id: Annotated[
        UUID,
        typer.Option(
            "--candidate-revision-id",
            help="Candidate scoring sheet revision id.",
        ),
    ],
    interaction_set_id: Annotated[
        UUID,
        typer.Option("--interaction-set-id", help="Interaction set the runs share."),
    ],
    output_format: Annotated[
        str,
        typer.Option(
            "--output-format",
            help=f"One of {_VALID_OUTPUT_FORMATS}.",
        ),
    ] = _OUTPUT_FORMAT_TEXT,
    output_file: Annotated[
        Optional[Path],
        typer.Option(
            "--output-file",
            help="Write output to this file instead of stdout.",
        ),
    ] = None,
) -> None:
    """Re-render a comparison from stored rubric_applications.

    Reads existing rubric_applications for both revisions against
    the given interaction set; does not run replay. The cost-query
    path still runs (success-rate plus cost-per-task) but does not
    poll for trace availability since the replay is presumed
    historical.
    """
    _validate_output_format(output_format)
    rendered = asyncio.run(
        run_report(
            tenant_id=tenant_id,
            baseline_revision_id=baseline_revision_id,
            candidate_revision_id=candidate_revision_id,
            interaction_set_id=interaction_set_id,
            output_format=output_format,
        )
    )
    _emit(rendered, output_file)


def _validate_output_format(output_format: str) -> None:
    if output_format not in _VALID_OUTPUT_FORMATS:
        raise typer.BadParameter(
            f"--output-format must be one of {_VALID_OUTPUT_FORMATS}, "
            f"got {output_format!r}"
        )


def _emit(rendered: str, output_file: Optional[Path]) -> None:
    if output_file is None:
        sys.stdout.write(rendered)
        if not rendered.endswith("\n"):
            sys.stdout.write("\n")
        return
    output_file.write_text(rendered, encoding="utf-8")


@ingest_app.command("worker")
def ingest_worker(
    tenant_id: Annotated[
        str,
        typer.Option(
            "--tenant-id",
            help="Tenant short label ('a', 'b') or UUID. The worker drains "
            "this tenant's pending-source queue.",
        ),
    ],
    poll_interval_seconds: Annotated[
        float,
        typer.Option(
            "--poll-interval-seconds",
            help="Seconds to wait between empty-queue polls.",
        ),
    ] = 1.0,
    max_iterations: Annotated[
        Optional[int],
        typer.Option(
            "--max-iterations",
            help="Bounded run for tests; production omits this.",
        ),
    ] = None,
) -> None:
    """Drain the tenant's pending-source queue.

    Long-running by default — exits gracefully on SIGINT or
    SIGTERM with the in-flight claim completing first. Pass
    ``--max-iterations N`` for bounded test runs that exit
    after N empty polls or N successful claims.
    """
    import logging as _logging

    _logging.basicConfig(
        level=_logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    processed = asyncio.run(
        run_ingest_worker(
            tenant_id=tenant_id,
            poll_interval_seconds=poll_interval_seconds,
            max_iterations=max_iterations,
        )
    )
    sys.stdout.write(f"worker: processed {processed} source(s)\n")


@ingest_app.command("run")
def ingest_run(
    file_path: Annotated[
        Path,
        typer.Argument(
            help="Path to the source file (markdown or plain text per D61).",
        ),
    ],
    tenant_id: Annotated[
        str,
        typer.Option(
            "--tenant-id", help="Tenant short label ('a', 'b') or UUID."
        ),
    ],
    user_id: Annotated[
        str,
        typer.Option(
            "--user-id",
            help="Acting user id; logged on the source row's created_by_user_id.",
        ),
    ] = "cli-operator",
) -> None:
    """Register a source file for ingestion into the tenant's data plane.

    Reads the file, validates the extension is supported per D61,
    persists a Source row in RECEIVED state, and prints the source
    id. The worker loop (``padhanam ingest worker``) picks up the
    row within seconds and parses it into chunks.
    """
    try:
        source_id = asyncio.run(
            run_ingest_run(
                tenant_id=tenant_id,
                file_path=file_path,
                user_id=user_id,
            )
        )
    except CLIIngestError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    sys.stdout.write(f"{source_id}\n")


if __name__ == "__main__":
    app()
