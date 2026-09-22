"""`analyze`: trend + spike + placebo stats, entirely from cached data
(SPEC.md §3.3).

Milestone 1 stub: wires the CLI contract and project-state staleness
bookkeeping, but does not yet compute any statistics — that's Milestone 4
(trend/spikes), Milestone 5 (placebo), wired together in Milestone 6.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from curiosity_radar import project_state
from curiosity_radar.cache.paths import resolve_data_dir
from curiosity_radar.errors import CommandError
from curiosity_radar.schemas import AnalyzeResult


def run(
    *,
    project: str,
    compare_languages: bool,
    placebo_basket_size: int,
    force_recompute: bool,
    data_dir: Path | None,
) -> AnalyzeResult:
    data_root = resolve_data_dir(data_dir)
    state = project_state.load(data_root, project)
    if state is None:
        raise CommandError(
            "project_not_found",
            f"No saved project '{project}'.",
            "Run resolve --save-as or fetch --project with --topic/--languages first.",
        )

    state.last_analyze_at = datetime.now(UTC).isoformat()
    state.analyze_stale = False
    project_state.save(data_root, state)

    return AnalyzeResult(
        project=project,
        generated_at=datetime.now(UTC).isoformat(),
        languages={},
        cross_language_ranking=[],
    )
