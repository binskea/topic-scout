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


async def get_sitelinks_and_aliases(
    client: httpx.AsyncClient, qid: str, alias_languages: list[str]
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Return `(sitelinks, aliases)` for a QID from a single `wbgetentities` call.

    `sitelinks` is `{dbname: title}` (e.g. `{"plwiki": "..."}`) as before — a
    dbname absent from the result means no sitelink exists for that wiki.

    `aliases` is `{language: [alias, ...]}`, restricted to `alias_languages`
    (Wikidata stores aliases per-language via `wbgetentities`'s own
    `languages` filter param; an entity may have zero aliases in a given
    language). These are Wikidata's "also known as" labels for the entity —
    real alternate phrasings a user could search next, not a general
    synonym dictionary.

    `[UNVERIFIED-LIVE]`: the `props=aliases` shape here follows Wikidata's
    documented Wikibase API contract exactly (same `entities.<QID>.aliases.
    <lang> = [{"language": ..., "value": ...}]` shape as every other
    Wikibase deployment), but — like the rest of `api-notes.md`'s few
    residual items — has not itself been exercised against a live call in
    this account's cloud environment (`SPEC.md` §9 item 8: Wikimedia/
    Wikidata domains are blocked outright here). The existing `props=
    sitelinks` half of this same call *is* `[CONFIRMED 2026-09-22]`.
    """
    langs_param = "|".join(alias_languages) if alias_languages else "en"
    params = {
        "action": "wbgetentities",
        "ids": qid,
        "props": "sitelinks|aliases",
        "languages": langs_param,
        "format": "json",
    }
    data = await get_json(client, WIKIDATA_API, params=params)
    entity = data.get("entities", {}).get(qid, {})
    sitelinks = {site: info["title"] for site, info in entity.get("sitelinks", {}).items()}
    aliases = {
        lang: [item["value"] for item in items] for lang, items in entity.get("aliases", {}).items()
    }
    return sitelinks, aliases
