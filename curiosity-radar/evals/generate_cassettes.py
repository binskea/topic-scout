"""Builds synthetic, cassette-backed AQS/Wikidata/MediaWiki data for every
scenario in `evals/scenarios/` — entirely synthetic (unlike `tests/
cassettes/milestone0/`, which is Milestone 0's real recorded traffic).
The eval's job is to exercise the full `resolve -> fetch -> analyze ->
chart -> report -> verify` chain against known, reproducible statistical
shapes (a real rising trend, a real flat one, a real spike), not to
double as another live-API-shape regression test — that's what the
Milestone 0 cassettes and `tests/test_resolve.py`/`test_fetch_and_cache.py`
already do.

Every request each scenario's `fetch`/`resolve` calls could make is
computed here the same way the real client code builds it (same `quote()`
encoding, same per-month closed/open split via `cache/store.py`, same
`cassette_key()` used at playback time in `wikimedia/cassette.py`) — so a
manifest miss during an eval run means an agent deviated from the
expected call shape (wrong dates, wrong title), not a fixture bug.

Usage: `uv run python -m evals.generate_cassettes` — regenerates every
scenario's `evals/cassettes/<slug>/manifest.json` from scratch
(deterministic given each `LanguageProfile`'s fixed `noise_seed`). Safe to
rerun any time a scenario's shape parameters change.
"""

from __future__ import annotations

import functools
import json
import math
import random
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

import httpx

from curiosity_radar.cache import store
from curiosity_radar.project_state import DEFAULT_LOOKBACK_DAYS
from curiosity_radar.wikimedia import cassette as cassette_module
from curiosity_radar.wikimedia.aqs_client import ACCESS, AGENT, AQS_BASE
from curiosity_radar.wikimedia.wikidata_client import WIKIDATA_API
from evals.scenarios import SCENARIOS, LanguageProfile, Scenario

CASSETTES_ROOT = Path(__file__).parent / "cassettes"
GRANULARITY = "daily"


def _fmt(d: date) -> str:
    return d.strftime("%Y%m%d")


def _key(method: str, url: str, params: dict[str, str] | None = None) -> str:
    return cassette_module.cassette_key(method, httpx.URL(url, params=params or {}))


def _article_views(profile: LanguageProfile, start: date, day: date) -> int:
    offset = (day - start).days
    rng = random.Random(profile.noise_seed * 100_000 + offset)
    value = profile.base_views + profile.growth_per_day * offset
    value += 0.08 * profile.base_views * math.sin(2 * math.pi * offset / 7)
    value += rng.uniform(-0.03, 0.03) * profile.base_views
    if offset in profile.spike_day_offsets:
        value *= 6.0
    return max(0, round(value))


def _aggregate_views(profile: LanguageProfile, start: date, day: date) -> int:
    offset = (day - start).days
    rng = random.Random(profile.noise_seed * 100_000 + 999_000 + offset)
    value = profile.aggregate_base_views + profile.aggregate_growth_per_day * offset
    value += rng.uniform(-0.01, 0.01) * profile.aggregate_base_views
    return max(0, round(value))


def _items(
    wiki: str, sub_start: date, sub_end: date, views_fn: Callable[[date], int], article: str | None
) -> list[dict]:
    items = []
    d = sub_start
    while d <= sub_end:
        entry: dict[str, object] = {
            "project": wiki,
            "granularity": GRANULARITY,
            "timestamp": f"{_fmt(d)}00",
            "access": ACCESS,
            "agent": AGENT,
            "views": views_fn(d),
        }
        if article is not None:
            entry["article"] = article
        items.append(entry)
        d += timedelta(days=1)
    return items


def _month_sub_ranges(range_start: date, range_end: date, today: date) -> list[tuple[date, date]]:
    """Exactly mirrors `cache/store.py::ensure_series`'s per-month request
    shaping: a closed month is requested in full; the open month only up
    to `range_end`."""
    ranges = []
    for year_month in store.iter_months(range_start, range_end):
        month_start, month_end = store.month_bounds(year_month)
        closed = store.is_closed_month(year_month, today=today)
        sub_end = month_end if closed else min(month_end, range_end)
        ranges.append((month_start, sub_end))
    return ranges


