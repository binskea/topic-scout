# PLAN — `curiosity-radar` milestones

Ordered, small, independently testable milestones from an empty skill
directory to a working, evaluated Agent Skill. Each has a concrete
definition of done. See `SPEC.md` for the target architecture and
`CLAUDE.md` for conventions each milestone should already follow.

## Milestone 0 — Live API verification (blocking) — ✅ DONE 2026-09-22

**Why it's first and blocking:** this dev session's network egress proxy
blocks all `wikimedia.org`/`*.wikipedia.org`/`*.wikidata.org` domains
outright, so every endpoint detail in
`curiosity-radar/references/api-notes.md` is currently drawn from
documented/memorized knowledge, not a real request, and is tagged
`[UNVERIFIED-LIVE]`. Milestones 2–3 (resolve/fetch) must not be treated as
finished — even if their code "looks like it works" against assumed shapes
— until this runs.

**Confirmed 2026-09-22: this is not fixable from within this account's
cloud environments.** Both this dev session and a second, independently
launched Claude Code on-the-web session (same account, its only available
environment) hit the identical proxy block. Real verification is being
done via a **manual handoff**: `curiosity-radar/references/
verify_live_api.sh` is run by the requester on their own machine (normal
internet access), and its output is pasted back to build the cassette
fixtures below. This works cleanly as a one-time bootstrap (AQS data for
closed months is immutable, so the resulting cassettes are reused
indefinitely), but see `SPEC.md` §9 item 8 for why it isn't a scalable
long-term answer — decide on a durable fix (org egress allowlist for this
environment, most likely) before the day this skill needs a fresh, real
API check rather than a replayed cassette.

**Definition of done — met:**
- ✅ `verify_live_api.sh` run by the requester on their own machine; all 10
  checklist items executed, output pasted back.
- ✅ Every raw response saved as a `tests/cassettes/milestone0/` fixture
  (see that directory's `README.md` for the request/result mapping) — the
  first real fixtures the rest of the test suite builds on.
- ✅ `references/api-notes.md` updated from `[UNVERIFIED-LIVE]` to
  `[CONFIRMED 2026-09-22]` throughout, with entries corrected where reality
  differed from the original assumption.

**Two findings materially changed the design** (both folded into `SPEC.md`
already — see its 2026-09-22 update note near the top):
1. AQS pageviews tracks a redirect title's traffic separately from its
   canonical target (confirmed with a real redirect: `USA` → `United
   States`, both showing distinct, nonzero views). `fetch` (Milestone 3)
   must now sum canonical + one known redirect alias per language, not
   just fetch the canonical title.
2. An earlier draft's worked examples hardcoded a Wikidata QID
   (`Q1631107`) as "intermittent fasting" from memory — it's actually
   "Bibliography." Every doc now uses an explicit `Q_EXAMPLE` placeholder
   instead, and this is exactly the kind of mistake `resolve` must never
   make at runtime (always resolve QIDs live).

**Four items remain genuinely unconfirmed but are non-blocking** (see
`api-notes.md`'s status table for detail — revisit only if the
corresponding Milestone-4/9 code behaves unexpectedly against real data):
true zero-view-day omission (never observed in this batch), double-redirect
hop resolution, the exact AQS history start date (only "before 2015-07-ish"
confirmed, not the precise boundary), and the true rate-limit ceiling
(5 concurrent requests all succeeded; higher concurrency untested).

**Unresolved structural risk, carried forward (see `SPEC.md` §9 item 8):**
this account's only Claude Code on-the-web environment cannot reach these
domains at all, so this manual-handoff process will be needed again for
any future live re-verification — decide on a durable fix (most likely an
org egress allowlist) before that need arises.

## Milestone 1 — Project skeleton

**Definition of done:** `curiosity-radar/pyproject.toml` + `uv.lock`
provisioned (`uv sync` succeeds from a clean checkout); `SKILL.md` stub
exists with correct Agent Skills frontmatter; every subcommand in `SPEC.md`
§3 is wired into the CLI and returns well-formed (even if empty/stubbed)
JSON matching its `schemas.py` model — `uv run curiosity-radar --help` and
each `<subcommand> --help` work.

## Milestone 2 — Wikidata/MediaWiki `resolve`, cassette-backed — ✅ DONE 2026-09-23

**Definition of done:** `resolve` implemented against Milestone 0's
cassettes covering: happy path (clean single QID, all languages resolve),
ambiguous entity, a language with no sitelink, and a redirect-chain case.
Output matches `SPEC.md` §3.1 exactly. Unit tests green for all four cases.

**Met:** `wikimedia/http.py` (shared async client, retry/backoff on
429/5xx), `wikimedia/wikidata_client.py` (`wbsearchentities`/
`wbgetentities`), and `wikimedia/mediawiki_client.py` (per-language
redirect resolution, defensively bounded at `MAX_REDIRECT_HOPS=5` per
`SPEC.md` §7's `redirect_resolution_failed`) back a fully live `resolve`.
`tests/test_resolve.py` covers all four required cases plus the
`no_qid_match`/`redirect_resolution_failed` error paths and an explicit
`--qid` bypass, reusing Milestone 0's real cassette bytes verbatim where
the shape fits (ambiguous search, sitelinks-with-gaps, single-redirect) and
constructing shape-faithful synthetic fixtures only for combinations that
session didn't happen to produce (a clean unambiguous search, sitelinks
for this repo's own test languages, a genuine double-hop redirect chain —
per `api-notes.md` §3, only a single hop was ever confirmed live).
`tests/conftest.py` adds a project-wide autouse fake-network fixture so
every other test file's incidental `resolve` calls (bootstrapping a
project for `analyze`/`chart`/etc.) stay network-free too, per `CLAUDE.md`'s
testing rules.

