# Wikimedia / Wikidata API notes

**Status: mostly CONFIRMED 2026-09-22.** This project's own dev sessions
(Claude Code on-the-web, `Default` environment) cannot reach `wikimedia.org`
/ `*.wikipedia.org` / `*.wikidata.org` / `api.wikimedia.org` at all (org
egress policy — confirmed in two independent sessions, see `PLAN.md`
Milestone 0 / `SPEC.md` §9 item 8). Real verification was done via a manual
handoff: `verify_live_api.sh` run on the requester's own machine, its
output turned into the fixtures under `tests/cassettes/milestone0/` (see
that directory's `README.md` for the full request/result table and the
findings that changed this design). Every entry below is now tagged
`[CONFIRMED 2026-09-22]` unless noted otherwise; a few narrower items
remain `[UNVERIFIED-LIVE]` and are called out explicitly — they're residual
and non-blocking, not reasons to distrust the rest.

**Two real findings from this pass are load-bearing enough to repeat up
front:**
1. **AQS per-article pageviews does not resolve redirects** — it tracks
   whatever title was literally requested. A redirect title (tested:
   `USA` → `United States`) gets its own real, nonzero, separate view
   count. See §1.1 and `SPEC.md`'s `fetch` design for how this is handled.
2. **Never hardcode a Wikidata QID as a "known" example.** An earlier draft
   of this project's docs used `Q1631107` as a stand-in for "intermittent
   fasting" from memory — it's actually the QID for **Bibliography**. Every
   example below now uses an obviously-fake placeholder (`Q_EXAMPLE`)
   instead. `resolve` must always look up QIDs live via
   `wbsearchentities`/`wbgetentities`; nothing in this codebase should ever
   hardcode one as if it were a known-good constant.

## 1. Wikimedia Analytics Query Service (AQS) — pageviews

Base: `https://wikimedia.org/api/rest_v1/metrics/pageviews/`

A descriptive `User-Agent` header (tool name + contact) was used for every
call and all succeeded — consistent with Wikimedia's documented User-Agent
policy, though we didn't separately test what happens with a generic/absent
one. `[CONFIRMED 2026-09-22, partial]`

### 1.1 Per-article

```
GET /metrics/pageviews/per-article/{project}/{access}/{agent}/{article}/{granularity}/{start}/{end}
```

- `project`: e.g. `en.wikipedia` (domain-style, not the MediaWiki dbname
  like `enwiki`). `[CONFIRMED 2026-09-22]`
- `access`: `all-access` | `desktop` | `mobile-app` | `mobile-web`.
- `agent`: `all-agents` | `user` | `spider` | `automated`; `agent=user`
  works as intended (excludes bots/spiders). `[CONFIRMED 2026-09-22]`
- `article`: exact title, percent-encoded, spaces as underscores. **AQS
  does NOT resolve redirects — it returns real traffic for the literal
  title requested, redirect or not.** Requesting `USA` (a redirect to
  `United States`) returned genuine, distinct, nonzero daily views (200–290
  views/day for the tested week) — it neither 404s, nor silently follows
  the redirect, nor returns zero. `[CONFIRMED 2026-09-22 —
  tests/cassettes/milestone0/03_per_article_redirect_title.json]`
  **Design consequence:** a canonical-title-only fetch undercounts a
  topic's true readership whenever people reach it via a known redirect.
  `fetch` now fetches and sums views for both the canonical title and the
  one redirect alias `resolve` already discovers (its `redirect_from`
  field), when present. Enumerating *every* title that redirects to an
  article (a full MediaWiki backlinks-of-redirects query) is out of scope
  for v1 — stated as a known limitation.
- `granularity`: `daily` | `monthly`.
- `start` / `end`: `YYYYMMDD`, **both endpoints inclusive** — a request for
  `20240801`–`20240831` returned exactly 31 daily items, one per calendar
  day in that closed range. `[CONFIRMED 2026-09-22]`

Confirmed response shape (real data):
```json
{
  "items": [
    {
      "project": "en.wikipedia",
      "article": "Intermittent_fasting",
      "granularity": "daily",
      "timestamp": "2024080100",
      "access": "all-access",
      "agent": "user",
      "views": 1626
    }
  ]
}
```
**Zero-fill quirk — still not directly observed.** Every article tested
(including a deliberately obscure one, `Theil–Sen_estimator`, 23–112
views/day) had at least some traffic every single day in the tested range,
so we never actually saw a true zero-view day omitted from `items`. The
"missing days are omitted, not returned as `views: 0`" assumption is
Wikimedia's documented behavior and is kept, but flagged
`[UNVERIFIED-LIVE — retest with a genuinely dormant article/range if
fetch's zero-fill logic ever looks wrong against real data]`.