def _manifest_for_scenario(scenario: Scenario) -> dict[str, dict]:
    today = date.fromisoformat(scenario.fake_today)
    range_end = today
    range_start = range_end.fromordinal(range_end.toordinal() - DEFAULT_LOOKBACK_DAYS)

    manifest: dict[str, dict] = {}

    # --- Wikidata: wbsearchentities (topic text wildcarded, see
    # cassette.py) + wbgetentities (fixed sitelinks for this QID) ---
    search_key = _key(
        "GET",
        WIKIDATA_API,
        {
            "action": "wbsearchentities",
            "search": "placeholder",
            "language": "en",
            "format": "json",
            "limit": "10",
        },
    )
    manifest[search_key] = {
        "body": {
            "searchinfo": {"search": scenario.topic_query},
            "search": [
                {
                    "id": scenario.qid,
                    "title": scenario.qid,
                    "pageid": 1,
                    "concepturi": f"http://www.wikidata.org/entity/{scenario.qid}",
                    "repository": "wikidata",
                    "url": f"//www.wikidata.org/wiki/{scenario.qid}",
                    "display": {"label": {"value": scenario.topic_query, "language": "en"}},
                    "label": scenario.topic_query,
                    "match": {"type": "label", "language": "en", "text": scenario.topic_query},
                }
            ],
            "search-continue": 10,
            "success": 1,
        }
    }

    # Same dedup/ordering as `resolve.py`'s own `alias_languages` (`"en"`
    # first, then each requested language, in the order the scenario's
    # `--languages` are passed) — the aliases `props`/`languages` params
    # must match exactly or this cassette entry misses.
    alias_languages = list(dict.fromkeys(["en", *(p.lang for p in scenario.languages)]))
    entities_key = _key(
        "GET",
        WIKIDATA_API,
        {
            "action": "wbgetentities",
            "ids": scenario.qid,
            "props": "sitelinks|aliases",
            "languages": "|".join(alias_languages),
            "format": "json",
        },
    )
    manifest[entities_key] = {
        "body": {
            "entities": {
                scenario.qid: {
                    "type": "item",
                    "id": scenario.qid,
                    "sitelinks": {
                        f"{p.lang}wiki": {"site": f"{p.lang}wiki", "title": p.title, "badges": []}
                        for p in scenario.languages
                    },
                    # No synthetic aliases here — this eval fixture's job is
                    # exercising the command chain against known trend
                    # shapes (see module docstring), not the alias-derived
                    # related_search_terms feature, which has its own
                    # dedicated cassette-backed tests in test_resolve.py.
                    "aliases": {},
                }
            },
            "success": 1,
        }
    }

    sub_ranges = _month_sub_ranges(range_start, range_end, today)

    for profile in scenario.languages:
        # --- MediaWiki: title normalization (no redirect, the plain case) ---
        mw_key = _key(
            "GET",
            f"https://{profile.lang}.wikipedia.org/w/api.php",
            {"action": "query", "titles": profile.title, "redirects": "1", "format": "json"},
        )
        manifest[mw_key] = {
            "body": {
                "batchcomplete": "",
                "query": {"pages": {"1": {"pageid": 1, "ns": 0, "title": profile.title}}},
            }
        }

        # --- AQS: per-article + aggregate, one request per calendar month ---
        for sub_start, sub_end in sub_ranges:
            per_article_url = (
                f"{AQS_BASE}/per-article/{profile.wiki}/{ACCESS}/{AGENT}/"
                f"{quote(profile.title, safe='')}/{GRANULARITY}/{_fmt(sub_start)}/{_fmt(sub_end)}"
            )
            article_views_fn = functools.partial(_article_views, profile, range_start)
            items = _items(profile.wiki, sub_start, sub_end, article_views_fn, profile.title)
            manifest[_key("GET", per_article_url)] = {"body": {"items": items}}

            aggregate_url = (
                f"{AQS_BASE}/aggregate/{profile.wiki}/{ACCESS}/{AGENT}/"
                f"{GRANULARITY}/{_fmt(sub_start)}/{_fmt(sub_end)}"
            )
            aggregate_views_fn = functools.partial(_aggregate_views, profile, range_start)
            agg_items = _items(profile.wiki, sub_start, sub_end, aggregate_views_fn, None)
            manifest[_key("GET", aggregate_url)] = {"body": {"items": agg_items}}

    return manifest


def main() -> None:
    for scenario in SCENARIOS:
        manifest = _manifest_for_scenario(scenario)
        out_dir = CASSETTES_ROOT / scenario.slug
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
        print(f"{scenario.slug}: {len(manifest)} cassette entries -> {out_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
