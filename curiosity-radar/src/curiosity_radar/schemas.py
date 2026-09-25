"""Pydantic models for every CLI JSON contract described in SPEC.md §3.

These are the single source of truth for each command's output shape.
`tests/test_cli_contracts.py` validates every command's actual stdout
against the model here, so drift between SPEC.md, this file, and the
implementation is caught automatically rather than discovered later by
an agent parsing unexpected JSON.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Shared: error contract (SPEC.md §3, top-level rule)
# ---------------------------------------------------------------------------


class ErrorDetail(StrictModel):
    code: str
    message: str
    hint: str | None = None


class ErrorResponse(StrictModel):
    error: ErrorDetail


# ---------------------------------------------------------------------------
# 3.1 resolve
# ---------------------------------------------------------------------------


class Candidate(StrictModel):
    qid: str
    label: str
    description: str | None = None
    match_type: Literal["label", "alias"]


class ArticleInfo(StrictModel):
    title: str | None = None
    wiki: str
    redirect_from: str | None = None
    exists: bool
    reason: str | None = None


class Cluster(StrictModel):
    primary_qid: str
    related_qids: list[str] = []
    articles: dict[str, ArticleInfo] = {}


class ResolveResult(StrictModel):
    topic_query: str | None = None
    resolved_qid: str | None = None
    candidates: list[Candidate] = []
    ambiguous: bool
    cluster: Cluster | None = None
    warnings: list[str] = []
    related_search_terms: list[str] = []


# ---------------------------------------------------------------------------
# 3.2 fetch
# ---------------------------------------------------------------------------


class FetchedSummary(StrictModel):
    articles_fetched: int
    redirect_aliases_fetched: int
    days_requested: int
    days_from_cache: int
    days_freshly_fetched: int
    http_requests_made: int


class CoverageEntry(StrictModel):
    wiki: str
    article: str | None = None
    redirect_alias_included: str | None = None
    first_day: str | None = None
    last_day: str | None = None
    missing_days: int
    zero_fill_days: int


class FetchResult(StrictModel):
    project: str
    fetched: FetchedSummary
    coverage: dict[str, CoverageEntry] = {}
    warnings: list[str] = []


# ---------------------------------------------------------------------------
# 3.3 analyze
# ---------------------------------------------------------------------------


class MannKendall(StrictModel):
    trend: Literal["increasing", "decreasing", "no trend"]
    p_value: float
    tau: float | None = None


class TrendResult(StrictModel):
    theil_sen_slope_per_day: float
    mann_kendall: MannKendall
    confidence_label: str


class Spike(StrictModel):
    date: str
    z_mad: float
    share_of_total_views: float


class Placebo(StrictModel):
    basket_size: int
    basket_median_slope: float
    topic_slope_percentile_vs_basket: float
    verdict: str


class DataQuality(StrictModel):
    total_days: int
    zero_view_days: int
    sufficient_for_trend: bool
    reason: str | None = None


class LanguageAnalysis(StrictModel):
    normalized_trend: TrendResult
    trend_excluding_spikes: TrendResult
    spikes_detected: list[Spike] = []
    placebo: Placebo | None = None
    data_quality: DataQuality


class CrossLanguageRankingEntry(StrictModel):
    lang: str
    rank: int
    reason: str | None = None


class AnalyzeResult(StrictModel):
    project: str
    generated_at: str
    languages: dict[str, LanguageAnalysis] = {}
    cross_language_ranking: list[CrossLanguageRankingEntry] = []


# ---------------------------------------------------------------------------
# 3.4 chart
# ---------------------------------------------------------------------------


class ChartEntry(StrictModel):
    kind: str
    language: str | None = None
    path: str
    caption: str


class ChartResult(StrictModel):
    project: str
    charts: list[ChartEntry] = []


# ---------------------------------------------------------------------------
# 3.5 report
# ---------------------------------------------------------------------------


class ReportResult(StrictModel):
    project: str
    pdf_path: str
    engine_used: Literal["weasyprint", "fpdf2"]
    page_count: int
    sections_rendered: list[str] = []
    numeric_claims_count: int


# ---------------------------------------------------------------------------
# 3.6 verify
# ---------------------------------------------------------------------------


class Mismatch(StrictModel):
    claim_text: str
    expected: str
    found_in_pdf: str


class VerifyResult(StrictModel):
    project: str
    pdf_path: str
    claims_checked: int
    claims_matched: int
    claims_mismatched: int
    status: Literal["verified", "failed_verification"]
    mismatches: list[Mismatch] = []


# ---------------------------------------------------------------------------
# 3.7 project
# ---------------------------------------------------------------------------


class TopicRef(StrictModel):
    qid: str
    query: str | None = None


class DateRange(StrictModel):
    start: str
    end: str


class StaleFlags(StrictModel):
    fetch_stale: bool
    analyze_stale: bool


class ProjectShowResult(StrictModel):
    project: str
    topic: TopicRef
    languages: list[str]
    date_range: DateRange
    exclusions: list[str] = []
    last_fetch_at: str | None = None
    last_analyze_at: str | None = None
    stale: StaleFlags


class ProjectListResult(StrictModel):
    projects: list[ProjectShowResult] = []
