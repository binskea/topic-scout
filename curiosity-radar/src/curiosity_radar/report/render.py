"""Pluggable one-page PDF renderer interface (SPEC.md §6).

`build_claims` is the single source of truth for every numeric/date fact
the report prints: both renderer implementations format their visible text
from `Claim.label`/`Claim.value` verbatim, and `verify` (Milestone 8)
rebuilds the exact same claims from a fresh `analyze` read to cross-check
against the rendered PDF — so the two commands can never drift apart on
what "the numbers" are, only on whether the PDF's actual printed text still
agrees with them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from curiosity_radar.project_state import ProjectState
from curiosity_radar.schemas import AnalyzeResult, ChartResult

PAGE_SIZE = "A4"
MAX_LANGUAGES = 4

LIMITATIONS = [
    "Pageview data reflects Wikipedia readership only, not search demand, "
    "app-store demand, or purchase intent.",
    "Short/noisy series near AQS's actual history start date are unreliable.",
    "Topic-to-article mapping can be imperfect for ambiguous topics.",
    "All comparisons are normalized (share of project traffic), not raw counts.",
]


def fmt_float(value: float, decimals: int = 6) -> str:
    """Fixed-point at `decimals` places, falling back to scientific notation
    when that many places would round a genuinely nonzero value down to an
    indistinguishable string of zeros — Theil-Sen slopes are in
    share-of-traffic units, routinely 1e-6 to 1e-8, and printing them all as
    "0.000000" hides both the trend's real magnitude and the very value the
    cross-language ranking tie-breaks on."""
    if value != 0 and round(value, decimals) == 0:
        return f"{value:.3e}"
    return f"{value:.{decimals}f}"


@dataclass
class Claim:
    label: str
    value: str


@dataclass
class ReportContext:
    state: ProjectState
    analysis: AnalyzeResult
    charts: ChartResult
    audience_note: str | None
    generated_at: str
    languages: list[str]
    truncated: bool
    topic_label: str


@dataclass
class RenderOutcome:
    sections_rendered: list[str] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)


class Renderer(Protocol):
    name: str

    def render(self, context: ReportContext, out_path: Path) -> RenderOutcome: ...


def build_context(
    state: ProjectState,
    analysis: AnalyzeResult,
    charts: ChartResult,
    audience_note: str | None,
) -> ReportContext:
    all_langs = list(analysis.languages.keys())
    languages = all_langs[:MAX_LANGUAGES]
    return ReportContext(
        state=state,
        analysis=analysis,
        charts=charts,
        audience_note=audience_note,
        generated_at=datetime.now(UTC).isoformat(),
        languages=languages,
        truncated=len(all_langs) > MAX_LANGUAGES,
        topic_label=state.topic_query or state.slug,
    )


def build_claims(context: ReportContext) -> list[Claim]:
    """Every numeric/date fact the report prints, as `(label, value)` pairs.

    A renderer prints these labels verbatim so `verify` can find each one
    in the extracted PDF text and check the number right after it.
    """
    # Note: `context.generated_at` (a fresh timestamp, re-stamped on every
    # `build_context` call including `verify`'s) is deliberately NOT a
    # claim — it can never match between when `report` ran and when
    # `verify` re-checks it, since it isn't derived from `analyze`'s JSON
    # at all. It's still shown in the header as informational context.
    claims: list[Claim] = [
        Claim("Project date range start", context.state.date_range_start),
        Claim("Project date range end", context.state.date_range_end),
    ]

    for lang in context.languages:
        analysis = context.analysis.languages[lang]
        prefix = f"[{lang}]"
        dq = analysis.data_quality
        claims.append(Claim(f"{prefix} Data days", str(dq.total_days)))
        claims.append(Claim(f"{prefix} Zero-view days", str(dq.zero_view_days)))
        if not dq.sufficient_for_trend:
            continue

        trend = analysis.normalized_trend
        claims.append(
            Claim(
                f"{prefix} Theil-Sen slope/day (with spikes)",
                fmt_float(trend.theil_sen_slope_per_day),
            )
        )
        claims.append(
            Claim(
                f"{prefix} Mann-Kendall p-value (with spikes)",
                fmt_float(trend.mann_kendall.p_value),
            )
        )
        if trend.mann_kendall.tau is not None:
            claims.append(
                Claim(f"{prefix} Mann-Kendall tau (with spikes)", fmt_float(trend.mann_kendall.tau))
            )

        excl = analysis.trend_excluding_spikes
        claims.append(
            Claim(
                f"{prefix} Theil-Sen slope/day (excluding spikes)",
                fmt_float(excl.theil_sen_slope_per_day),
            )
        )

        claims.append(Claim(f"{prefix} Spikes detected", str(len(analysis.spikes_detected))))

        if analysis.placebo is not None:
            claims.append(Claim(f"{prefix} Placebo basket size", str(analysis.placebo.basket_size)))
            claims.append(
                Claim(
                    f"{prefix} Placebo percentile",
                    fmt_float(analysis.placebo.topic_slope_percentile_vs_basket, decimals=1),
                )
            )

    return claims


def headline_text(context: ReportContext) -> str:
    if not context.languages:
        return f"No resolved articles for '{context.topic_label}'."
    if context.analysis.cross_language_ranking:
        top = context.analysis.cross_language_ranking[0]
        return f"'{context.topic_label}' on {top.lang}: {top.reason}."
    lang = context.languages[0]
    label = context.analysis.languages[lang].normalized_trend.confidence_label
    return f"'{context.topic_label}' on {lang}: {label}."


def assumptions_text(context: ReportContext) -> str:
    redirect_notes = []
    for lang in context.languages:
        article = context.state.articles.get(lang)
        if article and article.redirect_from:
            redirect_notes.append(f"{lang}: '{article.redirect_from}' redirect traffic folded in")
    text = "Views shown as % of project-wide daily traffic (agent=user), not raw counts. "
    text += "Date range reflects exclusions already applied. "
    if redirect_notes:
        text += "Redirect aliases included: " + "; ".join(redirect_notes) + "."
    return text


def render(context: ReportContext, out_path: Path, *, engine: str) -> tuple[RenderOutcome, str]:
    """Render `context` to `out_path`, returning `(outcome, engine_used)`.

    `engine="auto"` (SPEC.md §6) prefers WeasyPrint when it both imports
    *and* actually renders successfully — a Python-level import can succeed
    while a Cairo/Pango call still fails at render time on some platforms
    (SPEC.md §9 item 9) — falling back to fpdf2 transparently either way.
    `engine="weasyprint"`/`"fpdf2"` force that engine with no fallback, so a
    genuine failure surfaces instead of being silently swallowed.
    """
    from curiosity_radar.report.fpdf2_renderer import Fpdf2Renderer

    if engine == "fpdf2":
        return Fpdf2Renderer().render(context, out_path), "fpdf2"

    if engine == "weasyprint":
        from curiosity_radar.report.weasyprint_renderer import WeasyPrintRenderer

        return WeasyPrintRenderer().render(context, out_path), "weasyprint"

    # auto
    try:
        from curiosity_radar.report.weasyprint_renderer import WeasyPrintRenderer

        return WeasyPrintRenderer().render(context, out_path), "weasyprint"
    except Exception:
        return Fpdf2Renderer().render(context, out_path), "fpdf2"
