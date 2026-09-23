"""Project-wide safety net: no test may reach live Wikimedia/Wikidata/
MediaWiki APIs (CLAUDE.md testing rules).

`resolve` (Milestone 2) is real now, and several `test_cli_contracts.py`
cases call it only to bootstrap a project for `analyze`/`chart`/`report`/
`verify`/`project` — they don't care about resolve's own behavior, so they
get a generic, permissive fake transport here. Tests that *do* care about
resolve's behavior (`test_resolve.py`) override this per-test with
cassette-backed fixtures built from Milestone 0's real recordings.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from curiosity_radar.commands import fetch as fetch_cmd
from curiosity_radar.commands import resolve as resolve_cmd
from curiosity_radar.wikimedia import http as http_module


def _param(query: dict[str, list[str]], name: str, default: str = "") -> str:
    values = query.get(name)
    return values[0] if values else default


def _generic_fake_handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    query = parse_qs(urlparse(url).query)
    action = _param(query, "action")

    if "wikidata.org" in url and action == "wbsearchentities":
        term = _param(query, "search", "topic")
        qid = f"Q{abs(hash(term.casefold())) % 900000 + 100000}"
        return httpx.Response(
            200,
            json={
                "searchinfo": {"search": term},
                "search": [
                    {
                        "id": qid,
                        "title": qid,
                        "pageid": 1,
                        "concepturi": f"http://www.wikidata.org/entity/{qid}",
                        "repository": "wikidata",
                        "url": f"//www.wikidata.org/wiki/{qid}",
                        "display": {"label": {"value": term, "language": "en"}},
                        "label": term,
                        "match": {"type": "label", "language": "en", "text": term},
                    }
                ],
                "search-continue": 10,
                "success": 1,
            },
        )

    if "wikidata.org" in url and action == "wbgetentities":
        qid = _param(query, "ids", "Q0")
        # A fixed set of dbnames covers every language this test suite
        # currently exercises; a language outside this set legitimately
        # exercises resolve's own "no_sitelink" path where relevant.
        codes = ("en", "pl", "cs", "uk", "sk", "de")
        return httpx.Response(
            200,
            json={
                "entities": {
                    qid: {
                        "type": "item",
                        "id": qid,
                        "sitelinks": {
                            f"{code}wiki": {
                                "site": f"{code}wiki",
                                "title": f"Article {qid}",
                                "badges": [],
                            }
                            for code in codes
                        },
                    }
                },
                "success": 1,
            },
        )

    if action == "query" and "titles" in query:
        title = _param(query, "titles")
        return httpx.Response(
            200,
            json={
                "batchcomplete": "",
                "query": {"pages": {"1": {"pageid": 1, "ns": 0, "title": title}}},
            },
        )

    if "wikimedia.org/api/rest_v1/metrics/pageviews" in url:
        # No fixture-driven traffic needed for the generic bootstrap path —
        # an empty items list zero-fills cleanly (test_fetch_and_cache.py
        # exercises real pageview shapes against Milestone 0's cassettes).
        return httpx.Response(200, json={"items": []})

    raise AssertionError(f"unhandled fake request in test safety net: {url}")


@pytest.fixture(autouse=True)
def _no_live_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_build_client(transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers={"User-Agent": http_module.USER_AGENT},
            transport=httpx.MockTransport(_generic_fake_handler),
        )

    monkeypatch.setattr(http_module, "build_client", fake_build_client)
    monkeypatch.setattr(resolve_cmd, "build_client", fake_build_client)
    monkeypatch.setattr(fetch_cmd, "build_client", fake_build_client)
