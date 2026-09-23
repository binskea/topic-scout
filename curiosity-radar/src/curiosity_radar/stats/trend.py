"""Theil-Sen slope + Mann-Kendall trend test (SPEC.md §5).

Per `CLAUDE.md`: built directly on `scipy.stats.theilslopes` and
`scipy.stats.kendalltau` rather than a standalone Mann-Kendall package —
Kendall's tau of (day-index, views) *is* the Mann-Kendall trend statistic,
and its p-value is the MK significance test.

Confidence labels are mapped from the numbers, never the numbers alone
(SPEC.md §5): `p<0.01 & |tau|>0.3` -> "strong evidence of growth/decline",
`p<0.05` -> "likely growing/declining", otherwise -> "no clear trend
detected". `INSUFFICIENT_DATA_LABEL` is the label SPEC.md §7 assigns when
`check_sufficiency` below has already ruled out running the test at all.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy.stats import kendalltau, theilslopes

from curiosity_radar.schemas import MannKendall, TrendResult

MIN_DAYS_FOR_TREND = 60
STRONG_P_THRESHOLD = 0.01
STRONG_TAU_THRESHOLD = 0.3
LIKELY_P_THRESHOLD = 0.05
TREND_SIGNIFICANCE_ALPHA = 0.05
INSUFFICIENT_DATA_LABEL = "insufficient data"


@dataclass
class TrendCheck:
    sufficient: bool
    reason: str | None = None  # "all_zero_or_empty" | "too_short" | None
    days: int = 0


def check_sufficiency(views: Sequence[float], *, min_days: int = MIN_DAYS_FOR_TREND) -> TrendCheck:
    """Gate per SPEC.md §7: empty/all-zero and too-short series never reach
    Theil-Sen/Mann-Kendall — callers report `sufficient_for_trend: false`
    with this reason instead of fabricating a trend."""
    days = len(views)
    if days == 0 or all(v == 0 for v in views):
        return TrendCheck(sufficient=False, reason="all_zero_or_empty", days=days)
    if days < min_days:
        return TrendCheck(sufficient=False, reason="too_short", days=days)
    return TrendCheck(sufficient=True, days=days)


def _classify_trend(tau: float, p_value: float) -> Literal["increasing", "decreasing", "no trend"]:
    if p_value >= TREND_SIGNIFICANCE_ALPHA or tau == 0:
        return "no trend"
    return "increasing" if tau > 0 else "decreasing"


def _confidence_label(trend: str, p_value: float, tau: float) -> str:
    if trend == "no trend":
        return "no clear trend detected"
    noun = "growth" if trend == "increasing" else "decline"
    verb = "growing" if trend == "increasing" else "declining"
    if p_value < STRONG_P_THRESHOLD and abs(tau) > STRONG_TAU_THRESHOLD:
        return f"strong evidence of {noun}"
    if p_value < LIKELY_P_THRESHOLD:
        return f"likely {verb}"
    return "no clear trend detected"


def compute_trend(views: Sequence[float], x: Sequence[float] | None = None) -> TrendResult:
    """Compute Theil-Sen slope + Mann-Kendall trend over `views`.

    `x` lets a caller pass the original day-indices for a series with gaps
    removed (e.g. spike days masked out) so the slope stays in units of
    "per calendar day" rather than "per remaining sample". Defaults to
    `0..len(views)-1` for a contiguous series.

    Assumes the caller already checked `check_sufficiency` — this always
    returns a well-formed result, degrading to "no trend" for a constant
    series rather than hitting scipy's undefined-correlation NaN case.
    """
    y = np.asarray(views, dtype=float)
    n = len(y)
    xs = np.asarray(x, dtype=float) if x is not None else np.arange(n, dtype=float)

    if n < 2 or np.all(y == y[0]):
        return TrendResult(
            theil_sen_slope_per_day=0.0,
            mann_kendall=MannKendall(trend="no trend", p_value=1.0, tau=0.0),
            confidence_label="no clear trend detected",
        )

    slope, _intercept, _lo, _hi = theilslopes(y, xs)
    tau, p_value = kendalltau(xs, y)
    trend = _classify_trend(float(tau), float(p_value))
    label = _confidence_label(trend, float(p_value), float(tau))
    return TrendResult(
        theil_sen_slope_per_day=float(slope),
        mann_kendall=MannKendall(trend=trend, p_value=float(p_value), tau=float(tau)),
        confidence_label=label,
    )
