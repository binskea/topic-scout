# Statistical methods — implementation detail

Expands `SPEC.md` §5 with the actual constants/thresholds in
`src/curiosity_radar/stats/*.py`, so an agent (or a human) reading a
confidence label or a placebo verdict knows exactly what produced it. All
four modules are pure functions over in-memory series — no network, no
cache I/O — and are unit-tested against synthetic data
(`tests/test_trend_stats.py`, `tests/test_spikes.py`,
`tests/test_normalize.py`, `tests/test_placebo.py`), independent of
whatever Wikimedia's real data looks like.

## Trend: Theil-Sen slope + Mann-Kendall (`stats/trend.py`)

Built directly on `scipy.stats.theilslopes` / `scipy.stats.kendalltau` —
Kendall's tau of `(day-index, views)` *is* the Mann-Kendall trend
statistic, and its p-value is the MK significance test (`CLAUDE.md`'s
stack rationale: no separate, possibly-unmaintained MK package needed).

**Sufficiency gate, before any trend is computed** (`check_sufficiency`):
- `days == 0` or every value is `0` → `reason: "all_zero_or_empty"`.
- `days < MIN_DAYS_FOR_TREND` (**60**) → `reason: "too_short"`.
- Otherwise sufficient. Callers (`analyze._analyze_language`) never call
  `compute_trend` on an insufficient series — they return a fixed
  placeholder (`theil_sen_slope_per_day: 0.0`, `mann_kendall.trend: "no
  trend"`, `p_value: 1.0`, `confidence_label: "insufficient data"`)
  instead of fabricating a number from too little data.

**Classification** (`_classify_trend`): `p_value >= 0.05` (
`TREND_SIGNIFICANCE_ALPHA`) or `tau == 0` → `"no trend"`; otherwise
`"increasing"`/`"decreasing"` by the sign of `tau`.

**Confidence label** (`_confidence_label`), exactly per `SPEC.md` §5 —
asserted byte-for-byte against these thresholds in
`test_trend_stats.py::test_confidence_label_thresholds_match_spec_exactly`:
- `trend == "no trend"` → `"no clear trend detected"`.
- `p_value < 0.01` (`STRONG_P_THRESHOLD`) **and** `|tau| > 0.3`
  (`STRONG_TAU_THRESHOLD`) → `"strong evidence of growth"` /
  `"strong evidence of decline"`.
- `p_value < 0.05` (`LIKELY_P_THRESHOLD`) → `"likely growing"` /
  `"likely declining"`.
- Otherwise → `"no clear trend detected"`.

**Degenerate input**: fewer than 2 points, or every value identical, skips
scipy entirely and returns a "no clear trend detected" result directly —
avoids scipy's undefined-correlation `NaN` on a constant series.

**`x` (day-offsets) parameter**: callers can pass the original day-indices
for a series with gaps removed (spike days masked, excluded date ranges
dropped) so the returned slope stays in units of "per calendar day," not
"per remaining sample." `analyze.py` always passes real day-offsets, for
both the with-spikes and spikes-excluded reads and after any exclusions.

**Known limitation, not yet mitigated in code** (`SPEC.md` §5): Mann-Kendall
assumes independent observations, but daily pageviews have weekly
autocorrelation, which can inflate apparent significance. `SPEC.md`
suggested deseasonalizing (divide by a 7-day rolling median) or a seasonal-
MK variant as the fix — **not implemented** as of Milestone 10; a p-value
here should be read as "probably significant," not a rigorously correct
one. Worth revisiting before this skill's numbers are used for anything
more consequential than "where should I look next."

## Spike detection: MAD (`stats/spikes.py`)

`z = |x - median| / (median(|x - median|) * 1.4826)` (`MAD_SCALE`), flagged
when `z > 3.5` (`DEFAULT_THRESHOLD`). Median Absolute Deviation is robust
to the very outliers it's detecting — unlike a mean/stdev z-score, which a
big spike itself inflates (potentially masking itself or smaller spikes).

