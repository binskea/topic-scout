"""`stats/normalize.py`, pure-function unit tests against synthetic series."""

from __future__ import annotations

import pytest

from curiosity_radar.stats.normalize import normalize_by_aggregate


def test_normalizes_to_share_of_aggregate_traffic() -> None:
    article = [10.0, 20.0, 30.0]
    aggregate = [100.0, 100.0, 100.0]
    assert normalize_by_aggregate(article, aggregate) == [0.1, 0.2, 0.3]


def test_wiki_wide_growth_confound_washes_out_when_article_share_is_constant() -> None:
    # The article and the whole wiki both double in raw traffic over time —
    # a naive read of raw counts would look like "the article is trending,"
    # but its actual *share* of wiki attention hasn't changed at all.
    article = [10.0, 15.0, 20.0]
    aggregate = [100.0, 150.0, 200.0]
    normalized = normalize_by_aggregate(article, aggregate)
    assert normalized == pytest.approx([0.1, 0.1, 0.1])


def test_zero_aggregate_day_normalizes_to_zero_instead_of_crashing() -> None:
    article = [5.0, 0.0]
    aggregate = [100.0, 0.0]
    assert normalize_by_aggregate(article, aggregate) == [0.05, 0.0]


def test_mismatched_lengths_raise() -> None:
    with pytest.raises(ValueError, match="same length"):
        normalize_by_aggregate([1.0, 2.0], [1.0])
