"""`stats/spikes.py`, pure-function unit tests against synthetic series."""

from __future__ import annotations

from curiosity_radar.stats import spikes


def _jittered_baseline(n: int, base: float = 100.0) -> list[float]:
    # Small day-to-day wobble, like real (never bit-for-bit identical)
    # pageview data — a literally constant baseline collapses MAD to
    # exactly 0 (more than half the series ties the median), which is an
    # artifact of synthetic data, not a case MAD-based detection needs to
    # handle for real traffic.
    return [base + (i % 5 - 2) for i in range(n)]


def test_detects_a_clear_spike_day() -> None:
    views = _jittered_baseline(30)
    views[15] = 5000.0
    detected = spikes.detect_spikes(views)
    assert [s.index for s in detected] == [15]
    assert detected[0].z_mad > spikes.DEFAULT_THRESHOLD


def test_flat_series_has_no_spikes() -> None:
    assert spikes.detect_spikes([100.0] * 30) == []


def test_empty_series_has_no_spikes() -> None:
    assert spikes.detect_spikes([]) == []


def test_multiple_spikes_all_detected() -> None:
    views = _jittered_baseline(60)
    spike_indices = {5, 20, 40, 55}
    for i in spike_indices:
        views[i] = 8000.0
    detected = spikes.detect_spikes(views)
    assert {s.index for s in detected} == spike_indices


def test_mild_day_to_day_wobble_is_not_flagged() -> None:
    # Realistic daily noise (+/-10%) around a baseline shouldn't trip the
    # 3.5x-MAD threshold - only genuine outliers should.
    baseline = 100.0
    views = [baseline * (1 + 0.1 * (-1) ** i) for i in range(40)]
    assert spikes.detect_spikes(views) == []


def test_exclude_indices_preserves_original_day_positions() -> None:
    views = [1.0, 2.0, 3.0, 4.0, 5.0]
    xs, ys = spikes.exclude_indices(views, {1, 3})
    assert xs == [0, 2, 4]
    assert ys == [1.0, 3.0, 5.0]


def test_exclude_indices_with_nothing_excluded_returns_everything() -> None:
    views = [1.0, 2.0, 3.0]
    xs, ys = spikes.exclude_indices(views, set())
    assert xs == [0, 1, 2]
    assert ys == views
