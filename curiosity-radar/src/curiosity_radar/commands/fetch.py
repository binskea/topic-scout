"""`fetch`: pageviews + aggregate fetch, updates project state (SPEC.md §3.2).

Milestone 3: fetches/updates cached raw pageview data from AQS. Closed
months are served from `cache/raw/` without a network call; the open
month is always refetched; missing days are zero-filled (per Milestone 0's
documented-but-not-directly-observed AQS behavior); a redirect alias
discovered by `resolve` is fetched and summed into its language's series
(Milestone 0 finding: AQS tracks a redirect title's traffic separately from
its canonical target); the project-aggregate series is fetched/cached
alongside per-article data for later normalization (Milestone 4+).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from pathlib import Path

import httpx

from curiosity_radar import clock, project_state
from curiosity_radar.cache import store
from curiosity_radar.cache.paths import resolve_data_dir
from curiosity_radar.commands import resolve as resolve_cmd
from curiosity_radar.errors import CommandError
from curiosity_radar.project_state import ProjectState
from curiosity_radar.schemas import CoverageEntry, FetchedSummary, FetchResult
from curiosity_radar.wikimedia import aqs_client
from curiosity_radar.wikimedia.http import RETRY_STATUS_CODES, build_client

# [UNVERIFIED-LIVE] believed ~2015-07-01 (Milestone 0 only confirmed 2010 predates it,
# not the exact boundary) — used as a safe clamp point, not an exact cutoff.
AQS_EARLIEST_DATE = date(2015, 7, 1)
AGGREGATE_SLOT = store.AGGREGATE_SLOT


def run(
    *,
    project: str,
    topic: str | None,
    languages: list[str] | None,
    start: str | None,
    end: str | None,
    granularity: str,
    data_dir: Path | None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FetchResult:
    data_root = resolve_data_dir(data_dir)
    state = project_state.load(data_root, project)

    if state is None:
        if not (topic and languages):
            raise CommandError(
                "project_not_found",
                f"No saved project '{project}' and no --topic/--languages given to create one.",
                "Run resolve --save-as first, or pass --topic and --languages directly.",
            )
        resolved = asyncio.run(
            resolve_cmd._resolve(
                topic=topic, qid=None, languages=languages, related_qids=[], transport=transport
            )
        )
        state = project_state.save_from_resolve(
            data_root,
            project,
            topic_query=topic,
            qid=resolved.resolved_qid or "",
            languages=languages,
            articles=resolved.cluster.articles if resolved.cluster else {},
        )
    else:
        # A language added via `project set --add-language` (SPEC.md §2's "add
        # Slovak" flow) has no resolved article on file yet — resolve exactly
        # the newly-added language(s) here, live, before touching AQS, so
        # already-resolved languages never re-trigger any network call.
        missing_langs = [lang for lang in state.languages if lang not in state.articles]
        if missing_langs and state.qid:
            resolved = asyncio.run(
                resolve_cmd._resolve(
                    topic=state.topic_query,
                    qid=state.qid,
                    languages=missing_langs,
                    related_qids=[],
                    transport=transport,
                )
            )
            if resolved.cluster:
                state.articles.update(resolved.cluster.articles)
            project_state.save(data_root, state)

    result = asyncio.run(
        _fetch(data_root, state, start=start, end=end, granularity=granularity, transport=transport)
    )

    state.last_fetch_at = datetime.now(UTC).isoformat()
    state.fetch_stale = False
    state.analyze_stale = True
    state.date_range_start = (
        result.coverage_start.isoformat() if result.coverage_start else state.date_range_start
    )
    state.date_range_end = (
        result.coverage_end.isoformat() if result.coverage_end else state.date_range_end
    )
    project_state.save(data_root, state)

    return result.fetch_result


class _FetchOutcome:
    def __init__(
        self, fetch_result: FetchResult, coverage_start: date | None, coverage_end: date | None
    ) -> None:
        self.fetch_result = fetch_result
        self.coverage_start = coverage_start
        self.coverage_end = coverage_end


async def _fetch(
    data_root: Path,
    state: ProjectState,
    *,
    start: str | None,
    end: str | None,
    granularity: str,
    transport: httpx.AsyncBaseTransport | None,
) -> _FetchOutcome:
    today = clock.today()
    requested_start = (
        date.fromisoformat(start) if start else date.fromisoformat(state.date_range_start)
    )
    requested_end = date.fromisoformat(end) if end else date.fromisoformat(state.date_range_end)
    if requested_end > today:
        requested_end = today

    effective_start = max(requested_start, AQS_EARLIEST_DATE)
    days_requested = (requested_end - requested_start).days + 1
    clamped_days = (effective_start - requested_start).days

    warnings: list[str] = []
    if clamped_days > 0:
        warnings.append(
            f"Requested start {requested_start.isoformat()} predates AQS's available history; "
            f"clamped to {effective_start.isoformat()}."
        )

    coverage: dict[str, CoverageEntry] = {}
    http_requests_made = 0
    articles_fetched = 0
    redirect_aliases_fetched = 0
    fresh_months: set[str] = set()

    try:
        async with build_client(transport=transport) as client:
            for lang in state.languages:
                article = state.articles.get(lang)
                if article is None or not article.exists or article.title is None:
                    warnings.append(f"{lang}: no resolved article on file, skipping fetch")
                    continue

                wiki = article.wiki
                title = article.title

                def _make_range(wiki: str, title: str) -> store.FetchRange:
                    async def _range(m_start: date, m_end: date) -> list[dict]:
                        return await aqs_client.fetch_per_article(
                            client, wiki, title, granularity, m_start, m_end
                        )

                    return _range

                canonical_days, requests, months = await store.ensure_series(
                    data_root,
                    wiki=wiki,
                    article_slot=title,
                    granularity=granularity,
                    start=effective_start,
                    end=requested_end,
                    today=today,
                    fetch_range=_make_range(wiki, title),
                )
                http_requests_made += requests
                fresh_months |= months
                articles_fetched += 1

                summed = {d.date: d.views for d in canonical_days}
                if article.redirect_from:
                    redirect_from = article.redirect_from
                    alias_days, requests, months = await store.ensure_series(
                        data_root,
                        wiki=wiki,
                        article_slot=redirect_from,
                        granularity=granularity,
                        start=effective_start,
                        end=requested_end,
                        today=today,
                        fetch_range=_make_range(wiki, redirect_from),
                    )
                    http_requests_made += requests
                    fresh_months |= months
                    redirect_aliases_fetched += 1
                    for d in alias_days:
                        summed[d.date] = summed.get(d.date, 0) + d.views

                zero_fill_days = sum(1 for views in summed.values() if views == 0)
                coverage[lang] = CoverageEntry(
                    wiki=wiki,
                    article=article.title,
                    redirect_alias_included=article.redirect_from,
                    first_day=effective_start.isoformat(),
                    last_day=requested_end.isoformat(),
                    missing_days=clamped_days,
                    zero_fill_days=zero_fill_days,
                )

            wikis = {
                resolved.wiki
                for lang in state.languages
                if (resolved := state.articles.get(lang)) is not None and resolved.exists
            }

            def _make_aggregate_range(wiki: str) -> store.FetchRange:
                async def _range(m_start: date, m_end: date) -> list[dict]:
                    return await aqs_client.fetch_aggregate(
                        client, wiki, granularity, m_start, m_end
                    )

                return _range

            for wiki in wikis:
                _, requests, months = await store.ensure_series(
                    data_root,
                    wiki=wiki,
                    article_slot=AGGREGATE_SLOT,
                    granularity=granularity,
                    start=effective_start,
                    end=requested_end,
                    today=today,
                    fetch_range=_make_aggregate_range(wiki),
                )
                http_requests_made += requests
                fresh_months |= months
    except httpx.TransportError as exc:
        raise CommandError(
            "network_error",
            "Could not reach Wikimedia APIs.",
            "Check network/proxy connectivity; already-cached closed months are still usable "
            "via analyze without a fresh fetch.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in RETRY_STATUS_CODES:
            raise CommandError(
                "rate_limited",
                "Wikimedia API is rate-limiting this client.",
                "Wait a minute and rerun fetch — already-cached months are unaffected.",
            ) from exc
        raise

    days_freshly_fetched = 0
    for year_month in store.iter_months(effective_start, requested_end):
        if year_month not in fresh_months:
            continue
        month_start, month_end = store.month_bounds(year_month)
        sub_start, sub_end = max(month_start, effective_start), min(month_end, requested_end)
        days_freshly_fetched += (sub_end - sub_start).days + 1
    effective_days = (
        (requested_end - effective_start).days + 1 if effective_start <= requested_end else 0
    )
    days_from_cache = effective_days - days_freshly_fetched

    fetched = FetchedSummary(
        articles_fetched=articles_fetched,
        redirect_aliases_fetched=redirect_aliases_fetched,
        days_requested=days_requested,
        days_from_cache=days_from_cache,
        days_freshly_fetched=days_freshly_fetched,
        http_requests_made=http_requests_made,
    )

    fetch_result = FetchResult(
        project=state.slug, fetched=fetched, coverage=coverage, warnings=warnings
    )
    return _FetchOutcome(fetch_result, effective_start, requested_end)
