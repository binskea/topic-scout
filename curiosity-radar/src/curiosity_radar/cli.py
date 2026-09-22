"""Dispatches every `curiosity-radar` subcommand per SPEC.md §3.

Every command prints exactly one JSON object to stdout: either the
command's success schema (from `schemas.py`) or `{"error": {...}}` on
failure, with a nonzero exit code. Raw tracebacks never reach stdout — they
are written to `<data-dir>/logs/` instead.
"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer
from pydantic import BaseModel

from curiosity_radar.cache.paths import resolve_data_dir
from curiosity_radar.commands import analyze as analyze_cmd
from curiosity_radar.commands import chart as chart_cmd
from curiosity_radar.commands import fetch as fetch_cmd
from curiosity_radar.commands import project as project_cmd
from curiosity_radar.commands import report as report_cmd
from curiosity_radar.commands import resolve as resolve_cmd
from curiosity_radar.commands import verify as verify_cmd
from curiosity_radar.errors import CommandError
from curiosity_radar.schemas import ErrorDetail, ErrorResponse

app = typer.Typer(
    name="curiosity-radar",
    no_args_is_help=True,
    add_completion=False,
    help="Analyze Wikipedia pageview trends across languages to guide topic/audience decisions.",
)
project_app = typer.Typer(
    no_args_is_help=True, help="Inspect and mutate saved project state (SPEC.md §3.7)."
)
app.add_typer(project_app, name="project")


def _csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _emit(model: BaseModel) -> None:
    typer.echo(model.model_dump_json())


def _emit_error(code: str, message: str, hint: str | None = None) -> None:
    _emit(ErrorResponse(error=ErrorDetail(code=code, message=message, hint=hint)))


def _log_exception(data_dir: Path | None) -> None:
    root = resolve_data_dir(data_dir)
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    (logs / f"{stamp}.log").write_text(traceback.format_exc())


def _guard(log_data_dir: Path | None, fn: Callable[..., BaseModel], **kwargs: Any) -> None:
    try:
        result = fn(**kwargs)
    except CommandError as exc:
        _emit_error(exc.code, exc.message, exc.hint)
        raise typer.Exit(code=1) from None
    except Exception:
        _log_exception(log_data_dir)
        _emit_error(
            "internal_error",
            "An unexpected error occurred.",
            "Check <data-dir>/logs/ for the full traceback.",
        )
        raise typer.Exit(code=1) from None
    _emit(result)


@app.command()
def resolve(
    topic: str | None = typer.Option(None, "--topic", help="Topic text to resolve to a QID."),
    qid: str | None = typer.Option(None, "--qid", help="Explicit Wikidata QID, skips search."),
    languages: str = typer.Option(..., "--languages", help="Comma-separated language codes."),
    related_qids: str | None = typer.Option(
        None, "--related-qids", help="Comma-separated related QIDs to fold into the cluster."
    ),
    save_as: str | None = typer.Option(
        None, "--save-as", help="Project slug to create/update with this resolution."
    ),
    data_dir: Path | None = typer.Option(None, "--data-dir", help="Runtime data directory."),
) -> None:
    """Resolve a topic (or QID) to per-language Wikipedia articles."""
    if not topic and not qid:
        _emit_error(
            "missing_topic_or_qid",
            "Provide either --topic or --qid.",
            'Pass --topic "<text>" or --qid Q...',
        )
        raise typer.Exit(code=1)
    _guard(
        data_dir,
        resolve_cmd.run,
        topic=topic,
        qid=qid,
        languages=_csv(languages),
        related_qids=_csv(related_qids),
        save_as=save_as,
        data_dir=data_dir,
    )


@app.command()
def fetch(
    project: str = typer.Option(..., "--project", help="Project slug."),
    topic: str | None = typer.Option(None, "--topic", help="Used only to bootstrap a new project."),
    languages: str | None = typer.Option(
        None, "--languages", help="Used only to bootstrap a new project."
    ),
    start: str | None = typer.Option(None, "--start", help="YYYY-MM-DD, default: 730 days back."),
    end: str | None = typer.Option(None, "--end", help="YYYY-MM-DD, default: today."),
    granularity: str = typer.Option("daily", "--granularity", help="daily|monthly"),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """Fetch/update pageview + aggregate data for a saved project."""
    _guard(
        data_dir,
        fetch_cmd.run,
        project=project,
        topic=topic,
        languages=_csv(languages) if languages else None,
        start=start,
        end=end,
        granularity=granularity,
        data_dir=data_dir,
    )


@app.command()
def analyze(
    project: str = typer.Option(..., "--project"),
    compare_languages: bool = typer.Option(
        True, "--compare-languages/--no-compare-languages", help="Also rank across languages."
    ),
    placebo_basket_size: int = typer.Option(20, "--placebo-basket-size"),
    force_recompute: bool = typer.Option(False, "--force-recompute", help="Bypass derived cache."),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """Compute trend/spike/placebo stats for a project, from cached data only."""
    _guard(
        data_dir,
        analyze_cmd.run,
        project=project,
        compare_languages=compare_languages,
        placebo_basket_size=placebo_basket_size,
        force_recompute=force_recompute,
        data_dir=data_dir,
    )


@app.command()
def chart(
    project: str = typer.Option(..., "--project"),
    kinds: str | None = typer.Option(
        None, "--kinds", help="Comma-separated: trend,spike,cross-language (default: all)."
    ),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """Render chart image files from a project's derived stats."""
    _guard(data_dir, chart_cmd.run, project=project, kinds=_csv(kinds), data_dir=data_dir)


