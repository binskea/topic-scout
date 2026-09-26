"""Live sourcing of placebo-basket candidates (SPEC.md §9 item 1).

Milestone 13: `stats/placebo.py` has always been able to rank a topic's
slope against a *given* pool of candidates — what was missing was the pool
itself. This module builds it from two live sources:

1. AQS's "top articles" endpoint (`references/api-notes.md` §1.3,
   `[UNVERIFIED-LIVE]` — never exercised in Milestone 0) gives a wiki's
   most-viewed articles for one day, as a popularity-tier seed pool.
2. Each surviving candidate's Wikidata item, looked up by `(site, title)`
   one at a time, supplies the category QIDs `stats/placebo.select_basket`
   excludes on (see `wikidata_client.get_entity_by_site_title`'s docstring
   for why this isn't batched).

Actual pageview *series* for each candidate are fetched the ordinary way,
via `cache/store.ensure_series` — a candidate is just another cached
article, sharing the same `(wiki, title, month)` cache scheme SPEC.md §4
already intends for overlapping requests across projects.
"""

from __future__ import annotations

from datetime import date, timedelta

import httpx

from curiosity_radar.wikimedia import aqs_client, wikidata_client

# Namespaced/non-article pages that dominate a wiki's raw "top articles" list
# (the Main Page, search/login/special pages) but aren't candidates for a
# placebo comparison.
_NON_ARTICLE_PREFIXES = (
    "Special:",
    "Wikipedia:",
    "Talk:",
    "File:",
    "Category:",
    "Template:",
    "Portal:",
    "Help:",
    "User:",
    "Draft:",
    "MediaWiki:",
    "Module:",
)
_NON_ARTICLE_TITLES = frozenset({"Main_Page"})


def is_candidate_title(title: str) -> bool:
    if title in _NON_ARTICLE_TITLES:
        return False
    return not any(title.startswith(prefix) for prefix in _NON_ARTICLE_PREFIXES)


def dbname_for_wiki(wiki: str) -> str:
    """`"en.wikipedia"` -> `"enwiki"` — the MediaWiki dbname Wikidata's
    `sites` param expects, distinct from the domain-style project id AQS
    and this codebase's own cache otherwise use throughout (`references/
    api-notes.md`'s own explicit note on this)."""
    return wiki.split(".", 1)[0] + "wiki"


def reference_day(today: date) -> date:
    """The last day of the most recently *fully closed* month before
    `today` — safely settled data for a "top articles" snapshot, sidestepping
    the still-open-month edge cases `fetch`'s own clamping already handles
    for per-article/aggregate data."""
    first_of_this_month = date(today.year, today.month, 1)
    return first_of_this_month - timedelta(days=1)


async def fetch_candidate_titles(
    client: httpx.AsyncClient, wiki: str, *, day: date, limit: int
) -> list[str]:
    articles = await aqs_client.fetch_top_articles(client, wiki, day)
    titles: list[str] = []
    for entry in articles:
        title = entry.get("article")
        if title and is_candidate_title(title) and title not in titles:
            titles.append(title)
        if len(titles) >= limit:
            break
    return titles


async def fetch_candidate_category_qids(
    client: httpx.AsyncClient, wiki: str, titles: list[str]
) -> dict[str, frozenset[str]]:
    """One Wikidata lookup per title. Titles with no Wikidata item at all
    (a redirect/disambiguation oddity, or a genuinely wikibase-less page)
    are simply absent from the result, not an error — `fetch` drops them
    from the cached candidate pool entirely rather than caching a
    known-incomplete exclusion set for them."""
    site = dbname_for_wiki(wiki)
    result: dict[str, frozenset[str]] = {}
    for title in titles:
        entity = await wikidata_client.get_entity_by_site_title(client, site, title)
        if entity is not None:
            result[title] = wikidata_client.category_qids_from_entity(entity)
    return result