**Known limits, now with real data:**
- History start date: confirmed data does **not** exist for `20100101`–
  `20100107` (404 — see error shape below). The *exact* boundary (believed
  ~2015-07-01) wasn't pinpointed — this probe only proved 2010 is before
  it. `[CONFIRMED 2026-09-22: out-of-range behavior — 404 with a problem+json
  body, not an empty result. UNVERIFIED-LIVE: exact start date — a
  bisection-style check would pin it down, not needed to build a safe
  clamp]`
- Rate limiting: 5 concurrent requests to the aggregate endpoint all
  returned `200` with no `429`, no `Retry-After` header, no other
  rate-limit signal. The true ceiling is still unknown — just higher than
  5. `[CONFIRMED 2026-09-22 up to 5 concurrent; UNVERIFIED-LIVE beyond that]`
- Data-settling lag / grace period: **not directly measurable in a single
  script run** (would need a longer real-world gap between calls). Two
  calls to the identical already-closed-month range, seconds apart,
  returned byte-identical responses — supports (but doesn't fully prove)
  treating a closed month as stable/cacheable. `SPEC.md`'s 2-day grace
  period remains a placeholder. `[UNVERIFIED-LIVE]`
- Non-existent-range error shape, confirmed:
  ```json
  {
    "detail": "The date(s) you used are valid, but we either do not have data for those date(s), or the project you asked for is not loaded yet. Please check documentation for more information",
    "method": "get",
    "status": 404,
    "title": "Not Found",
    "type": "about:blank",
    "uri": "/metrics/pageviews/per-article/en.wikipedia/all-access/user/Intermittent_fasting/daily/20100101/20100107"
  }
  ```
  Content-Type `application/problem+json` (RESTBase-style problem response).
  `[CONFIRMED 2026-09-22 — tests/cassettes/milestone0/10_earliest_date_probe_404.json]`
- Cache headers observed (not currently used by our own cache design, but
  available): successful responses carry `cache-control: s-maxage=14400,
  max-age=14400` (4h); the 404 above carries `s-maxage=600` (10 min).
  `[CONFIRMED 2026-09-22]`

### 1.2 Aggregate (project-wide traffic, used for normalization)

```
GET /metrics/pageviews/aggregate/{project}/{access}/{agent}/{granularity}/{start}/{end}
```

Same segment semantics as §1.1 minus `article`. Confirmed shape:
```json
{
  "items": [
    {"project": "en.wikipedia", "access": "all-access", "agent": "user",
     "granularity": "daily", "timestamp": "2024080100", "views": 244964703}
  ]
}
```
`[CONFIRMED 2026-09-22 — tests/cassettes/milestone0/04_aggregate.json]`
Used as the denominator for "share of project daily traffic" normalization
(`SPEC.md` §5).

### 1.3 Top articles (not currently used by v1 design, noted for completeness)

```
GET /metrics/pageviews/top/{project}/{access}/{year}/{month}/{day}
```
Not exercised in this verification pass — still `[UNVERIFIED-LIVE]`, low
priority since v1 doesn't depend on it (placebo-basket sampling uses
Wikidata, not this endpoint).

## 2. Wikidata — topic → QID → sitelinks

### 2.1 Search (topic name → candidate QIDs)

```
GET https://www.wikidata.org/w/api.php?action=wbsearchentities&search={query}&language=en&format=json&limit=10
```
Confirmed shape (real query `search=Mercury`, deliberately ambiguous):
```json
{
  "searchinfo": {"search": "Mercury"},
  "search": [
    {
      "id": "Q613883", "title": "Q613883", "pageid": 578146,
      "concepturi": "http://www.wikidata.org/entity/Q613883",
      "repository": "wikidata", "url": "//www.wikidata.org/wiki/Q613883",
      "display": {"label": {"value": "Mercury", "language": "en"},
                  "description": {"value": "automobile marque of the Ford Motor Company", "language": "en"}},
      "label": "Mercury",
      "description": "automobile marque of the Ford Motor Company",
      "match": {"type": "label", "language": "en", "text": "Mercury"}
    }
  ],
  "search-continue": 10,
  "success": 1
}
```
`[CONFIRMED 2026-09-22 — tests/cassettes/milestone0/05_wikidata_search_ambiguous.json]`

**Correction from the original design draft: there is no relevance
`score` field.** Ambiguity is conveyed only by (a) list order (server-
ranked) and (b) `match.type` (`"label"` vs `"alias"`, with an `aliases`
array present on alias matches). `resolve`'s `candidates` output must not
invent a numeric score — `SPEC.md` has been corrected to drop it.
`search-continue` supports pagination beyond `limit`.

### 2.2 Entity data (QID → sitelinks, labels, descriptions)

