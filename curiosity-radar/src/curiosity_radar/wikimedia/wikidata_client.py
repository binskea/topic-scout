"""Wikidata: topic search and QID -> sitelinks (SPEC.md §2.1-2.2).

Shapes confirmed live in Milestone 0
(`tests/cassettes/milestone0/05_wikidata_search_ambiguous.json`,
`06_wikidata_sitelinks.json`) — see `references/api-notes.md` §2.
"""

from __future__ import annotations

from typing import Any

import httpx

from curiosity_radar.wikimedia.http import get_json

WIKIDATA_API = "https://www.wikidata.org/w/api.php"


async def search_entities(
    client: httpx.AsyncClient, query: str, *, language: str = "en", limit: int = 10
) -> list[dict[str, Any]]:
    """Return the raw `search` list from `wbsearchentities` (no relevance score field —
    ambiguity is conveyed only by list order plus each entry's `match.type`)."""
    params = {
        "action": "wbsearchentities",
        "search": query,
        "language": language,
        "format": "json",
        "limit": str(limit),
    }
    data = await get_json(client, WIKIDATA_API, params=params)
    return list(data.get("search", []))


async def get_sitelinks(client: httpx.AsyncClient, qid: str) -> dict[str, str]:
    """Return `{dbname: title}` (e.g. `{"plwiki": "..."}`) for a QID.

    A dbname absent from the result means no sitelink exists for that wiki.
    """
    params = {"action": "wbgetentities", "ids": qid, "props": "sitelinks", "format": "json"}
    data = await get_json(client, WIKIDATA_API, params=params)
    entity = data.get("entities", {}).get(qid, {})
    sitelinks = entity.get("sitelinks", {})
    return {site: info["title"] for site, info in sitelinks.items()}
