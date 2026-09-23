"""`TASK.md` example query 1 (verbatim): compare intermittent-fasting
interest growth between pl.wikipedia and cs.wikipedia over the last two
years. Polish is given a clear rising trend; Czech is left roughly flat
with noise — a real difference for the agent's cross-language ranking and
headline verdict to actually reflect, not a contrast that only exists in
the prompt.
"""

from __future__ import annotations

from evals.scenarios import LanguageProfile, Scenario

SCENARIO = Scenario(
    slug="01_intermittent_fasting_pl_cs",
    prompt=(
        "Порівняй зростання інтересу до інтервального голодування в "
        "польськомовній та чеськомовній Wikipedia за останні два роки."
    ),
    fake_today="2026-09-23",
    qid="Q_EVAL_FASTING",
    topic_query="intermittent fasting",
    languages=(
        LanguageProfile(
            lang="pl",
            wiki="pl.wikipedia",
            title="Głodówka przerywana",
            base_views=550.0,
            growth_per_day=0.85,  # ~+560 views/day (roughly doubling) over 730 days
            aggregate_base_views=45_000_000.0,
            aggregate_growth_per_day=1500.0,
            spike_day_offsets=(400,),
            noise_seed=1,
        ),
        LanguageProfile(
            lang="cs",
            wiki="cs.wikipedia",
            title="Přerušovaný půst",
            base_views=180.0,
            growth_per_day=0.02,  # essentially flat
            aggregate_base_views=8_000_000.0,
            aggregate_growth_per_day=200.0,
            spike_day_offsets=(),
            noise_seed=2,
        ),
    ),
)
