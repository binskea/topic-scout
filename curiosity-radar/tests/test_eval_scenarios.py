"""Smoke-tests the Milestone 11 eval fixtures themselves (`evals/scenarios/`
+ `evals/cassettes/`) — not the LLM-driven harness (`evals/run_scenarios.py`,
which needs a real model and isn't run in CI), but the deterministic,
non-agent half: that each scenario's generated cassette manifest actually
lets the real `resolve`/`fetch`/`analyze` commands complete against
`CURIOSITY_RADAR_CASSETTE_DIR` + `CURIOSITY_RADAR_FAKE_TODAY`, the same way
an eval-driven agent's shelled-out CLI calls would.

Guards against the generator (`evals/generate_cassettes.py`) and the real
client code (`wikimedia/*_client.py`, `cache/store.py`) silently drifting
apart — e.g. a URL-building change in `aqs_client.py` that the generator's
own copy of that logic doesn't get updated to match.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from curiosity_radar.commands import analyze as analyze_cmd
from curiosity_radar.commands import fetch as fetch_cmd
from curiosity_radar.commands import resolve as resolve_cmd
from curiosity_radar.wikimedia.http import CASSETTE_DIR_ENV
from curiosity_radar.wikimedia.http import build_client as real_build_client
from evals.scenarios import SCENARIOS

CASSETTES_ROOT = Path(__file__).parent.parent / "evals" / "cassettes"


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.slug)
def test_scenario_cassette_supports_the_full_resolve_fetch_analyze_chain(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, scenario
) -> None:
    cassette_dir = CASSETTES_ROOT / scenario.slug
    assert (cassette_dir / "manifest.json").exists(), (
        f"missing cassette for {scenario.slug} — run `uv run python -m evals.generate_cassettes`"
    )
    monkeypatch.setenv(CASSETTE_DIR_ENV, str(cassette_dir))
    monkeypatch.setenv("CURIOSITY_RADAR_FAKE_TODAY", scenario.fake_today)
    # Undo tests/conftest.py's autouse generic fake-network fixture for
    # this test only — it exists so *other* tests' incidental resolve/
    # fetch calls stay network-free without caring about their content;
    # here we specifically want the real `build_client`, so it picks up
    # CURIOSITY_RADAR_CASSETTE_DIR instead of the generic fake.
    monkeypatch.setattr(resolve_cmd, "build_client", real_build_client)
    monkeypatch.setattr(fetch_cmd, "build_client", real_build_client)

    languages = [p.lang for p in scenario.languages]
    resolved = resolve_cmd.run(
        topic=scenario.topic_query,
        qid=scenario.qid,
        languages=languages,
        related_qids=[],
        save_as=scenario.slug,
        data_dir=tmp_path,
    )
    assert resolved.cluster is not None
    for profile in scenario.languages:
        article = resolved.cluster.articles[profile.lang]
        assert article.exists is True
        assert article.title == profile.title

    fetched = fetch_cmd.run(
        project=scenario.slug,
        topic=None,
        languages=None,
        start=None,
        end=None,
        granularity="daily",
        data_dir=tmp_path,
    )
    assert set(fetched.coverage) == set(languages)
    assert not fetched.warnings

    analyzed = analyze_cmd.run(
        project=scenario.slug,
        compare_languages=True,
        placebo_basket_size=20,
        force_recompute=True,
        data_dir=tmp_path,
    )
    for profile in scenario.languages:
        lang_result = analyzed.languages[profile.lang]
        assert lang_result.data_quality.sufficient_for_trend is True
        # A meaningfully positive growth_per_day should read as an
        # increasing (not flat/decreasing) trend — a real check that the
        # generator's synthetic shape actually lands where intended, not
        # just that the command chain didn't crash.
        if profile.growth_per_day > 0.1:
            assert lang_result.normalized_trend.mann_kendall.trend == "increasing"
