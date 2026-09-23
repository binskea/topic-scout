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
from curiosity_radar.wikimedia.http import build_client


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

        sitelinks = await wikidata_client.get_sitelinks(client, resolved_qid)

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

        return ResolveResult(
            topic_query=topic,
            resolved_qid=resolved_qid,
            candidates=candidates,
            ambiguous=ambiguous,
            cluster=cluster,
            warnings=warnings,
        )
