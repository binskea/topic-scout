# Eval milestone (`PLAN.md` Milestone 11)

Runs the 3 `TASK.md` example queries end to end against a real LLM, with
`curiosity-radar` installed as the skill it's using — not a unit test, and
not run on every CI push (`CLAUDE.md`). It still never touches live
Wikimedia/Wikidata/MediaWiki: every scenario is backed by a synthetic,
reproducible cassette under `evals/cassettes/` (see "How this stays
reproducible" below).

## Running it

```
export OPENROUTER_API_KEY=...    # required — see below if you don't have one

uv run python -m evals.run_scenarios                          # all 3 scenarios
uv run python -m evals.run_scenarios --scenario 02_astronomy_uk
uv run python -m evals.run_scenarios --model "some/other-model:free"
```

If `evals/cassettes/*/manifest.json` is missing or a scenario's shape
parameters (`evals/scenarios/*.py`) changed, regenerate first:

```
uv run python -m evals.generate_cassettes
```

**Getting an `OPENROUTER_API_KEY`:** this repo has no key configured by
default. Add one under this environment's settings (cloud environment menu
in the session title bar → Edit → API credentials, or as a plain env var)
and start a new session — never paste a key into chat. `TASK.md` explicitly
allows a cheap/free OpenRouter model in place of Claude Haiku 4.5 for this
milestone; the default model (`DEFAULT_MODEL` in `run_scenarios.py`) is a
free-tier model as of when this was written — OpenRouter's free-tier
lineup changes over time, so if it 404s, pick a current one from
[openrouter.ai's free-model listing](https://openrouter.ai/models?max_price=0)
and pass `--model`.

## What it does

For each scenario: an isolated `--data-dir`, a fresh conversation with
`SKILL.md`'s full content as the system prompt (the same instructions a
real agent invoking this skill would see), and two tools — `run_command`
(runs `uv run curiosity-radar ...` only; argv-validated, not a raw shell,
so no shell-metacharacter injection is possible even from an unreliable
model) and `read_reference` (reads a file under `references/` or
`SKILL.md`, mirroring how an agent follows `SKILL.md`'s own pointers). The
loop ends when the model stops calling tools, or after 16 turns.

Full transcripts (`transcript.json`, every message/tool call/result) and a
human-readable summary (`transcript.md`: prompt, commands run, final
answer, any generated PDF, and a review checklist) are written to
`evals/results/<scenario-slug>/`, along with a copy of any PDF the model's
`report` calls produced. **This harness does not grade a run** — `PLAN.md`
Milestone 11 calls for human review against three criteria (also printed
in each `transcript.md`):

1. The model follows the intended command sequence (`resolve` → `fetch` →
   `analyze` → `chart` → `report` → `verify`) without needing hand-holding
   beyond what `SKILL.md` provides.
2. The final report's numeric claims pass `verify`.
3. A same-session follow-up tweak (not exercised by the base scenarios
   below, but worth trying by hand against a run's `--data-dir`) stays
   cheap and produces a coherent updated answer.

## The 3 scenarios (`evals/scenarios/`)

Straight from `TASK.md`, in the original Ukrainian (so the eval also
exercises Cyrillic topic/title handling, per `SPEC.md` §9 item 7) — the
third is concretized with specific language editions, since `TASK.md`'s
own third example is deliberately abstract about which ones a real user
would pick:

1. **`01_intermittent_fasting_pl_cs`** — compare intermittent-fasting
   interest growth on pl.wikipedia vs. cs.wikipedia over two years. Polish
   is given a clear rising trend, Czech roughly flat — a real difference
   for the cross-language ranking to reflect.
2. **`02_astronomy_uk`** — is interest in astronomy growing on
   uk.wikipedia, trustworthy enough for a course-addition decision?
   Moderate (not explosive) growth — the case where getting the confidence
   label right actually matters.
3. **`03_english_learning_es_de_ja`** — compare interest in learning
   English across es/de/ja Wikipedia and recommend which audiences to
   research next. Three distinct shapes (strongly rising, flat, moderately
   rising) for a genuine three-way ranking.

## How this stays reproducible

Two pieces make a live model's shelled-out CLI calls hit fixed, synthetic
data instead of the real network:

- **`CURIOSITY_RADAR_CASSETTE_DIR`** (`wikimedia/cassette.py`): a
  lookup-based transport, not the sequential-queue kind unit tests use —
  a live model doesn't call things in a knowable fixed order the way a
  test does, so requests are matched by identity (method + host + path +
  sorted query params), not by turn. The one deliberate exception:
  `wbsearchentities`'s `search` query param is wildcarded, since that's
  the model's own paraphrase of the user's ask, not something a fixture
  can pin word for word — any topic text still resolves to the scenario's
  fixed QID.
- **`CURIOSITY_RADAR_FAKE_TODAY`** (`clock.py`): pins "today" for every
  closed/open-month and default-date-range decision, so a compliant
  agent's plain `fetch --project <slug>` (no explicit `--start`/`--end`,
  the shape `SKILL.md`'s own example shows) resolves to the exact date
  range each scenario's cassette was generated for — regardless of which
  real calendar day the eval actually runs on.

`evals/generate_cassettes.py` builds each scenario's manifest using the
same request-shaping logic the real client code uses (same `cache/
store.py` month-closedness split, same URL encoding), and
`tests/test_eval_scenarios.py` smoke-tests every scenario's cassette
against the real, non-agent `resolve`/`fetch`/`analyze` commands directly —
so a manifest miss during an actual eval run means the model deviated from
the expected call shape (unexpected dates, a paraphrased title), not a
fixture bug. That non-agent smoke test *is* run in the normal test suite
(`uv run pytest`); the LLM-driven harness in this file is not, since it
needs a real model and its output isn't deterministic.
