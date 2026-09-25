# Error catalog

Every `curiosity-radar` command prints exactly one JSON object to stdout:
either its success shape or `{"error": {"code": ..., "message": ...,
"hint": ...}}` with a nonzero exit code — never a raw traceback (those go
to `<data-dir>/logs/`). This table is the actual set of `error.code` values
the implementation raises today (cross-checked against the code, not just
`SPEC.md` §7's original design — a couple of entries below closed real gaps
found while writing this doc; see the note under each). Branch on the
presence of an `error` key, not the exit code alone.

## Hard failures (`{"error": {...}}`, exit 1)

| `code` | Raised by | When | `hint` says |
|---|---|---|---|
| `missing_topic_or_qid` | `resolve` (CLI layer, before dispatch) | Neither `--topic` nor `--qid` given. | Pass `--topic "<text>"` or `--qid Q...`. |
| `no_qid_match` | `resolve` | `wbsearchentities` returns zero candidates for the topic text. | Try `--qid` directly, or rephrase the topic. |
| `redirect_resolution_failed` | `resolve` (via `mediawiki_client.resolve_title`) | A title's redirect chain doesn't stabilize within `MAX_REDIRECT_HOPS` (5) MediaWiki `query` calls. | Check the article manually — it may have been merged/deleted. |
| `project_not_found` | `fetch` (no saved state and no `--topic`/`--languages` to bootstrap one), `analyze`, `chart`, `report`, `verify`, `project show`/`set`/`fork` | The given `--project` slug has no file under `<data-dir>/projects/`. | Run `resolve --save-as` first, or check `project list`. |
| `unknown_engine` | `report` | `--engine` isn't one of `auto`/`weasyprint`/`fpdf2`. | Choose from the listed set. |
| `unknown_chart_kind` | `chart` | A `--kinds` value isn't one of `trend`/`spike`/`cross-language`. | Choose from the listed set. |
| `no_report_found` | `verify` | No `--pdf` given and the project has never run `report` (`last_report_pdf_path` unset). | Run `report` first, or pass `--pdf` explicitly. |
| `pdf_not_found` | `verify` | A resolved PDF path (explicit or recorded) doesn't exist on disk. | Rerun `report`, or pass the correct `--pdf` path. |
| `network_error` | `resolve`, `fetch` | A `httpx.TransportError` (DNS, connection refused, TLS) reaches the shared client — i.e. the request never got a response at all. | Check connectivity; already-cached closed months/resolved languages are still usable. |
| `rate_limited` | `resolve`, `fetch` | A `429`/`500`/`502`/`503`/`504` response survives `wikimedia/http.py`'s bounded retry (3 attempts, exponential backoff + jitter) without ever succeeding. | Wait a minute and retry — already-cached/resolved data is unaffected. See "Persistent rate-limiting" below if it keeps happening across several genuinely spaced-out retries. |
| `project_not_resolved` | `bootstrap-script` | The `--project` slug exists but has zero resolved articles (`resolve` never succeeded for it, or every language came back `exists: false`). | Run `resolve --save-as` first — `bootstrap-script` needs at least one language's real article/QID on file, even if `fetch` itself never completed. |
| `internal_error` | any command (CLI-level catch-all) | Anything not covered above (a real bug, an unexpected exception shape). Full traceback written to `<data-dir>/logs/<timestamp>.log`. | Check the log file. |

### Persistent rate-limiting: when to stop retrying and escalate

A single `rate_limited` is often transient — the documented "wait a minute
and retry" is the right first move. But some environments sit behind a
shared/heavily-used egress IP where Wikimedia's `429` `retry-after` header
does not shrink between attempts, it *grows* (observed directly: 14s, then
37s, after two spaced-out retries) — waiting longer makes no progress
because the shared IP stays under load regardless of how long any one
session waits. `SKILL.md` tells the agent: after a genuine second or third
`rate_limited` spread across a few minutes of real waiting (not a tight
retry loop), stop retrying resolve/fetch entirely and:

1. Tell the user plainly that Wikimedia is currently unreachable from this
   environment — this is an environment/network condition, not a bug in
   the skill or a sign the topic/languages were wrong.
2. If `resolve` has *ever* succeeded for this project (even once, even
   before `fetch` started hitting the limit) — run `bootstrap-script
   --project <slug>` and hand the user the generated script + its
   `instructions` verbatim: they run it on a machine with normal internet
   access (stdlib-only, no `uv`/`git`/pip installs needed), it writes
   `cache/raw/...` in the exact layout `fetch` itself would have produced,
   they zip and return `cache/`, and dropping that into `<data-dir>/cache/`
   lets `fetch` pick up every closed month with zero further network calls.
