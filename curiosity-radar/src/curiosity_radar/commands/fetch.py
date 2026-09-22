"""`fetch`: pageviews + aggregate fetch, updates project state (SPEC.md §3.2).

Milestone 1 stub: wires the CLI contract and project bootstrapping/state
update, but does not yet call the AQS pageviews API — that's Milestone 3.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from curiosity_radar import project_state
from curiosity_radar.cache.paths import resolve_data_dir
from curiosity_radar.errors import CommandError
from curiosity_radar.schemas import CoverageEntry, FetchedSummary, FetchResult

NOT_IMPLEMENTED_WARNING = (
    "fetch is not yet implemented against live AQS pageview data (see PLAN.md Milestone 3)"
)


def run(
    *,
    project: str,
    topic: str | None,
    languages: list[str] | None,
    start: str | None,
    end: str | None,
    granularity: str,
    data_dir: Path | None,
) -> FetchResult:
    data_root = resolve_data_dir(data_dir)
    state = project_state.load(data_root, project)
    if state is None:
        if topic and languages:
            state = project_state.create(
                data_root,
                project,
                topic_query=topic,
                qid=None,
                languages=languages,
                start=start,
                end=end,
            )
        else:
            raise CommandError(
                "project_not_found",
                f"No saved project '{project}' and no --topic/--languages given to create one.",
                "Run resolve --save-as first, or pass --topic and --languages directly.",
            )

    coverage = {
        lang: CoverageEntry(
            wiki=f"{lang}.wikipedia",
            article=None,
            redirect_alias_included=None,
            first_day=None,
            last_day=None,
            missing_days=0,
            zero_fill_days=0,
        )
        for lang in state.languages
    }
    fetched = FetchedSummary(
        articles_fetched=0,
        redirect_aliases_fetched=0,
        days_requested=0,
        days_from_cache=0,
        days_freshly_fetched=0,
        http_requests_made=0,
    )

    state.last_fetch_at = datetime.now(UTC).isoformat()
    state.fetch_stale = False
    project_state.save(data_root, state)

    return FetchResult(
        project=project,
        fetched=fetched,
        coverage=coverage,
        warnings=[NOT_IMPLEMENTED_WARNING],
    )
