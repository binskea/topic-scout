"""`report`: render the one-page PDF via the pluggable renderer
(SPEC.md §3.5, §6).

Milestone 8: calls `analyze`/`chart` (both cheap, cache-served, never
forced to recompute) to get the current stats + chart paths, builds the
shared `ReportContext`/claims from `report/render.py`, and renders via
`--engine auto|weasyprint|fpdf2`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from pypdf import PdfReader

from curiosity_radar import project_state
from curiosity_radar.cache.paths import resolve_data_dir
from curiosity_radar.commands import analyze as analyze_cmd
from curiosity_radar.commands import chart as chart_cmd
from curiosity_radar.errors import CommandError
from curiosity_radar.report import render as report_render
from curiosity_radar.schemas import ReportResult

_VALID_ENGINES = ("auto", "weasyprint", "fpdf2")
_DEFAULT_PLACEBO_BASKET_SIZE = 20


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

    if engine not in _VALID_ENGINES:
        raise CommandError(
            "unknown_engine",
            f"Unknown engine '{engine}'.",
            f"Choose from: {', '.join(_VALID_ENGINES)}.",
        )

    analysis = analyze_cmd.run(
        project=project,
        compare_languages=True,
        placebo_basket_size=_DEFAULT_PLACEBO_BASKET_SIZE,
        force_recompute=False,
        data_dir=data_root,
    )
    charts = chart_cmd.run(project=project, kinds=[], data_dir=data_root)
    context = report_render.build_context(state, analysis, charts, audience_note)

    pdf_path = out
    if pdf_path is None:
        today = datetime.now(UTC).date().isoformat()
        pdf_path = data_root / "reports" / f"{project}_{today}.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    outcome, engine_used = report_render.render(context, pdf_path, engine=engine)
    page_count = len(PdfReader(str(pdf_path)).pages)

    state.last_report_pdf_path = str(pdf_path)
    project_state.save(data_root, state)

    return ReportResult(
        project=project,
        pdf_path=str(pdf_path),
        engine_used=cast(Literal["weasyprint", "fpdf2"], engine_used),
        page_count=page_count,
        sections_rendered=outcome.sections_rendered,
        numeric_claims_count=len(outcome.claims),
    )
