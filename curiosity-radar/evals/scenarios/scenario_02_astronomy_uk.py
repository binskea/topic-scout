"""`TASK.md` example query 2 (verbatim): is interest in astronomy growing
on uk.wikipedia, trustworthy enough to justify adding an astronomy course
to an educational app? Single language, moderate (not explosive) growth —
the interesting case is a real but modest trend, which is exactly where
the Theil-Sen/Mann-Kendall confidence label (and the currently-always-
"insufficient" placebo verdict, see `SKILL.md`'s known-gap note) matters
most to get right in the agent's answer.
"""

from __future__ import annotations

from evals.scenarios import LanguageProfile, Scenario

SCENARIO = Scenario(
    slug="02_astronomy_uk",
    prompt=(
        "Ми думаємо додати курс з астрономії до освітнього застосунку. "
        "Чи зростає інтерес до цієї теми в україномовній Wikipedia, і "
        "наскільки цьому зростанню можна довіряти?"
    ),
    fake_today="2026-09-23",
    qid="Q_EVAL_ASTRONOMY",
    topic_query="astronomy",
    languages=(
        LanguageProfile(
            lang="uk",
            wiki="uk.wikipedia",
            title="Астрономія",
            base_views=260.0,
            growth_per_day=0.12,  # modest, real growth over 730 days
            aggregate_base_views=5_000_000.0,
            aggregate_growth_per_day=100.0,
            spike_day_offsets=(600,),
            noise_seed=3,
        ),
    ),
)
