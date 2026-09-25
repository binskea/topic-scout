"""`report` + `verify` (Milestone 8), cassette-free — both commands work
entirely from `cache/raw/` fixtures written directly, exactly like
`test_analyze.py`/`test_chart.py`.

Per PLAN.md's definition of done: both renderer implementations produce a
real one-page PDF from the same derived JSON (not just one working path),
`--engine auto` falls back to fpdf2 when WeasyPrint can't actually render
(not just when it fails to import), and `verify` is proven against a
deliberately-broken case, not just the happy path.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from pypdf import PdfReader

from curiosity_radar import project_state
from curiosity_radar.cache import store
from curiosity_radar.commands import report as report_cmd
from curiosity_radar.commands import verify as verify_cmd
from curiosity_radar.errors import CommandError
from curiosity_radar.schemas import ArticleInfo

START = date(2024, 6, 1)
END = date(2024, 8, 31)  # 92 days, safely closed


def _write_series(
    data_root: Path, wiki: str, slot: str, start: date, end: date, views_for_day
) -> None:
    for year_month in store.iter_months(start, end):
        month_start, month_end = store.month_bounds(year_month)
        days = []
        d = month_start
        while d <= month_end:
            days.append(store.DayPoint(date=d.isoformat(), views=views_for_day(d)))
            d += timedelta(days=1)
        store.save_month(
            store.raw_dir(data_root, wiki, slot, "daily"), year_month, days, closed=True
        )


def _rising(base: int = 100, step: int = 5, spike_days: tuple[int, ...] = (10, 45, 80)):
    def _views(d: date) -> int:
        offset = (d - START).days
        value = base + step * offset
        return value + 4000 if offset in spike_days else value

    return _views


def _flat(value: int = 100_000):
    return lambda _d: value


def _make_project(
    tmp_path: Path,
    *,
    slug: str = "demo",
    lang: str = "en",
    related_search_terms: list[str] | None = None,
) -> None:
    _write_series(tmp_path, "en.wikipedia", "Growing_Topic", START, END, _rising())
    _write_series(tmp_path, "en.wikipedia", store.AGGREGATE_SLOT, START, END, _flat())
    project_state.create(
        tmp_path,
        slug,
        topic_query="growing topic",
        qid="Q_EXAMPLE",
        languages=[lang],
        articles={lang: ArticleInfo(title="Growing_Topic", wiki="en.wikipedia", exists=True)},
        related_search_terms=related_search_terms,
        start=START.isoformat(),
        end=END.isoformat(),
    )


@pytest.mark.parametrize("engine", ["fpdf2", "weasyprint"])
def test_report_renders_exactly_one_page_for_both_engines(tmp_path: Path, engine: str) -> None:
    _make_project(tmp_path)
    result = report_cmd.run(
        project="demo", out=None, audience_note=None, engine=engine, data_dir=tmp_path
    )
    assert result.engine_used == engine
    assert result.page_count == 1
    assert Path(result.pdf_path).exists()
    assert len(result.sections_rendered) > 0
    assert result.numeric_claims_count > 0
    # Cross-check against the actual file, not just the reported count.
    assert len(PdfReader(result.pdf_path).pages) == 1


def test_report_default_engine_prefers_weasyprint_when_it_actually_renders(tmp_path: Path) -> None:
    _make_project(tmp_path)
    result = report_cmd.run(
        project="demo", out=None, audience_note=None, engine="auto", data_dir=tmp_path
    )
    assert result.engine_used == "weasyprint"
    assert result.page_count == 1


def test_report_auto_falls_back_to_fpdf2_when_weasyprint_render_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Simulate a Cairo/Pango-level render failure, not just a missing
    # import (SPEC.md §9 item 9's exact concern) — the *import* succeeds,
    # but calling into WeasyPrint raises.
    import curiosity_radar.report.weasyprint_renderer as weasyprint_mod

    def _boom(self, context, out_path):
        raise RuntimeError("simulated native library failure")

    monkeypatch.setattr(weasyprint_mod.WeasyPrintRenderer, "render", _boom)

    _make_project(tmp_path)
    result = report_cmd.run(
        project="demo", out=None, audience_note=None, engine="auto", data_dir=tmp_path
    )
    assert result.engine_used == "fpdf2"
    assert result.page_count == 1
    assert Path(result.pdf_path).exists()


def test_report_explicit_weasyprint_does_not_silently_fall_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import curiosity_radar.report.weasyprint_renderer as weasyprint_mod

    def _boom(self, context, out_path):
        raise RuntimeError("simulated native library failure")

    monkeypatch.setattr(weasyprint_mod.WeasyPrintRenderer, "render", _boom)

    _make_project(tmp_path)
    with pytest.raises(RuntimeError):
        report_cmd.run(
            project="demo", out=None, audience_note=None, engine="weasyprint", data_dir=tmp_path
        )


def test_report_unknown_engine_is_a_clean_error(tmp_path: Path) -> None:
    _make_project(tmp_path)
    with pytest.raises(CommandError) as exc_info:
        report_cmd.run(
            project="demo", out=None, audience_note=None, engine="bogus", data_dir=tmp_path
        )
    assert exc_info.value.code == "unknown_engine"


def test_report_unknown_project_is_a_clean_error(tmp_path: Path) -> None:
    with pytest.raises(CommandError) as exc_info:
        report_cmd.run(
            project="nope", out=None, audience_note=None, engine="auto", data_dir=tmp_path
        )
    assert exc_info.value.code == "project_not_found"


@pytest.mark.parametrize("engine", ["fpdf2", "weasyprint"])
def test_verify_passes_on_a_freshly_rendered_report(tmp_path: Path, engine: str) -> None:
    _make_project(tmp_path)
    report_cmd.run(project="demo", out=None, audience_note=None, engine=engine, data_dir=tmp_path)

    result = verify_cmd.run(project="demo", pdf=None, data_dir=tmp_path)

    assert result.status == "verified"
    assert result.claims_mismatched == 0
    assert result.claims_checked > 0
    assert result.claims_checked == result.claims_matched
    assert result.mismatches == []


def test_verify_catches_a_deliberately_broken_template(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import curiosity_radar.report.fpdf2_renderer as fpdf2_mod
    import curiosity_radar.report.render as render_mod

    real_build_claims = render_mod.build_claims

    def _tampered(context):
        claims = real_build_claims(context)
        # Corrupt exactly one claim's *rendered* value — simulating a
        # template bug where the printed number disagrees with the JSON.
        claims[2].value = "9999.999999"
        return claims

    _make_project(tmp_path)
    with monkeypatch.context() as m:
        m.setattr(fpdf2_mod, "build_claims", _tampered)
        report_cmd.run(
            project="demo", out=None, audience_note=None, engine="fpdf2", data_dir=tmp_path
        )

    # verify recomputes claims fresh (unpatched) and must catch the mismatch.
    result = verify_cmd.run(project="demo", pdf=None, data_dir=tmp_path)

    assert result.status == "failed_verification"
    assert result.claims_mismatched >= 1
    assert result.claims_checked > result.claims_matched
    assert any(
        m.expected != "9999.999999" and m.found_in_pdf == "9999.999999" for m in result.mismatches
    )


def test_verify_without_a_prior_report_is_a_clean_error(tmp_path: Path) -> None:
    _make_project(tmp_path)
    with pytest.raises(CommandError) as exc_info:
        verify_cmd.run(project="demo", pdf=None, data_dir=tmp_path)
    assert exc_info.value.code == "no_report_found"


def test_verify_missing_pdf_file_is_a_clean_error(tmp_path: Path) -> None:
    _make_project(tmp_path)
    with pytest.raises(CommandError) as exc_info:
        verify_cmd.run(project="demo", pdf=tmp_path / "nonexistent.pdf", data_dir=tmp_path)
    assert exc_info.value.code == "pdf_not_found"


def test_verify_unknown_project_is_a_clean_error(tmp_path: Path) -> None:
    with pytest.raises(CommandError) as exc_info:
        verify_cmd.run(project="nope", pdf=None, data_dir=tmp_path)
    assert exc_info.value.code == "project_not_found"


def test_report_multi_language_includes_cross_language_ranking(tmp_path: Path) -> None:
    _write_series(
        tmp_path, "pl.wikipedia", "Strong_Topic", START, END, _rising(step=50, spike_days=())
    )
    _write_series(tmp_path, "pl.wikipedia", store.AGGREGATE_SLOT, START, END, _flat())
    _write_series(
        tmp_path, "cs.wikipedia", "Weak_Topic", START, END, _rising(step=1, spike_days=())
    )
    _write_series(tmp_path, "cs.wikipedia", store.AGGREGATE_SLOT, START, END, _flat())
    project_state.create(
        tmp_path,
        "cmp",
        topic_query="comparison topic",
        qid="Q_EXAMPLE",
        languages=["pl", "cs"],
        articles={
            "pl": ArticleInfo(title="Strong_Topic", wiki="pl.wikipedia", exists=True),
            "cs": ArticleInfo(title="Weak_Topic", wiki="cs.wikipedia", exists=True),
        },
        start=START.isoformat(),
        end=END.isoformat(),
    )

    result = report_cmd.run(
        project="cmp", out=None, audience_note=None, engine="fpdf2", data_dir=tmp_path
    )
    assert result.page_count == 1
    assert "cross_language_ranking" in result.sections_rendered

    verify_result = verify_cmd.run(project="cmp", pdf=None, data_dir=tmp_path)
    assert verify_result.status == "verified"


@pytest.mark.parametrize("engine", ["fpdf2", "weasyprint"])
def test_report_includes_related_search_terms_section(tmp_path: Path, engine: str) -> None:
    # Top 10 Wikidata aliases, some deliberately long, to also prove this
    # new section doesn't push the report past one page (SPEC.md §6).
    terms = [f"alternate phrasing number {i} for the growing topic" for i in range(10)]
    _make_project(tmp_path, related_search_terms=terms)

    result = report_cmd.run(
        project="demo", out=None, audience_note=None, engine=engine, data_dir=tmp_path
    )
    assert result.page_count == 1
    assert "related_search_terms" in result.sections_rendered

    text = PdfReader(result.pdf_path).pages[0].extract_text() or ""
    assert terms[0] in text
    assert terms[-1] in text

    # Not a numeric claim: verify never checks it, but must still pass.
    verify_result = verify_cmd.run(project="demo", pdf=None, data_dir=tmp_path)
    assert verify_result.status == "verified"


@pytest.mark.parametrize("engine", ["fpdf2", "weasyprint"])
def test_report_related_search_terms_falls_back_gracefully_when_none_found(
    tmp_path: Path, engine: str
) -> None:
    _make_project(tmp_path, related_search_terms=[])

    result = report_cmd.run(
        project="demo", out=None, audience_note=None, engine=engine, data_dir=tmp_path
    )
    assert result.page_count == 1
    assert "related_search_terms" in result.sections_rendered

    text = PdfReader(result.pdf_path).pages[0].extract_text() or ""
    assert "No alternate phrasings found in Wikidata for this topic." in text


@pytest.mark.parametrize("engine", ["fpdf2", "weasyprint"])
def test_report_handles_a_non_latin_script_topic(tmp_path: Path, engine: str) -> None:
    # SPEC.md §9 item 7: a Cyrillic topic (the Ukrainian TASK.md example)
    # must not crash the renderer — this is exactly the class of bug a
    # core Helvetica/Latin-1-only font hits (it doesn't have the glyphs).
    _write_series(tmp_path, "uk.wikipedia", "Астрономія", START, END, _rising())
    _write_series(tmp_path, "uk.wikipedia", store.AGGREGATE_SLOT, START, END, _flat())
    project_state.create(
        tmp_path,
        "uk-demo",
        topic_query="Астрономія",
        qid="Q_EXAMPLE",
        languages=["uk"],
        articles={"uk": ArticleInfo(title="Астрономія", wiki="uk.wikipedia", exists=True)},
        start=START.isoformat(),
        end=END.isoformat(),
    )

    result = report_cmd.run(
        project="uk-demo", out=None, audience_note=None, engine=engine, data_dir=tmp_path
    )
    assert result.page_count == 1

    verify_result = verify_cmd.run(project="uk-demo", pdf=None, data_dir=tmp_path)
    assert verify_result.status == "verified"