```
GET https://www.wikidata.org/w/api.php?action=wbgetentities&ids={QID}&props=sitelinks&format=json
```
`[CONFIRMED 2026-09-22 — tests/cassettes/milestone0/06_wikidata_sitelinks.json]`
Confirmed shape:
```json
{
  "entities": {
    "Q_EXAMPLE": {
      "type": "item",
      "id": "Q_EXAMPLE",
      "sitelinks": {
        "enwiki": {"site": "enwiki", "title": "Example Article", "badges": []},
        "plwiki": {"site": "plwiki", "title": "Przykładowy artykuł", "badges": []}
      }
    }
  },
  "success": 1
}
```
Sitelinks are keyed by MediaWiki dbname (`enwiki`, `dewiki`, `jawiki`,
`nlwiki`, `ptwiki`, `viwiki`, ... — the `{lang-code}wiki` pattern held for
every sitelink observed in this test). A language with no key present in
`sitelinks` ⇒ no article exists for that topic on that wiki (`resolve`
reports `exists: false, reason: "no_sitelink"`). `[CONFIRMED 2026-09-22 for
the dbname pattern on the languages observed; still worth a lookup table
rather than blind concatenation for languages with known irregular codes,
none of which appeared in this sample]`

**Reminder (see top of file): don't reuse `Q1631107` as "intermittent
fasting" anywhere — it's Bibliography.** Use `Q_EXAMPLE` in docs/tests, and
resolve real topics live via `wbsearchentities` at runtime.

## 3. MediaWiki API — title normalization & redirect resolution

```
GET https://{lang}.wikipedia.org/w/api.php?action=query&titles={title}&redirects=1&format=json
```

Confirmed behavior for three cases:
- **Normal title, no adjustment needed** (`Python (programming language)`
  on en.wikipedia): response has *only* a `pages` key — no `normalized` or
  `redirects` key present at all when nothing needed adjusting. Code/
  schemas should treat these as optional/nullable, not always-present
  (possibly-empty) arrays. `[CONFIRMED 2026-09-22 —
  tests/cassettes/milestone0/07a_mediawiki_normal.json]`
  ```json
  {"batchcomplete": "", "query": {"pages": {"23862": {"pageid": 23862, "ns": 0, "title": "Python (programming language)"}}}}
  ```
- **Single redirect** (`USA` on en.wikipedia): `redirects` array present,
  `pages` keyed by the *final* canonical title's page ID.
  `[CONFIRMED 2026-09-22 — tests/cassettes/milestone0/07b_mediawiki_single_redirect.json]`
  ```json
  {"batchcomplete": "", "query": {"redirects": [{"from": "USA", "to": "United States"}], "pages": {"3434750": {"pageid": 3434750, "ns": 0, "title": "United States"}}}}
  ```
- **Non-Latin script title** (`Астрономія` on uk.wikipedia): resolves
  correctly once properly percent-encoded as UTF-8 — confirms Cyrillic
  topic names work at the transport level, relevant since the Ukrainian
  TASK.md example needs exactly this. `[CONFIRMED 2026-09-22 —
  tests/cassettes/milestone0/07c_mediawiki_uk.json]`

**Still open:** whether a single `redirects=1` call fully resolves a
**double redirect** (redirect → redirect → real article) or only one hop —
no double-redirect title was tested. `resolve`'s bounded-hop-loop /
`redirect_resolution_failed` error path (per `SPEC.md` §7) stays as
designed defensively either way. `[UNVERIFIED-LIVE — test explicitly with a
known double-redirect title if/when one is identified]`

## Milestone 0 verification checklist — status

`curiosity-radar/references/verify_live_api.sh` automates all of these; see
`tests/cassettes/milestone0/README.md` for the exact request/response
mapping. Status per original checklist item:

1. Ordinary per-article — **done**, shape and inclusive date range confirmed.
2. Known low-traffic per-article (zero-day check) — **partially done**;
   ran, but didn't land on a true zero day. Residual, non-blocking.
3. Per-article for a redirect title — **done**; major finding (see top of
   file and §1.1).
4. Aggregate endpoint — **done**, shape confirmed.
5. Ambiguous Wikidata search — **done**; corrected the assumed schema (no
   `score` field).
6. Sitelinks for a QID — **done**; also caught and corrected a wrong
   example QID.
7. MediaWiki redirects (normal + single) — **done**. Double-redirect case —
   **not done**, no test title identified; residual, non-blocking.
8. Closed-month stability (repeat call) — **done** for a short interval
   (identical response); a longer-gap re-check is a nice-to-have, not
   blocking.
9. Rate-limit/backoff probe — **done** at small scale (5 concurrent, all
   200); true ceiling still unknown, residual and non-blocking.
10. Earliest-date probe — **done**; confirmed 404 + exact error shape for
    an out-of-range request; exact boundary date not pinned down
    (residual, non-blocking).

Net: Milestones 2–3 (resolve/fetch) can now proceed with confidence against
real, confirmed shapes and the redirect-title-tracking finding baked into
the design. The four residual items above are worth a follow-up check but
don't block implementation.