@app.command()
def report(
    project: str = typer.Option(..., "--project"),
    out: Path | None = typer.Option(None, "--out", help="Default: under <data-dir>/reports/."),
    audience_note: str | None = typer.Option(
        None, "--audience-note", help="Optional one-line plain-text framing, never a numeric claim."
    ),
    engine: str = typer.Option("auto", "--engine", help="auto|weasyprint|fpdf2"),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """Render the one-page PDF report for a project."""
    _guard(
        data_dir,
        report_cmd.run,
        project=project,
        out=out,
        audience_note=audience_note,
        engine=engine,
        data_dir=data_dir,
    )


@app.command()
def verify(
    project: str = typer.Option(..., "--project"),
    pdf: Path | None = typer.Option(
        None, "--pdf", help="Default: the path recorded from the last `report` run."
    ),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """Cross-check a rendered report's numbers against the derived-stats JSON."""
    _guard(data_dir, verify_cmd.run, project=project, pdf=pdf, data_dir=data_dir)


@project_app.command("list")
def project_list(data_dir: Path | None = typer.Option(None, "--data-dir")) -> None:
    """List saved projects."""
    _guard(data_dir, project_cmd.list_projects, data_dir=data_dir)


@project_app.command("show")
def project_show(
    project: str = typer.Option(..., "--project"),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """Show a saved project's state."""
    _guard(data_dir, project_cmd.show, project=project, data_dir=data_dir)


@project_app.command("set")
def project_set(
    project: str = typer.Option(..., "--project"),
    add_language: str | None = typer.Option(None, "--add-language"),
    remove_language: str | None = typer.Option(None, "--remove-language"),
    exclude_date_range: str | None = typer.Option(
        None, "--exclude-date-range", help="YYYY-MM-DD:YYYY-MM-DD"
    ),
    set_date_range: str | None = typer.Option(
        None, "--set-date-range", help="YYYY-MM-DD:YYYY-MM-DD"
    ),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """Mutate a saved project's languages/date-range/exclusions."""
    _guard(
        data_dir,
        project_cmd.set_project,
        project=project,
        add_language=add_language,
        remove_language=remove_language,
        exclude_date_range=exclude_date_range,
        set_date_range=set_date_range,
        data_dir=data_dir,
    )


@project_app.command("fork")
def project_fork(
    project: str = typer.Option(..., "--project"),
    as_slug: str = typer.Option(..., "--as"),
    data_dir: Path | None = typer.Option(None, "--data-dir"),
) -> None:
    """Clone a saved project's state under a new slug, without mutating the original."""
    _guard(data_dir, project_cmd.fork, project=project, as_slug=as_slug, data_dir=data_dir)


if __name__ == "__main__":
    app()
