---
name: curiosity-radar
description: Analyzes Wikipedia pageview trends across languages to help B2C founders decide which topics to build next and which language editions to launch in, producing charts and a verified one-page PDF report grounded in Wikipedia readership data. Use when the user asks to compare interest in a topic across Wikipedia language editions, wants to know whether interest in a topic is growing (and how much to trust that trend), or wants a shareable report recommending which audiences/languages to investigate next.
---

# curiosity-radar

Turn a topic + a set of Wikipedia language editions into: a resolved
Wikidata entity and per-language article set, cached pageview history, a
robust (Theil-Sen/Mann-Kendall) trend read with spike detection and a
placebo-basket sanity check against wiki-wide background drift, small
charts, and a one-page PDF report whose every number is verified against
the underlying computed data before being handed to the user.

**When to use this skill:** the user wants to compare interest in a topic
across Wikipedia language editions, wants to know whether interest in a
topic is growing (and how much to trust that), or wants a shareable report
recommending which audiences/languages to investigate next — the kind of
signal a B2C founder uses to decide what to build or localize next.

**Known gap, always disclose it:** `analyze`'s `placebo` field is real and
schema-valid, but always reports "insufficient comparison data... found 0"
today — there's no live basket-sourcing mechanism yet (`SPEC.md` §9 item
1). Don't present a placebo percentile as a real confidence signal in your
answer to the user; lean on the Theil-Sen/Mann-Kendall `confidence_label`
instead, and say so if asked how much to trust a trend.

## Command sequence

```
uv run curiosity-radar resolve --topic "<text>" --languages <codes> --save-as <slug>
uv run curiosity-radar fetch   --project <slug>
uv run curiosity-radar analyze --project <slug>
uv run curiosity-radar chart   --project <slug>
uv run curiosity-radar report  --project <slug>
uv run curiosity-radar verify  --project <slug>
```

Run every command via `uv run curiosity-radar ...` (never invoke the
Python module directly) so the pinned `uv.lock` environment is always
used. Pick one `--data-dir` (or set `CURIOSITY_RADAR_DATA_DIR`) at the
start of a conversation and reuse it for every command, so follow-ups hit
the same cache and project state instead of starting cold.

Every command's stdout is exactly one JSON object — either its success
shape or `{"error": {"code": ..., "message": ..., "hint": ...}}` — never a
raw traceback. Branch your control flow on `"error" in result`, not the
exit code alone.

**After `resolve`**, before running `fetch`: check `ambiguous` and
`cluster.articles[lang].exists` for every requested language.
- `ambiguous: true` → don't guess which `candidates` entry is right; ask
  the user to pick, or rerun with an explicit `--qid`.
- A language with `exists: false` → that language has no article for this
  topic (no sitelink, or the sitelink's title doesn't resolve). It's
  silently skipped by every later command — tell the user which
  language(s) got dropped and why, don't let it pass unmentioned.

**After `analyze`**, before running `chart`/`report`: check each
language's `data_quality.sufficient_for_trend`. If `false`
(`"all_zero_or_empty"` or `"too_short"`, under 60 days), don't describe a
trend for that language at all — say the data's insufficient and why.

**Before handing a report to the user**: always run `verify` and check its
`status`. `"failed_verification"` is blocking — rerun `report` (never
hand-edit the PDF) and `verify` again. The report's own footer line is a
fixed string, not a live check — it does not mean `verify` already passed
(see `references/report-template.md`).

## Follow-ups without starting cold

For a same-conversation follow-up ("also check Slovak," "drop 2024," "what
about German instead"), use `curiosity-radar project set ...` (or `fork`
for a new branch off the same assumptions) before re-running only the
steps that actually changed:

- **Adding a language** (`project set --add-language sk`) → rerun `fetch`
  (it resolves and fetches only the new language; already-cached languages
  cost zero network calls) → `analyze`/`chart`/`report`/`verify`.
- **Excluding/narrowing a date range** (`project set --exclude-date-range
  ...` / `--set-date-range ...`) → an exclusion needs only `analyze` (pure
  local recomputation, zero network calls); a widened date range needs
  `fetch` first too, since it may reach beyond what's cached.
- **Removing a language** (`project set --remove-language xx`) → `analyze`
  only (nothing to fetch).
- **A different topic/comparison entirely** → `project fork --as
  <new-slug>` first, so the original stays intact for the user to come
  back to.

`project show --project <slug>` reports `stale.fetch_stale`/
`stale.analyze_stale` after any mutation — trust it over guessing which
steps are still needed. Full detail: `references/caching.md`.

## Where to look next

- `references/error-catalog.md` — every `error.code` this skill can
  return, plus the non-fatal "soft failure" signals (`ambiguous`,
  `exists: false`, `sufficient_for_trend: false`, a `verify` mismatch) and
  what `verify` does and doesn't catch.
- `references/stats-methods.md` — exact thresholds behind every
  `confidence_label` and the placebo verdict tiers, plus known
  methodological limitations (weekly autocorrelation, the placebo-basket
  gap above).
- `references/caching.md` — cache key schemes, staleness flags, and why
  the two follow-up flows above are cheap.
- `references/report-template.md` — the PDF's exact section order and
  claim list, and the footer-isn't-a-live-check caveat.
- `references/api-notes.md` — the underlying Wikimedia/Wikidata/MediaWiki
  API contracts this design depends on.
- `references/examples.md` — real worked command sequences and JSON
  output for all 3 `TASK.md` example queries.
- `SPEC.md` / `PLAN.md` (repo root, dev docs, not shipped with this skill)
  — the frozen architecture and build history, for anyone modifying the
  skill itself rather than using it.
