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


async def get_entity(
    client: httpx.AsyncClient, qid: str, *, props: str = "sitelinks"
) -> dict[str, Any]:
    """Return the raw entity dict for `qid` (whichever top-level keys `props`
    asked for — e.g. `"sitelinks"`, `"claims"`, or `"sitelinks|claims"` to
    get both in one call rather than two round-trips)."""
    params = {"action": "wbgetentities", "ids": qid, "props": props, "format": "json"}
    data = await get_json(client, WIKIDATA_API, params=params)
    return dict(data.get("entities", {}).get(qid, {}))


async def get_entity_by_site_title(
    client: httpx.AsyncClient, site: str, title: str
) -> dict[str, Any] | None:
    """`wbgetentities` looked up by `(site, title)` (a MediaWiki dbname like
    `"enwiki"` plus a page title) instead of a known QID — used by
    `wikimedia/basket_source.py` to find a placebo-basket candidate's
    Wikidata item from its title alone. One title per call (batching
    several via `sites=...&titles=a|b|c` was never exercised live and its
    response can't be reliably mapped back to each title without an extra,
    unverified assumption — see that module's docstring). Returns `None`
    when the title has no corresponding Wikidata item at all.
    """
    params = {
        "action": "wbgetentities",
        "sites": site,
        "titles": title,
        "props": "claims",
        "format": "json",
    }
    data = await get_json(client, WIKIDATA_API, params=params)
    for entity in data.get("entities", {}).values():
        if "missing" in entity:
            return None
        return dict(entity)
    return None


def sitelinks_from_entity(entity: dict[str, Any]) -> dict[str, str]:
    """`{dbname: title}` (e.g. `{"plwiki": "..."}`) from an entity dict
    fetched with `props` including `"sitelinks"`. A dbname absent from the
    result means no sitelink exists for that wiki."""
    sitelinks = entity.get("sitelinks", {})
    return {site: info["title"] for site, info in sitelinks.items()}


async def get_sitelinks(client: httpx.AsyncClient, qid: str) -> dict[str, str]:
    """Return `{dbname: title}` (e.g. `{"plwiki": "..."}`) for a QID.

    A dbname absent from the result means no sitelink exists for that wiki.
    """
    return sitelinks_from_entity(await get_entity(client, qid, props="sitelinks"))


# "Instance of" / "subclass of" — used as this implementation's practical
# proxy for SPEC.md §5's "the topic's Wikidata category tree": no single
# Wikidata property is literally named that, and P910 ("topic's main
# category", the closest literal match) is sparsely populated in practice;
# P31/P279 (what kind of thing an item *is*) classify a topic well enough
# to exclude thematically related placebo candidates, and are populated on
# almost every item. This implementation's own choice, not a frozen SPEC.md
# threshold — see `references/stats-methods.md`.
CATEGORY_CLAIM_PROPERTIES = ("P31", "P279")


def category_qids_from_entity(entity: dict[str, Any]) -> frozenset[str]:
    """QIDs from `entity`'s `CATEGORY_CLAIM_PROPERTIES` claims (an entity
    dict fetched with `props` including `"claims"`) — empty when the entity
    has none of those claims, or wasn't fetched with claims at all."""
    qids: set[str] = set()
    for prop in CATEGORY_CLAIM_PROPERTIES:
        for claim in entity.get("claims", {}).get(prop, []):
            value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
            if isinstance(value, dict) and "id" in value:
                qids.add(value["id"])
    return frozenset(qids)
