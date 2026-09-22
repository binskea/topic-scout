# Wikimedia / Wikidata API notes

**Status: UNVERIFIED-LIVE.** This session's network egress proxy blocks all
`wikimedia.org` / `*.wikipedia.org` / `*.wikidata.org` / `api.wikimedia.org`
domains outright (confirmed via both `curl` and a fetch tool — proxy
`403`/`EGRESS_BLOCKED`, an organization network policy, not a code problem).
Every endpoint shape, quirk, and limit below is drawn from documented/
memorized knowledge of these APIs, **not from a live request made in this
session**. Every claim is tagged `[UNVERIFIED-LIVE]`. `PLAN.md` Milestone 0
is a hard blocking step: run the curl checklist at the bottom of this file in
an unrestricted environment, replace each tag with `[CONFIRMED <date>]` (or
correct the entry), and save the raw responses as `tests/cassettes/`
fixtures before the fetch/cache code (Milestones 2–3) is trusted.

## 1. Wikimedia Analytics Query Service (AQS) — pageviews

Base: `https://wikimedia.org/api/rest_v1/metrics/pageviews/`

All AQS calls require a descriptive `User-Agent` header identifying the tool
and a contact (per Wikimedia's User-Agent policy) or risk a `403`.
`[UNVERIFIED-LIVE]`

### 1.1 Per-article

```
GET /metrics/pageviews/per-article/{project}/{access}/{agent}/{article}/{granularity}/{start}/{end}
```

- `project`: e.g. `en.wikipedia`, `pl.wikipedia`, `uk.wikipedia` (domain-style, not the MediaWiki dbname like `enwiki`). `[UNVERIFIED-LIVE]`
- `access`: `all-access` | `desktop` | `mobile-app` | `mobile-web`.
- `agent`: `all-agents` | `user` | `spider` | `automated`. The design uses
  `agent=user` to exclude bots/spiders. `[UNVERIFIED-LIVE]`
- `article`: exact canonical MediaWiki title, percent-encoded, spaces as
  underscores (e.g. `Intermittent_fasting`). Redirects are **not** resolved
  by this endpoint — a redirect title likely 404s or returns zero data; the
  caller must resolve to the canonical title first via the MediaWiki API
  (§3). `[UNVERIFIED-LIVE]`
- `granularity`: `daily` | `monthly`.
- `start` / `end`: `YYYYMMDD` (daily) — inclusive range, `[UNVERIFIED-LIVE]`
  on whether `end` is inclusive or exclusive.

Expected response shape:
```json
{
  "items": [
    {
      "project": "en.wikipedia",
      "article": "Intermittent_fasting",
      "granularity": "daily",
      "timestamp": "2023010100",
      "access": "all-access",
      "agent": "user",
      "views": 4213
    }
  ]
}
```
**Quirk (load-bearing for our zero-fill design):** days with zero views are
believed to be **omitted from `items` entirely**, not returned as `views: 0`
— this is exactly why `fetch` must zero-fill missing days itself rather than
trusting array length. `[UNVERIFIED-LIVE — confirm by requesting a known
low-traffic article/range and checking for gaps]`

**Known/likely limits:**
- Data with the `access`/`agent` breakdown is believed to start around
  **2015-07-01**; nothing before that in this API family (a separate legacy
  "pagecounts-raw" dataset covers earlier dates with a different, cruder
  schema and no agent split — out of scope for v1). `[UNVERIFIED-LIVE]`
- No officially documented hard rate limit for this endpoint at time of
  writing, but the API is known to `429` under heavy parallel load; design
  assumes bounded retry+backoff is required. `[UNVERIFIED-LIVE]`
- Data-settling lag: a given UTC day's counts are believed to stabilize
  within roughly 24–48h of that day ending; SPEC.md's "closed month" grace
  period (2 days) is a conservative placeholder pending confirmation.
  `[UNVERIFIED-LIVE]`
- Non-existent article title: expected `404` with a JSON error body (not
  confirmed exact shape). `[UNVERIFIED-LIVE]`

### 1.2 Aggregate (project-wide traffic, used for normalization)

```
GET /metrics/pageviews/aggregate/{project}/{access}/{agent}/{granularity}/{start}/{end}
```

Same segment semantics as §1.1 minus `article`. Expected shape:
```json
{
  "items": [
    {"project": "en.wikipedia", "access": "all-access", "agent": "user",
     "granularity": "daily", "timestamp": "2023010100", "views": 18345213}
  ]
}
```
Used as the denominator for "share of project daily traffic" normalization
(SPEC.md §5). `[UNVERIFIED-LIVE]`

### 1.3 Top articles (not currently used by v1 design, noted for completeness)

```
GET /metrics/pageviews/top/{project}/{access}/{year}/{month}/{day}
```
`day` can be `all-days` for a monthly rollup. Returns a ranked list capped
at (believed) the top 1000 articles for that period — a possible future
source for placebo-basket sampling but not required for v1 since basket
articles can be chosen via Wikidata random/category sampling instead.
`[UNVERIFIED-LIVE]`

## 2. Wikidata — topic → QID → sitelinks

### 2.1 Search (topic name → candidate QIDs)

```
GET https://www.wikidata.org/w/api.php?action=wbsearchentities&search={query}&language=en&format=json&limit=10
```
Expected shape: `{"search": [{"id": "Q1631107", "label": "intermittent fasting", "description": "...", "match": {...}}, ...]}`.
Used by `resolve` to produce the `candidates` list when `--qid` isn't given
directly; `ambiguous: true` when top candidates are close in relevance/no
single exact label match. `[UNVERIFIED-LIVE]`

### 2.2 Entity data (QID → sitelinks, labels, descriptions)

Two equivalent options:
```
GET https://www.wikidata.org/wiki/Special:EntityData/{QID}.json
GET https://www.wikidata.org/w/api.php?action=wbgetentities&ids={QID}&props=sitelinks|labels|descriptions&languages=en&format=json
```
The `wbgetentities` form with an explicit `props` list is preferred (smaller
payload — a full entity dump can be large for well-connected QIDs).
`[UNVERIFIED-LIVE]`

Sitelinks are keyed by MediaWiki **dbname**, not the language code alone —
e.g. `enwiki`, `plwiki`, `cswiki`, `ukwiki` for standard Wikipedia projects.
Mapping `{lang-code}` → `{lang-code}wiki` works for the great majority of
Wikipedia language editions but is **not universal** (e.g. some historical/
variant codes differ) — `resolve` needs an explicit lookup table, not a
blind string-concatenation rule, with a fallback error if a requested
language code has no known dbname mapping. `[UNVERIFIED-LIVE — confirm the
dbname mapping is regular for our target language set before hardcoding it]`

Expected sitelinks shape:
```json
{
  "entities": {
    "Q1631107": {
      "sitelinks": {
        "enwiki": {"site": "enwiki", "title": "Intermittent fasting", "badges": []},
        "plwiki": {"site": "plwiki", "title": "Głodówka przerywana", "badges": []}
      }
    }
  }
}
```
A language with no key present in `sitelinks` ⇒ no article exists for that
topic on that wiki (`resolve` reports `exists: false, reason: "no_sitelink"`
per SPEC.md's error-handling table). `[UNVERIFIED-LIVE]`

## 3. MediaWiki API — title normalization & redirect resolution

```
GET https://{lang}.wikipedia.org/w/api.php?action=query&titles={title}&redirects=1&format=json
```
Expected response includes a `normalized` array (input title → MediaWiki's
canonical form: underscore/space and capitalization normalization) and,
when the input resolves through a redirect, a `redirects` array of
`{"from": ..., "to": ...}` pairs, with `query.pages` keyed by page ID
holding the final canonical title. `[UNVERIFIED-LIVE]`

**Open question flagged, not yet confirmed:** whether a single call with
`redirects=1` fully resolves a **double redirect** (redirect → redirect →
real article) or only one hop. If only one hop, `resolve` needs to loop
until the title stabilizes (bounded, e.g. 5 hops, then error per SPEC.md's
`redirect_resolution_failed` case). `[UNVERIFIED-LIVE — test explicitly with
a known double-redirect title in Milestone 0]`

## Milestone 0 verification checklist (run in an unrestricted environment)

`verify_live_api.sh` (in this same directory) automates all of the checks
below with a proper `User-Agent` header and saves every raw response to
`./milestone0-responses/` — run it on a machine with normal internet access
(this project's dev sessions in the `Default` Claude Code on-the-web
environment cannot reach these domains at all; see `PLAN.md` Milestone 0
and `SPEC.md` §9 item 8). Paste its output back to turn the responses into
`tests/cassettes/` fixtures and update this file's tags below.

Manually, each of these should be run with a real, descriptive `User-Agent`
header, its raw JSON response saved as a `tests/cassettes/` fixture, and
this file's tags updated accordingly:

1. Per-article, ordinary case (e.g. `en.wikipedia`, a well-known article,
   `agent=user`, a 7–30 day daily range) — confirm response shape, confirm
   whether zero-view days are omitted or present as `0`.
2. Per-article for a **known low-traffic** article over a range that should
   include at least one true zero-view day — confirms the zero-fill quirk
   directly.
3. Per-article for a title that is itself a **redirect** — confirm whether
   AQS 404s, returns zero data, or silently follows the redirect.
4. Aggregate endpoint for the same project/range — confirm shape and units
   match §1.2's assumption.
5. Wikidata `wbsearchentities` for an ambiguous query (e.g. a topic with
   multiple plausible entities) — confirm `candidates`/`ambiguous` heuristic
   is workable against real result structure.
6. Wikidata `wbgetentities` sitelinks for a QID known to be missing a
   sitelink in at least one target language — confirm the "absent key"
   behavior assumed above.
7. MediaWiki `action=query&redirects=1` for (a) a normal title, (b) a single
   redirect, (c) a known **double** redirect if one can be found — confirms
   how many hops one call resolves.
8. Two calls to the per-article endpoint for the **same already-closed
   month**, a few minutes apart — sanity-check that closed-month data is
   stable (supports treating it as permanently cacheable).
9. Deliberately fire a burst of parallel requests to gauge real rate-limit
   behavior (`429` threshold, `Retry-After` header presence) so `fetch`'s
   backoff can be tuned to real behavior rather than a guess.
10. Confirm the actual earliest available date for the `agent`-split
    per-article endpoint (try a `start` well before 2015-07 and see how the
    API responds) — needed to correctly clamp/warn on over-long date-range
    requests per SPEC.md.