## Milestone 3 — AQS `fetch` + raw cache — ✅ DONE 2026-09-23

**Definition of done:** `fetch` implemented against cassettes: closed-month
files are read from cache without a network call; the current/open month
is always refetched; missing days are zero-filled per the confirmed (post-
Milestone-0) behavior; the project-aggregate series is fetched and cached
alongside per-article data. A test explicitly asserts "second `fetch` call
for an already-closed range makes zero HTTP requests."

**Met:** `cache/store.py` implements the raw cache exactly per `SPEC.md`
§4 — keyed by `(wiki, article-title-post-redirect, granularity, calendar
month)`, **not** by our own saved-project slug, so two saved projects
referencing the same wiki article transparently share one cached file.
Closed months are fetched once and cached in full (so a later, differently
-bounded request for the same month is still a cache hit); the open/
current month is always refetched into `current.json`. `wikimedia/
aqs_client.py` adds per-article/aggregate AQS calls, treating a 404
("no data for this range," confirmed shape from Milestone 0's
`10_earliest_date_probe_404.json`) as zero-fillable rather than a hard
failure. `resolve`'s per-language `ArticleInfo` (title + `redirect_from`)
is now persisted on `ProjectState` so `fetch` knows, without re-resolving,
which title(s) to pull per language — including fetching and summing a
redirect alias's traffic into its canonical article's series, per
Milestone 0's redirect-tracking finding. `fetch` also proactively clamps
an over-long requested start to `AQS_EARLIEST_DATE` (`[UNVERIFIED-LIVE]`
exact boundary, per `api-notes.md`) with a warning, surfaced via
`coverage[...].missing_days`.

`tests/test_fetch_and_cache.py` covers all four required behaviors —
including the exact "second fetch of an already-closed range makes zero
HTTP requests" assertion — reusing Milestone 0's real cassette bytes
(`01_per_article_ordinary.json`, `03_per_article_redirect_title.json`,
`04_aggregate.json`) for the shapes that fit, and a synthetic gap for the
zero-fill case (never observed live, per `api-notes.md` §1.1's residual
item). `tests/conftest.py`'s safety net now also fakes AQS endpoints so
`test_cli_contracts.py`'s incidental `fetch` calls stay off the live
network too.

## Milestone 4 — Stats core — ✅ DONE 2026-09-23