**Degenerate case**: if `MAD == 0` (more than half the series ties the
median — common in idealized/synthetic data, essentially never in real
daily pageviews), `detect_spikes` returns no spikes rather than dividing by
zero or flagging every nonzero wobble as an "infinite-z" spike.

`exclude_indices` drops flagged positions while keeping original day-
indices, so `trend.compute_trend`'s slope stays in true per-calendar-day
units when re-run on the spike-masked series (`analyze`'s
`trend_excluding_spikes`).

**Known limitation** (`SPEC.md` §5): if more than roughly half a series is
itself "outlying" (a genuinely bursty-baseline topic, not occasional
spikes on a stable baseline), spike-removal can strip real signal, not
noise. Not auto-detected — `data_quality.zero_view_days` and a visibly odd
with-spikes-vs-excluding-spikes gap are the closest proxies today.

## Normalization (`stats/normalize.py`)

`article_views[i] / aggregate_views[i]` per day, `0.0` when the
aggregate is `0` (avoids a `ZeroDivisionError`; a zero-traffic day for an
entire wiki would be its own anomaly worth noticing separately, not a
`NaN` here). Turns raw counts into "share of the project's daily
`agent=user` traffic," controlling for wiki-wide confounds (overall
readership growth, mobile-app adoption shifts, seasonal effects) that
would otherwise masquerade as topic-specific trend — this is why every
`theil_sen_slope_per_day` in `analyze`'s output is a slope over a *share*,
not a raw view count, and why the report's Assumptions box states this
explicitly (`SPEC.md` §6).

## Placebo test (`stats/placebo.py`)

**Scope, stated plainly:** this module is the pure statistical core only —
`select_basket` filters a *caller-supplied* candidate pool (title +
average daily views + Wikidata category QIDs); `compute_verdict`
percentile-ranks a topic's slope against a list of *already-computed*
basket slopes. **Actually sourcing that candidate pool live from Wikimedia
is not implemented** (`SPEC.md` §9 item 1 is still an open question,
`api-notes.md` §1.3 notes the AQS "top articles" endpoint isn't wired in
for exactly this reason) — `analyze.py` currently calls `compute_verdict`
with an **empty** basket every time, so **every placebo verdict in this
skill's output today reads "insufficient comparison data... found 0."**
This is honest (never a fabricated percentile, never a bare `null`), but
it means the placebo confidence signal `SPEC.md` §5 describes as the
"most persuasive, legible" headline metric isn't actually live yet — lean
on the Theil-Sen/Mann-Kendall `confidence_label` instead until a basket
source exists.

`select_basket`: eligible = within `POPULARITY_TIER_ORDERS_OF_MAGNITUDE`
(**1**) order of magnitude of the topic's own average daily views, **and**
sharing no Wikidata category QID with the topic (excludes thematically
related articles, e.g. other diet articles for an "intermittent fasting"
placebo). Samples down to `basket_size` (default `DEFAULT_BASKET_SIZE`
**20**) if the eligible pool is larger; returns everything if smaller.

`compute_verdict`: refuses to report a real percentile below
`MIN_ELIGIBLE_FOR_VERDICT` (**10**) basket members — `SPEC.md` §9 item 1's
open question, resolved here. Otherwise: `basket_median_slope` = median of
basket slopes; `topic_slope_percentile_vs_basket` via
`scipy.stats.percentileofscore(..., kind="mean")`; verdict tiers (this
implementation's own choice — `SPEC.md` §5 gives only one example string,
not a frozen threshold table):
- `>= 90th percentile` (`STRONG_PERCENTILE`) → `"trend exceeds wiki-wide
  background drift"`.
- `>= 50th percentile` (`TYPICAL_PERCENTILE`) → `"trend is stronger than
  typical wiki-wide background drift"`.
- else → `"trend is within normal wiki-wide background drift"`.
