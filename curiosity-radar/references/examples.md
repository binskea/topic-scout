# Worked examples — the 3 `TASK.md` queries

Real command sequences and real (trimmed, not fabricated) JSON output for
each of `TASK.md`'s three example asks. Captured by driving the CLI
directly against `evals/`'s synthetic cassette data
(`CURIOSITY_RADAR_CASSETTE_DIR` + `CURIOSITY_RADAR_FAKE_TODAY=2026-09-23`,
see `evals/README.md`) — the same fixtures the Milestone 11 eval harness
uses, not live Wikimedia data. Useful as a concrete reference for the exact
shape each command returns, independent of whether the Milestone 11 eval
has actually been run against a live model yet (`PLAN.md` Milestone 11 —
as of this writing, it hasn't: no model API key is configured in the dev
environment that wrote this).

Every example below reached `verify`'s `"status": "verified"` with zero
mismatches — the anti-hallucination loop working end to end, not just
individual commands succeeding in isolation.

## 1. Compare intermittent-fasting interest: pl vs. cs

> Порівняй зростання інтересу до інтервального голодування в
> польськомовній та чеськомовній Wikipedia за останні два роки.

```
uv run curiosity-radar resolve --topic "intermittent fasting" --languages pl,cs --save-as fasting-pl-cs
uv run curiosity-radar fetch   --project fasting-pl-cs
uv run curiosity-radar analyze --project fasting-pl-cs
uv run curiosity-radar chart   --project fasting-pl-cs
uv run curiosity-radar report  --project fasting-pl-cs
uv run curiosity-radar verify  --project fasting-pl-cs
```

`resolve` finds both languages cleanly, no ambiguity, no missing sitelink:

```json
{
  "ambiguous": false,
  "cluster": {
    "articles": {
      "pl": {"title": "Głodówka przerywana", "wiki": "pl.wikipedia", "exists": true},
      "cs": {"title": "Přerušovaný půst", "wiki": "cs.wikipedia", "exists": true}
    }
  },
  "warnings": []
}
```

`analyze`'s two languages read very differently — this is the point of
comparing them, not a fixture accident: Polish shows a strong, real trend
with one detected spike; Czech is much weaker (real, but far less
confident):

```json
{
  "languages": {
    "pl": {
      "normalized_trend": {
        "theil_sen_slope_per_day": 1.81e-08,
        "mann_kendall": {"trend": "increasing", "p_value": 1.5e-277, "tau": 0.880},
        "confidence_label": "strong evidence of growth"
      },
      "spikes_detected": [{"date": "2025-10-28", "z_mad": 21.05, "share_of_total_views": 0.0088}],
      "data_quality": {"total_days": 731, "sufficient_for_trend": true}
    },
    "cs": {
      "normalized_trend": {
        "theil_sen_slope_per_day": 1.87e-09,
        "mann_kendall": {"trend": "increasing", "p_value": 1.05e-14, "tau": 0.191},
        "confidence_label": "likely growing"
      },
      "spikes_detected": [],
      "data_quality": {"total_days": 731, "sufficient_for_trend": true}
    }
  },
  "cross_language_ranking": [
    {"lang": "pl", "rank": 1, "reason": "strong evidence of growth"},
    {"lang": "cs", "rank": 2, "reason": "likely growing"}
  ]
}
```

`report` → `verify`: one page, 20 numeric claims, all 20 matched.
An answer grounded in this would say: growth is real in both, but
substantially stronger and more confidently established on pl.wikipedia
(strong evidence, one real spike day in late Oct 2025) than cs.wikipedia
(a weaker but still real "likely growing" signal) — plus the standing
caveat that the placebo-basket confidence check isn't live yet (see
`stats-methods.md`), so this reads on Theil-Sen/Mann-Kendall alone.

## 2. Is astronomy interest on uk.wikipedia trustworthy enough to act on?

> Ми думаємо додати курс з астрономії до освітнього застосунку. Чи
> зростає інтерес до цієї теми в україномовній Wikipedia, і наскільки
> цьому зростанню можна довіряти?

```
uv run curiosity-radar resolve --topic "astronomy" --languages uk --save-as astronomy-uk
uv run curiosity-radar fetch   --project astronomy-uk
uv run curiosity-radar analyze --project astronomy-uk
uv run curiosity-radar chart   --project astronomy-uk
uv run curiosity-radar report  --project astronomy-uk
uv run curiosity-radar verify  --project astronomy-uk
```

