"""Scenario definitions for the Milestone 11 eval — the 3 `TASK.md`
example queries, each with the fixed topic/language/traffic-shape metadata
`evals/generate_cassettes.py` needs to build matching synthetic cassette
data (`evals/cassettes/<slug>/manifest.json`), and `evals/run_scenarios.py`
needs to actually run the scenario and know what to check.

Each scenario pins `fake_today` (consumed via `CURIOSITY_RADAR_FAKE_TODAY`,
see `src/curiosity_radar/clock.py`) so the default 730-day lookback a
compliant agent's `fetch --project <slug>` (no explicit `--start`/`--end`)
resolves to is reproducible regardless of which real calendar day the eval
actually runs on.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LanguageProfile:
    """One language's synthetic pageview shape for a scenario.

    `views(day) ≈ base_views + growth_per_day * day_offset`, plus a small
    weekly wave and noise (see `evals/generate_cassettes.py`), with an
    optional multiplicative spike on specific day offsets — a deliberately
    simple, reproducible-by-seed shape, not an attempt to look like real
    Wikimedia traffic beyond matching AQS's confirmed response shape
    (`references/api-notes.md` §1.1/§1.2).
    """

    lang: str
    wiki: str
    title: str
    base_views: float
    growth_per_day: float
    aggregate_base_views: float
    aggregate_growth_per_day: float = 0.0
    spike_day_offsets: tuple[int, ...] = ()
    noise_seed: int = 0


@dataclass(frozen=True)
class Scenario:
    slug: str
    prompt: str
    fake_today: str  # YYYY-MM-DD
    qid: str
    topic_query: str
    languages: tuple[LanguageProfile, ...]
    review_criteria: tuple[str, ...] = field(
        default=(
            "Follows the intended command sequence "
            "(resolve -> fetch -> analyze -> chart -> report -> verify) "
            "without needing hand-holding beyond what SKILL.md provides.",
            "The final report's numeric claims pass `verify`.",
            "A same-session follow-up tweak stays cheap (no unnecessary "
            "refetching) and produces a coherent updated answer.",
        )
    )


from evals.scenarios import (  # noqa: E402
    scenario_01_intermittent_fasting,
    scenario_02_astronomy_uk,
    scenario_03_english_learning,
)

SCENARIOS: tuple[Scenario, ...] = (
    scenario_01_intermittent_fasting.SCENARIO,
    scenario_02_astronomy_uk.SCENARIO,
    scenario_03_english_learning.SCENARIO,
)
