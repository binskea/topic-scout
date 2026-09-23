# CLAUDE.md — `curiosity-radar` dev conventions

This repo is the take-home development workspace for a single Agent Skill,
`curiosity-radar/`. See `TASK.md` for the brief, `SPEC.md` for the frozen
architecture, `PLAN.md` for the build order. This file is about how to work
in this codebase day to day.

## Stack

- **Python 3.12**, managed with **uv**. `uv.lock` is committed and pinned —
  `uv sync` must reproduce the exact environment on any machine, no
  system-Python assumptions beyond the interpreter itself.
- **HTTP**: `httpx`, not `requests` — native async (useful for fetching
  several articles/languages concurrently within Wikimedia's rate limits),
  explicit timeout handling, and it pairs cleanly with `httpx.MockTransport`
  for cassette-backed tests.
- **Stats**: `scipy` + `numpy` (`scipy.stats.theilslopes`,
  `scipy.stats.kendalltau` as the basis for Mann-Kendall — implement the
  MK statistic directly rather than pulling in a possibly-unmaintained
  standalone package, unless one is verified suitable). No `pandas` — the
  actual data volumes (a few years of daily integers, a handful of
  articles) don't need it, and skipping it keeps `uv sync` fast.
- **Charts**: `matplotlib`, static PNG output. This is a static-PDF context
  (no interactivity needed); matplotlib has the smallest, most stable
  dependency footprint and renders deterministically enough for tests
  (file-existence/shape assertions), unlike plotly's JS/headless-browser
  output story.
- **PDF**: pluggable renderer (see `SPEC.md` §6) — **WeasyPrint** preferred
  (HTML/CSS layout, best one-page control) with automatic fallback to
  **fpdf2** (pure-Python, zero system deps) when WeasyPrint's native
  libraries aren't usable at runtime. Both are real implementations, both
  tested. Never assume WeasyPrint is available; the fallback path is not
  optional scaffolding. A Unicode font (`DejaVuSans.ttf`/`-Bold.ttf`) is
  bundled under `assets/fonts/` and referenced directly by both renderers
  (never a bare font-family name the runtime may or may not have) — fpdf2's
  core Helvetica/Courier fonts are Latin-1 only and raise on anything
  outside that range, including a plain em dash, not just non-Latin
  scripts. **PDF text extraction** (for `verify`, Milestone 8): `pypdf` —
  pure-Python, no system deps, same reproducibility rationale as fpdf2.
- **CLI**: `typer` (or plain `argparse` if it turns out simpler in
  practice) for subcommand dispatch and `--help` text.
- **Schema validation**: `pydantic` models in `src/curiosity_radar/
  schemas.py` are the single source of truth for every command's JSON
  contract — `SPEC.md` describes them, the models enforce them, tests catch
  drift between the two.

## Lint / format / types

- `ruff check` and `ruff format` — one tool for both, no separate
  black/flake8/isort stack.
- `mypy` in at least basic mode over `src/curiosity_radar/`.
- Run before every commit: `uv run ruff check . && uv run ruff format
  --check . && uv run mypy src/`.

## Testing rules

- **Never call live Wikimedia, Wikidata, or MediaWiki APIs in unit tests or
  CI.** All HTTP-touching tests run against recorded fixtures under
  `tests/cassettes/` (an `httpx.MockTransport` fed from saved JSON, in the
  spirit of VCR). The first real fixtures come directly from Milestone 0's
  live-verification session (see `PLAN.md`) — save those raw responses
  verbatim rather than hand-writing synthetic ones for the initial set.
- Stats functions (`stats/trend.py`, `stats/spikes.py`, `stats/normalize.py`,
  `stats/placebo.py`) get pure-function unit tests against synthetic series
  (flat, steadily rising, spiky, all-zero, too-short) with no network
  fixture involved at all — these should be fast and exhaustive regardless
  of what Wikimedia's real data looks like.
- `tests/test_cli_contracts.py` asserts every command's JSON output against
  its `schemas.py` pydantic model, so a schema change that isn't reflected
  in `SPEC.md` (or vice versa) is caught in CI, not discovered later by an
  agent parsing unexpected JSON.
- `report`/`verify` tests must include at least one deliberately-broken
  case (a template edit that renders a number inconsistent with the
  underlying derived JSON) to prove `verify` actually catches a mismatch —
  a `verify` implementation that only ever returns `"status": "verified"`
  on every test fixture hasn't been tested at all.
- The **eval** milestone (running the 3 `TASK.md` example queries against
  Claude Haiku 4.5, or a cheap/free OpenRouter equivalent) is explicitly
  **not** a unit test — it exercises the real agent + skill loop, is run
  on demand (not on every CI push), and lives under `evals/scenarios/` with
  results/transcripts saved to `evals/results/` for human review. It must
  still run against cassette-backed data, not live Wikimedia calls, so it
  stays reproducible and doesn't silently start depending on live network
  access. Document the exact invocation for running it once
  `evals/scenarios/` exists (a `uv run` entry point that shells out to
  whatever harness drives the eval model against the installed skill).

## How to run things

```
uv sync                                  # provision the pinned environment
uv run pytest                            # unit + cassette-backed tests
uv run ruff check . && uv run ruff format --check .
uv run mypy src/
uv run curiosity-radar <subcommand> ...  # exercise the CLI directly
uv run python -m evals.generate_cassettes  # (re)build synthetic eval cassette data
uv run python -m evals.run_scenarios     # run the eval scenarios against a real model; needs
                                          # OPENROUTER_API_KEY — see curiosity-radar/evals/README.md
```

## Working conventions

- Everything the skill needs at runtime (code, `SKILL.md`, `references/`,
  `assets/`) lives inside `curiosity-radar/` — no dependency on files
  elsewhere in this repo. `TASK.md`/`SPEC.md`/`CLAUDE.md`/`PLAN.md` at the
  repo root are this project's *development* docs, not part of the shipped
  skill.
- No compiled binaries checked in anywhere. Environment reproducibility
  comes from `uv.lock` alone.
- Every CLI command's stdout is JSON-only (or an `{"error": {...}}` object)
  — see `SPEC.md` §3 for the exact contract. Never print a stack trace to
  stdout; write it to `<data-dir>/logs/` instead.
- Prefer small, focused commits per `PLAN.md` milestone over large
  multi-milestone changes, so each step is independently reviewable and
  testable.
