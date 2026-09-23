"""MAD-based spike detection (SPEC.md §5).

Median Absolute Deviation is robust to the very outliers it detects (unlike
a mean/stdev z-score, which the outliers themselves contaminate). Flags any
day with `|x - median| / MAD > threshold` (3.5, with the standard 1.4826
scaling constant that makes MAD a consistent estimator of the standard
deviation for normal data).

Returns index-based results only — mapping an index back to a calendar
date and computing `share_of_total_views` needs the full dated series and
project total, which is `analyze`'s job (Milestone 6), not this pure
function's.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

MAD_SCALE = 1.4826
DEFAULT_THRESHOLD = 3.5


@dataclass
class SpikeDay:
    index: int
    z_mad: float


def detect_spikes(
    views: Sequence[float], *, threshold: float = DEFAULT_THRESHOLD
) -> list[SpikeDay]:
    arr = np.asarray(views, dtype=float)
    if arr.size == 0:
        return []

    median = float(np.median(arr))
    mad = float(np.median(np.abs(arr - median))) * MAD_SCALE
    if mad == 0:
        # Degenerate spread (e.g. a near-constant baseline) — comparing
        # against it would flag every nonzero wobble as an infinite-z
        # "spike," so there's nothing meaningful to flag.
        return []

    z = np.abs(arr - median) / mad
    return [SpikeDay(index=i, z_mad=float(z[i])) for i in range(len(arr)) if z[i] > threshold]


def exclude_indices(views: Sequence[float], exclude: set[int]) -> tuple[list[int], list[float]]:
    """Return (day-indices, values) with `exclude`d positions dropped,
    keeping the original day-indices so a trend computed over the result
    stays in units of "per calendar day" (see `stats.trend.compute_trend`)."""
    kept = [(i, v) for i, v in enumerate(views) if i not in exclude]
    return [i for i, _ in kept], [v for _, v in kept]