**Definition of done:** `stats/trend.py` (Theil-Sen + Mann-Kendall),
`stats/spikes.py` (MAD-based detection), `stats/normalize.py` (aggregate-
traffic normalization) implemented and unit-tested against synthetic series
(flat, steadily rising, spiky, all-zero, too-short-for-trend) — no network
fixture involved. Confidence-label thresholds from `SPEC.md` §5 match the
code exactly.

**Met:** `stats/trend.py` builds directly on `scipy.stats.theilslopes`/
`kendalltau` per `CLAUDE.md` (Kendall's tau of day-index vs. views *is*
the Mann-Kendall statistic); `check_sufficiency` gates the
all-zero/too-short cases from `SPEC.md` §7 before a trend is ever computed,
and `compute_trend` accepts an optional explicit x-coordinate array so a
spike-masked series keeps its slope in true "per calendar day" units
rather than "per remaining sample." Confidence labels
(`strong evidence of growth/decline` / `likely growing/declining` /
`no clear trend detected`) are asserted against SPEC.md §5's exact
thresholds (`p<0.01 & |tau|>0.3`, `p<0.05`) in
`tests/test_trend_stats.py::test_confidence_label_thresholds_match_spec_exactly`.
`stats/spikes.py` implements MAD detection (3.5× threshold, 1.4826 scaling
constant) plus an `exclude_indices` helper for the "spikes masked" trend
read. `stats/normalize.py` is a small, pure aggregate-share divide.

One real bug surfaced and was fixed along the way: a *perfectly* constant
synthetic baseline collapses MAD to exactly 0 (more than half the series
ties the median), which is an artifact of idealized test data — real daily
pageviews are essentially never bit-for-bit identical across dozens of
days — so the fix was to give the test fixtures small realistic jitter
rather than complicate the detector with an ad hoc epsilon floor.

`tests/test_trend_stats.py`, `tests/test_spikes.py`, and
`tests/test_normalize.py` cover all required synthetic scenarios; none of
this milestone touches the network or `cache/`.

## Milestone 5 — Placebo test — ✅ DONE 2026-09-23

**Definition of done:** `stats/placebo.py` implemented: basket selection
(similar-popularity tier, category-tree exclusion) and percentile-verdict
computation. Tested against a synthetic "wiki" with a known background-
drift rate vs. a synthetically trending topic, confirming the verdict
correctly distinguishes the two.

**Met, and one scope boundary worth flagging explicitly:** `select_basket`
and `compute_verdict` are the pure statistical core only — `select_basket`
filters/samples a candidate pool the caller already supplies (each with an
average-views figure and Wikidata category-QID membership), and
`compute_verdict` percentile-ranks a topic's slope against a list of
already-computed basket slopes (via `scipy.stats.percentileofscore`, no
hand-rolled percentile math). Actually *sourcing* that candidate pool live
from Wikimedia is **not** built here — `SPEC.md` §9 item 1 leaves the exact
sourcing mechanism as an open question, and `references/api-notes.md` §1.3
already notes the AQS "top articles" endpoint isn't wired into v1 for
exactly this reason. Wiring a live source is `analyze`'s job (Milestone 6)
or later — this milestone only had to prove the selection/verdict math
itself is correct against synthetic data, which it now is.

