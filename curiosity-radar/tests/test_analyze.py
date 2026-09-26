"""`analyze` (Milestone 6), wiring Milestones 4-5's stats together over
pre-populated `cache/raw/` fixtures — analyze never touches the network,
so these tests write raw cache files directly (as `fetch` would have)
rather than going through any HTTP layer at all.

Per PLAN.md's definition of done: produces the exact SPEC.md §3.3 JSON
shape, and bumping the derived-cache schema version triggers recomputation
(one new `cache/derived/` file) without any raw refetch.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from curiosity_radar import project_state
from curiosity_radar.cache import basket as basket_cache
from curiosity_radar.cache import store
from curiosity_radar.commands import analyze as analyze_cmd
from curiosity_radar.project_state import ExclusionRange
from curiosity_radar.schemas import ArticleInfo

START = date(2024, 6, 1)
END = date(2024, 8, 31)  # 92 days, safely closed relative to any real "today"


def _write_series(
    data_root: Path, wiki: str, slot: str, start: date, end: date, views_for_day
) -> None:
    for year_month in store.iter_months(start, end):
        month_start, month_end = store.month_bounds(year_month)
        days = []
        d = month_start
        while d <= month_end:
            days.append(store.DayPoint(date=d.isoformat(), views=views_for_day(d)))
            d += timedelta(days=1)
        directory = store.raw_dir(data_root, wiki, slot, "daily")
        store.save_month(directory, year_month, days, closed=True)


def _make_project(
    tmp_path: Path,
    *,
    slug: str = "demo",
    lang: str = "en",
    wiki: str = "en.wikipedia",
    title: str = "Growing_Topic",
    article_series,
    aggregate_series,
    start: date = START,
    end: date = END,
    exclusions: list[ExclusionRange] | None = None,
) -> None:
    _write_series(tmp_path, wiki, title, start, end, article_series)
    _write_series(tmp_path, wiki, store.AGGREGATE_SLOT, start, end, aggregate_series)
    state = project_state.create(
        tmp_path,
        slug,
        topic_query="growing topic",
        qid="Q1",
        languages=[lang],
        articles={lang: ArticleInfo(title=title, wiki=wiki, exists=True)},
        start=start.isoformat(),
        end=end.isoformat(),
    )
    if exclusions:
        state.exclusions = exclusions
        project_state.save(tmp_path, state)


def _rising(base: int = 100, step: int = 5):
    def _views(d: date) -> int:
        return base + step * (d - START).days

    return _views


def _flat(value: int = 100_000):
    def _views(_d: date) -> int:
        return value

    return _views


def test_analyze_produces_a_clear_growth_trend_from_real_cached_data(tmp_path: Path) -> None:
    _make_project(tmp_path, article_series=_rising(), aggregate_series=_flat())

    result = analyze_cmd.run(
        project="demo",
        compare_languages=True,
        placebo_basket_size=20,
        force_recompute=False,
        data_dir=tmp_path,
    )

    assert result.project == "demo"
    lang_result = result.languages["en"]
    assert lang_result.data_quality.sufficient_for_trend is True
    assert lang_result.data_quality.total_days == 92
    assert lang_result.normalized_trend.mann_kendall.trend == "increasing"
    assert lang_result.normalized_trend.theil_sen_slope_per_day > 0
    assert lang_result.normalized_trend.confidence_label == "strong evidence of growth"
    assert lang_result.placebo is not None
    assert "insufficient comparison data" in lang_result.placebo.verdict
    assert len(result.cross_language_ranking) == 1
    assert result.cross_language_ranking[0].lang == "en"
    assert result.cross_language_ranking[0].rank == 1
    assert result.cross_language_ranking[0].reason == "strong evidence of growth"


def test_analyze_reports_insufficient_data_when_nothing_was_ever_fetched(tmp_path: Path) -> None:
    project_state.create(
        tmp_path,
        "empty",
        topic_query="nothing fetched",
        qid="Q2",
        languages=["en"],
        articles={"en": ArticleInfo(title="Never_Fetched", wiki="en.wikipedia", exists=True)},
        start=START.isoformat(),
        end=END.isoformat(),
    )
    result = analyze_cmd.run(
        project="empty",
        compare_languages=True,
        placebo_basket_size=20,
        force_recompute=False,
        data_dir=tmp_path,
    )
    lang_result = result.languages["en"]
    assert lang_result.data_quality.sufficient_for_trend is False
    assert lang_result.data_quality.reason == "all_zero_or_empty"
    assert lang_result.placebo is None


def test_analyze_reports_too_short_for_a_narrow_date_range(tmp_path: Path) -> None:
    short_start, short_end = date(2024, 8, 1), date(2024, 8, 10)
    _make_project(
        tmp_path,
        article_series=_rising(),
        aggregate_series=_flat(),
        start=short_start,
        end=short_end,
    )
    result = analyze_cmd.run(
        project="demo",
        compare_languages=True,
        placebo_basket_size=20,
        force_recompute=False,
        data_dir=tmp_path,
    )
    lang_result = result.languages["en"]
    assert lang_result.data_quality.sufficient_for_trend is False
    assert lang_result.data_quality.reason == "too_short"
    assert lang_result.data_quality.total_days == 10


def test_analyze_excludes_dropped_date_ranges_from_the_series(tmp_path: Path) -> None:
    _make_project(
        tmp_path,
        article_series=_rising(),
        aggregate_series=_flat(),
        exclusions=[ExclusionRange(start="2024-07-01", end="2024-07-31")],
    )
    result = analyze_cmd.run(
        project="demo",
        compare_languages=True,
        placebo_basket_size=20,
        force_recompute=False,
        data_dir=tmp_path,
    )
    lang_result = result.languages["en"]
    # 92 days total, minus the 31 excluded July days.
    assert lang_result.data_quality.total_days == 92 - 31


def test_analyze_result_is_cached_and_reused_on_a_second_call(tmp_path: Path) -> None:
    _make_project(tmp_path, article_series=_rising(), aggregate_series=_flat())
    first = analyze_cmd.run(
        project="demo",
        compare_languages=True,
        placebo_basket_size=20,
        force_recompute=False,
        data_dir=tmp_path,
    )

    derived_root = tmp_path / "cache" / "derived" / str(analyze_cmd.SCHEMA_VERSION) / "demo"
    files_before = list(derived_root.glob("*.json"))
    assert len(files_before) == 1

    second = analyze_cmd.run(
        project="demo",
        compare_languages=True,
        placebo_basket_size=20,
        force_recompute=False,
        data_dir=tmp_path,
    )
    files_after = list(derived_root.glob("*.json"))
    assert len(files_after) == 1  # no new file: served from the derived cache
    assert second.model_dump() == first.model_dump()


def test_force_recompute_bypasses_the_derived_cache(tmp_path: Path) -> None:
    _make_project(tmp_path, article_series=_rising(), aggregate_series=_flat())
    analyze_cmd.run(
        project="demo",
        compare_languages=True,
        placebo_basket_size=20,
        force_recompute=False,
        data_dir=tmp_path,
    )
    derived_root = tmp_path / "cache" / "derived" / str(analyze_cmd.SCHEMA_VERSION) / "demo"
    (path,) = derived_root.glob("*.json")
    path.write_text('{"tampered": true}')

    result = analyze_cmd.run(
        project="demo",
        compare_languages=True,
        placebo_basket_size=20,
        force_recompute=True,
        data_dir=tmp_path,
    )
    assert result.project == "demo"  # recomputed fresh, not the tampered stub
    assert path.read_text() != '{"tampered": true}'


def test_bumping_schema_version_recomputes_without_any_raw_refetch(
    monkeypatch, tmp_path: Path
) -> None:
    _make_project(tmp_path, article_series=_rising(), aggregate_series=_flat())
    analyze_cmd.run(
        project="demo",
        compare_languages=True,
        placebo_basket_size=20,
        force_recompute=False,
        data_dir=tmp_path,
    )
    v1_dir = tmp_path / "cache" / "derived" / "1" / "demo"
    assert len(list(v1_dir.glob("*.json"))) == 1

    raw_files_before = sorted(p.read_bytes() for p in (tmp_path / "cache" / "raw").rglob("*.json"))

    monkeypatch.setattr(analyze_cmd, "SCHEMA_VERSION", 2)
    analyze_cmd.run(
        project="demo",
        compare_languages=True,
        placebo_basket_size=20,
        force_recompute=False,
        data_dir=tmp_path,
    )

    # Old version's derived file untouched; a new one appears under v2.
    assert len(list(v1_dir.glob("*.json"))) == 1
    v2_dir = tmp_path / "cache" / "derived" / "2" / "demo"
    assert len(list(v2_dir.glob("*.json"))) == 1

    # No raw cache file changed — analyze has no HTTP client at all, so a
    # schema-version bump can only ever trigger local recomputation.
    raw_files_after = sorted(p.read_bytes() for p in (tmp_path / "cache" / "raw").rglob("*.json"))
    assert raw_files_before == raw_files_after


def test_cross_language_ranking_orders_strongest_trend_first(tmp_path: Path) -> None:
    _write_series(tmp_path, "en.wikipedia", "Strong_Topic", START, END, _rising(step=50))
    _write_series(tmp_path, "en.wikipedia", "Weak_Topic", START, END, _flat(500))
    _write_series(tmp_path, "en.wikipedia", store.AGGREGATE_SLOT, START, END, _flat())
    project_state.create(
        tmp_path,
        "cmp",
        topic_query="t",
        qid="Q1",
        languages=["strong_lang", "weak_lang"],
        articles={
            "strong_lang": ArticleInfo(title="Strong_Topic", wiki="en.wikipedia", exists=True),
            "weak_lang": ArticleInfo(title="Weak_Topic", wiki="en.wikipedia", exists=True),
        },
        start=START.isoformat(),
        end=END.isoformat(),
    )

    result = analyze_cmd.run(
        project="cmp",
        compare_languages=True,
        placebo_basket_size=20,
        force_recompute=False,
        data_dir=tmp_path,
    )
    assert [entry.lang for entry in result.cross_language_ranking] == ["strong_lang", "weak_lang"]
    assert result.cross_language_ranking[0].rank == 1
    assert result.cross_language_ranking[1].rank == 2


def test_analyze_produces_a_real_placebo_verdict_from_a_sourced_basket(tmp_path: Path) -> None:
    """Milestone 13: with a `cache/basket/` file present (as `fetch` now
    writes), `analyze` must produce a real verdict rather than always
    hitting the empty-pool "insufficient comparison data" path — and must
    apply both the popularity-tier and category-exclusion filters, not just
    dump every cached candidate straight into the basket."""
    wiki = "en.wikipedia"
    title = "Growing_Topic"
    _write_series(tmp_path, wiki, title, START, END, _rising(base=1000, step=50))
    _write_series(tmp_path, wiki, store.AGGREGATE_SLOT, START, END, _flat(100_000))

    candidates = []
    for i in range(15):
        candidate_title = f"Flat_Candidate_{i}"
        _write_series(tmp_path, wiki, candidate_title, START, END, _flat(1000 + i))
        candidates.append(basket_cache.BasketCandidateMeta(title=candidate_title, category_qids=[]))

    # Shares the topic's own category — must be excluded despite being in the
    # right popularity tier.
    same_category_title = "Same_Category_Candidate"
    _write_series(tmp_path, wiki, same_category_title, START, END, _flat(1000))
    candidates.append(
        basket_cache.BasketCandidateMeta(title=same_category_title, category_qids=["Q_TOPIC_CAT"])
    )

    # Wildly more popular (outside ±1 order of magnitude) — must be excluded
    # by the popularity-tier filter, unrelated category or not.
    too_popular_title = "Too_Popular_Candidate"
    _write_series(tmp_path, wiki, too_popular_title, START, END, _flat(10_000_000))
    candidates.append(basket_cache.BasketCandidateMeta(title=too_popular_title, category_qids=[]))

    basket_cache.save(
        tmp_path,
        wiki,
        basket_cache.BasketCacheFile(sourced_month="2024-08", candidates=candidates),
    )

    project_state.create(
        tmp_path,
        "demo",
        topic_query="growing topic",
        qid="Q1",
        languages=["en"],
        articles={"en": ArticleInfo(title=title, wiki=wiki, exists=True)},
        category_qids=["Q_TOPIC_CAT"],
        start=START.isoformat(),
        end=END.isoformat(),
    )

    result = analyze_cmd.run(
        project="demo",
        compare_languages=True,
        placebo_basket_size=20,
        force_recompute=False,
        data_dir=tmp_path,
    )
    lang_result = result.languages["en"]
    assert lang_result.placebo is not None
    assert "insufficient comparison data" not in lang_result.placebo.verdict
    # 15 flat candidates eligible; same-category and too-popular both dropped.
    assert lang_result.placebo.basket_size == 15
    assert lang_result.placebo.basket_median_slope == 0.0
    assert lang_result.placebo.topic_slope_percentile_vs_basket == 100.0
    assert lang_result.placebo.verdict == "trend exceeds wiki-wide background drift"


def test_analyze_still_reports_insufficient_data_when_no_basket_was_ever_sourced(
    tmp_path: Path,
) -> None:
    """A project whose wiki was never `fetch`ed with basket sourcing (or
    predates Milestone 13 entirely) has no `cache/basket/` file at all —
    `analyze` must degrade to the pre-Milestone-13 behavior, not crash."""
    _make_project(tmp_path, article_series=_rising(), aggregate_series=_flat())
    result = analyze_cmd.run(
        project="demo",
        compare_languages=True,
        placebo_basket_size=20,
        force_recompute=False,
        data_dir=tmp_path,
    )
    lang_result = result.languages["en"]
    assert lang_result.placebo is not None
    assert "insufficient comparison data" in lang_result.placebo.verdict


def test_compare_languages_false_skips_ranking(tmp_path: Path) -> None:
    _make_project(tmp_path, article_series=_rising(), aggregate_series=_flat())
    result = analyze_cmd.run(
        project="demo",
        compare_languages=False,
        placebo_basket_size=20,
        force_recompute=False,
        data_dir=tmp_path,
    )
    assert result.cross_language_ranking == []
