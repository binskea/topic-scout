"""`project`: inspect/list/mutate saved project state (SPEC.md §3.7).

Pure local state manipulation, no cache/network involved, so this is fully
implemented (not stubbed) already in Milestone 1 — the follow-up flows in
Milestone 9 build the network-aware behavior (`fetch`/`analyze` reacting to
these mutations), not this command itself.
"""

from __future__ import annotations

from pathlib import Path

from curiosity_radar import project_state
from curiosity_radar.cache.paths import resolve_data_dir
from curiosity_radar.errors import CommandError
from curiosity_radar.schemas import ProjectListResult, ProjectShowResult


def _load_or_raise(data_root: Path, project: str) -> project_state.ProjectState:
    state = project_state.load(data_root, project)
    if state is None:
        raise CommandError(
            "project_not_found",
            f"No saved project '{project}'.",
            "Run resolve --save-as first.",
        )
    return state


def list_projects(*, data_dir: Path | None) -> ProjectListResult:
    data_root = resolve_data_dir(data_dir)
    slugs = project_state.list_slugs(data_root)
    shows = [project_state.load(data_root, slug) for slug in slugs]
    return ProjectListResult(projects=[s.to_show_result() for s in shows if s is not None])


def show(*, project: str, data_dir: Path | None) -> ProjectShowResult:
    data_root = resolve_data_dir(data_dir)
    return _load_or_raise(data_root, project).to_show_result()


def set_project(
    *,
    project: str,
    add_language: str | None,
    remove_language: str | None,
    exclude_date_range: str | None,
    set_date_range: str | None,
    data_dir: Path | None,
) -> ProjectShowResult:
    data_root = resolve_data_dir(data_dir)
    state = _load_or_raise(data_root, project)

    if add_language and add_language not in state.languages:
        state.languages.append(add_language)
        state.fetch_stale = True
        state.analyze_stale = True
    if remove_language and remove_language in state.languages:
        state.languages.remove(remove_language)
        state.analyze_stale = True
    if exclude_date_range:
        start, end = exclude_date_range.split(":", 1)
        state.exclusions.append(project_state.ExclusionRange(start=start, end=end))
        state.analyze_stale = True
    if set_date_range:
        start, end = set_date_range.split(":", 1)
        state.date_range_start = start
        state.date_range_end = end
        state.fetch_stale = True
        state.analyze_stale = True

    project_state.save(data_root, state)
    return state.to_show_result()


def fork(*, project: str, as_slug: str, data_dir: Path | None) -> ProjectShowResult:
    data_root = resolve_data_dir(data_dir)
    state = _load_or_raise(data_root, project)
    forked = state.model_copy(update={"slug": as_slug})
    project_state.save(data_root, forked)
    return forked.to_show_result()
