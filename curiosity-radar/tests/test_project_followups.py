"""Milestone 9: `project list/show/set/fork` (SPEC.md §3.7) plus the two
named cheap-follow-up flows from SPEC.md §2, asserted on actual *network*
behavior, not just output shape (`test_cli_contracts.py` already covers the
`project` subcommands' JSON shape).

- "Add Slovak": `project set --add-language sk` then `fetch` must resolve
  and pull pageviews for Slovak only — the already-resolved, already-cached
  languages must not trigger a single extra HTTP request.
- "Drop 2024": `project set --exclude-date-range ...` then `analyze` must be
  pure local recomputation over already-cached raw data — zero HTTP
  requests of any kind, proven by making every network entry point raise if
  called at all, not just by inspecting a request counter.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest
from _cassette import SequentialCassette

from curiosity_radar import project_state
from curiosity_radar.cache import store
from curiosity_radar.commands import analyze as analyze_cmd
from curiosity_radar.commands import fetch as fetch_cmd
from curiosity_radar.commands import project as project_cmd
from curiosity_radar.commands import resolve as resolve_cmd
from curiosity_radar.schemas import ArticleInfo
from curiosity_radar.wikimedia import http as http_module
from curiosity_radar.wikimedia.http import build_client as real_build_client

START = date(2024, 8, 1)
END = date(2024, 8, 31)  # a single, safely-closed month


def _write_month(data_root: Path, wiki: str, slot: str, start: date, end: date, views: int) -> None:
    days = []
    d = start
    while d <= end:
        days.append(store.DayPoint(date=d.isoformat(), views=views))
        d += timedelta(days=1)
    directory = store.raw_dir(data_root, wiki, slot, "daily")
    store.save_month(directory, store.month_key(start), days, closed=True)


def _use_cassette(monkeypatch: pytest.MonkeyPatch, cassette: SequentialCassette) -> None:
    def _transport_factory(transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
        return real_build_client(cassette.transport())

    monkeypatch.setattr(fetch_cmd, "build_client", _transport_factory)
    monkeypatch.setattr(resolve_cmd, "build_client", _transport_factory)


def test_add_language_only_fetches_the_new_language(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # pl and cs already resolved and already fully cached for August 2024 —
    # as if an earlier `resolve --save-as` + `fetch` had already run.
    project_state.create(
        tmp_path,
        "demo",
        topic_query="intermittent fasting",
        qid="Q1",
        languages=["pl", "cs"],
        articles={
            "pl": ArticleInfo(title="Glodowka", wiki="pl.wikipedia", exists=True),
            "cs": ArticleInfo(title="Pust", wiki="cs.wikipedia", exists=True),
        },
        start=START.isoformat(),
        end=END.isoformat(),
    )
    for wiki, title in (("pl.wikipedia", "Glodowka"), ("cs.wikipedia", "Pust")):
        _write_month(tmp_path, wiki, title, START, END, views=500)
        _write_month(tmp_path, wiki, store.AGGREGATE_SLOT, START, END, views=1_000_000)

    result = project_cmd.set_project(
        project="demo",
        add_language="sk",
        remove_language=None,
        exclude_date_range=None,
        set_date_range=None,
        data_dir=tmp_path,
    )
    assert result.languages == ["pl", "cs", "sk"]
    assert result.stale.fetch_stale is True

    # Only Slovak is missing a resolved article and cached pageviews — the
    # cassette below has exactly the calls that resolving+fetching Slovak
    # requires. Any attempt to re-resolve or re-fetch pl/cs would either
    # exhaust the cassette early or hit an unexpected-request assertion.
    cassette = SequentialCassette(
        [
            (
                {"action": "wbgetentities", "ids": "Q1"},
                {
                    "entities": {
                        "Q1": {
                            "type": "item",
                            "id": "Q1",
                            "sitelinks": {
                                "skwiki": {
                                    "site": "skwiki",
                                    "title": "Prerusovany_post",
                                    "badges": [],
                                }
                            },
                        }
                    },
                    "success": 1,
                },
            ),
            (
                {"action": "query", "titles": "Prerusovany_post"},
                {
                    "batchcomplete": "",
                    "query": {"pages": {"1": {"pageid": 1, "ns": 0, "title": "Prerusovany_post"}}},
                },
            ),
            (
                "/per-article/sk.wikipedia/all-access/user/Prerusovany_post/daily/"
                "20240801/20240831",
                {"items": []},
            ),
            (
                "/aggregate/sk.wikipedia/all-access/user/daily/20240801/20240831",
                {"items": []},
            ),
        ]
    )
    _use_cassette(monkeypatch, cassette)

    fetch_result = fetch_cmd.run(
        project="demo",
        topic=None,
        languages=None,
        start=None,
        end=None,
        granularity="daily",
        data_dir=tmp_path,
    )
    cassette.assert_exhausted()

    assert set(fetch_result.coverage) == {"pl", "cs", "sk"}
    assert fetch_result.coverage["sk"].wiki == "sk.wikipedia"
    assert fetch_result.coverage["sk"].article == "Prerusovany_post"
    # pl/cs coverage came entirely from cache, with no fresh network calls.
    assert fetch_result.coverage["pl"].zero_fill_days == 0
    assert fetch_result.coverage["cs"].zero_fill_days == 0

    saved = project_state.load(tmp_path, "demo")
    assert saved is not None
    assert saved.articles["sk"].title == "Prerusovany_post"


def test_drop_date_range_is_pure_local_recomputation_with_zero_http_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    wiki, title = "en.wikipedia", "Astronomy"
    project_state.create(
        tmp_path,
        "demo",
        topic_query="astronomy",
        qid="Q1",
        languages=["en"],
        articles={"en": ArticleInfo(title=title, wiki=wiki, exists=True)},
        start=START.isoformat(),
        end=END.isoformat(),
    )
    _write_month(tmp_path, wiki, title, START, END, views=500)
    _write_month(tmp_path, wiki, store.AGGREGATE_SLOT, START, END, views=1_000_000)

    baseline = analyze_cmd.run(
        project="demo",
        compare_languages=True,
        placebo_basket_size=20,
        force_recompute=True,
        data_dir=tmp_path,
    )
    assert baseline.languages["en"].data_quality.total_days == 31

    def _forbid_network(transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
        raise AssertionError("`analyze` must never construct an HTTP client")

    monkeypatch.setattr(http_module, "build_client", _forbid_network)
    monkeypatch.setattr(resolve_cmd, "build_client", _forbid_network)
    monkeypatch.setattr(fetch_cmd, "build_client", _forbid_network)

    show = project_cmd.set_project(
        project="demo",
        add_language=None,
        remove_language=None,
        exclude_date_range="2024-08-10:2024-08-20",
        set_date_range=None,
        data_dir=tmp_path,
    )
    assert show.exclusions == ["2024-08-10:2024-08-20"]
    assert show.stale.analyze_stale is True

    result = analyze_cmd.run(
        project="demo",
        compare_languages=True,
        placebo_basket_size=20,
        force_recompute=True,
        data_dir=tmp_path,
    )

    # The excluded 11 days are gone from the recomputed series — proving the
    # exclusion actually took effect locally, not just that nothing crashed.
    assert result.languages["en"].data_quality.total_days == 31 - 11
