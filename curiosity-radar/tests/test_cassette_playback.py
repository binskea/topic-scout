"""`wikimedia/cassette.py` (Milestone 11): the lookup-based cassette
transport that backs eval runs, plus `build_client`'s `CURIOSITY_RADAR_
CASSETTE_DIR` activation switch. Distinct from `tests/_cassette.py`'s
`SequentialCassette`, which unit tests use directly — this is the
production code path a real `uv run curiosity-radar ...` subprocess goes
through during an eval, keyed on request identity rather than call order.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from curiosity_radar.wikimedia import cassette
from curiosity_radar.wikimedia.http import CASSETTE_DIR_ENV, build_client


def test_cassette_key_is_order_independent_on_query_params() -> None:
    a = httpx.URL("https://www.wikidata.org/w/api.php?action=wbgetentities&ids=Q1")
    b = httpx.URL("https://www.wikidata.org/w/api.php?ids=Q1&action=wbgetentities")
    assert cassette.cassette_key("GET", a) == cassette.cassette_key("GET", b)


def test_cassette_key_wildcards_wbsearchentities_search_param() -> None:
    a = httpx.URL(
        "https://www.wikidata.org/w/api.php"
        "?action=wbsearchentities&search=intermittent+fasting&language=en&limit=10"
    )
    b = httpx.URL(
        "https://www.wikidata.org/w/api.php"
        "?action=wbsearchentities&search=%D0%B0%D1%81%D1%82%D1%80%D0%BE%D0%BD%D0%BE%D0%BC%D1%96%D1%8F"
        "&language=en&limit=10"
    )
    assert cassette.cassette_key("GET", a) == cassette.cassette_key("GET", b)


def test_cassette_key_does_not_wildcard_search_for_other_actions() -> None:
    a = httpx.URL("https://en.wikipedia.org/w/api.php?action=query&search=foo")
    b = httpx.URL("https://en.wikipedia.org/w/api.php?action=query&search=bar")
    assert cassette.cassette_key("GET", a) != cassette.cassette_key("GET", b)


def test_cassette_key_distinguishes_host_and_path() -> None:
    sk = httpx.URL("https://sk.wikipedia.org/w/api.php?action=query&titles=Foo")
    cs = httpx.URL("https://cs.wikipedia.org/w/api.php?action=query&titles=Foo")
    assert cassette.cassette_key("GET", sk) != cassette.cassette_key("GET", cs)


def test_build_transport_serves_inline_body(tmp_path: Path) -> None:
    manifest = {
        "GET https://www.wikidata.org/w/api.php?action=wbgetentities&ids=Q1": {
            "body": {"entities": {"Q1": {"id": "Q1"}}},
        }
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    transport = cassette.build_transport(tmp_path)

    async def _fetch() -> dict:
        client = httpx.AsyncClient(transport=transport)
        response = await client.get(
            "https://www.wikidata.org/w/api.php", params={"action": "wbgetentities", "ids": "Q1"}
        )
        return response.json()

    result = asyncio.run(_fetch())
    assert result == {"entities": {"Q1": {"id": "Q1"}}}


def test_build_transport_serves_a_referenced_file(tmp_path: Path) -> None:
    (tmp_path / "response.json").write_text(json.dumps({"items": [{"views": 42}]}))
    manifest = {
        "GET https://wikimedia.org/api/rest_v1/metrics/pageviews/aggregate/en.wikipedia": {
            "file": "response.json",
        }
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    transport = cassette.build_transport(tmp_path)

    async def _fetch() -> dict:
        client = httpx.AsyncClient(transport=transport)
        response = await client.get(
            "https://wikimedia.org/api/rest_v1/metrics/pageviews/aggregate/en.wikipedia"
        )
        return response.json()

    result = asyncio.run(_fetch())
    assert result == {"items": [{"views": 42}]}


def test_build_transport_raises_a_clear_error_on_a_miss(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text(json.dumps({}))
    transport = cassette.build_transport(tmp_path)

    async def _fetch() -> None:
        client = httpx.AsyncClient(transport=transport)
        await client.get("https://www.wikidata.org/w/api.php", params={"action": "nope"})

    with pytest.raises(cassette.CassetteMissError, match="cassette miss"):
        asyncio.run(_fetch())


def test_missing_manifest_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        cassette.build_transport(tmp_path)


def test_build_client_uses_cassette_dir_env_var_when_no_transport_given(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifest = {"GET https://example.org/probe": {"body": {"ok": True}}}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setenv(CASSETTE_DIR_ENV, str(tmp_path))

    async def _fetch() -> dict:
        async with build_client() as client:
            response = await client.get("https://example.org/probe")
            return response.json()

    assert asyncio.run(_fetch()) == {"ok": True}


def test_build_client_explicit_transport_takes_precedence_over_cassette_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(CASSETTE_DIR_ENV, str(tmp_path))  # no manifest.json written — would blow up

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"from": "explicit"})

    async def _fetch() -> dict:
        async with build_client(transport=httpx.MockTransport(_handler)) as client:
            response = await client.get("https://example.org/probe")
            return response.json()

    assert asyncio.run(_fetch()) == {"from": "explicit"}
