"""`TASK.md` example query 3, concretized: the original ("compare interest
across the language editions we've chosen") is deliberately abstract about
which editions — a real user's ask never is, so this scenario names three
(es, de, ja) explicitly, matching TASK.md's own framing that examples are
illustrative and real users bring specific topics/languages. Three
distinct trend shapes (strongly rising, flat, moderately rising) give the
agent a genuine three-way ranking to produce and a real basis for "which
audiences to research next."
"""

from __future__ import annotations

from evals.scenarios import LanguageProfile, Scenario

SCENARIO = Scenario(
    slug="03_english_learning_es_de_ja",
    prompt=(
        "Ми створюємо застосунок для вивчення англійської мови. Порівняй "
        "інтерес до вивчення англійської в іспанській (es), німецькій (de) "
        "та японській (ja) мовних розділах Wikipedia та підготуй короткий "
        "звіт: які аудиторії варто дослідити наступними й чому?"
    ),
    fake_today="2026-09-23",
    qid="Q_EVAL_LEARN_ENGLISH",
    topic_query="learning English",
    languages=(
        LanguageProfile(
            lang="es",
            wiki="es.wikipedia",
            title="Aprendizaje del inglés",
            base_views=420.0,
            growth_per_day=0.55,  # strongly rising
            aggregate_base_views=30_000_000.0,
            aggregate_growth_per_day=800.0,
            spike_day_offsets=(250,),
            noise_seed=4,
        ),
        LanguageProfile(
            lang="de",
            wiki="de.wikipedia",
            title="Englischunterricht",
            base_views=300.0,
            growth_per_day=0.0,  # flat
            aggregate_base_views=28_000_000.0,
            aggregate_growth_per_day=500.0,
            spike_day_offsets=(),
            noise_seed=5,
        ),
        LanguageProfile(
            lang="ja",
            wiki="ja.wikipedia",
            title="英語学習",
            base_views=350.0,
            growth_per_day=0.20,  # moderately rising
            aggregate_base_views=20_000_000.0,
            aggregate_growth_per_day=400.0,
            spike_day_offsets=(550,),
            noise_seed=6,
        ),
    ),
)
