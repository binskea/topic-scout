"""`analyze`: trend + spike + placebo stats (SPEC.md §3.3).

Milestone 6: wires Milestones 4-5's pure stats functions together, reading
exclusively from `cache/raw/` (never the network) per SPEC.md §2. Results
are cached under `cache/derived/<schema-version>/<project>/<hash>.json`,
keyed by a hash of the project's exclusions/date-range plus the actual raw
cache file contents used — so bumping `SCHEMA_VERSION` (whenever the
trend/spike/placebo logic or thresholds change) invalidates only derived
results, never triggers a raw refetch (SPEC.md §4).

Placebo-basket **sourcing** is intentionally not implemented here: SPEC.md
§9 item 1 leaves the exact live-sourcing mechanism as an open question,
and Milestone 5 built only the pure selection/verdict math against a
caller-supplied candidate pool. Passing an empty pool through the same,
already-tested `stats.placebo.compute_verdict` path yields an honest
"insufficient comparison data" verdict rather than a fabricated one or a
bare `null` — see PLAN.md Milestone 5/6 for the full reasoning.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from curiosity_radar import clock, project_state
from curiosity_radar.cache import store
from curiosity_radar.cache.paths import resolve_data_dir
from curiosity_radar.errors import CommandError
from curiosity_radar.project_state import ProjectState
from curiosity_radar.schemas import (
    AnalyzeResult,
    ArticleInfo,
    CrossLanguageRankingEntry,
    DataQuality,
    LanguageAnalysis,
    MannKendall,
    Spike,
    TrendResult,
)
from curiosity_radar.stats import normalize, placebo, spikes, trend

SCHEMA_VERSION = 1
GRANULARITY = "daily"

_CONFIDENCE_TIER = {
    "strong evidence of growth": 3,
    "likely growing": 2,
    "no clear trend detected": 1,
    "likely declining": 0,
    "strong evidence of decline": -1,
    trend.INSUFFICIENT_DATA_LABEL: -2,
}


def run(
    *,
    project: str,
    compare_languages: bool,
    placebo_basket_size: int,
    force_recompute: bool,
    data_dir: Path | None,
) -> AnalyzeResult:
    data_root = resolve_data_dir(data_dir)
    state = project_state.load(data_root, project)
    if state is None:
        raise CommandError(
            "project_not_found",
            f"No saved project '{project}'.",
            "Run resolve --save-as first, or check the slug via `project list`.",
        )

    raw_hashes = _collect_raw_file_hashes(data_root, state)
    analysis_hash = _compute_analysis_hash(state, raw_hashes, placebo_basket_size)
    derived_path = _derived_path(data_root, state.slug, analysis_hash)

    if not force_recompute and derived_path.exists():
        return AnalyzeResult.model_validate_json(derived_path.read_text())

    result = _compute_analysis(
        data_root,
        state,
        compare_languages=compare_languages,
        placebo_basket_size=placebo_basket_size,
    )

    derived_path.parent.mkdir(parents=True, exist_ok=True)
    derived_path.write_text(result.model_dump_json(indent=2))

    state.last_analyze_at = datetime.now(UTC).isoformat()
    state.analyze_stale = False
    project_state.save(data_root, state)

    return result


def _derived_path(data_root: Path, slug: str, analysis_hash: str) -> Path:
    return data_root / "cache" / "derived" / str(SCHEMA_VERSION) / slug / f"{analysis_hash}.json"


def resolved_articles(state: ProjectState) -> dict[str, ArticleInfo]:
    """Languages with a real, existing resolved article — shared with `chart`
    (Milestone 7), which needs the same set to know what it can render."""
    return {
        lang: article
        for lang in state.languages
        if (article := state.articles.get(lang)) is not None
        and article.exists
        and article.title is not None
    }


def analysis_date_range(state: ProjectState) -> tuple[date, date]:
    return date.fromisoformat(state.date_range_start), date.fromisoformat(state.date_range_end)


def _collect_raw_file_hashes(data_root: Path, state: ProjectState) -> list[str]:
    hashes: list[str] = []
    wikis_seen: set[str] = set()
    for article in resolved_articles(state).values():
        assert article.title is not None
        for slot in (article.title, article.redirect_from):
            if slot is None:
                continue
            hashes.extend(_hash_dir(store.raw_dir(data_root, article.wiki, slot, GRANULARITY)))
        wikis_seen.add(article.wiki)
    for wiki in wikis_seen:
        hashes.extend(_hash_dir(store.raw_dir(data_root, wiki, store.AGGREGATE_SLOT, GRANULARITY)))
    return hashes


def _hash_dir(directory: Path) -> list[str]:
    if not directory.exists():
        return []
    return [
        hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(directory.glob("*.json"))
    ]


def _compute_analysis_hash(
    state: ProjectState, raw_hashes: list[str], placebo_basket_size: int
) -> str:
    payload = json.dumps(
        {
            "project": state.slug,
            "raw_file_hashes": sorted(raw_hashes),
            "exclusions": sorted(f"{e.start}:{e.end}" for e in state.exclusions),
            "date_range": [state.date_range_start, state.date_range_end],
            "placebo_basket_size": placebo_basket_size,
            "schema_version": SCHEMA_VERSION,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def excluded_days(state: ProjectState, start: date, end: date) -> set[str]:
    excluded: set[str] = set()
    for ex in state.exclusions:
        ex_start = max(date.fromisoformat(ex.start), start)
        ex_end = min(date.fromisoformat(ex.end), end)
        d = ex_start
        while d <= ex_end:
            excluded.add(d.isoformat())
            d += timedelta(days=1)
    return excluded


def _summed_series(
    data_root: Path, article: ArticleInfo, start: date, end: date, today: date
) -> dict[str, int]:
    assert article.title is not None
    series = store.read_cached_range(
        data_root, article.wiki, article.title, GRANULARITY, start, end, today
    )
    if not article.redirect_from:
        return series
    alias = store.read_cached_range(
        data_root, article.wiki, article.redirect_from, GRANULARITY, start, end, today
    )
    combined = dict(series)
    for day, views in alias.items():
        combined[day] = combined.get(day, 0) + views
    return combined


@dataclass
class LanguageSeries:
    """The per-day series behind one language's `LanguageAnalysis` — never
    part of `analyze`'s own compact JSON output (SPEC.md §3: "never echoes
    a raw time-series array"), but `chart` (Milestone 7) needs exactly this
    to actually draw a line, so it's exposed here rather than duplicated."""

    days: list[str]
    raw_views: list[int]
    aggregate_views: list[int]
    day_offsets: list[int]
    normalized: list[float]


