"""`chart`: render chart image files from derived stats (SPEC.md §3.4).

Milestone 1 stub: wires the CLI contract, but does not yet render any
images — that's Milestone 7.
"""

from __future__ import annotations

from pathlib import Path

from curiosity_radar import project_state
from curiosity_radar.cache.paths import resolve_data_dir
from curiosity_radar.errors import CommandError
from curiosity_radar.schemas import ChartResult


def run(*, project: str, kinds: list[str], data_dir: Path | None) -> ChartResult:
    data_root = resolve_data_dir(data_dir)
    state = project_state.load(data_root, project)
    if state is None:
        raise CommandError(
            "project_not_found",
            f"No saved project '{project}'.",
            "Run resolve --save-as, fetch, and analyze first.",
        )
    return ChartResult(project=project, charts=[])