Single language, real Cyrillic title (`Астрономія`) end to end through
resolve → fetch → the rendered PDF, no encoding issues at any layer:

```json
{
  "normalized_trend": {
    "theil_sen_slope_per_day": 2.28e-08,
    "mann_kendall": {"trend": "increasing", "p_value": 1.27e-147, "tau": 0.640},
    "confidence_label": "strong evidence of growth"
  },
  "spikes_detected": [{"date": "2026-05-16", "z_mad": 49.58, "share_of_total_views": 0.0084}],
  "data_quality": {"total_days": 731, "sufficient_for_trend": true}
}
```

11 numeric claims, all verified, single page (`sections_rendered` omits
`cross_language_ranking` — a single-language report doesn't get one, per
`report-template.md`). The honest answer here: growth reads as strong by
Theil-Sen/Mann-Kendall over the full two years, with one real spike day
that doesn't change the with-spikes-vs-excluding-spikes verdict — but per
`SKILL.md`'s standing disclosure, the placebo-basket cross-check (the
metric `SPEC.md` §5 designed as the most legible "how much to trust this"
signal) isn't sourced live yet, so "trustworthy" should be qualified: the
statistical trend read is solid, the wiki-wide-noise sanity check is not
yet available.

## 3. Compare English-learning interest across es/de/ja and recommend next steps

> Ми створюємо застосунок для вивчення англійської мови. Порівняй
> інтерес до вивчення англійської в іспанській (es), німецькій (de) та
> японській (ja) мовних розділах Wikipedia та підготуй короткий звіт:
> які аудиторії варто дослідити наступними й чому?

(`TASK.md`'s original third example is deliberately abstract about which
language editions — a real user's ask never is, so this worked example
concretizes it with three specific editions; see `evals/README.md`.)

```
uv run curiosity-radar resolve --topic "learning English" --languages es,de,ja --save-as english-es-de-ja
uv run curiosity-radar fetch   --project english-es-de-ja
uv run curiosity-radar analyze --project english-es-de-ja
uv run curiosity-radar chart   --project english-es-de-ja
uv run curiosity-radar report  --project english-es-de-ja
uv run curiosity-radar verify  --project english-es-de-ja
```

Three languages, three genuinely different verdicts — exactly the kind of
spread a "which audiences next" recommendation needs to be grounded in
something real, not a coin flip:

```json
{
  "cross_language_ranking": [
    {"lang": "es", "rank": 1, "reason": "strong evidence of growth"},
    {"lang": "ja", "rank": 2, "reason": "strong evidence of growth"},
    {"lang": "de", "rank": 3, "reason": "no clear trend detected"}
  ]
}
```

`chart` renders 6 files here (3 `trend`, 2 `spike` — es and ja each had a
detected spike, de had none — and 1 `cross_language_bar`), though `report`
only embeds the 3 `trend` PNGs (see `report-template.md`'s note that
`spike`/`cross_language_bar` PNGs aren't embedded — the ranking section is
the text-list variant instead). 29 numeric claims, all verified. A grounded
answer: es and ja both show strong, real growth (es more so) and are worth
prioritizing for follow-up research; de currently reads as flat — not
necessarily "no opportunity," but not evidenced by Wikipedia readership
right now, worth re-checking later rather than deprioritizing outright
given a single flat two-year read.

## Reproducing these yourself

```
export CURIOSITY_RADAR_CASSETTE_DIR=<repo>/curiosity-radar/evals/cassettes/01_intermittent_fasting_pl_cs
export CURIOSITY_RADAR_FAKE_TODAY=2026-09-23
export CURIOSITY_RADAR_DATA_DIR=/tmp/whatever
uv run curiosity-radar resolve --topic "intermittent fasting" --languages pl,cs \
  --save-as fasting-pl-cs --qid Q_EVAL_FASTING
# ...then fetch/analyze/chart/report/verify as above.
```

`--qid` bypasses the live Wikidata search step (`wbsearchentities`),
useful when reproducing by hand since the eval cassettes wildcard that one
call's `search` text anyway (see `evals/README.md`) — omitting `--qid` and
passing any `--topic` text works too, and is closer to how a real agent
would call `resolve`. Swap the cassette dir / QID / languages per §1-3
above for the other two scenarios (`02_astronomy_uk`,
`03_english_learning_es_de_ja`).
