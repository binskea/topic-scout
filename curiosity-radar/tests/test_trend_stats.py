"""`stats/trend.py`, pure-function unit tests against synthetic series
(CLAUDE.md: no network fixture involved) covering PLAN.md Milestone 4's
required cases: flat, steadily rising, spiky, all-zero, too-short-for-trend.
Confidence-label thresholds are asserted to match SPEC.md §5 exactly.
"""

from __future__ import annotations

from curiosity_radar.stats import spikes, trend


def test_flat_series_is_sufficient_but_shows_no_trend() -> None:
    views = [50.0] * 100
    check = trend.check_sufficiency(views)
    assert check.sufficient is True

    result = trend.compute_trend(views)
    assert result.theil_sen_slope_per_day == 0.0
    assert result.mann_kendall.trend == "no trend"
    assert result.confidence_label == "no clear trend detected"


def test_steadily_rising_series_is_strong_evidence_of_growth() -> None:
    views = [float(i) for i in range(1, 101)]
    check = trend.check_sufficiency(views)
    assert check.sufficient is True

    result = trend.compute_trend(views)
    assert result.theil_sen_slope_per_day > 0
    assert result.mann_kendall.trend == "increasing"
    assert result.mann_kendall.tau is not None and abs(result.mann_kendall.tau) > 0.3
    assert result.mann_kendall.p_value < 0.01
    assert result.confidence_label == "strong evidence of growth"


def test_steadily_declining_series_is_strong_evidence_of_decline() -> None:
    views = [float(100 - i) for i in range(100)]
    result = trend.compute_trend(views)
    assert result.theil_sen_slope_per_day < 0
    assert result.mann_kendall.trend == "decreasing"
    assert result.confidence_label == "strong evidence of decline"


def test_spiky_series_theil_sen_slope_is_robust_to_the_spikes() -> None:
    # A (realistically-jittered, not perfectly flat) baseline with 3 days
    # of viral traffic. Theil-Sen's slope is the median of pairwise
    # slopes, so a handful of outlier days shouldn't move it (SPEC.md §5's
    # whole rationale for choosing it over OLS).
    n = 90
    views = [100.0 + (i % 5 - 2) for i in range(n)]
    spike_indices = {10, 45, 80}
    for i in spike_indices:
        views[i] = 5000.0

    detected = spikes.detect_spikes(views)
    assert {s.index for s in detected} == spike_indices

    check = trend.check_sufficiency(views)
    assert check.sufficient is True
    result = trend.compute_trend(views)
    assert result.theil_sen_slope_per_day == 0.0
    assert result.confidence_label == "no clear trend detected"

    # With the spike days masked out, the trend read shouldn't change
    # (the underlying series really is flat) — this is the "trend
    # excluding spikes" side-by-side view from SPEC.md §3.3.
    xs, ys = spikes.exclude_indices(views, spike_indices)
    excluding_spikes = trend.compute_trend(ys, x=xs)
    assert excluding_spikes.theil_sen_slope_per_day == 0.0
    assert excluding_spikes.confidence_label == "no clear trend detected"


def test_all_zero_series_is_not_sufficient_for_trend() -> None:
    check = trend.check_sufficiency([0.0] * 100)
    assert check.sufficient is False
    assert check.reason == "all_zero_or_empty"


def test_empty_series_is_not_sufficient_for_trend() -> None:
    check = trend.check_sufficiency([])
    assert check.sufficient is False
    assert check.reason == "all_zero_or_empty"
    assert check.days == 0


def test_too_short_series_is_not_sufficient_for_trend() -> None:
    views = [float(i) for i in range(14)]
    check = trend.check_sufficiency(views)
    assert check.sufficient is False
    assert check.reason == "too_short"
    assert check.days == 14


def test_confidence_label_thresholds_match_spec_exactly() -> None:
    # p<0.01 & |tau|>0.3 -> "strong evidence of growth" (SPEC.md §5).
    assert trend._confidence_label("increasing", 0.006, 0.31) == "strong evidence of growth"
    assert trend._confidence_label("decreasing", 0.006, -0.31) == "strong evidence of decline"
    # p<0.05 (but not the strong tier) -> "likely growing".
    assert trend._confidence_label("increasing", 0.02, 0.2) == "likely growing"
    assert trend._confidence_label("decreasing", 0.02, -0.2) == "likely declining"
    # p<0.01 alone, without |tau|>0.3, doesn't qualify for the strong tier.
    assert trend._confidence_label("increasing", 0.005, 0.1) == "likely growing"
    # Anything else -> "no clear trend detected".
    assert trend._confidence_label("no trend", 0.5, 0.0) == "no clear trend detected"
    assert trend._confidence_label("increasing", 0.2, 0.05) == "no clear trend detected"
