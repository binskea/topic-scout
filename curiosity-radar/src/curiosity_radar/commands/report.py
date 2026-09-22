"""`report`: render the one-page PDF via the pluggable renderer
(SPEC.md §3.5, §6).

Milestone 1 stub: wires the CLI contract, but does not yet render a PDF —
that's Milestone 8.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, cast, get_args

from curiosity_radar import project_state
from curiosity_radar.cache.paths import resolve_data_dir
from curiosity_radar.errors import CommandError
from curiosity_radar.schemas import ReportResult

_Engine = Literal["weasyprint", "fpdf2"]
_ENGINES: tuple[str, ...] = get_args(_Engine)
_DEFAULT_ENGINE: _Engine = "fpdf2"


def run(
    *,
    project: str,
    out: Path | None,
    audience_note: str | None,
    engine: str,
    data_dir: Path | None,
) -> ReportResult:
    data_root = resolve_data_dir(data_dir)
    state = project_state.load(data_root, project)
    if state is None:
        raise CommandError(
            "project_not_found",
            f"No saved project '{project}'.",
            "Run resolve --save-as, fetch, analyze, and chart first.",
        )

    engine_used: _Engine = cast(_Engine, engine) if engine in _ENGINES else _DEFAULT_ENGINE
    pdf_path = out if out is not None else data_root / "reports" / f"{project}_stub.pdf"

    state.last_report_pdf_path = str(pdf_path)
    project_state.save(data_root, state)

    return ReportResult(
        project=project,
        pdf_path=str(pdf_path),
        engine_used=engine_used,
        page_count=0,
        sections_rendered=[],
        numeric_claims_count=0,
    )
