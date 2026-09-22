"""`verify`: cross-check a rendered report's numbers against derived stats
(SPEC.md §3.6).

Milestone 1 stub: wires the CLI contract, but does not yet extract or
cross-check any claims — that's Milestone 8.
"""

from __future__ import annotations

from pathlib import Path

from curiosity_radar import project_state
from curiosity_radar.cache.paths import resolve_data_dir
from curiosity_radar.errors import CommandError
from curiosity_radar.schemas import VerifyResult


def run(*, project: str, pdf: Path | None, data_dir: Path | None) -> VerifyResult:
    data_root = resolve_data_dir(data_dir)
    state = project_state.load(data_root, project)
    if state is None:
        raise CommandError(
            "project_not_found",
            f"No saved project '{project}'.",
            "Run resolve --save-as, fetch, analyze, chart, and report first.",
        )

    pdf_path = str(pdf) if pdf is not None else (state.last_report_pdf_path or "")

    return VerifyResult(
        project=project,
        pdf_path=pdf_path,
        claims_checked=0,
        claims_matched=0,
        claims_mismatched=0,
        status="verified",
        mismatches=[],
    )