`SPEC.md` §9 item 1 ("is there a principled minimum count below which the
placebo verdict shouldn't be reported at all") is resolved here: yes, 10
— `compute_verdict` refuses a percentile below 10 basket members rather
than fabricating one from too few, returning an explicit
"insufficient comparison data" verdict instead. Verdict tiers (`>=90th
percentile` -> "exceeds," `>=50th` -> "stronger than typical," else ->
"within normal" background drift) aren't spelled out numerically in
`SPEC.md` §5 the way `trend.py`'s confidence-label thresholds are — only
one example verdict string is given — so these cutoffs are this
implementation's own reasonable choice, documented here rather than
presented as a frozen spec number.

`tests/test_placebo.py` covers basket filtering (popularity tier + category
exclusion + sampling), the median/percentile math with hand-computed
expected values, and the two required synthetic-wiki cases side by side: a
topic slope far above a background-drift basket (verdict: exceeds) vs. a
topic slope drawn from that same background-drift distribution (verdict:
does not claim exceedance) — confirming the verdict actually distinguishes
real trend from wiki-wide noise.

## Milestone 6 — `analyze` command + derived cache

**Definition of done:** Milestones 4–5 wired together behind `analyze`,
producing the exact compact per-language JSON from `SPEC.md` §3.3. Derived-
cache versioning verified directly: bumping the stats `schema-version`
constant triggers recomputation without triggering any raw refetch (assert
zero HTTP calls, one new `cache/derived/` file).

## Milestone 7 — Charts

**Definition of done:** `chart` renders real PNG files from `analyze`
output for a cassette-backed project, matching `SPEC.md` §3.4's JSON shape
(paths + captions). Visually spot-checked once by hand, then covered going
forward by file-existence/non-trivial-size assertions in tests.

## Milestone 8 — Report + verify

**Definition of done:** `report` renders the one-page PDF via the pluggable
renderer (`--engine auto` picks WeasyPrint when its native libraries import
*and* render successfully, falls back to fpdf2 otherwise, always reports
`engine_used`); both renderer implementations produce a real one-page PDF
from the same derived JSON + chart paths, not just one working path.
`verify` implemented and proven against a deliberately-broken template case
(a number in the template made to disagree with the derived JSON) —
`verify` must return `status: "failed_verification"` with a populated
`mismatches` list on that case, not just pass on the happy path.

## Milestone 9 — Project state + cheap follow-up flows

**Definition of done:** `project list/show/set/fork` implemented per
`SPEC.md` §3.7. Tests simulate the two named follow-up flows end to end and
assert the *network* behavior, not just the output shape: "add Slovak"
triggers HTTP calls only for the newly-added language (existing languages'
closed months stay cache hits); "drop 2024" triggers zero HTTP calls
(pure local recomputation via `analyze` over already-cached raw data).

## Milestone 10 — `SKILL.md` finalization + references

**Definition of done:** `SKILL.md` trimmed to a short body (<500 lines)
covering triggers, the command sequence (`resolve` → `fetch` → `analyze` →
`chart` → `report` → `verify`), and pointers into `references/*.md` for
anything beyond the basics. `references/error-catalog.md`,
`references/stats-methods.md`, `references/caching.md`,
`references/report-template.md` fully written (expanding `SPEC.md` §5–7 into
skill-facing detail) and cross-checked against the actual implemented
behavior, not just the original design.

## Milestone 11 — Eval milestone

**Definition of done:** the 3 `TASK.md` example queries run end to end,
with the skill installed, on Claude Haiku 4.5 (or a cheap/free OpenRouter
equivalent if Haiku access isn't available in the eval environment), using
cassette-backed data (no live Wikimedia calls needed):
1. Compare intermittent-fasting interest growth between pl.wikipedia and
   cs.wikipedia over the last two years.
2. Assess whether interest in astronomy is growing on uk.wikipedia, and how
   trustworthy that trend is, for a course-addition decision.
3. Compare interest in learning English across several language editions
   and recommend which audiences to research next.

Full transcripts and the generated PDFs are saved under `evals/results/`.
Each scenario is reviewed by a human against three criteria: (a) the model
follows the intended command sequence without needing hand-holding beyond
what `SKILL.md` provides, (b) the final report's numeric claims pass
`verify`, (c) a same-session follow-up tweak (e.g. "also check Slovak," "
drop the most recent spike") stays cheap (no unnecessary refetching) and
produces a coherent updated answer.

## Milestone 12 — Packaging pass

**Definition of done:** a fresh `uv sync` from a clean checkout of
`curiosity-radar/` alone (no dependence on anything elsewhere in this repo)
succeeds and the full command chain runs against cassette data with no
manual setup steps beyond `uv sync`. `SPEC.md`/`CLAUDE.md`/`PLAN.md`
updated to reflect the as-built system where it diverged from this plan.
Every item in `SPEC.md` §9's Open Questions & Risks list is either resolved
(with the resolution noted) or explicitly deferred with a stated reason —
none left silently unaddressed.
