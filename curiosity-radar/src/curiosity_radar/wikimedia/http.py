"""Shared httpx client for every Wikimedia/Wikidata/MediaWiki call.

One place for the User-Agent, timeout, and retry/backoff policy (SPEC.md
§7: bounded retry with exponential backoff + jitter on 429/5xx) so every
client module behaves consistently and every test can swap in an
`httpx.MockTransport` via the `transport` parameter instead of touching
the network (CLAUDE.md: never call live Wikimedia/Wikidata/MediaWiki APIs
in unit tests or CI).
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Mapping

import httpx

USER_AGENT = (
    "curiosity-radar/0.1 (https://github.com/binskea/topic-scout; contact: marina@binskea.com)"
)
DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
MAX_ATTEMPTS = 3
RETRY_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def build_client(transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=DEFAULT_TIMEOUT,
        transport=transport,
    )


def _backoff_delay(attempt: int) -> float:
    base = 0.5 * (2 ** (attempt - 1))
    return base + random.uniform(0, base * 0.25)


async def get_json(
    client: httpx.AsyncClient, url: str, *, params: Mapping[str, str] | None = None
) -> dict:
    """GET `url`, retrying on transient failures, and return the parsed JSON body."""
    last_exc: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = await client.get(url, params=params)
        except httpx.TransportError as exc:
            last_exc = exc
        else:
            if response.status_code == 200:
                return response.json()
            if response.status_code in RETRY_STATUS_CODES and attempt < MAX_ATTEMPTS:
                last_exc = None
            else:
                response.raise_for_status()
        if attempt < MAX_ATTEMPTS:
            await asyncio.sleep(_backoff_delay(attempt))
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("unreachable: retry loop exited without returning or raising")
