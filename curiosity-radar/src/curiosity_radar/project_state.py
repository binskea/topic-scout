"""Load/save/mutate the per-project state file under `<data-dir>/projects/`.

This is the cheap lever behind every follow-up flow in SPEC.md §2/§3.7: it
persists a project's topic/QID, languages, date range, and exclusions so
that `fetch`/`analyze`/`chart`/`report`/`verify` can be re-run against a
consistent target across a whole conversation without the agent re-passing
everything each time.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from curiosity_radar import clock
from curiosity_radar.schemas import ArticleInfo, DateRange, ProjectShowResult, StaleFlags, TopicRef

DEFAULT_LOOKBACK_DAYS = 730


class ExclusionRange(BaseModel):
    start: str
    end: str


class ProjectState(BaseModel):
    slug: str
    topic_query: str | None = None
    qid: str | None = None
    languages: list[str] = []
    articles: dict[str, ArticleInfo] = {}
    related_search_terms: list[str] = []
    date_range_start: str
    date_range_end: str
    exclusions: list[ExclusionRange] = []
    created_at: str
    last_fetch_at: str | None = None
    last_analyze_at: str | None = None
    fetch_stale: bool = True
    analyze_stale: bool = True
    last_report_pdf_path: str | None = None

    def to_show_result(self) -> ProjectShowResult:
        return ProjectShowResult(
            project=self.slug,
            topic=TopicRef(qid=self.qid or "", query=self.topic_query),
            languages=self.languages,
            date_range=DateRange(start=self.date_range_start, end=self.date_range_end),
            exclusions=[f"{e.start}:{e.end}" for e in self.exclusions],
            last_fetch_at=self.last_fetch_at,
            last_analyze_at=self.last_analyze_at,
            stale=StaleFlags(fetch_stale=self.fetch_stale, analyze_stale=self.analyze_stale),
        )


def _path(data_dir: Path, slug: str) -> Path:
    return data_dir / "projects" / f"{slug}.json"


def load(data_dir: Path, slug: str) -> ProjectState | None:
    path = _path(data_dir, slug)
    if not path.exists():
        return None
    return ProjectState.model_validate_json(path.read_text())


def save(data_dir: Path, state: ProjectState) -> None:
    path = _path(data_dir, state.slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(state.model_dump_json(indent=2))


def list_slugs(data_dir: Path) -> list[str]:
    projects_dir = data_dir / "projects"
    if not projects_dir.exists():
        return []
    return sorted(f.stem for f in projects_dir.glob("*.json"))


def _default_date_range() -> tuple[str, str]:
    end = clock.today()
    start = end.fromordinal(end.toordinal() - DEFAULT_LOOKBACK_DAYS)
    return start.isoformat(), end.isoformat()


def create(
    data_dir: Path,
    slug: str,
    *,
    topic_query: str | None,
    qid: str | None,
    languages: list[str],
    articles: dict[str, ArticleInfo] | None = None,
    related_search_terms: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
) -> ProjectState:
    default_start, default_end = _default_date_range()
    state = ProjectState(
        slug=slug,
        topic_query=topic_query,
        qid=qid,
        languages=languages,
        articles=articles or {},
        related_search_terms=related_search_terms or [],
        date_range_start=start or default_start,
        date_range_end=end or default_end,
        created_at=datetime.now(UTC).isoformat(),
    )
    save(data_dir, state)
    return state


def save_from_resolve(
    data_dir: Path,
    slug: str,
    *,
    topic_query: str | None,
    qid: str,
    languages: list[str],
    articles: dict[str, ArticleInfo] | None = None,
    related_search_terms: list[str] | None = None,
) -> ProjectState:
    existing = load(data_dir, slug)
    if existing is not None:
        existing.topic_query = topic_query
        existing.qid = qid
        existing.languages = languages
        existing.articles = articles or {}
        existing.related_search_terms = related_search_terms or []
        existing.analyze_stale = True
        save(data_dir, existing)
        return existing
    return create(
        data_dir,
        slug,
        topic_query=topic_query,
        qid=qid,
        languages=languages,
        articles=articles,
        related_search_terms=related_search_terms,
    )
