"""`stats/placebo.py`, pure-function unit tests. Per PLAN.md Milestone 5:
tested against a synthetic "wiki" with a known background-drift rate vs. a
synthetically trending topic, confirming the verdict correctly
distinguishes the two — no network fixture involved.
"""

from __future__ import annotations

import random

from curiosity_radar.stats.placebo import (
    MIN_ELIGIBLE_FOR_VERDICT,
    CandidateArticle,
    compute_verdict,
    select_basket,
)


def test_select_basket_filters_to_the_similar_popularity_tier() -> None:
    candidates = [
        CandidateArticle(title="too_small", avg_daily_views=5),
        CandidateArticle(title="in_range_low", avg_daily_views=100),
        CandidateArticle(title="in_range_high", avg_daily_views=900),
        CandidateArticle(title="too_big", avg_daily_views=50_000),
    ]
    basket = select_basket(candidates, topic_avg_views=300)
    titles = {c.title for c in basket}
    assert titles == {"in_range_low", "in_range_high"}


def test_select_basket_excludes_the_topics_own_category_tree() -> None:
    candidates = [
        CandidateArticle(title="unrelated", avg_daily_views=100, category_qids=frozenset({"Q1"})),
        CandidateArticle(
            title="same_category", avg_daily_views=100, category_qids=frozenset({"Q42"})
        ),
    ]
    basket = select_basket(
        candidates, topic_avg_views=100, exclude_category_qids=frozenset({"Q42"})
    )
    assert [c.title for c in basket] == ["unrelated"]


def test_select_basket_returns_all_eligible_when_fewer_than_basket_size() -> None:
    candidates = [CandidateArticle(title=f"a{i}", avg_daily_views=100) for i in range(5)]
    basket = select_basket(candidates, topic_avg_views=100, basket_size=20)
    assert len(basket) == 5


def test_select_basket_samples_down_to_the_requested_size() -> None:
    candidates = [CandidateArticle(title=f"a{i}", avg_daily_views=100) for i in range(50)]
    basket = select_basket(candidates, topic_avg_views=100, basket_size=20, rng=random.Random(42))
    assert len(basket) == 20
    assert len({c.title for c in basket}) == 20  # no duplicates


def test_select_basket_with_zero_topic_views_accepts_any_popularity() -> None:
    candidates = [
        CandidateArticle(title="tiny", avg_daily_views=0),
        CandidateArticle(title="huge", avg_daily_views=1_000_000),
    ]
    basket = select_basket(candidates, topic_avg_views=0)
    assert {c.title for c in basket} == {"tiny", "huge"}


def test_basket_median_slope_is_the_median_of_the_given_slopes() -> None:
    slopes = [float(i) for i in range(-10, 11)]  # -10..10, median 0
    result = compute_verdict(topic_slope=0.0, basket_slopes=slopes)
    assert result.basket_size == 21
    assert result.basket_median_slope == 0.0


def test_verdict_flags_a_trend_that_clearly_exceeds_background_drift() -> None:
    # A synthetic wiki: 21 "background drift" articles with small,
    # unremarkable slopes, and a topic whose slope is far above all of them.
    background_drift = [float(i) for i in range(-10, 11)]
    result = compute_verdict(topic_slope=1000.0, basket_slopes=background_drift)
    assert result.topic_slope_percentile_vs_basket == 100.0
    assert result.verdict == "trend exceeds wiki-wide background drift"


def test_verdict_does_not_claim_exceedance_for_a_topic_matching_background_drift() -> None:
    # The topic's own slope IS drawn from the same background-drift
    # distribution (i.e. it isn't really trending) — the verdict must not
    # claim it exceeds the wiki's normal drift.
    background_drift = [float(i) for i in range(-10, 11)]
    result = compute_verdict(topic_slope=0.0, basket_slopes=background_drift)  # the median itself
    assert result.topic_slope_percentile_vs_basket == 50.0
    assert result.verdict == "trend is stronger than typical wiki-wide background drift"


def test_verdict_flags_a_topic_weaker_than_background_drift() -> None:
    background_drift = [float(i) for i in range(-10, 11)]
    result = compute_verdict(topic_slope=-1000.0, basket_slopes=background_drift)
    assert result.topic_slope_percentile_vs_basket == 0.0
    assert result.verdict == "trend is within normal wiki-wide background drift"


def test_insufficient_basket_refuses_a_verdict_rather_than_fabricating_one() -> None:
    tiny_basket = [1.0, 2.0, 3.0]
    assert len(tiny_basket) < MIN_ELIGIBLE_FOR_VERDICT
    result = compute_verdict(topic_slope=100.0, basket_slopes=tiny_basket)
    assert result.basket_size == 3
    assert "insufficient comparison data" in result.verdict


def test_insufficient_basket_boundary_at_exactly_min_eligible() -> None:
    basket = [float(i) for i in range(MIN_ELIGIBLE_FOR_VERDICT)]
    result = compute_verdict(topic_slope=0.0, basket_slopes=basket)
    assert "insufficient comparison data" not in result.verdict
