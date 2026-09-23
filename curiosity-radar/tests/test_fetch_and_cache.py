"""`fetch` + the raw pageview cache (Milestone 3), cassette-backed per
PLAN.md's definition of done: closed months are served from cache without
a network call, the open/current month is always refetched, missing days
are zero-filled, and the project-aggregate series is fetched/cached
alongside per-article data.

Real Milestone 0 cassettes (`01_per_article_ordinary.json`,
`03_per_article_redirect_title.json`, `04_aggregate.json`) are reused
verbatim for the shapes that fit; the zero-fill gap itself is synthetic
(Milestone 0 never actually observed a true missing day live —
`references/api-notes.md` §1.1 flags this as residual/non-blocking, so a
constructed gap is the correct way to exercise the code path).
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest
from _cassette import SequentialCassette

from curiosity_radar import project_state
from curiosity_radar.cache import store
from curiosity_radar.commands import fetch as fetch_cmd
from curiosity_radar.errors import CommandError
from curiosity_radar.schemas import ArticleInfo
from curiosity_radar.wikimedia import http as http_module
from curiosity_radar.wikimedia.http import build_client as real_build_client

CASSETTES = Path(__file__).parent / "cassettes" / "milestone0"


def _load(name: str) -> dict:
    return json.loads((CASSETTES / name).read_text())


def _use_cassette(monkeypatch: pytest.MonkeyPatch, cassette: SequentialCassette) -> None:
    # `real_build_client` is captured at module-import time (above), before
    # conftest.py's autouse fixture ever monkeypatches the live attribute —
    # importing it here instead would pick up that fixture's fake instead.
    monkeypatch.setattr(
        fetch_cmd, "build_client", lambda transport=None: real_build_client(cassette.transport())
    )


def _make_project(
    tmp_path: Path, *, slug: str, lang: str, article: ArticleInfo, start: str, end: str
) -> None:
    project_state.create(
        tmp_path,
        slug,
        topic_query="test topic",
        qid="Q1",
        languages=[lang],
        articles={lang: article},
        start=start,
        end=end,
    )


def test_second_fetch_of_an_already_closed_range_makes_zero_http_requests(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _make_project(
        tmp_path,
        slug="demo",
        lang="en",
        article=ArticleInfo(title="Intermittent_fasting", wiki="en.wikipedia", exists=True),
        start="2024-08-01",
        end="2024-08-31",
    )

    first_cassette = SequentialCassette(
        [
            (
                "/per-article/en.wikipedia/all-access/user/Intermittent_fasting/daily/"
                "20240801/20240831",
                _load("01_per_article_ordinary.json"),
            ),
            (
                "/aggregate/en.wikipedia/all-access/user/daily/20240801/20240831",
                _load("04_aggregate.json"),
            ),
        ]
    )
    _use_cassette(monkeypatch, first_cassette)
    result = fetch_cmd.run(
        project="demo",
        topic=None,
        languages=None,
        start=None,
        end=None,
        granularity="daily",
        data_dir=tmp_path,
    )
    first_cassette.assert_exhausted()
    assert result.fetched.http_requests_made == 2
    assert result.fetched.articles_fetched == 1
    assert result.coverage["en"].zero_fill_days == 0
    assert result.coverage["en"].missing_days == 0

    second_cassette = SequentialCassette([])
    _use_cassette(monkeypatch, second_cassette)
    result2 = fetch_cmd.run(
        project="demo",
        topic=None,
        languages=None,
        start=None,
        end=None,
        granularity="daily",
        data_dir=tmp_path,
    )
    second_cassette.assert_exhausted()
    assert result2.fetched.http_requests_made == 0
    assert result2.fetched.days_from_cache == result2.fetched.days_requested


def test_open_current_month_is_always_refetched(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    today = datetime.now(UTC).date()
    month_start = date(today.year, today.month, 1)
    date_path = f"{month_start.strftime('%Y%m%d')}/{today.strftime('%Y%m%d')}"

    _make_project(
        tmp_path,
        slug="demo",
        lang="en",
        article=ArticleInfo(title="Some_Article", wiki="en.wikipedia", exists=True),
        start=month_start.isoformat(),
        end=today.isoformat(),
    )

    def _cassette() -> SequentialCassette:
        return SequentialCassette(
            [
                (
                    f"/per-article/en.wikipedia/all-access/user/Some_Article/daily/{date_path}",
                    {"items": []},
                ),
                (f"/aggregate/en.wikipedia/all-access/user/daily/{date_path}", {"items": []}),
            ]
        )

    first_cassette = _cassette()
    _use_cassette(monkeypatch, first_cassette)
    result = fetch_cmd.run(
        project="demo",
        topic=None,
        languages=None,
        start=None,
        end=None,
        granularity="daily",
        data_dir=tmp_path,
    )
    first_cassette.assert_exhausted()
    assert result.fetched.http_requests_made == 2

    # Same, still-open month: a second fetch must refetch again, not hit cache.
    second_cassette = _cassette()
    _use_cassette(monkeypatch, second_cassette)
    result2 = fetch_cmd.run(
        project="demo",
        topic=None,
        languages=None,
        start=None,
        end=None,
        granularity="daily",
        data_dir=tmp_path,
    )
    second_cassette.assert_exhausted()
    assert result2.fetched.http_requests_made == 2
    assert result2.fetched.days_from_cache == 0


def test_missing_days_are_zero_filled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # A closed month (January 2023) with only 5 of 31 days present in the
    # AQS response — the rest must come back as zero-filled, not omitted.
    present_days = [1, 2, 3, 10, 31]
    items = [
        {
            "project": "en.wikipedia",
            "article": "Obscure_Article",
            "granularity": "daily",
            "timestamp": f"202301{day:02d}00",
            "access": "all-access",
            "agent": "user",
            "views": 42,
        }
        for day in present_days
    ]

    _make_project(
        tmp_path,
        slug="demo",
        lang="en",
        article=ArticleInfo(title="Obscure_Article", wiki="en.wikipedia", exists=True),
        start="2023-01-01",
        end="2023-01-31",
    )

    cassette = SequentialCassette(
        [
            (
                "/per-article/en.wikipedia/all-access/user/Obscure_Article/daily/20230101/20230131",
                {"items": items},
            ),
            ("/aggregate/en.wikipedia/all-access/user/daily/20230101/20230131", {"items": []}),
        ]
    )
    _use_cassette(monkeypatch, cassette)
    result = fetch_cmd.run(
        project="demo",
        topic=None,
        languages=None,
        start=None,
        end=None,
        granularity="daily",
        data_dir=tmp_path,
    )
    cassette.assert_exhausted()

    assert result.coverage["en"].zero_fill_days == 31 - len(present_days)

    cached = store.load_cached_month(
        store.raw_dir(tmp_path, "en.wikipedia", "Obscure_Article", "daily"), "2023-01", closed=True
    )
    assert cached is not None
    assert len(cached) == 31
    by_date = {d.date: d.views for d in cached}
    for day in range(1, 32):
        expected = 42 if day in present_days else 0
        assert by_date[f"2023-01-{day:02d}"] == expected


def test_aggregate_series_cached_alongside_per_article(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _make_project(
        tmp_path,
        slug="demo",
        lang="en",
        article=ArticleInfo(title="Intermittent_fasting", wiki="en.wikipedia", exists=True),
        start="2024-08-01",
        end="2024-08-31",
    )
    cassette = SequentialCassette(
        [
            (
                "/per-article/en.wikipedia/all-access/user/Intermittent_fasting/daily/"
                "20240801/20240831",
                _load("01_per_article_ordinary.json"),
            ),
            (
                "/aggregate/en.wikipedia/all-access/user/daily/20240801/20240831",
                _load("04_aggregate.json"),
            ),
        ]
    )
    _use_cassette(monkeypatch, cassette)
    fetch_cmd.run(
        project="demo",
        topic=None,
        languages=None,
        start=None,
        end=None,
        granularity="daily",
        data_dir=tmp_path,
    )
    cassette.assert_exhausted()

    aggregate_cache = (
        store.raw_dir(tmp_path, "en.wikipedia", "_aggregate", "daily") / "2024-08.json"
    )
    assert aggregate_cache.exists()
    payload = json.loads(aggregate_cache.read_text())
    assert len(payload["days"]) == 31
    assert payload["days"][0]["views"] == 244964703


def test_redirect_alias_is_fetched_and_summed_into_the_language_series(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    canonical_items = [
        {
            "project": "en.wikipedia",
            "article": "United_States",
            "granularity": "daily",
            "timestamp": f"202408{day:02d}00",
            "access": "all-access",
            "agent": "user",
            "views": 1000,
        }
        for day in range(1, 32)
    ]

    _make_project(
        tmp_path,
        slug="demo",
        lang="en",
        article=ArticleInfo(
            title="United_States", wiki="en.wikipedia", redirect_from="USA", exists=True
        ),
        start="2024-08-01",
        end="2024-08-31",
    )
    cassette = SequentialCassette(
        [
            (
                "/per-article/en.wikipedia/all-access/user/United_States/daily/20240801/20240831",
                {"items": canonical_items},
            ),
            (
                "/per-article/en.wikipedia/all-access/user/USA/daily/20240801/20240831",
                # Real Milestone 0 recording — only 7 of 31 days present.
                _load("03_per_article_redirect_title.json"),
            ),
            (
                "/aggregate/en.wikipedia/all-access/user/daily/20240801/20240831",
                {"items": []},
            ),
        ]
    )
    _use_cassette(monkeypatch, cassette)
    result = fetch_cmd.run(
        project="demo",
        topic=None,
        languages=None,
        start=None,
        end=None,
        granularity="daily",
        data_dir=tmp_path,
    )
    cassette.assert_exhausted()

    assert result.fetched.articles_fetched == 1
    assert result.fetched.redirect_aliases_fetched == 1
    assert result.coverage["en"].redirect_alias_included == "USA"

    canonical_cached = store.load_cached_month(
        store.raw_dir(tmp_path, "en.wikipedia", "United_States", "daily"), "2024-08", closed=True
    )
    alias_cached = store.load_cached_month(
        store.raw_dir(tmp_path, "en.wikipedia", "USA", "daily"), "2024-08", closed=True
    )
    assert canonical_cached is not None and alias_cached is not None
    assert len(canonical_cached) == len(alias_cached) == 31
    # Day 1: real alias traffic (290) on top of the synthetic canonical (1000).
    assert canonical_cached[0].views == 1000
    assert alias_cached[0].views == 290
    # Day 8 onward: the alias response only covered 7 days, so it zero-fills.
    assert alias_cached[7].views == 0


def test_persistent_rate_limit_is_a_clean_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """SPEC.md §7's "Rate-limited / 429" row, exercised through `fetch`'s
    own AQS calls (distinct from resolve's — see `test_resolve.py`'s
    equivalent for the Wikidata/MediaWiki side)."""
    _make_project(
        tmp_path,
        slug="demo",
        lang="en",
        article=ArticleInfo(title="Intermittent_fasting", wiki="en.wikipedia", exists=True),
        start="2024-08-01",
        end="2024-08-31",
    )

    async def _no_sleep(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(http_module.asyncio, "sleep", _no_sleep)

    def _always_429(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    monkeypatch.setattr(
        fetch_cmd,
        "build_client",
        lambda transport=None: real_build_client(httpx.MockTransport(_always_429)),
    )

    with pytest.raises(CommandError) as exc_info:
        fetch_cmd.run(
            project="demo",
            topic=None,
            languages=None,
            start=None,
            end=None,
            granularity="daily",
            data_dir=tmp_path,
        )
    assert exc_info.value.code == "rate_limited"


def test_fake_today_env_var_pins_which_month_is_treated_as_open(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Milestone 11 (evals): `CURIOSITY_RADAR_FAKE_TODAY` must actually
    drive `fetch`'s closed/open-month decision, independent of real wall
    time — otherwise cassette data recorded for a fixed "today" would go
    stale the moment a real eval run happened on a different day."""
    monkeypatch.setenv("CURIOSITY_RADAR_FAKE_TODAY", "2025-03-20")

    _make_project(
        tmp_path,
        slug="demo",
        lang="en",
        article=ArticleInfo(title="Fixed_Point", wiki="en.wikipedia", exists=True),
        start="2025-03-01",
        end="2025-03-20",
    )

    # If FAKE_TODAY weren't honored, March 2025 would be treated as closed
    # (safely in the past at real wall time) and requested in full
    # (03-01..03-31) instead of as the still-open current month
    # (03-01..03-20, the pinned "today").
    cassette = SequentialCassette(
        [
            (
                "/per-article/en.wikipedia/all-access/user/Fixed_Point/daily/20250301/20250320",
                {"items": []},
            ),
            ("/aggregate/en.wikipedia/all-access/user/daily/20250301/20250320", {"items": []}),
        ]
    )
    _use_cassette(monkeypatch, cassette)
    fetch_cmd.run(
        project="demo",
        topic=None,
        languages=None,
        start=None,
        end=None,
        granularity="daily",
        data_dir=tmp_path,
    )
    cassette.assert_exhausted()

    assert (
        store.raw_dir(tmp_path, "en.wikipedia", "Fixed_Point", "daily") / "current.json"
    ).exists()
    assert not (
        store.raw_dir(tmp_path, "en.wikipedia", "Fixed_Point", "daily") / "2025-03.json"
    ).exists()
