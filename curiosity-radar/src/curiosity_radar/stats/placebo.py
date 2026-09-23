"""Placebo-basket comparison (SPEC.md §5): is a topic's normalized trend
distinguishable from a similar-popularity tier's wiki-wide background
drift, or is it just noise?

This module is the pure statistical core only. `select_basket` filters a
*given* candidate pool — wiki articles the caller already knows the average
daily views and Wikidata category-QID membership for — down to a similar-
popularity tier, excluding the topic's own category tree. `compute_verdict`
turns the topic's slope plus the resulting basket's own slopes into a
percentile + plain-language verdict. Actually *sourcing* that candidate
pool live from Wikimedia (a "similarly popular, unrelated articles"
query) is out of this milestone's scope: SPEC.md §9 item 1 leaves the
exact sourcing/minimum-basket-size question open, and
`references/api-notes.md` §1.3 notes the AQS "top articles" endpoint isn't
wired into v1 for exactly this reason — wiring a live source is `analyze`'s
concern in a later milestone.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy.stats import percentileofscore

from curiosity_radar.schemas import Placebo

DEFAULT_BASKET_SIZE = 20
POPULARITY_TIER_ORDERS_OF_MAGNITUDE = 1

# SPEC.md §9 item 1 ("is there a principled minimum count below which the
# placebo verdict shouldn't be reported at all") — resolved here: yes, 10,
# per that same open question's own suggested figure.
MIN_ELIGIBLE_FOR_VERDICT = 10

STRONG_PERCENTILE = 90
TYPICAL_PERCENTILE = 50

INSUFFICIENT_BASKET_VERDICT = "insufficient comparison data for a placebo verdict"


@dataclass
class CandidateArticle:
    title: str
    avg_daily_views: float
    category_qids: frozenset[str] = frozenset()


def select_basket(
    candidates: Sequence[CandidateArticle],
    *,
    topic_avg_views: float,
    exclude_category_qids: frozenset[str] = frozenset(),
    basket_size: int = DEFAULT_BASKET_SIZE,
    rng: random.Random | None = None,
) -> list[CandidateArticle]:
    """Filter to a similar-popularity tier (within ~1 order of magnitude of
    `topic_avg_views`), drop anything sharing a category with the topic
    (SPEC.md §5's "accidentally including thematically related articles
    undermines the point"), then sample up to `basket_size` of the rest."""
    if topic_avg_views <= 0:
        low, high = 0.0, float("inf")
    else:
        scale = 10**POPULARITY_TIER_ORDERS_OF_MAGNITUDE
        low, high = topic_avg_views / scale, topic_avg_views * scale

    eligible = [
        c
        for c in candidates
        if low <= c.avg_daily_views <= high and not (c.category_qids & exclude_category_qids)
    ]
    if len(eligible) <= basket_size:
        return eligible
    picker = rng if rng is not None else random.Random()
    return picker.sample(eligible, basket_size)


def compute_verdict(
    topic_slope: float,
    basket_slopes: Sequence[float],
    *,
    min_eligible: int = MIN_ELIGIBLE_FOR_VERDICT,
) -> Placebo:
    """Percentile-rank `topic_slope` against the empirical distribution of
    `basket_slopes` and map it to a plain-language verdict (SPEC.md §5:
    "reported as a plain verdict plus percentile... rather than a raw
    z-score"). Refuses to report a verdict below `min_eligible` basket
    members rather than fabricating a noisy percentile from too few."""
    n = len(basket_slopes)
    if n < min_eligible:
        return Placebo(
            basket_size=n,
            basket_median_slope=0.0,
            topic_slope_percentile_vs_basket=0.0,
            verdict=(
                f"{INSUFFICIENT_BASKET_VERDICT} "
                f"(need at least {min_eligible} similarly-popular articles, found {n})"
            ),
        )

    median_slope = float(np.median(basket_slopes))
    percentile = float(percentileofscore(basket_slopes, topic_slope, kind="mean"))
    return Placebo(
        basket_size=n,
        basket_median_slope=median_slope,
        topic_slope_percentile_vs_basket=percentile,
        verdict=_verdict_label(percentile),
    )


def _verdict_label(percentile: float) -> str:
    if percentile >= STRONG_PERCENTILE:
        return "trend exceeds wiki-wide background drift"
    if percentile >= TYPICAL_PERCENTILE:
        return "trend is stronger than typical wiki-wide background drift"
    return "trend is within normal wiki-wide background drift"
