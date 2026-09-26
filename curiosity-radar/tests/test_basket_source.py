"""`wikimedia/basket_source.py` + the new `wikidata_client`/`aqs_client`
helpers it's built on (Milestone 13), pure-function/unit tests — no network
fixture involved for the pure helpers; a `SequentialCassette` for the two
thin async wrappers that do make an HTTP call.
"""

from __future__ import annotations

import asyncio
from datetime import date

import httpx
import pytest
from _cassette import SequentialCassette

from curiosity_radar.wikimedia import aqs_client, basket_source, wikidata_client
from curiosity_radar.wikimedia import http as http_module
from curiosity_radar.wikimedia.http import build_client


def test_is_candidate_title_filters_main_page_and_namespaced_pages() -> None:
    assert basket_source.is_candidate_title("Intermittent_fasting") is True
    assert basket_source.is_candidate_title("Main_Page") is False
    assert basket_source.is_candidate_title("Special:Search") is False
    assert basket_source.is_candidate_title("Category:Diets") is False
    assert basket_source.is_candidate_title("Talk:Something") is False


def test_dbname_for_wiki_converts_domain_style_to_mediawiki_dbname() -> None:
    assert basket_source.dbname_for_wiki("en.wikipedia") == "enwiki"
    assert basket_source.dbname_for_wiki("uk.wikipedia") == "ukwiki"


def test_reference_day_is_the_last_day_of_the_previous_closed_month() -> None:
    assert basket_source.reference_day(date(2025, 3, 20)) == date(2025, 2, 28)
    assert basket_source.reference_day(date(2025, 1, 15)) == date(2024, 12, 31)


def test_category_qids_from_entity_extracts_instance_and_subclass_of_claims() -> None:
    entity = {
        "id": "Q42",
        "claims": {
            "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}],
            "P279": [{"mainsnak": {"datavalue": {"value": {"id": "Q123"}}}}],
            "P18": [{"mainsnak": {"datavalue": {"value": "some_image.jpg"}}}],  # non-entity claim
        },
    }
    assert wikidata_client.category_qids_from_entity(entity) == frozenset({"Q5", "Q123"})


def test_category_qids_from_entity_is_empty_when_no_relevant_claims() -> None:
    assert wikidata_client.category_qids_from_entity({}) == frozenset()
    assert wikidata_client.category_qids_from_entity({"claims": {}}) == frozenset()


def test_sitelinks_from_entity_extracts_dbname_to_title() -> None:
    entity = {"sitelinks": {"enwiki": {"site": "enwiki", "title": "Foo", "badges": []}}}
    assert wikidata_client.sitelinks_from_entity(entity) == {"enwiki": "Foo"}


def test_fetch_candidate_titles_filters_and_caps_at_limit() -> None:
    cassette = SequentialCassette(
        [
            (
                "/top/en.wikipedia/all-access/2025/02/28",
                {
                    "items": [
                        {
                            "articles": [
                                {"article": "Main_Page", "views": 999, "rank": 1},
                                {"article": "A", "views": 500, "rank": 2},
                                {"article": "Special:Search", "views": 400, "rank": 3},
                                {"article": "B", "views": 300, "rank": 4},
                                {"article": "C", "views": 200, "rank": 5},
                            ]
                        }
                    ]
                },
            )
        ]
    )

    async def _run() -> list[str]:
        async with build_client(transport=cassette.transport()) as client:
            return await basket_source.fetch_candidate_titles(
                client, "en.wikipedia", day=date(2025, 2, 28), limit=2
            )

    titles = asyncio.run(_run())
    cassette.assert_exhausted()
    assert titles == ["A", "B"]


def test_fetch_candidate_category_qids_drops_titles_with_no_wikidata_item() -> None:
    cassette = SequentialCassette(
        [
            (
                {"action": "wbgetentities", "sites": "enwiki", "titles": "A"},
                {
                    "entities": {
                        "Q1": {
                            "id": "Q1",
                            "claims": {
                                "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q9"}}}}]
                            },
                        }
                    }
                },
            ),
            (
                {"action": "wbgetentities", "sites": "enwiki", "titles": "B"},
                {"entities": {"enwiki:B": {"missing": ""}}},
            ),
        ]
    )

    async def _run() -> dict[str, frozenset[str]]:
        async with build_client(transport=cassette.transport()) as client:
            return await basket_source.fetch_candidate_category_qids(
                client, "en.wikipedia", ["A", "B"]
            )

    result = asyncio.run(_run())
    cassette.assert_exhausted()
    assert result == {"A": frozenset({"Q9"})}


def test_fetch_candidate_category_qids_skips_a_title_whose_lookup_stays_rate_limited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One flaky title among several must not lose the ones already looked
    up, or block the ones after it — there's no per-title cache to fall
    back on here, so a hard failure would otherwise cost the whole batch."""

    async def _no_sleep(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(http_module.asyncio, "sleep", _no_sleep)

    def _handler(request: httpx.Request) -> httpx.Response:
        query = dict(pair.split("=") for pair in str(request.url.query, "utf-8").split("&"))
        if query.get("titles") == "Flaky":
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(
            200,
            json={"entities": {"Q1": {"id": "Q1", "claims": {}}}},
        )

    async def _run() -> dict[str, frozenset[str]]:
        async with build_client(transport=httpx.MockTransport(_handler)) as client:
            return await basket_source.fetch_candidate_category_qids(
                client, "en.wikipedia", ["A", "Flaky", "B"]
            )

    result = asyncio.run(_run())
    assert result == {"A": frozenset(), "B": frozenset()}


def test_aqs_fetch_top_articles_returns_empty_list_on_404() -> None:
    def _404(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "not found"})

    async def _run() -> list[dict]:
        async with build_client(transport=httpx.MockTransport(_404)) as client:
            return await aqs_client.fetch_top_articles(client, "en.wikipedia", date(2025, 2, 28))

    assert asyncio.run(_run()) == []
