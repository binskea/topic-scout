"""Wikimedia Analytics Query Service (AQS): per-article + aggregate pageviews
(SPEC.md §1.1-1.2, `references/api-notes.md` §1).

Confirmed live in Milestone 0: `start`/`end` are both inclusive, `agent=user`
excludes bots/spiders, and an out-of-range request 404s with an
`application/problem+json` body rather than an empty `items` array
(`tests/cassettes/milestone0/10_earliest_date_probe_404.json`) — treated
here as "no data for this range" (zero-fillable), not a hard failure.
"""

from __future__ import annotations

from datetime import date
from urllib.parse import quote

import httpx

from curiosity_radar.wikimedia.http import get_json

AQS_BASE = "https://wikimedia.org/api/rest_v1/metrics/pageviews"
ACCESS = "all-access"
AGENT = "user"


def _fmt(d: date) -> str:
    return d.strftime("%Y%m%d")


async def fetch_per_article(
    client: httpx.AsyncClient, wiki: str, article: str, granularity: str, start: date, end: date
) -> list[dict]:
    url = (
        f"{AQS_BASE}/per-article/{wiki}/{ACCESS}/{AGENT}/{quote(article, safe='')}"
        f"/{granularity}/{_fmt(start)}/{_fmt(end)}"
    )
    return await _get_items(client, url)


async def fetch_aggregate(
    client: httpx.AsyncClient, wiki: str, granularity: str, start: date, end: date
) -> list[dict]:
    url = f"{AQS_BASE}/aggregate/{wiki}/{ACCESS}/{AGENT}/{granularity}/{_fmt(start)}/{_fmt(end)}"
    return await _get_items(client, url)


async def _get_items(client: httpx.AsyncClient, url: str) -> list[dict]:
    try:
        data = await get_json(client, url)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return []
        raise
    return list(data.get("items", []))
