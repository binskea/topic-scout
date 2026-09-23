"""`verify`: cross-check a rendered report's numbers against derived stats
(SPEC.md §3.6) — the anti-hallucination guarantee.

Milestone 8: rebuilds the exact same claims `report` would generate *right
now* (via a fresh, cache-served `analyze`/`chart`) and searches the PDF's
extracted text for each claim's label, comparing whatever value follows it
against the freshly-computed expected value. A mismatch — or a missing
label entirely — means the PDF's printed numbers no longer agree with the
data that's supposed to back them: a template bug, a stale PDF kept around
after `analyze` reran with new data, or a manual edit.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pypdf import PdfReader

from curiosity_radar import project_state
from curiosity_radar.cache.paths import resolve_data_dir
from curiosity_radar.commands import analyze as analyze_cmd
from curiosity_radar.commands import chart as chart_cmd
from curiosity_radar.errors import CommandError
from curiosity_radar.report.render import build_claims, build_context
from curiosity_radar.schemas import Mismatch, VerifyResult

_DEFAULT_PLACEBO_BASKET_SIZE = 20
_NOT_FOUND = "(label not found in PDF)"


def run(*, project: str, pdf: Path | None, data_dir: Path | None) -> VerifyResult:
    data_root = resolve_data_dir(data_dir)
    state = project_state.load(data_root, project)
    if state is None:
        raise CommandError(
            "project_not_found",
            f"No saved project '{project}'.",
            "Run resolve --save-as, fetch, analyze, chart, and report first.",
        )

    pdf_path = pdf if pdf is not None else _default_pdf_path(state)
    if pdf_path is None:
        raise CommandError(
            "no_report_found",
            f"No report has been generated for '{project}' yet.",
            "Run `report --project ...` first, or pass --pdf explicitly.",
        )
    if not pdf_path.exists():
        raise CommandError(
            "pdf_not_found",
            f"PDF not found at '{pdf_path}'.",
            "Rerun `report` to regenerate it, or pass the correct --pdf path.",
        )

    analysis = analyze_cmd.run(
        project=project,
        compare_languages=True,
        placebo_basket_size=_DEFAULT_PLACEBO_BASKET_SIZE,
        force_recompute=False,
        data_dir=data_root,
    )
    charts = chart_cmd.run(project=project, kinds=[], data_dir=data_root)
    context = build_context(state, analysis, charts, audience_note=None)
    claims = build_claims(context)

    text = _extract_text(pdf_path)

    mismatches: list[Mismatch] = []
    matched = 0
    for claim in claims:
        found = _find_value(text, claim.label)
        if found is None:
            mismatches.append(
                Mismatch(claim_text=claim.label, expected=claim.value, found_in_pdf=_NOT_FOUND)
            )
        elif found == claim.value:
            matched += 1
        else:
            mismatches.append(
                Mismatch(claim_text=claim.label, expected=claim.value, found_in_pdf=found)
            )

    status: Literal["verified", "failed_verification"] = (
        "verified" if not mismatches else "failed_verification"
    )
    return VerifyResult(
        project=project,
        pdf_path=str(pdf_path),
        claims_checked=len(claims),
        claims_matched=matched,
        claims_mismatched=len(mismatches),
        status=status,
        mismatches=mismatches,
    )


def _default_pdf_path(state: project_state.ProjectState) -> Path | None:
    return Path(state.last_report_pdf_path) if state.last_report_pdf_path else None


def _extract_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _find_value(text: str, label: str) -> str | None:
    pattern = re.compile(re.escape(label) + r"\s*:\s*([^\s]+)")
    match = pattern.search(text)
    if match is None:
        return None
    return match.group(1).rstrip(".,;")