3. If `resolve` itself has never once succeeded, there is no project to
   bootstrap from — say so, and either wait longer before retrying `resolve`
   (its own request volume is far smaller than `fetch`'s, so it succeeds
   far more often even when `fetch` is thoroughly blocked) or ask the user
   if they already know the exact Wikidata QID / per-language article
   titles, so `resolve --qid ...` can skip the search step that's failing.

**Two gaps closed while writing this doc (Milestone 10):** `SPEC.md` §7
always documented a clean `rate_limited` error, but neither `resolve.py`
nor `fetch.py` actually caught `httpx.HTTPStatusError` before this
milestone — a persistent 429/5xx after retries were exhausted fell through
to the generic `internal_error` path instead, with a real traceback that
had nothing to do with a bug. `resolve.py`'s `_resolve` also had no
`network_error` handling at all (only `fetch.py` did) despite being just as
network-dependent. Both commands now map `httpx.TransportError` →
`network_error` and a retry-exhausted `httpx.HTTPStatusError` →
`rate_limited`, consistently. Covered by
`test_resolve.py::test_resolve_persistent_rate_limit_is_a_clean_error` and
`test_fetch_and_cache.py::test_persistent_rate_limit_is_a_clean_error`
(both patch `asyncio.sleep` to a no-op so the retry backoff doesn't slow
the test suite down).

## Soft failures — not an `error`, still worth knowing

These are valid, schema-conforming JSON on a successful exit — the failure
mode is real, but per-item/per-language, not fatal to the whole command.

| Signal | Where | Meaning |
|---|---|---|
| `"ambiguous": true` + populated `candidates` | `resolve` | Multiple Wikidata entities share the exact search label. Don't guess — surface `candidates` to the user and ask them to pick, or rerun with an explicit `--qid`. |
| `cluster.articles[lang].exists: false, reason: "no_sitelink"` | `resolve` | The resolved QID has no sitelink for that language's wiki. That language is silently skipped by every downstream command (`fetch` warns and skips it; `analyze`/`chart` never see it via `resolved_articles()`). |
| `cluster.articles[lang].exists: false, reason: "page_missing" \| "page_not_found"` | `resolve` | The sitelink's title doesn't resolve to a real page on that wiki (deleted/never existed post-sitelink). Same downstream skip behavior as `no_sitelink`. |
| `data_quality.sufficient_for_trend: false, reason: "all_zero_or_empty" \| "too_short"` | `analyze` | Fewer than `MIN_DAYS_FOR_TREND` (60) days of data, or every day is zero. `normalized_trend`/`trend_excluding_spikes` come back as a fixed "insufficient data" placeholder (`theil_sen_slope_per_day: 0.0`, `mann_kendall.trend: "no trend"`) rather than a fabricated number — never treat those as real when `sufficient_for_trend` is false. |
| `placebo.verdict` starting with `"insufficient comparison data..."` | `analyze` | Fewer than `MIN_ELIGIBLE_FOR_VERDICT` (10) basket members. **Always true today** — no live basket-sourcing mechanism exists yet (`SPEC.md` §9 item 1, `PLAN.md` Milestone 5/6), so the candidate pool `analyze` passes in is always empty. Don't present the placebo percentile as a real confidence signal until this is wired up; lean on the Theil-Sen/Mann-Kendall confidence label instead. |
| `verify` → `"status": "failed_verification"` + populated `mismatches` | `verify` | A rendered PDF's printed number/date no longer matches what a fresh, cache-served `analyze`/`chart` would produce right now — a stale PDF kept around after data changed, or (in testing) a deliberately broken template. This is the normal, expected shape of a real mismatch, not a bug in `verify` itself. Rerun `report`, never hand-edit the PDF. |
| `fetch`'s `warnings` array | `fetch` | Non-fatal notes: a clamped over-long date range (`AQS_EARLIEST_DATE`), a language skipped for lack of a resolved article. Always check `warnings` even on success. |

## What `verify` catches vs. doesn't

`verify` re-derives the exact claim list `report` would produce right now
(same `build_claims()` function, same cache-served `analyze`/`chart` calls)
and regex-searches the PDF's extracted text for each claim's label,
comparing the value immediately after it. It **will** catch: a template
rendering the wrong number, a PDF kept around after `analyze` reran with
different data (new fetch, new exclusion, schema-version bump), or a manual
edit to the PDF text. It does **not** re-validate the report's prose
(`headline_text`) word-for-word, only the specific `label: value` pairs
`build_claims()` emits — and the footer's literal "Numeric claims verified
against source data: PASS" line is a fixed string baked into both
renderers, not something `verify` itself writes or checks; it asserts that
the report *is* meant to be checked, not that a prior `verify` call already
passed. Always run `verify` as its own step — a PDF is not verified until
you have — and treat `status: "failed_verification"` as blocking:
regenerate via `report`, never patch the PDF by hand.
