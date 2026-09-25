"""`resolve`: topic -> QID -> per-language articles (SPEC.md §3.1).

Milestone 2: resolves live against Wikidata (`wbsearchentities`/
`wbgetentities`) and MediaWiki (per-language redirect/title normalization).
`resolve` never hardcodes a QID (see `references/api-notes.md`'s
`Q1631107` cautionary tale) — every topic is looked up fresh.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from curiosity_radar import project_state
from curiosity_radar.cache.paths import resolve_data_dir
from curiosity_radar.errors import CommandError
from curiosity_radar.schemas import ArticleInfo, Candidate, Cluster, ResolveResult
from curiosity_radar.wikimedia import mediawiki_client, wikidata_client
from curiosity_radar.wikimedia.http import RETRY_STATUS_CODES, build_client

MAX_RELATED_SEARCH_TERMS = 10


def run(
    *,
    topic: str | None,
    qid: str | None,
    languages: list[str],
    related_qids: list[str],
    save_as: str | None,
    data_dir: Path | None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ResolveResult:
    data_root = resolve_data_dir(data_dir)
    result = asyncio.run(
        _resolve(
            topic=topic,
            qid=qid,
            languages=languages,
            related_qids=related_qids,
            transport=transport,
        )
    )

    if save_as:
        project_state.save_from_resolve(
            data_root,
            save_as,
            topic_query=topic,
            qid=result.resolved_qid or "",
            languages=languages,
            articles=result.cluster.articles if result.cluster else {},
            related_search_terms=result.related_search_terms,
        )

    return result


async def _resolve(
    *,
    topic: str | None,
    qid: str | None,
    languages: list[str],
    related_qids: list[str],
    transport: httpx.AsyncBaseTransport | None,
) -> ResolveResult:
    """Thin wrapper around `_resolve_impl` that maps network-layer failures
    onto SPEC.md §7's `network_error`/`rate_limited` contract — kept separate
    from the actual resolving logic so that logic doesn't need an extra
    indent level just to sit inside a `try`."""
    try:
        return await _resolve_impl(
            topic=topic,
            qid=qid,
            languages=languages,
            related_qids=related_qids,
            transport=transport,
        )
    except httpx.TransportError as exc:
        raise CommandError(
            "network_error",
            "Could not reach Wikimedia APIs.",
            "Check network/proxy connectivity and retry.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in RETRY_STATUS_CODES:
            raise CommandError(
                "rate_limited",
                "Wikimedia API is rate-limiting this client.",
                "Wait a minute and retry.",
            ) from exc
        raise


async def _resolve_impl(
    *,
    topic: str | None,
    qid: str | None,
    languages: list[str],
    related_qids: list[str],
    transport: httpx.AsyncBaseTransport | None,
) -> ResolveResult:
    async with build_client(transport=transport) as client:
        candidates: list[Candidate] = []
        ambiguous = False
        resolved_qid = qid
        warnings: list[str] = []

        if resolved_qid is None:
            assert topic is not None  # enforced by the CLI before calling run()
            raw_candidates = await wikidata_client.search_entities(client, topic)
            if not raw_candidates:
                raise CommandError(
                    "no_qid_match",
                    f"No Wikidata entity found for '{topic}'.",
                    "Try --qid with a specific Wikidata ID, or rephrase the topic more "
                    "specifically.",
                )
            candidates = [
                Candidate(
                    qid=item["id"],
                    label=item.get("label", item["id"]),
                    description=item.get("description"),
                    match_type=item.get("match", {}).get("type", "label"),
                )
                for item in raw_candidates
            ]
            resolved_qid = candidates[0].qid

            exact_label_matches = [c for c in candidates if c.label.casefold() == topic.casefold()]
            if len(exact_label_matches) > 1:
                ambiguous = True
                resolved_qid = exact_label_matches[0].qid
                warnings.append(
                    f"Multiple Wikidata entities share the label '{topic}'; "
                    "confirm resolved_qid or rerun with --qid."
                )

        # Aliases in "en" (the default search language, SPEC.md §3.1) plus
        # every requested wiki's own language code, deduped, order-preserved
        # — Wikidata language codes match wiki language codes for every case
        # this project's languages currently exercise.
        alias_languages = list(dict.fromkeys(["en", *languages]))
        sitelinks, aliases_by_language = await wikidata_client.get_sitelinks_and_aliases(
            client, resolved_qid, alias_languages
        )

        articles: dict[str, ArticleInfo] = {}
        for lang in languages:
            wiki = f"{lang}.wikipedia"
            sitelink_title = sitelinks.get(f"{lang}wiki")
            if sitelink_title is None:
                articles[lang] = ArticleInfo(wiki=wiki, exists=False, reason="no_sitelink")
                warnings.append(f"{lang}: no Wikidata sitelink for this QID")
                continue

            resolved = await mediawiki_client.resolve_title(client, lang, sitelink_title)
            if not resolved.exists:
                reason = resolved.reason or "not_found"
                articles[lang] = ArticleInfo(wiki=wiki, exists=False, reason=reason)
                warnings.append(f"{lang}: {reason}")
                continue

            articles[lang] = ArticleInfo(
                title=resolved.title,
                wiki=wiki,
                redirect_from=resolved.redirect_from,
                exists=True,
            )

        cluster = Cluster(primary_qid=resolved_qid, related_qids=related_qids, articles=articles)

        already_known = {topic} if topic else set()
        for article in articles.values():
            if article.title:
                already_known.add(article.title)
            if article.redirect_from:
                already_known.add(article.redirect_from)
        related_search_terms = _extract_related_search_terms(
            aliases_by_language, alias_languages, already_known
        )

        return ResolveResult(
            topic_query=topic,
            resolved_qid=resolved_qid,
            candidates=candidates,
            ambiguous=ambiguous,
            cluster=cluster,
            warnings=warnings,
            related_search_terms=related_search_terms,
        )


def _extract_related_search_terms(
    aliases_by_language: dict[str, list[str]],
    alias_languages: list[str],
    already_known: set[str],
) -> list[str]:
    """Flatten Wikidata's per-language alias lists into a deduped, capped
    top-`MAX_RELATED_SEARCH_TERMS` list — real "also known as" phrasings a
    user could try in a follow-up `resolve --topic`, distinct from
    `candidates`/`cluster` (which are about *this* resolution, not future
    queries).

    Iterates `alias_languages` in the order `resolve` requested them (so
    output order is deterministic across languages, even though a JSON
    object's own key order isn't guaranteed), dedupes case-insensitively
    (keeping the first-seen casing), and drops anything that's just the
    topic query or an already-known article/redirect title under a
    different case — those aren't new search terms, they're what was
    already typed or already resolved.
    """
    known_casefold = {term.casefold() for term in already_known}
    seen_casefold: set[str] = set()
    terms: list[str] = []
    for lang in alias_languages:
        for alias in aliases_by_language.get(lang, []):
            folded = alias.casefold()
            if folded in known_casefold or folded in seen_casefold:
                continue
            seen_casefold.add(folded)
            terms.append(alias)
            if len(terms) >= MAX_RELATED_SEARCH_TERMS:
                return terms
    return terms
