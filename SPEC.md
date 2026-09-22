# SPEC — `curiosity-radar`

An Agent Skill (per the [Agent Skills spec](https://agentskills.io/specification))
that lets an AI agent analyze Wikipedia pageview data to help B2C founders
decide which topics to build next and which languages/wikis to launch in —
producing data-backed answers, charts, and a shareable one-page PDF report
with explicit assumptions and limitations. See `TASK.md` for the full brief
and `PLAN.md` for how this gets built incrementally.

This document is the frozen architecture reference. `CLAUDE.md` covers dev
conventions; `curiosity-radar/references/api-notes.md` covers the Wikimedia/
Wikidata API contracts this design depends on.

**Updated 2026-09-22 after Milestone 0's live verification** (see
`api-notes.md` and `tests/cassettes/milestone0/README.md` for full detail).
Two findings changed this design: (1) AQS pageviews tracks redirect titles
as separate traffic from their canonical target, so `fetch` (§3.2) now
sums canonical + one known redirect alias per language; (2) an earlier
draft's worked examples used a memorized Wikidata QID (`Q1631107`) that
turned out to be wrong (it's "Bibliography," not the intended topic) — all
examples below now use an explicit `Q_EXAMPLE` placeholder, and `resolve`
must always look up QIDs live, never hardcode one.

## 1. Directory layout

```
curiosity-radar/
├── SKILL.md                          # short (<500 lines): triggers, command index, pointers to references/
├── pyproject.toml                    # console-script entry point, deps
├── uv.lock                           # pinned lockfile (committed)
├── .python-version                   # 3.12
├── src/curiosity_radar/
│   ├── cli.py                        # dispatches subcommands
│   ├── commands/
│   │   ├── resolve.py                # topic -> QID -> per-language articles
│   │   ├── fetch.py                  # pageviews + aggregate fetch, updates project state
│   │   ├── analyze.py                # trend + spike + placebo stats
│   │   ├── chart.py                  # renders chart image files
│   │   ├── report.py                 # renders the one-page PDF
│   │   ├── verify.py                 # checks rendered report numbers vs. computed JSON
│   │   └── project.py                # list/show/set/fork saved project state
│   ├── wikimedia/
│   │   ├── wikidata_client.py        # search, sitelinks
│   │   ├── mediawiki_client.py       # title normalization, redirect resolution
│   │   ├── aqs_client.py             # per-article + aggregate pageviews
│   │   └── http.py                   # shared httpx client: retries, backoff, User-Agent
│   ├── stats/
│   │   ├── trend.py                  # Theil-Sen + Mann-Kendall
│   │   ├── spikes.py                 # MAD-based spike detection
│   │   ├── normalize.py              # per-project aggregate-traffic normalization
│   │   └── placebo.py                # similar-popularity basket + comparison
│   ├── report/
│   │   ├── render.py                 # pluggable renderer interface (see §6)
│   │   ├── weasyprint_renderer.py
│   │   ├── fpdf2_renderer.py
│   │   └── template.html             # HTML/CSS layout used by the WeasyPrint path
│   ├── cache/
│   │   ├── store.py                  # cache key scheme, read/write, closed-month logic
│   │   └── paths.py                  # resolves the runtime data dir (see below)
│   ├── project_state.py              # load/save/mutate the project/session file
│   └── schemas.py                    # pydantic models for every JSON contract in §3
├── references/
│   ├── api-notes.md                  # Wikimedia/Wikidata API contracts (UNVERIFIED-LIVE until Milestone 0)
│   ├── stats-methods.md              # Theil-Sen/MK/MAD/placebo rationale (§5, expanded)
│   ├── caching.md                    # cache key/versioning/invalidation details (§4, expanded)
│   ├── report-template.md            # one-page PDF layout spec (§6, expanded)
│   ├── error-catalog.md              # every known failure mode -> agent-facing message (§7)
│   └── examples.md                   # worked transcripts for the 3 TASK.md example queries
├── assets/
│   └── fonts/                        # bundled Cyrillic-capable font, if the default lacks glyphs (Ukrainian example)
├── tests/
│   ├── cassettes/                    # recorded HTTP fixtures — first ones come from Milestone 0's live session
│   ├── test_resolve.py
│   ├── test_fetch_and_cache.py
│   ├── test_trend_stats.py
│   ├── test_placebo.py
│   ├── test_report_and_verify.py
│   └── test_cli_contracts.py         # asserts JSON shape against schemas.py, catches drift
└── evals/
    └── scenarios/                    # the 3 TASK.md example queries as Haiku eval prompts
```

### Runtime writable state

The skill directory is packaged/installed content — it should not be where
cache growth or session-state mutation silently happens (no assumption it's
even writable, and it shouldn't accumulate untracked state under what may be
a synced/versioned location). Three things need to be writable at runtime:
the HTTP/derived cache, project/session state, and rendered charts/PDFs.
None of these live inside `curiosity-radar/`.

Resolution order for the runtime data root, first one that's set/writable
wins:
1. `--data-dir <path>` flag (every command accepts it) or
   `CURIOSITY_RADAR_DATA_DIR` env var — lets the invoking agent pin a
   consistent directory across a whole conversation.
2. `$XDG_DATA_HOME/curiosity-radar` (falling back to
   `~/.local/share/curiosity-radar` per the XDG base-directory spec).
3. `./.curiosity-radar/` under the current working directory, as a
   last-resort fallback if neither of the above is set/writable.

`SKILL.md` instructs the agent to pick and keep reusing one `--data-dir`
per conversation so follow-ups hit the same cache and project file rather
than starting cold.

```
<data-dir>/
├── projects/
│   └── <project-slug>.json                                     # one file per saved project (see §8)
├── cache/
│   ├── wikidata/                                                # QID + sitelink lookups, keyed by QID/topic
│   ├── raw/
│   │   └── <project>/<article-or-aggregate>/<granularity>/<YYYY-MM>.json   # one file per closed month, immutable
│   │   └── <project>/<article-or-aggregate>/<granularity>/current.json    # always-refetched partial period
│   └── derived/
│       └── <schema-version>/<project-slug>/<analysis-hash>.json # cached stats results (see §4)
├── charts/
│   └── <project-slug>/<chart-id>.png
├── reports/
│   └── <project-slug>_<date>.pdf
└── logs/                                                        # tracebacks/debug info; never printed to stdout
```

## 2. End-to-end data flow

1. A natural-language ask arrives at the agent. `SKILL.md`'s short body
   tells it: run `resolve` first and inspect `ambiguous`/`warnings`; if
   clean, run `fetch`, then `analyze`, then `chart`, then `report`, then
   `verify` before replying. Consult `references/*.md` only when a command
   errors or an output flag looks off (`ambiguous: true`,
   `sufficient_for_trend: false`, a `verify` failure).
2. **Resolve**: `resolve --topic "intermittent fasting" --languages pl,cs
   --save-as intermittent-fasting-pl-cs`. Agent reads only the compact JSON
   (QID, per-language titles, warnings) — never touches Wikidata's raw
   entity dump directly.
3. **Fetch**: `fetch --project intermittent-fasting-pl-cs --start ... --end
   ...`. Internally: resolve redirects per language if not already cached;
   for each closed month, check `cache/raw/...month.json` and skip the
   network entirely on a hit; fetch only the current partial month plus any
   genuinely missing closed months; zero-fill missing days; fetch the
   matching project-aggregate series for normalization. Agent sees only a
   coverage/counts summary — never a raw daily array (that would blow a
   cheap model's context for a 2-year multi-language pull).
4. **Analyze**: `analyze --project ...` reads exclusively from `cache/raw/`,
   applies any exclusions from project state (e.g. a dropped date range),
   normalizes by aggregate traffic, computes Theil-Sen/Mann-Kendall with and
   without MAD-flagged spikes, runs the placebo-basket comparison, writes a
   `cache/derived/` entry, and prints the compact per-language JSON in §3.
5. **Chart + report**: `chart` renders image files from that same derived
   JSON (returns paths + captions, never pixel data); `report` templates the
   one-page PDF from derived JSON + chart paths (every number template-
   filled, never freely written by the model); `verify` re-extracts every
   numeric claim from the rendered PDF and cross-checks it against the same
   derived JSON, closing the anti-hallucination loop.
6. **Agent's final answer** is prose the agent writes itself around the
   compact JSON numbers, plus a pointer to the verified PDF's path.

**Cheap follow-ups**, the reason project state exists at all:
- *"Add Slovak"* → `project set --add-language sk` → `fetch` (only Slovak
  has no cache entry, so only Slovak triggers network calls — Polish/Czech
  closed months are cache hits) → `analyze`/`chart`/`report`/`verify` rerun
  (cheap, local computation over already-fetched data).
- *"Drop 2024"* → `project set --exclude-date-range 2024-01-01:2024-12-31`
  → `analyze` only (pure local recomputation over cached raw data, zero
  network calls) → downstream steps as needed.
- *"What about German instead"* → effectively a new `resolve`/`fetch` for
  `de`; `project fork` lets the agent branch a new comparison without
  mutating the original saved project.

## 3. CLI commands

Every command is a subcommand of one console-script entry point, invoked as
`uv run curiosity-radar <subcommand> ...` so the pinned lockfile env is
always used. Contract, uniformly:
- Exactly one JSON object printed to stdout on success.
- On failure: `{"error": {"code": "...", "message": "...", "hint": "..."}}`
  to stdout, nonzero exit — **never** a raw Python traceback on stdout
  (tracebacks go to `<data-dir>/logs/`, for a human to inspect, not the
  agent). A command's output is either clean JSON or has an `error` key,
  never a mix of partial success and silent failure.
- Never echoes a raw time-series array back to the agent — only counts,
  coverage summaries, or already-digested statistics.
- Every JSON shape below is the single source of truth in
  `src/curiosity_radar/schemas.py` (pydantic models), so drift between this
  doc, the code, and `tests/test_cli_contracts.py` is caught automatically.

### 3.1 `resolve`
Turn a topic name (or explicit QID) into a resolved cluster: canonical QID,
per-language article titles post-redirect, optional related QIDs folded in
as a "topic cluster" (several articles counted as one topic).

Inputs: `--topic "<text>"` (required unless `--qid`), `--qid Q...`,
`--languages en,pl,cs,uk` (required), `--related-qids Q...,Q...` (optional),
`--save-as <project-slug>` (optional — creates/updates a project), `--data-dir`.

`Q_EXAMPLE` below is a placeholder, not a real Wikidata ID — Milestone 0
caught an earlier draft of this doc using a memorized, incorrect QID as a
worked example (it resolved to "Bibliography," not the intended topic; see
`curiosity-radar/references/api-notes.md`). `resolve` must always look QIDs
up live via `wbsearchentities`/`wbgetentities`; nothing in this codebase
hardcodes one.

```json
{
  "topic_query": "intermittent fasting",
  "resolved_qid": "Q_EXAMPLE",
  "candidates": [{"qid": "Q_EXAMPLE", "label": "intermittent fasting", "description": "...", "match_type": "label"}],
  "ambiguous": false,
  "cluster": {
    "primary_qid": "Q_EXAMPLE",
    "related_qids": [],
    "articles": {
      "pl": {"title": "Głodówka przerywana", "wiki": "pl.wikipedia", "redirect_from": null, "exists": true},
      "cs": {"title": "Přerušovaný půst", "wiki": "cs.wikipedia", "redirect_from": "Intermitentní půst", "exists": true},
      "uk": {"wiki": "uk.wikipedia", "exists": false, "reason": "no_sitelink"}
    }
  },
  "warnings": ["uk: no Wikidata sitelink for this QID"]
}
```
`candidates` has no numeric relevance score — real `wbsearchentities`
responses don't return one (confirmed in Milestone 0). Ambiguity is
conveyed by list order (server-ranked) plus `match_type` (`"label"` vs.
`"alias"`); an invented `score` field from an earlier draft has been
removed.

**Redirect aliases are tracked separately by AQS pageviews** — confirmed in
Milestone 0, a redirect title (e.g. `cs`'s `Intermitentní půst` above)
receives its own real, distinct traffic, separate from the canonical title
it points to. So when `redirect_from` is non-null for a language, `fetch`
(§3.2) fetches pageviews for **both** the canonical title and that redirect
alias and sums them into that language's series — otherwise readers who
land via the old/alternate title would be silently undercounted. This only
covers the one redirect `resolve` already discovered on the way to the
canonical title; enumerating *every* title that redirects to an article
(a full MediaWiki backlinks-of-redirects query) is out of scope for v1 and
called out in Limitations (§8).

### 3.2 `fetch`
Pull/update pageview + project-aggregate data for a saved project's current
article set and date range; updates the cache and the project's
`data_coverage`.

Inputs: `--project <slug>` (loads topic/languages/date-range/exclusions from
saved state; can also take `--topic/--languages/--start/--end` directly on
first use, implicitly creating the project), `--start`, `--end` (default:
last 730 days, clamped with a warning to AQS's actual earliest date — see
`references/api-notes.md`), `--granularity daily|monthly` (default daily),
`--data-dir`.

```json
{
  "project": "intermittent-fasting-pl-cs",
  "fetched": {"articles_fetched": 2, "redirect_aliases_fetched": 1, "days_requested": 730, "days_from_cache": 700, "days_freshly_fetched": 30, "http_requests_made": 4},
  "coverage": {
    "pl": {"wiki": "pl.wikipedia", "article": "Głodówka przerywana", "redirect_alias_included": null, "first_day": "2024-09-22", "last_day": "2026-09-21", "missing_days": 0, "zero_fill_days": 4},
    "cs": {"wiki": "cs.wikipedia", "article": "Přerušovaný půst", "redirect_alias_included": "Intermitentní půst", "first_day": "2024-09-22", "last_day": "2026-09-21", "missing_days": 0, "zero_fill_days": 1}
  },
  "warnings": []
}
```
`redirect_alias_included` records whether that language's series is the
canonical title alone (`null`) or canonical + one summed redirect alias
(the alias's title) — surfaced so `analyze`/the report's Assumptions box
can state plainly whether redirect traffic was folded in for that
language.
No raw daily arrays in stdout — those live only in `cache/raw/`.

### 3.3 `analyze`
Compute normalization, Theil-Sen/Mann-Kendall trend (with-spikes and
spikes-removed), MAD spike list, and placebo-basket comparison, entirely
from cached data; writes a derived-cache entry.

Inputs: `--project <slug>`, `--compare-languages` (default true — also
produces a cross-language ranking), `--placebo-basket-size` (default 20),
`--force-recompute` (bypass derived cache).

```json
{
  "project": "intermittent-fasting-pl-cs",
  "generated_at": "2026-09-22T00:00:00Z",
  "languages": {
    "pl": {
      "normalized_trend": {"theil_sen_slope_per_day": 0.00041, "mann_kendall": {"trend": "increasing", "p_value": 0.006, "tau": 0.21}, "confidence_label": "likely growing"},
      "trend_excluding_spikes": {"theil_sen_slope_per_day": 0.00038, "mann_kendall": {"trend": "increasing", "p_value": 0.011}, "confidence_label": "likely growing"},
      "spikes_detected": [{"date": "2025-01-04", "z_mad": 6.2, "share_of_total_views": 0.09}],
      "placebo": {"basket_size": 20, "basket_median_slope": 0.00003, "topic_slope_percentile_vs_basket": 94, "verdict": "trend exceeds wiki-wide background drift"},
      "data_quality": {"total_days": 730, "zero_view_days": 12, "sufficient_for_trend": true}
    },
    "cs": {"...": "analogous"}
  },
  "cross_language_ranking": [{"lang": "pl", "rank": 1, "reason": "stronger trend + passes placebo"}, {"lang": "cs", "rank": 2}]
}
```

### 3.4 `chart`
Render chart image files from the derived-stats cache only (never
recomputes stats). Returns file paths + one-line captions, not pixel data.

Inputs: `--project <slug>`, `--kinds trend,spike,cross-language` (default:
all applicable), `--data-dir`.

```json
{
  "project": "intermittent-fasting-pl-cs",
  "charts": [
    {"kind": "trend", "language": "pl", "path": "<data-dir>/charts/intermittent-fasting-pl-cs/trend_pl.png", "caption": "Normalized interest in 'intermittent fasting' on pl.wikipedia, spikes marked"},
    {"kind": "cross_language_bar", "path": "<data-dir>/charts/intermittent-fasting-pl-cs/cross_lang.png", "caption": "Relative trend strength across pl, cs"}
  ]
}
```

### 3.5 `report`
Render the one-page PDF from project state + derived stats + chart files,
via the template in §6. Every numeric string is filled by the template
engine from JSON — never typed by the model.

Inputs: `--project <slug>`, `--out <path.pdf>` (default under
`<data-dir>/reports/`), `--audience-note "<optional one-line framing>"`
(plain-text passthrough, never a numeric claim), `--engine
auto|weasyprint|fpdf2` (default `auto` — see §6).

```json
{
  "project": "intermittent-fasting-pl-cs",
  "pdf_path": "<data-dir>/reports/intermittent-fasting-pl-cs_2026-09-22.pdf",
  "engine_used": "weasyprint",
  "page_count": 1,
  "sections_rendered": ["summary", "trend_chart_pl", "trend_chart_cs", "confidence", "assumptions", "limitations"],
  "numeric_claims_count": 14
}
```

### 3.6 `verify`
Re-extract every number/percentage/date the report rendered and cross-check
each against the derived-stats JSON that produced it; fails loudly on any
mismatch (catches template bugs, a stale cache reused after `analyze`
reran, or a manual edit). This is what makes the anti-hallucination
guarantee real.

Inputs: `--project <slug>`, `--pdf <path>` (defaults to the path recorded in
project state from the last `report` run).

```json
{
  "project": "intermittent-fasting-pl-cs",
  "pdf_path": "<data-dir>/reports/intermittent-fasting-pl-cs_2026-09-22.pdf",
  "claims_checked": 14,
  "claims_matched": 14,
  "claims_mismatched": 0,
  "status": "verified",
  "mismatches": []
}
```
On mismatch: `"status": "failed_verification"` plus a `mismatches` list of
`{claim_text, expected, found_in_pdf}`. `SKILL.md` instructs the agent to
treat this as blocking — do not hand the PDF to the user until `verify`
passes; on failure, rerun `report` (never hand-edit the PDF).

### 3.7 `project`
Inspect/list/mutate saved project state without touching cache or
triggering fetch/analyze — the cheap lever behind every follow-up.

Subcommands: `project list`; `project show --project <slug>`; `project set
--project <slug> --add-language sk | --remove-language xx |
--exclude-date-range 2024-01-01:2024-12-31 | --set-date-range
2023-09-01:2026-09-21`; `project fork --project <slug> --as <new-slug>`
(clone assumptions to branch a comparison without mutating the original).

```json
{
  "project": "intermittent-fasting-pl-cs",
  "topic": {"qid": "Q_EXAMPLE", "query": "intermittent fasting"},
  "languages": ["pl", "cs"],
  "date_range": {"start": "2023-09-22", "end": "2026-09-21"},
  "exclusions": [],
  "last_fetch_at": "2026-09-22T00:00:00Z",
  "last_analyze_at": "2026-09-22T00:05:00Z",
  "stale": {"fetch_stale": false, "analyze_stale": false}
}
```
`set` mutations mark `analyze_stale: true` (and `fetch_stale: true` only
when languages/date-range widened beyond cached coverage), so `SKILL.md`
can tell the agent exactly which of `fetch`/`analyze`/`chart`/`report` it
actually needs to rerun rather than always running the full chain.

## 4. Caching strategy

**Cache key** for raw pageview data: `(project=<lang>.wikipedia,
article-title-post-redirect, granularity, calendar month)` — one JSON file
per closed month. Keying by month (not by arbitrary requested range) means
overlapping requests across projects/date-ranges/follow-ups naturally share
files instead of duplicating fetches. The project-aggregate series used for
normalization is cached the same way, under a reserved `_aggregate` article
slot per project.

**Closed vs. open month**: a month is "closed" once
`end_of_month(month) < today - grace_period` (2-day grace period as a
placeholder for AQS's data-settling lag — `[UNVERIFIED-LIVE]`, confirm exact
lag in Milestone 0). A closed month's cache file is written once and never
re-fetched or re-validated automatically — this covers the large majority
of "two years of history" cost. The current month (and, conservatively, the
prior month while inside the grace window) is always refetched on `fetch`,
overwriting `current.json` in place; no closed month is touched by this.

**Raw vs. derived cache split** (deliberate): `cache/derived/<schema-
version>/...` is keyed by a hash of `(project-slug, raw-cache-file-hashes-
used, exclusions, placebo-basket-seed, stats-code-version)`. Bumping
`schema-version` (a constant bumped whenever the Theil-Sen/Mann-Kendall/MAD/
placebo logic or thresholds change) invalidates only derived results, never
raw pageviews — a stats-methodology change never forces re-fetching from
Wikimedia, only re-running `analyze` against already-cached raw data.

**Invalidation, concretely:**
- Closed-month raw entry: never auto-invalidated; a manual
  `--force-refetch-month` escape hatch exists for the rare case Wikimedia
  backfills/corrects historical data.
- Open-month raw entry: refetched unconditionally on every `fetch`.
- Derived entry: invalidated whenever its hash key's inputs change (new
  exclusion, new stats-code version, changed underlying raw data).
- Pruning: deferred to v2. Pageview JSON per article-month is small (~30
  daily integers), so even dozens of projects stay in the tens of MB;
  documented as a size-cap config default (see Open Questions) rather than
  built as active eviction logic before real usage data justifies it.

## 5. Statistical methods

| Method | Why it fits this data | Key failure modes / assumptions | How it's surfaced |
|---|---|---|---|
| **Theil-Sen slope + Mann-Kendall** | Both nonparametric and robust to the heavy-tailed, spike-prone shape of pageview series. Theil-Sen's slope is the median of all pairwise slopes, so a handful of viral days can't dominate it the way an OLS fit's slope can; Mann-Kendall tests only monotonic trend, tolerating non-normal, heteroscedastic residuals that daily web traffic essentially always has. Plain OLS is the obvious alternative but isn't robust to a single viral spike, and its p-values assume normal/independent/homoscedastic residuals that don't hold here. | Mann-Kendall assumes independent observations; daily pageviews have weekly autocorrelation, which can inflate apparent significance — mitigated by deseasonalizing (dividing by a 7-day rolling median before running MK) or a seasonal-MK variant, documented in `references/stats-methods.md`. Neither method characterizes acceleration or cyclicality — acceptable here since the question is "growing or not," not curve-fitting. | Never a raw p-value as the headline. Mapped to a plain-language label (e.g. `p<0.01 & |tau|>0.3` → "strong evidence of growth"; `p<0.05` → "likely growing"; else → "no clear trend detected"), shown alongside (not instead of) the numeric p-value/tau. |
| **MAD-based spike detection** | Median Absolute Deviation is robust to the very outliers it detects — a mean/stdev-based z-score is contaminated by the spikes themselves (a huge spike inflates stdev, potentially masking itself and smaller spikes), while MAD's median-based center and scale barely move. Flag any day with `\|x - median\| / MAD > threshold` (3.5, with the standard 1.4826 scaling constant) as a spike, then rerun Theil-Sen/MK with those days masked. | Degrades when more than roughly half the series is itself "outlying" (a genuinely bursty-baseline topic) — in that regime, "spike-removed" trend may remove real signal; flagged via `data_quality.zero_view_days`/general low-baseline indicators rather than silently trusted. | Both trend numbers (with spikes / spikes excluded) shown side by side, not collapsed to one — this is both explicitly requested and the more honest framing for a founder deciding on build priorities. |
| **Normalization by project aggregate traffic** | Controls for wiki-wide confounds (overall readership growth, mobile-app adoption shifts, seasonal academic-calendar effects) that would otherwise masquerade as topic-specific trend. Dividing an article's daily views by that project's total daily `agent=user` views turns absolute counts into "share of wiki attention," comparable across a ~2-year window and across languages/wikis with very different baseline sizes (raw counts alone would mostly measure wiki size). | Aggregate normalization can itself have discontinuities (a Wikimedia bot-classification or mobile-counting methodology change) that look like an artificial level shift — because the same normalization applies to the placebo basket too, genuine wiki-wide artifacts should mostly wash out in the topic-vs-basket comparison. Whole-project aggregate (vs. a category-matched subset) is the simpler v1 default; flagged as a v2 candidate in Open Questions. | Stated plainly in the report's Assumptions box ("views shown as % of project-wide daily traffic, not raw counts") since this transformation is easy to misread as raw popularity. |
| **Placebo test** (basket of similar-popularity, presumably-unrelated articles from the same wiki) | Directly addresses the real risk that an apparent trend is wiki-wide drift or noise rather than topic-specific — a single-article trend test alone can't distinguish "this topic is rising" from "this wiki's traffic patterns shifted." Comparing the topic's normalized slope against the empirical distribution of slopes from a similar-popularity-tier basket gives a wiki-specific, popularity-tier-specific null distribution, more defensible than an assumed theoretical one. | Basket selection is the crux: too few articles gives a noisy percentile estimate; a poorly matched popularity tier invalidates the comparison; accidentally including thematically related articles (e.g. other diet/health articles for an "intermittent fasting" placebo) undermines the point. Default basket size 20–30, sampled within roughly ±1 order of magnitude of the topic's own average daily views, explicitly excluding the topic's Wikidata category tree. | Reported as a plain verdict plus percentile ("stronger than 94% of similarly-popular, unrelated articles on this wiki") rather than a raw z-score — the most persuasive, legible confidence signal for a non-technical founder, positioned as the headline confidence metric with Theil-Sen/MK detail available alongside. |

## 6. Report layout — one-page PDF

Target: renders reliably to exactly one physical page at a fixed size
(pick one of Letter/A4 and hardcode it — mixing invites overflow),
degrading gracefully (a visible data-quality note, never a silent omission)
when a language has a coverage warning.

Section order, top to bottom:
1. **Header** — topic name, QID, languages compared, date range, generation
   timestamp, project slug (traceability).
2. **Headline verdict** (1–2 sentences, template-filled from `analyze`'s
   `confidence_label`/`cross_language_ranking` — not free model prose, since
   this is exactly the kind of claim that must come from computed JSON).
3. **Trend chart(s)** — one small-multiple per language (or a single overlay
   if ≤3 languages), normalized share-of-traffic over time, spikes marked,
   with a caption noting both with/without-spike trend readings.
4. **Confidence panel** — compact per-language table: Mann-Kendall p/tau,
   spike-adjusted verdict, placebo percentile, data-quality flag.
5. **Cross-language ranking** (multi-language asks only) — small bar chart
   or ranked list answering "which language/audience to prioritize."
6. **Assumptions** — boxed, same visual weight as body text (never
   footnote-sized): normalization method, `agent=user` filter, date range
   actually used post-exclusions, placebo basket size, redirect resolution
   applied and whether a redirect alias's traffic was folded into the
   count for each language (per `fetch`'s `redirect_alias_included`).
7. **Limitations** — equally prominent: pageview data reflects Wikipedia
   readership only, not search demand or purchase intent; short/noisy
   series near AQS's start date are unreliable; topic-to-article mapping
   may be imperfect for ambiguous topics; normalized (not raw) counts are
   shown.
8. **Footer** — the `verify` command's PASS/FAIL stamp printed literally
   ("Numeric claims verified against source data: PASS"), so the
   anti-hallucination check is visibly attached to the artifact, not just
   asserted.

Cap languages compared at a sane default (4) with an explicit truncation
note if more were requested ("comparison truncated to top 4 by data
quality — full data via `project show`"); prefer small multiples over one
dense chart to keep the page count fixed at one.

**Rendering engine — pluggable, decided with the requester:** `report/
render.py` defines a small renderer interface with two real
implementations, `weasyprint_renderer.py` (HTML/CSS via `template.html`,
the best one-page layout control, but depends on system Cairo/Pango/
GDK-Pixbuf libraries not installable via `uv` alone) and `fpdf2_renderer.py`
(pure-Python, zero system dependencies, more manual/imperative layout code
to guarantee one page). `--engine auto` (the default) prefers WeasyPrint
when its native libraries import cleanly at runtime and falls back to
fpdf2 automatically otherwise; `report`'s output JSON always records
`engine_used` so this is never silent. Both implementations are real (not
one a stub) and both are covered by tests — this directly protects the
"reproducible env, Python + uv" hard constraint regardless of what the
eventual grading/eval machine has installed, without forcing a single
irreversible choice now.

## 7. Error handling

| Failure mode | Agent-facing behavior |
|---|---|
| Topic doesn't map to a clean QID | `{"error":{"code":"no_qid_match","message":"No Wikidata entity found for 'X'.","hint":"Try --qid with a specific Wikidata ID, or rephrase the topic more specifically."}}` |
| Ambiguous entity (multiple plausible QIDs) | Not a hard failure — `resolve` exits 0 with `"ambiguous": true` and a `candidates` list; `SKILL.md` tells the agent to ask the user to disambiguate rather than guessing. |
| Article doesn't exist in a requested language wiki | Not a hard failure — per-language `"exists": false, "reason": "no_sitelink"` in `resolve`'s output; downstream commands skip that language and note it in `warnings` rather than aborting the whole run. |
| Redirect chain / circular redirect | `{"error":{"code":"redirect_resolution_failed","message":"Could not resolve a stable title for 'X' on cs.wikipedia after 5 redirect hops.","hint":"Check the article manually; it may have been merged or deleted."}}` |
| Rate-limited / 429 | Bounded retry with exponential backoff + jitter (e.g. 3 attempts) transparently; if still failing: `{"error":{"code":"rate_limited","message":"Wikimedia API is rate-limiting this client.","hint":"Wait a minute and rerun fetch — already-cached months are unaffected."}}` |
| Empty / all-zero data | Not an error — `analyze` reports `"sufficient_for_trend": false, "reason": "all_zero_or_empty"` and a confidence label of "insufficient data" rather than fabricating a trend. |
| Insufficient date range for trend stats | Enforce a minimum (e.g. 60 days with nonzero variance) before running Theil-Sen/MK; below that, same `sufficient_for_trend: false` path with a specific hint ("need at least 60 days of history; current range has 14"). |
| Network failure (DNS, timeout, TLS) | `{"error":{"code":"network_error","message":"Could not reach Wikimedia APIs.","hint":"Check network/proxy connectivity; already-cached closed months are still usable via analyze without a fresh fetch."}}` — never a raw traceback on stdout; full tracebacks go to `<data-dir>/logs/`. |

General rule baked into `SKILL.md`: every command's JSON has a top-level
`error` key or none at all, so the agent's control flow is a single
`if "error" in result` check throughout.

## 8. Known limitations (surfaced in every report, not just this doc)

- Pageview data reflects Wikipedia readership only — not search demand,
  app-store demand, or purchase intent; it's a proxy signal for "where to
  look next," not a market-sizing tool.
- Short or noisy series near AQS's actual history start date
  (`[UNVERIFIED-LIVE]`, believed ~2015-07) are unreliable; `fetch` clamps
  over-long requested ranges and warns rather than silently truncating.
- Topic-to-article mapping can be imperfect for ambiguous topics or topics
  without a clean 1:1 Wikidata sitelink per language.
- All comparisons are normalized (share of project traffic), not raw view
  counts — stated explicitly since it's easy to misread as raw popularity.
- Only one redirect alias per language (the one found while resolving to
  the canonical title) is folded into view counts — confirmed via
  Milestone 0 that AQS tracks redirect titles as separate traffic streams.
  Other, unrelated titles that also redirect to the same article are not
  discovered or included, so totals can still be a modest undercount.

## 9. Open Questions & Risks (for the requester)

1. **Placebo basket size / minimum-eligible threshold.** Default 20–30
   articles, sampled within ~±1 order of magnitude of the topic's own
   average daily views, excluding its Wikidata category tree. Open: is
   there a principled minimum count below which the placebo verdict
   shouldn't be reported at all (e.g. refuse below 10 eligible comparison
   articles for a very niche, low-traffic topic)?
2. **No Wikidata sitelink for a requested language.** Current design skips
   that language with a warning (graceful degradation). An alternative —
   falling back to a cross-wiki title search without a formal sitelink — is
   weaker (no guarantee of "same topic") and **not** recommended for v1;
   flagged rather than silently attempted.
3. **AQS true history start date and over-long-range clamping.**
   `[UNVERIFIED-LIVE]` — confirm in Milestone 0, then clamp/warn rather than
   silently return less data than requested.
4. **Whole-project vs. category-matched normalization denominator.**
   Whole-project aggregate is the simpler, chosen v1 default; a
   category-matched denominator (e.g. only other health articles) would
   better isolate topic-specific trend from category-wide attention shifts
   but requires a fair category-matching method — flagged as a v2
   candidate, not a v1 blocker.
5. **Cache pruning policy.** Deferred to v2 given how small this data
   actually is; a documented size-cap default should exist so it's not
   silently unbounded forever, but active eviction logic isn't a launch
   requirement.
6. **Project-state file format and slug scheme.** JSON chosen (single
   serialization format end-to-end: JSON commands in, JSON state, JSON
   out). Slugs should be deterministic from topic + sorted language codes
   so re-running `resolve --save-as` idempotently updates rather than
   duplicating a project — confirm this scheme reads well for end users
   who might reference a slug directly.
7. **Non-Latin-script topics.** Recommended supported from day one — the
   Ukrainian TASK.md example requires it, and Wikidata search handles
   Cyrillic natively. The PDF path needs a bundled Cyrillic-capable font
   under `assets/fonts/` if the default WeasyPrint/system font lacks the
   glyphs — a concrete check item for the report milestone, not a v2 nicety.
8. **Milestone 0 as a hard dependency — and a structural gap, not just this
   session's.** Confirmed (2026-09-22) that this account's *only* available
   Claude Code on-the-web environment (`Default`) blocks all Wikimedia/
   Wikidata domains, in two independent cloud sessions — this isn't a
   one-off fluke of the current conversation, it's this account's entire
   cloud setup. Milestone 0 is being completed via a manual handoff instead
   (a verification script run on the requester's own machine, its output
   pasted back to turn into `tests/cassettes/` fixtures). That workaround is
   viable exactly once, cheaply, precisely because AQS data for closed
   months is immutable and the resulting cassettes are reused indefinitely
   by every later milestone — but it doesn't scale to "re-verify whenever
   we're unsure," and it means no cloud session in this account can
   independently fetch *new* live data (e.g. re-running Milestone 0's
   checklist after a schema/behavior change, or the day this skill needs a
   real non-cassette smoke test). Worth deciding before that need arises:
   (a) ask whoever administers this Claude Code account/org to allow
   egress to `wikimedia.org`/`*.wikipedia.org`/`*.wikidata.org`/
   `api.wikimedia.org` for the `Default` environment (the durable fix), or
   (b) accept manual paste-back as a standing, documented process (not just
   a one-time bootstrap) and design for it explicitly — e.g. keep this
   verification script under version control (`curiosity-radar/references/
   verify_live_api.sh` or similar) rather than a scratch file, so re-running
   it later is a known, repeatable step rather than reconstructed from
   scratch.
9. **PDF engine auto-detection edge cases.** `--engine auto`'s
   "importable at runtime" check for WeasyPrint needs to also probe that
   its *system* libraries (not just the Python package) actually load
   without erroring — a Python-level import can succeed while a
   Cairo/Pango call still fails at render time on some platforms; the
   fallback logic should catch that render-time failure too, not just a
   missing-import case, and still fall back to fpdf2 rather than surfacing
   a raw error to the agent.
