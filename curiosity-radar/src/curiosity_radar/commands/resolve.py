"""`resolve`: topic -> QID -> per-language articles (SPEC.md §3.1).

Milestone 1 stub: wires the CLI contract and (optionally) saves a project,
but does not yet call Wikidata/MediaWiki — that's Milestone 2.
"""

from __future__ import annotations

from pathlib import Path

from curiosity_radar import project_state
from curiosity_radar.cache.paths import resolve_data_dir
from curiosity_radar.schemas import ArticleInfo, Cluster, ResolveResult

NOT_IMPLEMENTED_WARNING = (
    "resolve is not yet implemented against live Wikidata/MediaWiki data (see PLAN.md Milestone 2)"
)


def run(
    *,
    topic: str | None,
    qid: str | None,
    languages: list[str],
    related_qids: list[str],
    save_as: str | None,
    data_dir: Path | None,
) -> ResolveResult:
    data_root = resolve_data_dir(data_dir)
    articles = {
        lang: ArticleInfo(wiki=f"{lang}.wikipedia", exists=False, reason="not_implemented")
        for lang in languages
    }
    cluster = Cluster(primary_qid=qid or "", related_qids=related_qids, articles=articles)

    if save_as:
        project_state.save_from_resolve(
            data_root, save_as, topic_query=topic, qid=qid or "", languages=languages
        )

    return ResolveResult(
        topic_query=topic,
        resolved_qid=qid,
        candidates=[],
        ambiguous=False,
        cluster=cluster,
        warnings=[NOT_IMPLEMENTED_WARNING],
    )
