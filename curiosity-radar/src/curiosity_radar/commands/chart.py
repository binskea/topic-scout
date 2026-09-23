"""`chart`: render chart image files from derived stats (SPEC.md §3.4).

Milestone 7: renders real matplotlib PNGs from `analyze`'s already-computed
stats — never recomputes them — plus the underlying per-day series that
`analyze`'s own compact JSON deliberately omits (SPEC.md §3: "never echoes
a raw time-series array"). That series is reconstructed via
`analyze.build_language_series`, the exact same series-building code
`analyze` itself uses, so this never duplicates any *statistics*
computation (trend/spike detection), only the already-cached data read
needed to actually draw a line.

Three chart kinds, matching SPEC.md §3.4's example JSON shape and its
`--kinds trend,spike,cross-language` CLI values (the output `kind` for the
last one is `cross_language_bar`, exactly as SPEC.md's example shows):
- `trend`: one per language with enough data for a trend read — the
  normalized daily series with MAD-flagged spike days marked.
- `spike`: one per language that actually has spike days — a small bar
  chart of each spike's MAD z-score.
- `cross_language_bar`: one chart (not per-language), only when at least
  two languages were compared — relative Theil-Sen slope per language.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

from datetime import date  # noqa: E402
from pathlib import Path  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402

from curiosity_radar import clock, project_state  # noqa: E402
from curiosity_radar.cache.paths import ensure_subdir, resolve_data_dir  # noqa: E402
from curiosity_radar.commands import analyze as analyze_cmd  # noqa: E402
from curiosity_radar.errors import CommandError  # noqa: E402
from curiosity_radar.schemas import (  # noqa: E402
    AnalyzeResult,
    ChartEntry,
    ChartResult,
    LanguageAnalysis,
)

ALL_KINDS = ("trend", "spike", "cross-language")
DEFAULT_PLACEBO_BASKET_SIZE = 20

TREND_COLOR = "#4C72B0"
SPIKE_COLOR = "#C44E52"
CROSS_LANG_COLOR = "#55A868"


def run(*, project: str, kinds: list[str], data_dir: Path | None) -> ChartResult:
    data_root = resolve_data_dir(data_dir)
    state = project_state.load(data_root, project)
    if state is None:
        raise CommandError(
            "project_not_found",
            f"No saved project '{project}'.",
            "Run resolve --save-as, fetch, and analyze first.",
        )

    requested = kinds or list(ALL_KINDS)
    for kind in requested:
        if kind not in ALL_KINDS:
            raise CommandError(
                "unknown_chart_kind",
                f"Unknown chart kind '{kind}'.",
                f"Choose from: {', '.join(ALL_KINDS)}.",
            )

    result = analyze_cmd.run(
        project=project,
        compare_languages=True,
        placebo_basket_size=DEFAULT_PLACEBO_BASKET_SIZE,
        force_recompute=False,
        data_dir=data_root,
    )

    charts_dir = ensure_subdir(data_root, "charts", state.slug)
    today = clock.today()
    start, end = analyze_cmd.analysis_date_range(state)
    excluded = analyze_cmd.excluded_days(state, start, end)
    articles = analyze_cmd.resolved_articles(state)
    topic_label = state.topic_query or state.slug

    entries: list[ChartEntry] = []

    if "trend" in requested:
        for lang, article in articles.items():
            lang_analysis = result.languages.get(lang)
            if lang_analysis is None or not lang_analysis.data_quality.sufficient_for_trend:
                continue
            series = analyze_cmd.build_language_series(
                data_root, article, start, end, excluded, today
            )
            path = charts_dir / f"trend_{lang}.png"
            _render_trend_chart(path, series, lang_analysis, f"{topic_label} — {article.wiki}")
            entries.append(
                ChartEntry(
                    kind="trend",
                    language=lang,
                    path=str(path),
                    caption=(
                        f"Normalized interest in '{topic_label}' on {article.wiki}, spikes marked "
                        f"(with spikes: {lang_analysis.normalized_trend.confidence_label}; "
                        "excluding spikes: "
                        f"{lang_analysis.trend_excluding_spikes.confidence_label})"
                    ),
                )
            )

    if "spike" in requested:
        for lang, article in articles.items():
            lang_analysis = result.languages.get(lang)
            if lang_analysis is None or not lang_analysis.spikes_detected:
                continue
            path = charts_dir / f"spike_{lang}.png"
            _render_spike_chart(path, lang_analysis)
            entries.append(
                ChartEntry(
                    kind="spike",
                    language=lang,
                    path=str(path),
                    caption=(
                        f"{len(lang_analysis.spikes_detected)} spike day(s) detected on "
                        f"{article.wiki} (MAD z-score)"
                    ),
                )
            )

    if "cross-language" in requested and len(result.cross_language_ranking) >= 2:
        path = charts_dir / "cross_lang.png"
        _render_cross_language_chart(path, result)
        langs = ", ".join(entry.lang for entry in result.cross_language_ranking)
        entries.append(
            ChartEntry(
                kind="cross_language_bar",
                path=str(path),
                caption=f"Relative trend strength across {langs}",
            )
        )

    return ChartResult(project=project, charts=entries)


def _render_trend_chart(
    path: Path, series: analyze_cmd.LanguageSeries, lang_analysis: LanguageAnalysis, title: str
) -> None:
    dates = [date.fromisoformat(d) for d in series.days]
    spike_dates = {s.date for s in lang_analysis.spikes_detected}

    fig, ax = plt.subplots(figsize=(8, 3))
    # matplotlib's own stubs are stricter than its runtime behavior, which
    # accepts (and correctly formats) a plain list of `datetime.date`.
    x_values: list[float] = dates  # type: ignore[assignment]
    ax.plot(x_values, series.normalized, color=TREND_COLOR, linewidth=1, label="normalized share")
    paired = list(zip(dates, series.normalized, series.days, strict=True))
    spike_x = [d for d, _, iso in paired if iso in spike_dates]
    spike_y = [v for _, v, iso in paired if iso in spike_dates]
    if spike_x:
        ax.scatter(spike_x, spike_y, color=SPIKE_COLOR, zorder=3, label="spike")  # type: ignore[arg-type]
    ax.set_title(title, fontsize=10)
    ax.set_ylabel("share of wiki traffic")
    ax.legend(loc="upper left", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=100)
    plt.close(fig)


def _render_spike_chart(path: Path, lang_analysis: LanguageAnalysis) -> None:
    spikes_sorted = sorted(lang_analysis.spikes_detected, key=lambda s: s.date)
    labels = [s.date for s in spikes_sorted]
    values = [s.z_mad for s in spikes_sorted]

    fig, ax = plt.subplots(figsize=(6, 3))
    ax.bar(labels, values, color=SPIKE_COLOR)
    ax.set_ylabel("MAD z-score")
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=100)
    plt.close(fig)


def _render_cross_language_chart(path: Path, result: AnalyzeResult) -> None:
    ranking = result.cross_language_ranking
    langs = [entry.lang for entry in ranking]
    slopes = [
        result.languages[entry.lang].normalized_trend.theil_sen_slope_per_day for entry in ranking
    ]

    fig, ax = plt.subplots(figsize=(6, 3))
    ax.bar(langs, slopes, color=CROSS_LANG_COLOR)
    ax.set_ylabel("Theil-Sen slope / day")
    fig.tight_layout()
    fig.savefig(path, dpi=100)
    plt.close(fig)
