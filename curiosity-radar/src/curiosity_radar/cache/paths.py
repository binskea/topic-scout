"""Resolves the runtime data root per SPEC.md §1 "Runtime writable state".

Resolution order, first one that's set/writable wins:
1. an explicit path (the `--data-dir` flag or `CURIOSITY_RADAR_DATA_DIR`)
2. `$XDG_DATA_HOME/curiosity-radar` (falling back to
   `~/.local/share/curiosity-radar`)
3. `./.curiosity-radar/` under the current working directory
"""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR_NAME = "curiosity-radar"
ENV_VAR = "CURIOSITY_RADAR_DATA_DIR"


def _candidate_dirs(explicit: Path | str | None) -> list[Path]:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    else:
        env = os.environ.get(ENV_VAR)
        if env:
            candidates.append(Path(env).expanduser())
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    candidates.append(base / APP_DIR_NAME)
    candidates.append(Path.cwd() / f".{APP_DIR_NAME}")
    return candidates


def resolve_data_dir(explicit: Path | str | None = None) -> Path:
    """Return the runtime data root, creating it if necessary."""
    last_error: OSError | None = None
    for candidate in _candidate_dirs(explicit):
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write-check"
            probe.touch()
            probe.unlink()
        except OSError as exc:
            last_error = exc
            continue
        return candidate
    assert last_error is not None
    raise last_error


def ensure_subdir(data_dir: Path, *parts: str) -> Path:
    path = data_dir.joinpath(*parts)
    path.mkdir(parents=True, exist_ok=True)
    return path
