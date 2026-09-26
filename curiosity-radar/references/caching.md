# Caching — implementation detail

Expands `SPEC.md` §4 with exact key schemes, invalidation triggers, and
staleness semantics from `src/curiosity_radar/cache/store.py`,
`cache/paths.py`, `project_state.py`, and `commands/analyze.py`. Useful
whenever a follow-up ask's cost looks wrong (an "add Slovak" that seems to
refetch everything, an "add a year of history" that returns instantly when
it shouldn't) — read this before assuming a bug.

## Runtime data root

Resolution order (`cache/paths.py::resolve_data_dir`), first
set-and-writable wins:
1. `--data-dir <path>` (every command accepts it) or
   `CURIOSITY_RADAR_DATA_DIR`.
2. `$XDG_DATA_HOME/curiosity-radar` (falling back to
   `~/.local/share/curiosity-radar`).
3. `./.curiosity-radar/` under the current working directory.

Each candidate is probed with an actual `mkdir` + touch/unlink before being
accepted — a set-but-unwritable `--data-dir` falls through to the next
candidate rather than failing outright. Pick one per conversation and keep
passing it; nothing here auto-discovers a prior session's directory.

## Raw pageview cache (`cache/raw/`)

**Key**: `(wiki, article-title-post-redirect, granularity, calendar
month)` — directory path
`cache/raw/<url-encoded wiki>/<url-encoded article-or-_aggregate>/<granularity>/`,
one file per month: `<YYYY-MM>.json` for a **closed** month, `current.json`
for the **open** one (always the same filename, overwritten in place, not
a moving per-month name). Deliberately **not** keyed by our own project
slug — two saved projects referencing the same wiki article (e.g. two
different-date-range projects both tracking `en.wikipedia`/`Astronomy`)
transparently share one cache file. The project-aggregate series (used for
normalization) reuses the exact same scheme under the reserved article
slot `_aggregate` (`store.AGGREGATE_SLOT`).

**Closed vs. open**: `is_closed_month(year_month, today)` = `(today -
end_of_month(year_month)).days > GRACE_PERIOD_DAYS` (**2**, still
`[UNVERIFIED-LIVE]` — a placeholder for AQS's real data-settling lag;
`api-notes.md` couldn't pin this down live in the Milestone 0 session).

- **Closed month, cache hit**: read straight from `<YYYY-MM>.json`, zero
  network calls.
- **Closed month, cache miss**: fetched **in full** for the whole calendar
  month (not just the requested sub-range) and written once — so a later,
  differently-bounded request touching the same month is a cache hit even
  if its exact date range never lined up with an earlier one.
- **Open month**: always refetched into `current.json` on every `fetch`
  call that touches it, unconditionally — this is deliberate (data for the
  current month is still settling) and shows up as
  `fetch`'s `days_freshly_fetched` even on a run where every other month
  was a cache hit.
- **Manual override**: `--force-refetch-month` exists as an escape hatch
  for the rare case Wikimedia backfills/corrects historical data (a closed
  month is otherwise *never* auto-invalidated).

**Zero-fill**: `zero_fill()` turns AQS's items-only-for-days-with-data
response into a complete daily series over the requested range, filling
any day AQS omitted with `views: 0` — applied once, at write time, so a
cached month file always has one entry per calendar day.

**`analyze`'s read path is separate from `fetch`'s write path**:
`store.read_cached_range` (used by `analyze`, never by `fetch`) tries
*both* the closed-month filename and `current.json` for each requested
month — a month can close between one `fetch` and a later `analyze` without
an intervening `fetch` ever "promoting" `current.json` to `<YYYY-MM>.json`.
A month with no cache file at all (never fetched) is simply absent from the
result, not zero-filled — don't confuse "never fetched" with "fetched and
found empty."

## Placebo-basket candidate cache (`cache/basket/<wiki>.json`)

**Key**: wiki only (not project/topic) — directory path
`cache/basket/<url-encoded wiki>.json`, one file per wiki, holding the
candidate titles + Wikidata category QIDs `fetch` last sourced for it
(Milestone 13, `SPEC.md` §9 item 1). Written by `fetch`
(`cache/basket.py::save`), read by `analyze` (`commands/analyze.py::
_load_basket_candidates`) — `analyze` never sources or refreshes this
cache itself, only reads it, same as raw pageview data.

**Refresh cadence**: at most once per calendar month per wiki
(`cache/basket.py::needs_refresh` compares the file's `sourced_month`
against the current one) — a Wikidata lookup per candidate isn't cheap
enough to repeat on every `fetch`, and which articles are currently
popular doesn't meaningfully change day to day. `fetch.BASKET_POOL_SIZE`
(**20** by default, `0` disables sourcing entirely) controls how many
candidates are sourced when a refresh does happen.

**Not itself a pageview cache**: this file holds only *which* titles are
candidates and their category QIDs. Each candidate's actual daily pageview
series is fetched and cached the ordinary way, under `cache/raw/` exactly
like any project article (same closed/open-month rules above) — a
candidate is just another cached article, sharing the same "overlapping
requests naturally share files" cache scheme.

## Derived-stats cache (`cache/derived/<schema-version>/<project-slug>/<hash>.json`)

Written by `analyze`, one file per distinct `(project, exclusions,
date-range, placebo-basket-size, category-qids, raw-data-actually-used,
stats-code-version)` combination. The hash (`analyze._compute_analysis_hash`)
covers:
- the project slug,
- **every raw cache file's own content hash** that this analysis actually
  read (per-article + redirect-alias + aggregate, per resolved language,
  **plus each wiki's `cache/basket/` file and every one of its candidates'
  raw cache files** — `_collect_raw_file_hashes`, SHA-256 of each
  `cache/raw/.../*.json` file under the relevant directories), so a basket
  candidate's data changing (a fresh sourcing pass, a new day fetched)
  invalidates the derived cache exactly like the topic's own data changing
  would,
- sorted exclusion ranges,
- the project's date range,
- `placebo_basket_size`,
- the project's `category_qids` (Milestone 13 — a different topic
  category set changes which basket candidates get excluded),
