"""MediaWiki: per-language title normalization and redirect resolution
(SPEC.md §3 "MediaWiki API — title normalization & redirect resolution").

Confirmed live in Milestone 0
(`tests/cassettes/milestone0/07a_mediawiki_normal.json`,
`07b_mediawiki_single_redirect.json`, `07c_mediawiki_uk.json`): a single
`redirects=1` call resolves (at most) one redirect hop and omits the
`redirects`/`normalized` keys entirely when nothing needed adjusting.
Whether a *double* redirect is fully resolved by one call was never tested
live (`references/api-notes.md` §3, "Still open") — SPEC.md's
`redirect_resolution_failed` error path is designed defensively for that
case either way, so `resolve_title` below re-queries with the latest known
title whenever a hop was reported, until the response reports no further
hop or `MAX_REDIRECT_HOPS` is exceeded.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from curiosity_radar.errors import CommandError
from curiosity_radar.wikimedia.http import get_json

MAX_REDIRECT_HOPS = 5


@dataclass
class ResolvedTitle:
    title: str | None
    exists: bool
    redirect_from: str | None = None
    reason: str | None = None


def _api_url(lang: str) -> str:
    return f"https://{lang}.wikipedia.org/w/api.php"


async def resolve_title(client: httpx.AsyncClient, lang: str, title: str) -> ResolvedTitle:
    """Resolve `title` on `{lang}.wikipedia` to its stable, post-redirect canonical title.

    `redirect_from` is set to the originally-requested title whenever the
    final title differs from it, regardless of how many hops it took.
    """
    original = title
    current = title
    for _ in range(MAX_REDIRECT_HOPS):
        params = {"action": "query", "titles": current, "redirects": "1", "format": "json"}
        data = await get_json(client, _api_url(lang), params=params)
        query = data.get("query", {})
        pages: dict = query.get("pages", {})
        page = next(iter(pages.values()), None)
        if page is None:
            return ResolvedTitle(title=None, exists=False, reason="page_not_found")
        if "missing" in page:
            return ResolvedTitle(title=None, exists=False, reason="page_missing")
        final_title = page["title"]
        if query.get("redirects") and final_title != current:
            current = final_title
            continue
        redirect_from = original if final_title != original else None
        return ResolvedTitle(title=final_title, exists=True, redirect_from=redirect_from)

    raise CommandError(
        "redirect_resolution_failed",
        f"Could not resolve a stable title for '{original}' on {lang}.wikipedia "
        f"after {MAX_REDIRECT_HOPS} redirect hops.",
        "Check the article manually; it may have been merged or deleted.",
    )
