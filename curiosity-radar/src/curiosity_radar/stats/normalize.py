"""Per-project aggregate-traffic normalization (SPEC.md §5).

Dividing an article's daily views by that project's total daily
`agent=user` views turns absolute counts into "share of wiki attention" —
controlling for wiki-wide confounds (readership growth, mobile-app
adoption shifts, seasonal effects) that would otherwise masquerade as
topic-specific trend.
"""

from __future__ import annotations

from collections.abc import Sequence


def normalize_by_aggregate(
    article_views: Sequence[float], aggregate_views: Sequence[float]
) -> list[float]:
    if len(article_views) != len(aggregate_views):
        raise ValueError("article_views and aggregate_views must be the same length")
    return [
        (article / aggregate) if aggregate > 0 else 0.0
        for article, aggregate in zip(article_views, aggregate_views, strict=True)
    ]
