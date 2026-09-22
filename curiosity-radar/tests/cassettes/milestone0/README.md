# Milestone 0 cassettes

Real Wikimedia/Wikidata/MediaWiki API responses captured 2026-09-22 by
running `curiosity-radar/references/verify_live_api.sh` on an unrestricted
machine (this project's own dev sessions cannot reach these domains — see
`PLAN.md` Milestone 0). These are the first real fixtures for
`tests/cassettes/` — later milestones' mock-transport tests should match
against these shapes rather than hand-invented ones.

User-Agent used for all requests: `curiosity-radar/0.1
(https://github.com/binskea/topic-scout; contact: marina@binskea.com)`.

| File | Request | Result |
|---|---|---|
| `01_per_article_ordinary.json` | `GET /metrics/pageviews/per-article/en.wikipedia/all-access/user/Intermittent_fasting/daily/20240801/20240831` | 200, 31 daily items, no gaps |
| `02_per_article_low_traffic.json` | same endpoint, `Theil–Sen_estimator`, `20240801`–`20240831` | 200, 31 items, all nonzero (23–112 views/day) — did **not** land on a true zero-view day, see note below |
| `03_per_article_redirect_title.json` | same endpoint, `USA`, `20240801`–`20240807` | 200, 7 items — see "redirect titles" finding below |
| `04_aggregate.json` | `GET /metrics/pageviews/aggregate/en.wikipedia/all-access/user/daily/20240801/20240831` | 200, 31 daily items |
| `05_wikidata_search_ambiguous.json` | `GET /w/api.php?action=wbsearchentities&search=Mercury&language=en&format=json&limit=10` (www.wikidata.org) | 200, 10 candidates (planet, element, car marque, Roman god, record label, sports team, ...) |
| `06_wikidata_sitelinks.json` | `GET /w/api.php?action=wbgetentities&ids=Q1631107&props=sitelinks&format=json` (www.wikidata.org) | 200 — **Q1631107 is "Bibliography", not "intermittent fasting"**, see finding below |
| `07a_mediawiki_normal.json` | `GET /w/api.php?action=query&titles=Python (programming language)&redirects=1&format=json` (en.wikipedia.org) | 200, no `redirects`/`normalized` key at all (title needed neither) |
| `07b_mediawiki_single_redirect.json` | same endpoint, `titles=USA` | 200, `redirects: [{"from":"USA","to":"United States"}]` |
| `07c_mediawiki_uk.json` | same endpoint, `titles=Астрономія` (uk.wikipedia.org) | 200 — confirms Cyrillic/non-Latin titles work once properly percent-encoded |
| `10_earliest_date_probe_404.json` | per-article endpoint, `Intermittent_fasting`, `20100101`–`20100107` | **404**, `application/problem+json` body (see shape below) |

Not saved as separate cassette files (redundant/uninteresting content, but
noted here): `08_per_article_repeat.json` was byte-identical to
`01_per_article_ordinary.json` (confirms short-interval response stability);
`09_burst_{1..5}.json` were 5 concurrent requests to the aggregate endpoint,
all 200 (confirms 5-way concurrency doesn't trigger rate limiting — the
true rate-limit ceiling is still unknown, we just didn't hit it).

## Findings that changed `api-notes.md` / `SPEC.md`

1. **AQS per-article does not resolve redirects — it tracks the literally
   requested title.** `03_per_article_redirect_title.json` returned real,
   distinct, nonzero traffic for `USA` even though `USA` is a redirect to
   `United States`. This means a canonical-title-only fetch **undercounts**
   a topic's true readership whenever people link to it via a known
   redirect title. `SPEC.md`'s `fetch` design now fetches and sums views
   for both the canonical title and the one redirect alias `resolve`
   already discovers (its `redirect_from` field), when present — full
   enumeration of *every* title that redirects to an article (a MediaWiki
   backlinks query) is out of scope for v1 and stated as a limitation.

2. **The example QID used throughout the original design draft
   (`Q1631107`) was wrong.** `06_wikidata_sitelinks.json` shows it
   resolves to "Bibliography" (sitelink titles are German
   "Literaturverzeichnis", Japanese "書誌", Dutch "Bibliografie",
   Portuguese "Bibliografia", Vietnamese "Thư mục (văn học)" — all mean
   bibliography), not "intermittent fasting". This was a memorized/
   fabricated example ID, not a real lookup — exactly the class of mistake
   Milestone 0 exists to catch. Every doc has been corrected to use an
   obviously-fake placeholder QID in examples instead of a specific real
   one, with an explicit note that `resolve` must always look QIDs up live
   via `wbsearchentities`/`wbgetentities`, never hardcode one.

3. **`wbsearchentities` has no relevance `score` field.** The real response
   (`05_wikidata_search_ambiguous.json`) has `id`, `label`, `description`,
   `match: {type, language, text}` (and `aliases` when matched via an
   alias), in server-ranked order — no numeric score. `SPEC.md`'s
   `resolve` candidate schema no longer invents a `score`; ambiguity is
   conveyed by list order plus `match.type`.

4. **MediaWiki's `redirects`/`normalized` keys are absent, not empty,
   when nothing needed adjusting.** `07a_mediawiki_normal.json` has only a
   `pages` key. Code and schemas should treat these as optional/nullable
   fields, not always-present (possibly-empty) arrays.

5. **The AQS out-of-range error is `application/problem+json`:**
   `{"detail": "...", "method": "get", "status": 404, "title": "Not Found", "type": "about:blank", "uri": "..."}`.
   Useful, concrete shape for `fetch`'s error handling — confirms a 404
   with a `detail` string is what "no data for this range" looks like, not
   an empty `items` array.

## Still not directly confirmed (residual, non-blocking)

- **True zero-view-day omission**: the low-traffic article tested still
  landed on 23+ views every day in this particular window; the "missing
  days are omitted, not returned as 0" assumption is Wikimedia's documented
  behavior but wasn't directly observed in this batch. Low risk; revisit
  if `fetch`'s zero-fill logic ever looks wrong against real data.
- **Double-redirect resolution**: no double-redirect title was tested;
  single-redirect resolution (`07b`) works as designed.
- **Exact AQS history start date**: confirmed data does NOT exist for
  2010-01, not confirmed exactly where the real boundary is (believed
  ~2015-07). A bisection-style check would pin this down precisely; not
  blocking since `fetch` only needs a safe clamp point, not the exact date.
- **True rate-limit ceiling**: 5 concurrent requests all succeeded with no
  `Retry-After`/`429` — the real threshold is still unknown, just higher
  than 5.
