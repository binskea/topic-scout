"""`chart` (Milestone 7): renders real PNGs from `analyze` output.

Per PLAN.md's definition of done: file-existence/non-trivial-size
assertions (a human already spot-checked the actual pixels once) — no
attempt to assert exact pixel content, which would be both fragile and
beside the point for a data-correctness-focused test suite.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from curiosity_radar import project_state
from curiosity_radar.cache import store
from curiosity_radar.commands import chart as chart_cmd
from curiosity_radar.errors import CommandError
from curiosity_radar.schemas import ArticleInfo

START = date(2024, 6, 1)
END = date(2024, 8, 31)  # 92 days, safely closed

# A file-existence/size check is meaningless below some tiny floor — a
# malformed/empty PNG could still technically "exist."
MIN_PNG_BYTES = 1000


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
        store.save_month(
            store.raw_dir(data_root, wiki, slot, "daily"), year_month, days, closed=True
        )


def _rising(base: int = 100, step: int = 5):
    return lambda d: base + step * (d - START).days


def _flat(value: int = 100_000):
    return lambda _d: value


def _spiky(base: int = 100, spike_days: tuple[int, ...] = (10, 45, 80), spike_value: int = 20_000):
    def _views(d: date) -> int:
        offset = (d - START).days
        return spike_value if offset in spike_days else base + (offset % 5 - 2)

    return _views


def test_renders_a_trend_chart_with_a_real_nontrivial_png(tmp_path: Path) -> None:
    _write_series(tmp_path, "en.wikipedia", "Growing_Topic", START, END, _rising())
    _write_series(tmp_path, "en.wikipedia", store.AGGREGATE_SLOT, START, END, _flat())
    project_state.create(
        tmp_path,
        "demo",
        topic_query="growing topic",
        qid="Q1",
        languages=["en"],
        articles={"en": ArticleInfo(title="Growing_Topic", wiki="en.wikipedia", exists=True)},
        start=START.isoformat(),
        end=END.isoformat(),
    )

    result = chart_cmd.run(project="demo", kinds=["trend"], data_dir=tmp_path)

    assert len(result.charts) == 1
    entry = result.charts[0]
    assert entry.kind == "trend"
    assert entry.language == "en"
    assert "spikes marked" in entry.caption
    path = Path(entry.path)
    assert path.exists()
    assert path.stat().st_size > MIN_PNG_BYTES
    assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"  # real PNG magic bytes


def test_renders_a_spike_chart_only_when_spikes_were_detected(tmp_path: Path) -> None:
    _write_series(tmp_path, "en.wikipedia", "Spiky_Topic", START, END, _spiky())
    _write_series(tmp_path, "en.wikipedia", store.AGGREGATE_SLOT, START, END, _flat())
    project_state.create(
        tmp_path,
        "demo",
        topic_query="spiky topic",
        qid="Q1",
        languages=["en"],
        articles={"en": ArticleInfo(title="Spiky_Topic", wiki="en.wikipedia", exists=True)},
        start=START.isoformat(),
        end=END.isoformat(),
    )

    result = chart_cmd.run(project="demo", kinds=["spike", "trend"], data_dir=tmp_path)

    kinds = {c.kind for c in result.charts}
    assert "spike" in kinds
    spike_entry = next(c for c in result.charts if c.kind == "spike")
    assert Path(spike_entry.path).stat().st_size > MIN_PNG_BYTES


def test_no_spike_chart_when_no_spikes_detected(tmp_path: Path) -> None:
    _write_series(tmp_path, "en.wikipedia", "Flat_Topic", START, END, _flat(500))
    _write_series(tmp_path, "en.wikipedia", store.AGGREGATE_SLOT, START, END, _flat())
    project_state.create(
        tmp_path,
        "demo",
        topic_query="flat topic",
        qid="Q1",
        languages=["en"],
        articles={"en": ArticleInfo(title="Flat_Topic", wiki="en.wikipedia", exists=True)},
        start=START.isoformat(),
        end=END.isoformat(),
    )

    result = chart_cmd.run(project="demo", kinds=["spike"], data_dir=tmp_path)
    assert result.charts == []


def test_renders_cross_language_chart_only_with_at_least_two_languages(tmp_path: Path) -> None:
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

    result = chart_cmd.run(project="cmp", kinds=["cross-language"], data_dir=tmp_path)
    assert len(result.charts) == 1
    entry = result.charts[0]
    assert entry.kind == "cross_language_bar"
    assert entry.language is None
    assert Path(entry.path).stat().st_size > MIN_PNG_BYTES


def test_single_language_project_skips_cross_language_chart(tmp_path: Path) -> None:
    _write_series(tmp_path, "en.wikipedia", "Solo_Topic", START, END, _rising())
    _write_series(tmp_path, "en.wikipedia", store.AGGREGATE_SLOT, START, END, _flat())
    project_state.create(
        tmp_path,
        "demo",
        topic_query="solo topic",
        qid="Q1",
        languages=["en"],
        articles={"en": ArticleInfo(title="Solo_Topic", wiki="en.wikipedia", exists=True)},
        start=START.isoformat(),
        end=END.isoformat(),
    )
    result = chart_cmd.run(project="demo", kinds=["cross-language"], data_dir=tmp_path)
    assert result.charts == []


def test_default_kinds_renders_all_applicable_charts(tmp_path: Path) -> None:
    _write_series(tmp_path, "en.wikipedia", "Strong_Topic", START, END, _rising(step=50))
    _write_series(tmp_path, "en.wikipedia", "Spiky_Topic", START, END, _spiky())
    _write_series(tmp_path, "en.wikipedia", store.AGGREGATE_SLOT, START, END, _flat())
    project_state.create(
        tmp_path,
        "cmp",
        topic_query="t",
        qid="Q1",
        languages=["strong_lang", "spiky_lang"],
        articles={
            "strong_lang": ArticleInfo(title="Strong_Topic", wiki="en.wikipedia", exists=True),
            "spiky_lang": ArticleInfo(title="Spiky_Topic", wiki="en.wikipedia", exists=True),
        },
        start=START.isoformat(),
        end=END.isoformat(),
    )

    result = chart_cmd.run(project="cmp", kinds=[], data_dir=tmp_path)
    kinds = {c.kind for c in result.charts}
    assert kinds == {"trend", "spike", "cross_language_bar"}


def test_unknown_kind_is_a_clean_error(tmp_path: Path) -> None:
    project_state.create(
        tmp_path,
        "demo",
        topic_query="t",
        qid="Q1",
        languages=["en"],
        articles={"en": ArticleInfo(title="X", wiki="en.wikipedia", exists=True)},
        start=START.isoformat(),
        end=END.isoformat(),
    )
    with pytest.raises(CommandError) as exc_info:
        chart_cmd.run(project="demo", kinds=["bogus"], data_dir=tmp_path)
    assert exc_info.value.code == "unknown_chart_kind"


def test_unknown_project_is_a_clean_error(tmp_path: Path) -> None:
    with pytest.raises(CommandError) as exc_info:
        chart_cmd.run(project="nope", kinds=[], data_dir=tmp_path)
    assert exc_info.value.code == "project_not_found"


def test_chart_does_not_force_recompute_of_an_existing_derived_result(tmp_path: Path) -> None:
    from curiosity_radar.commands import analyze as analyze_cmd

    _write_series(tmp_path, "en.wikipedia", "Growing_Topic", START, END, _rising())
    _write_series(tmp_path, "en.wikipedia", store.AGGREGATE_SLOT, START, END, _flat())
    project_state.create(
        tmp_path,
        "demo",
        topic_query="growing topic",
        qid="Q1",
        languages=["en"],
        articles={"en": ArticleInfo(title="Growing_Topic", wiki="en.wikipedia", exists=True)},
        start=START.isoformat(),
        end=END.isoformat(),
    )
    analyze_cmd.run(
        project="demo",
        compare_languages=True,
        placebo_basket_size=20,
        force_recompute=False,
        data_dir=tmp_path,
    )
    derived_dir = tmp_path / "cache" / "derived" / str(analyze_cmd.SCHEMA_VERSION) / "demo"
    (derived_file,) = derived_dir.glob("*.json")
    before = derived_file.read_bytes()

    chart_cmd.run(project="demo", kinds=["trend"], data_dir=tmp_path)

    after = derived_file.read_bytes()
    assert before == after
