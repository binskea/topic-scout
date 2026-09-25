"""`bootstrap-script` (SPEC.md §3.8): the escalation path for a persistent
`rate_limited` from `resolve`/`fetch` -- generates a stdlib-only local
fetcher whose cache output must be readable by the real `fetch --project
...` with zero HTTP requests for any already-closed month, exactly as if
`fetch` itself had produced it. That compatibility (not just "the script
runs") is the actual point, so it's exercised end to end below rather than
just asserting the command's own JSON shape.
"""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import httpx
import pytest

from curiosity_radar import project_state
from curiosity_radar.cache import store
from curiosity_radar.commands import bootstrap_script as bootstrap_cmd
from curiosity_radar.commands import fetch as fetch_cmd
from curiosity_radar.errors import CommandError
from curiosity_radar.schemas import ArticleInfo
from curiosity_radar.wikimedia.http import build_client as real_build_client


def _make_project(
    tmp_path: Path, *, slug: str, lang: str, article: ArticleInfo, start: str, end: str
) -> None:
    project_state.create(
        tmp_path,
        slug,
        topic_query="voice training",
        qid="Q1",
        languages=[lang],
        articles={lang: article},
        start=start,
        end=end,
    )


def test_no_saved_project_is_a_clean_error(tmp_path: Path) -> None:
    with pytest.raises(CommandError) as exc:
        bootstrap_cmd.run(project="nope", data_dir=tmp_path)
    assert exc.value.code == "project_not_found"


def test_unresolved_project_is_a_clean_error(tmp_path: Path) -> None:
    _make_project(
        tmp_path,
        slug="demo",
        lang="uk",
        article=ArticleInfo(wiki="uk.wikipedia", exists=False, reason="no_sitelink"),
        start="2024-08-01",
        end="2024-08-31",
    )
    with pytest.raises(CommandError) as exc:
        bootstrap_cmd.run(project="demo", data_dir=tmp_path)
    assert exc.value.code == "project_not_resolved"


def test_generates_a_syntactically_valid_script_covering_redirect_alias(tmp_path: Path) -> None:
    _make_project(
        tmp_path,
        slug="demo",
        lang="cs",
        article=ArticleInfo(
            title="Přerušovaný půst",
            wiki="cs.wikipedia",
            redirect_from="Intermitentní půst",
            exists=True,
        ),
        start="2024-08-01",
        end="2024-08-31",
    )
    result = bootstrap_cmd.run(project="demo", data_dir=tmp_path)
    assert result.articles_covered == 2  # canonical title + redirect alias
    script_path = Path(result.script_path)
    compile(script_path.read_text(), str(script_path), "exec")  # raises SyntaxError if invalid


class _FakeUrlopenResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> _FakeUrlopenResponse:
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


def test_generated_script_cache_output_lets_a_real_fetch_skip_the_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole point of `bootstrap-script`: run the generated script (with
    the network faked here, standing in for the user's own machine), copy
    its `cache/` output into a real data-dir, and prove a real `fetch
    --project ...` treats the closed month as already cached -- zero HTTP
    requests for it, not just "the script happens to run"."""
    article = ArticleInfo(title="Постановка голосу", wiki="uk.wikipedia", exists=True)
    _make_project(
        tmp_path, slug="demo", lang="uk", article=article, start="2024-08-01", end="2024-08-31"
    )
    result = bootstrap_cmd.run(project="demo", data_dir=tmp_path)
    script_path = Path(result.script_path)

    # Execute the generated script's own function definitions (never its
    # network-touching `main()`) against a fake `urlopen` -- the same
    # never-touch-the-live-network substitution CLAUDE.md's testing rules
    # require, just applied to this generated, dependency-free script
    # rather than to `httpx`.
    ns: dict = {"__name__": "bootstrap_script_under_test"}
    exec(compile(script_path.read_text(), str(script_path), "exec"), ns)
    ns["urlopen"] = lambda req, timeout=20: _FakeUrlopenResponse(json.dumps({"items": []}).encode())
    monkeypatch.setattr(ns["time"], "sleep", lambda seconds: None)

    work_dir = tmp_path / "local_machine"
    work_dir.mkdir()
    monkeypatch.chdir(work_dir)

    # Mirrors exactly how the generated script's own `main()` calls
    # `ensure_series` -- `end` doubles as both the iteration bound and the
    # "today" reference `is_closed_month` compares against, since on a real
    # local run `END` is always `date.today()`.
    article_start, today = date(2024, 8, 1), date.today()
    article_fetch = lambda w, s, e: ns["fetch_per_article"](w, "Постановка голосу", s, e)  # noqa: E731
    ns["ensure_series"]("uk.wikipedia", "Постановка голосу", article_fetch, article_start, today)
    ns["ensure_series"](
        "uk.wikipedia", ns["AGGREGATE_SLOT"], ns["fetch_aggregate"], article_start, today
    )

    generated_cache = work_dir / "cache"
    assert generated_cache.exists()

    # Hand-off, exactly as `result.instructions` tells the user to do it:
    # drop the generated `cache/` folder into the real data-dir.
    shutil.copytree(generated_cache, tmp_path / "cache", dirs_exist_ok=True)

    def _forbid_any_request(request: httpx.Request) -> httpx.Response:
        raise AssertionError(
            f"fetch made a live request for an already-cached closed month: {request.url}"
        )

    monkeypatch.setattr(
        fetch_cmd,
        "build_client",
        lambda transport=None: real_build_client(httpx.MockTransport(_forbid_any_request)),
    )

    fetch_result = fetch_cmd.run(
        project="demo",
        topic=None,
        languages=None,
        start=None,
        end=None,
        granularity="daily",
        data_dir=tmp_path,
    )
    assert fetch_result.fetched.http_requests_made == 0
    assert fetch_result.fetched.days_from_cache == fetch_result.fetched.days_requested

    # And the schema really is `cache/store.py`'s own -- not just "some
    # JSON that happens to parse" -- since a real `analyze` reads it too.
    cached = store.load_cached_month(
        store.raw_dir(tmp_path, "uk.wikipedia", "Постановка голосу", "daily"),
        "2024-08",
        closed=True,
    )
    assert cached is not None
    assert len(cached) == 31