def build_language_series(
    data_root: Path, article: ArticleInfo, start: date, end: date, excluded: set[str], today: date
) -> LanguageSeries:
    raw_by_day = _summed_series(data_root, article, start, end, today)
    aggregate_by_day = store.read_cached_range(
        data_root, article.wiki, store.AGGREGATE_SLOT, GRANULARITY, start, end, today
    )

    days: list[str] = []
    d = start
    while d <= end:
        iso = d.isoformat()
        if iso not in excluded and iso in raw_by_day:
            days.append(iso)
        d += timedelta(days=1)

    raw_views = [raw_by_day[day] for day in days]
    aggregate_views = [aggregate_by_day.get(day, 0) for day in days]
    day_offsets = [(date.fromisoformat(day) - start).days for day in days]
    normalized = normalize.normalize_by_aggregate(raw_views, aggregate_views)

    return LanguageSeries(
        days=days,
        raw_views=raw_views,
        aggregate_views=aggregate_views,
        day_offsets=day_offsets,
        normalized=normalized,
    )


def _insufficient_trend() -> TrendResult:
    return TrendResult(
        theil_sen_slope_per_day=0.0,
        mann_kendall=MannKendall(trend="no trend", p_value=1.0, tau=0.0),
        confidence_label=trend.INSUFFICIENT_DATA_LABEL,
    )


