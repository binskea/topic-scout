# Report layout — implementation detail

Expands `SPEC.md` §6 with what `report/render.py`,
`report/weasyprint_renderer.py`, and `report/fpdf2_renderer.py` actually
produce. Both engines render from the exact same `ReportContext`/`Claim`
list (`report/render.py::build_context` / `build_claims`) — this is the
single source of truth both renderers format, and the same one `verify`
rebuilds fresh to cross-check against, so the two renderers can never
disagree on *what* the numbers are, only (if something's broken) on
whether the printed PDF text still matches them.

## Page size and truncation

Fixed at **A4** (`PAGE_SIZE` in `render.py`) for both engines — not
configurable per report, matching `SPEC.md` §6's "pick one, hardcode it."
Languages are capped at `MAX_LANGUAGES` (**4**); `context.truncated` is set
when the project actually has more, and both renderers print a visible
truncation notice near the header (not a footnote) rather than silently
dropping languages.

## Section order, as actually rendered

1. **Header**: topic label (`state.topic_query` or the slug if unset), QID
   (or `"(no QID)"` if somehow unresolved), the (possibly-truncated)
   language list, project slug, project date range
   (`state.date_range_start`/`end` — reflects exclusions already applied,
   since `analyze` computes over the excluded range, not the nominal one),
   and `context.generated_at` (a fresh timestamp on *every* render,
   informational only — see "What isn't a claim" below).
2. **Headline** (`headline_text`): one sentence, template-filled, never
   free model prose — `'<topic>' on <top-ranked-lang>: <ranking reason>.`
   when a cross-language ranking exists, else `'<topic>' on <lang>:
   <confidence_label>.` for a single language, or a flat "no resolved
   articles" sentence if none resolved at all.
3. **Charts**: only **`trend`-kind** chart PNGs are embedded
   (`chart_paths = [c.path for c in context.charts.charts if c.kind ==
   "trend"]`) — one per language with a sufficient trend read. The `spike`
   and `cross_language_bar` PNGs `chart` renders are **not** embedded in
   the PDF at all; the cross-language section below is the ranked-list
   variant `SPEC.md` §6 point 5 explicitly allows as an alternative to a
   bar chart, not an oversight.
4. **Confidence & data** (the "claims panel"): every `Claim` from
   `build_claims`, printed verbatim as `label: value` — see the exact list
   below. This is what `verify` checks.
5. **Cross-language ranking**: only when more than one language was
   compared **and** `analysis.cross_language_ranking` is non-empty — a
   `rank. lang — reason` line per entry, in ranked order. Silently omitted
   (not a placeholder) for a single-language report.
6. **Assumptions** (`assumptions_text`), same visual weight as body text:
   "Views shown as % of project-wide daily traffic (agent=user), not raw
   counts. Date range reflects exclusions already applied." plus, for any
   language whose fetch summed in a redirect alias, `"<lang>: '<alias>'
   redirect traffic folded in"`.
7. **Limitations** (`LIMITATIONS` in `render.py`, fixed list, same for
   every report): pageview data isn't search/purchase-intent demand; short
   series near AQS's history start are unreliable; topic-to-article
   mapping can be imperfect; comparisons are normalized, not raw counts.
8. **Footer**: the literal string `"Numeric claims verified against source
   data: PASS"` — see the important caveat below.

## The exact claim list (`build_claims`)

Two project-level claims, then per language (for each of up to
`MAX_LANGUAGES` languages, in `context.languages` order):

- `Project date range start` / `Project date range end`
- `[<lang>] Data days`, `[<lang>] Zero-view days` — always present.
- **Only if `data_quality.sufficient_for_trend` is true** (otherwise the
  language contributes just the two lines above and nothing else — an
  insufficient-data language is never given a fabricated slope/p-value):
  - `[<lang>] Theil-Sen slope/day (with spikes)` — 6 decimal places
    (`fmt_float`, default `decimals=6`).
  - `[<lang>] Mann-Kendall p-value (with spikes)` — 6 decimals.
  - `[<lang>] Mann-Kendall tau (with spikes)` — 6 decimals, only if `tau`
    isn't `None`.
  - `[<lang>] Theil-Sen slope/day (excluding spikes)` — 6 decimals.
  - `[<lang>] Spikes detected` — integer count.
  - `[<lang>] Placebo basket size` / `[<lang>] Placebo percentile` (1
    decimal) — only if `analysis.placebo` is set (it always is, per
    `stats-methods.md`'s placebo caveat — currently always basket size 0).

`verify` finds each label with `re.escape(label) + r"\s*:\s*([^\s]+)"`
against the PDF's extracted text and compares the captured token
(right-stripped of trailing `.,;`) to the expected value **exactly** —
this is why every numeric claim is formatted with a fixed decimal count
(`fmt_float`) rather than Python's default `str(float)`: a renderer and
`verify`'s freshly-recomputed value must format identically or a
false-positive mismatch would fire on formatting alone, not a real
discrepancy.

## What isn't a claim (deliberately)

`context.generated_at` is stamped fresh on *every* `build_context` call,
including `verify`'s own re-derivation — it can never match between when
`report` ran and when `verify` checks, and it isn't derived from
`analyze`'s JSON at all. It's shown in the header as informational
context only, specifically excluded from `build_claims` so `verify` never
flags it as a false mismatch.

## The footer's "PASS" is not a live verify result

The footer text is a **fixed string**, identical in both renderers
(`template.html`'s `<footer>` for WeasyPrint, `Fpdf2Renderer._footer` for
fpdf2) — it does not read an actual prior `verify` outcome, and can't:
`report` renders before `verify` ever runs in the intended command
sequence (`resolve → fetch → analyze → chart → report → verify`), so there
is no real result yet to print at render time. Read it as "this report was
built to be independently verifiable," not "this exact PDF has already
passed `verify`." The only way to know a given PDF's numbers actually check
out is to run `verify --project <slug>` and look at its own `status`
field — never hand a report to the user on the strength of this footer
line alone.

## Engine selection (`--engine auto|weasyprint|fpdf2`)

`auto` (default) tries a real `WeasyPrintRenderer().render(...)` call
inside a `try`/`except Exception` — not just an import check, since a
Cairo/Pango-level failure can surface only at actual render time on some
platforms (`SPEC.md` §9 item 9) — and falls back to `Fpdf2Renderer`
transparently on any exception. `--engine weasyprint`/`fpdf2` force that
engine with no fallback, so a genuine failure surfaces as an `internal_error`
instead of being silently swallowed. `report`'s JSON always records
`engine_used`, so which path ran is never ambiguous from the output alone.
Both engines reference the bundled `assets/fonts/DejaVuSans{,-Bold}.ttf`
directly (a `file://` URI for WeasyPrint's `@font-face`, `add_font()` for
fpdf2) rather than trusting the runtime to have a matching Unicode font
family installed — fpdf2's core Helvetica/Courier fonts are Latin-1 only
and raise on anything outside that range, not just non-Latin scripts (a
plain em dash is enough) — this is what Milestone 8 found and fixed.