- `SCHEMA_VERSION` (a constant in `analyze.py`, bumped whenever the
  Theil-Sen/Mann-Kendall/MAD/placebo *logic or thresholds* change).

**Consequence, directly testable and tested**
(`test_analyze.py`'s schema-version-bump case): bumping `SCHEMA_VERSION`
invalidates only derived results — a fresh `cache/derived/<new-version>/`
file appears, the old version's files are untouched, and **zero raw
refetch happens**, since the raw cache lives under a completely separate
key scheme with no dependency on `SCHEMA_VERSION` at all. A stats-
methodology change never costs a re-fetch from Wikimedia.

`analyze --force-recompute` bypasses the derived-cache read (still writes
a fresh entry under the same hash-derived path) without touching raw data
either.

## Project state (`<data-dir>/projects/<slug>.json`) and staleness flags

Not really a "cache" in the invalidation sense — it's the durable record
of what a project *is* (topic/QID, languages, resolved per-language
`ArticleInfo`, date range, exclusions) plus two booleans that exist purely
to tell an agent which of `fetch`/`analyze` it actually still needs to run
after a `project set` mutation (`project_cmd.set_project`):

| Mutation | `fetch_stale` | `analyze_stale` |
|---|---|---|
| `--add-language` | → `true` | → `true` |
| `--remove-language` | unchanged | → `true` |
| `--exclude-date-range` | unchanged | → `true` |
| `--set-date-range` | → `true` | → `true` |

`fetch` and `analyze` themselves clear the corresponding flag (and
`analyze` sets `fetch_stale`'s sibling `analyze_stale = true` right back on
every `fetch`, since new raw data always needs a fresh `analyze`). Nothing
currently *enforces* these flags — no command refuses to run against a
stale project — they're advisory, read via `project show`, so the agent
can skip a step it knows is unnecessary (SPEC.md §2's whole point: "drop
2024" only needs `analyze`, not a full `fetch`→`analyze`→`chart`→`report`
chain) rather than always re-running the full sequence defensively.

**Why `--add-language` doesn't itself trigger any network call**: SPEC.md
§3.7 is explicit that `project` "inspect[s]/mutate[s] saved project state
without touching cache or triggering fetch/analyze" — it only appends the
language and flips the two flags above. The newly-added language has no
resolved `ArticleInfo` yet at that point. `fetch` closes that gap itself:
on every run, it diffs `state.languages` against `state.articles` and
resolves (live, reusing the project's already-known QID — no redundant
`wbsearchentities` search) exactly the languages missing an entry, before
touching AQS at all. Already-resolved languages are never touched by this
step, which is what actually makes "add Slovak → fetch" cheap: the
resolve-the-gap step is genuinely new network I/O (unavoidable — Slovak
was never looked up before), and the subsequent per-language AQS loop
finds Polish/Czech's closed months already cached. Verified end-to-end,
network-call-by-network-call, in
`tests/test_project_followups.py::test_add_language_only_fetches_the_new_language`.
The "drop 2024" flow needs no such gap-filling: `analyze` reads exclusively
from `cache/raw/` and never constructs an HTTP client at all, so it was
already pure local recomputation before Milestone 9 — proven (not just
assumed) in
`test_project_followups.py::test_drop_date_range_is_pure_local_recomputation_with_zero_http_calls`,
which patches every network entry point to raise if called.

## Pruning

Deferred to v2 (`SPEC.md` §9 item 5) — no active eviction logic exists.
Pageview JSON per article-month is small (~30 daily integers), so even
dozens of projects stay in the tens of MB; a documented size-cap default
is still an open item, not a launch blocker.