def _analyze_language(
    data_root: Path,
    article: ArticleInfo,
    start: date,
    end: date,
    excluded: set[str],
    today: date,
    placebo_basket_size: int,  # not yet used — no basket-sourcing mechanism exists yet
) -> LanguageAnalysis:
    series = build_language_series(data_root, article, start, end, excluded, today)
    days, raw_views, day_offsets = series.days, series.raw_views, series.day_offsets

    total_days = len(days)
    zero_view_days = sum(1 for v in raw_views if v == 0)

    check = trend.check_sufficiency(raw_views)
    if not check.sufficient:
        insufficient = _insufficient_trend()
        return LanguageAnalysis(
            normalized_trend=insufficient,
            trend_excluding_spikes=insufficient,
            spikes_detected=[],
            placebo=None,
            data_quality=DataQuality(
                total_days=total_days,
                zero_view_days=zero_view_days,
                sufficient_for_trend=False,
                reason=check.reason,
            ),
        )

    normalized = series.normalized
    normalized_trend = trend.compute_trend(normalized, x=day_offsets)

    detected = spikes.detect_spikes(normalized)
    spike_positions = {s.index for s in detected}
    total_raw_views = sum(raw_views) or 1
    spikes_detected = [
        Spike(
            date=days[s.index],
            z_mad=s.z_mad,
            share_of_total_views=raw_views[s.index] / total_raw_views,
        )
        for s in detected
    ]

    kept = [i for i in range(len(normalized)) if i not in spike_positions]
    if kept and len(kept) != len(normalized):
        trend_excluding_spikes = trend.compute_trend(
            [normalized[i] for i in kept], x=[day_offsets[i] for i in kept]
        )
    else:
        trend_excluding_spikes = normalized_trend

    # No live basket-sourcing mechanism yet (see module docstring) — an
    # empty candidate pool still yields a real, honest Placebo verdict via
    # the same tested path a populated one would.
    basket_slopes: list[float] = []
    placebo_result = placebo.compute_verdict(
        normalized_trend.theil_sen_slope_per_day, basket_slopes
    )

    return LanguageAnalysis(
        normalized_trend=normalized_trend,
        trend_excluding_spikes=trend_excluding_spikes,
        spikes_detected=spikes_detected,
        placebo=placebo_result,
        data_quality=DataQuality(
            total_days=total_days, zero_view_days=zero_view_days, sufficient_for_trend=True
        ),
    )


def _rank_languages(languages: dict[str, LanguageAnalysis]) -> list[CrossLanguageRankingEntry]:
    def sort_key(item: tuple[str, LanguageAnalysis]) -> tuple[int, float]:
        _, analysis = item
        tier = _CONFIDENCE_TIER.get(analysis.normalized_trend.confidence_label, 0)
        return (tier, analysis.normalized_trend.theil_sen_slope_per_day)

    ranked = sorted(languages.items(), key=sort_key, reverse=True)
    entries = []
    for rank, (lang, analysis) in enumerate(ranked, start=1):
        reason = analysis.normalized_trend.confidence_label
        if analysis.placebo is not None and "insufficient" not in analysis.placebo.verdict:
            reason = f"{reason}; {analysis.placebo.verdict}"
        entries.append(CrossLanguageRankingEntry(lang=lang, rank=rank, reason=reason))
    return entries


def _compute_analysis(
    data_root: Path, state: ProjectState, *, compare_languages: bool, placebo_basket_size: int
) -> AnalyzeResult:
    today = clock.today()
    start, end = analysis_date_range(state)
    excluded = excluded_days(state, start, end)

    languages: dict[str, LanguageAnalysis] = {}
    for lang, article in resolved_articles(state).items():
        languages[lang] = _analyze_language(
            data_root, article, start, end, excluded, today, placebo_basket_size
        )

    ranking = _rank_languages(languages) if compare_languages else []

    return AnalyzeResult(
        project=state.slug,
        generated_at=datetime.now(UTC).isoformat(),
        languages=languages,
        cross_language_ranking=ranking,
    )
