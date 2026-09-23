---
name: curiosity-radar
description: Analyzes Wikipedia pageview trends across languages to help B2C founders decide which topics to build next and which language editions to launch in, producing charts and a verified one-page PDF report grounded in Wikipedia readership data. Use when the user asks to compare interest in a topic across Wikipedia language editions, wants to know whether interest in a topic is growing (and how much to trust that trend), or wants a shareable report recommending which audiences/languages to investigate next.
---

# curiosity-radar

**Status: partial (Milestone 5 of `PLAN.md`).** The command chain below is
wired end to end and returns well-formed JSON. `resolve` and `fetch` are
fully implemented against live Wikidata/MediaWiki/AQS; the underlying
trend/spike/normalization/placebo statistics (`src/curiosity_radar/stats/`)
are implemented and unit-tested but not yet wired into a command —
`analyze`/`chart`/`report`/`verify` are still stubs — see `PLAN.md` for the
milestone that fills in each one. This file will be trimmed to its final, short
(<500 line) form in Milestone 10; treat it as a placeholder until then.

## What this skill will do

Turn a topic + a set of Wikipedia language editions into: a resolved
Wikidata entity and per-language article set, cached pageview history, a
robust (Theil-Sen/Mann-Kendall) trend read with spike detection and a
placebo-basket sanity check against wiki-wide background drift, small
charts, and a one-page PDF report whose every number is verified against
the underlying computed data before being handed to the user.

## Command sequence (see `SPEC.md` §2–3 for full contracts)

```
uv run curiosity-radar resolve --topic "<text>" --languages <codes> --save-as <slug>
uv run curiosity-radar fetch   --project <slug>
uv run curiosity-radar analyze --project <slug>
uv run curiosity-radar chart   --project <slug>
uv run curiosity-radar report  --project <slug>
uv run curiosity-radar verify  --project <slug>
```

Pick one `--data-dir` (or set `CURIOSITY_RADAR_DATA_DIR`) at the start of a
conversation and reuse it for every command, so follow-ups hit the same
cache and project state instead of starting cold. Every command's stdout is
a single JSON object — either the success shape or `{"error": {...}}`;
branch on the presence of `error` rather than the exit code alone.

For follow-up asks ("also check Slovak", "drop 2024"), use
`curiosity-radar project set ...` before re-running `analyze`/`chart`/
`report`/`verify` — see `SPEC.md` §2 "Cheap follow-ups" for which steps are
actually necessary after each kind of change.

## Where to look next

- `references/api-notes.md` — Wikimedia/Wikidata/MediaWiki API contracts
  this design depends on.
- `SPEC.md` (repo root, dev doc, not shipped) — the frozen architecture.
- `PLAN.md` (repo root, dev doc, not shipped) — build order and current
  milestone status.

`references/stats-methods.md`, `references/caching.md`,
`references/report-template.md`, and `references/error-catalog.md` do not
exist yet — they land in Milestone 10.
