"""`resolve` (Milestone 2), cassette-backed per PLAN.md's four required cases:
happy path, ambiguous entity, a language with no sitelink, and a redirect-
chain case — plus the `no_qid_match`/`redirect_resolution_failed` error
paths from SPEC.md §7.

Fixtures reuse Milestone 0's real recordings verbatim wherever the shape
fits (`tests/cassettes/milestone0/`); combinations that milestone didn't
happen to produce (a clean single-candidate search, sitelinks for our own
test languages, a genuine multi-hop redirect chain) are built here to match
the confirmed shapes documented in `references/api-notes.md`, never by
touching the live APIs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _cassette import SequentialCassette

from curiosity_radar.commands import resolve as resolve_cmd
from curiosity_radar.errors import CommandError
from curiosity_radar.wikimedia.http import build_client as real_build_client

CASSETTES = Path(__file__).parent / "cassettes" / "milestone0"


def _load(name: str) -> dict:
    return json.loads((CASSETTES / name).read_text())


def _use_cassette(monkeypatch: pytest.MonkeyPatch, cassette: SequentialCassette) -> None:
    """Override the project-wide fake-network safety net (conftest.py) for one test."""
    monkeypatch.setattr(
        resolve_cmd, "build_client", lambda transport=None: real_build_client(cassette.transport())
    )


def test_resolve_happy_path_all_languages_resolve(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    qid = "Q28865"
    cassette = SequentialCassette(
        [
            (
                {"action": "wbsearchentities", "search": "Python (programming language)"},
                {
                    "searchinfo": {"search": "Python (programming language)"},
                    "search": [
                        {
                            "id": qid,
                            "title": qid,
                            "pageid": 1,
                            "concepturi": f"http://www.wikidata.org/entity/{qid}",
                            "repository": "wikidata",
                            "url": f"//www.wikidata.org/wiki/{qid}",
                            "display": {
                                "label": {"value": "Python", "language": "en"},
                                "description": {"value": "programming language", "language": "en"},
                            },
                            "label": "Python",
                            "description": "programming language",
                            "match": {
                                "type": "label",
                                "language": "en",
                                "text": "Python (programming language)",
                            },
                        }
                    ],
                    "search-continue": 10,
                    "success": 1,
                },
            ),
            (
                {"action": "wbgetentities", "ids": qid},
                {
                    "entities": {
                        qid: {
                            "type": "item",
                            "id": qid,
                            "sitelinks": {
                                "enwiki": {
                                    "site": "enwiki",
                                    "title": "Python (programming language)",
                                    "badges": [],
                                },
                                "plwiki": {
                                    "site": "plwiki",
                                    "title": "Python (język programowania)",
                                    "badges": [],
                                },
                                "cswiki": {
                                    "site": "cswiki",
                                    "title": "Python (programovací jazyk)",
                                    "badges": [],
                                },
                            },
                        }
                    },
                    "success": 1,
                },
            ),
            (
                {"action": "query", "titles": "Python (programming language)"},
                # Real Milestone 0 recording — this exact title, no redirect.
                _load("07a_mediawiki_normal.json"),
            ),
            (
                {"action": "query", "titles": "Python (język programowania)"},
                {
                    "batchcomplete": "",
                    "query": {
                        "pages": {
                            "1": {"pageid": 1, "ns": 0, "title": "Python (język programowania)"}
                        }
                    },
                },
            ),
            (
                {"action": "query", "titles": "Python (programovací jazyk)"},
                {
                    "batchcomplete": "",
                    "query": {
                        "pages": {
                            "1": {"pageid": 1, "ns": 0, "title": "Python (programovací jazyk)"}
                        }
                    },
                },
            ),
        ]
    )
    _use_cassette(monkeypatch, cassette)

    result = resolve_cmd.run(
        topic="Python (programming language)",
        qid=None,
        languages=["en", "pl", "cs"],
        related_qids=[],
        save_as=None,
        data_dir=tmp_path,
    )

    cassette.assert_exhausted()
    assert result.resolved_qid == qid
    assert result.ambiguous is False
    assert result.warnings == []
    assert result.cluster is not None
    assert result.cluster.articles["en"].exists is True
    assert result.cluster.articles["en"].title == "Python (programming language)"
    assert result.cluster.articles["en"].redirect_from is None
    assert result.cluster.articles["pl"].title == "Python (język programowania)"
    assert result.cluster.articles["cs"].title == "Python (programovací jazyk)"


def test_resolve_ambiguous_entity_flagged_not_guessed_silently(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cassette = SequentialCassette(
        [
            (
                {"action": "wbsearchentities", "search": "Mercury"},
                # Real Milestone 0 recording — 7 of its 10 candidates share
                # the exact label "Mercury"/"mercury".
                _load("05_wikidata_search_ambiguous.json"),
            ),
            (
                {"action": "wbgetentities", "ids": "Q613883"},
                {
                    "entities": {
                        "Q613883": {
                            "type": "item",
                            "id": "Q613883",
                            "sitelinks": {
                                "enwiki": {
                                    "site": "enwiki",
                                    "title": "Mercury (automobile)",
                                    "badges": [],
                                }
                            },
                        }
                    },
                    "success": 1,
                },
            ),
            (
                {"action": "query", "titles": "Mercury (automobile)"},
                {
                    "batchcomplete": "",
                    "query": {
                        "pages": {"1": {"pageid": 1, "ns": 0, "title": "Mercury (automobile)"}}
                    },
                },
            ),
        ]
    )
    _use_cassette(monkeypatch, cassette)

    result = resolve_cmd.run(
        topic="Mercury",
        qid=None,
        languages=["en"],
        related_qids=[],
        save_as=None,
        data_dir=tmp_path,
    )

    cassette.assert_exhausted()
    assert result.ambiguous is True
    # The first candidate sharing the exact query label, per server-ranked order.
    assert result.resolved_qid == "Q613883"
    assert len(result.candidates) == 10
    assert any("Multiple Wikidata entities share the label" in w for w in result.warnings)
    assert result.cluster is not None
    assert result.cluster.articles["en"].exists is True


def test_resolve_language_with_no_sitelink_is_not_a_hard_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cassette = SequentialCassette(
        [
            (
                {"action": "wbsearchentities", "search": "Bibliography"},
                {
                    "searchinfo": {"search": "Bibliography"},
                    "search": [
                        {
                            "id": "Q1631107",
                            "title": "Q1631107",
                            "pageid": 1,
                            "concepturi": "http://www.wikidata.org/entity/Q1631107",
                            "repository": "wikidata",
                            "url": "//www.wikidata.org/wiki/Q1631107",
                            "display": {"label": {"value": "Bibliography", "language": "en"}},
                            "label": "Bibliography",
                            "match": {"type": "label", "language": "en", "text": "Bibliography"},
                        }
                    ],
                    "search-continue": 10,
                    "success": 1,
                },
            ),
            (
                {"action": "wbgetentities", "ids": "Q1631107"},
                # Real Milestone 0 recording — no plwiki/ukwiki sitelink present.
                _load("06_wikidata_sitelinks.json"),
            ),
            (
                {"action": "query", "titles": "Literaturverzeichnis"},
                {
                    "batchcomplete": "",
                    "query": {
                        "pages": {"1": {"pageid": 1, "ns": 0, "title": "Literaturverzeichnis"}}
                    },
                },
            ),
        ]
    )
    _use_cassette(monkeypatch, cassette)

    result = resolve_cmd.run(
        topic="Bibliography",
        qid=None,
        languages=["pl", "de"],
        related_qids=[],
        save_as=None,
        data_dir=tmp_path,
    )

    cassette.assert_exhausted()
    assert result.ambiguous is False
    assert result.cluster is not None
    pl_article = result.cluster.articles["pl"]
    assert pl_article.exists is False
    assert pl_article.reason == "no_sitelink"
    assert "pl: no Wikidata sitelink for this QID" in result.warnings
    de_article = result.cluster.articles["de"]
    assert de_article.exists is True
    assert de_article.title == "Literaturverzeichnis"


def test_resolve_redirect_chain_including_a_double_hop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    qid = "Q_EXAMPLE_CHAIN"
    cassette = SequentialCassette(
        [
            (
                {"action": "wbsearchentities", "search": "topic with redirects"},
                {
                    "searchinfo": {"search": "topic with redirects"},
                    "search": [
                        {
                            "id": qid,
                            "title": qid,
                            "pageid": 1,
                            "concepturi": f"http://www.wikidata.org/entity/{qid}",
                            "repository": "wikidata",
                            "url": f"//www.wikidata.org/wiki/{qid}",
                            "display": {
                                "label": {"value": "topic with redirects", "language": "en"}
                            },
                            "label": "topic with redirects",
                            "match": {
                                "type": "label",
                                "language": "en",
                                "text": "topic with redirects",
                            },
                        }
                    ],
                    "search-continue": 10,
                    "success": 1,
                },
            ),
            (
                {"action": "wbgetentities", "ids": qid},
                {
                    "entities": {
                        qid: {
                            "type": "item",
                            "id": qid,
                            "sitelinks": {
                                "enwiki": {"site": "enwiki", "title": "USA", "badges": []},
                                "cswiki": {
                                    "site": "cswiki",
                                    "title": "Intermitentní půst",
                                    "badges": [],
                                },
                            },
                        }
                    },
                    "success": 1,
                },
            ),
            # en: single hop, real Milestone 0 recording (USA -> United States)...
            ({"action": "query", "titles": "USA"}, _load("07b_mediawiki_single_redirect.json")),
            # ...then resolve_title re-queries the reported target to confirm
            # it's stable (no further hop), since a single MediaWiki call was
            # never confirmed live to fully resolve a *chain* (api-notes.md §3).
            (
                {"action": "query", "titles": "United States"},
                {
                    "batchcomplete": "",
                    "query": {"pages": {"1": {"pageid": 1, "ns": 0, "title": "United States"}}},
                },
            ),
            # cs: a genuine double redirect, synthetic (never observed live).
            (
                {"action": "query", "titles": "Intermitentní půst"},
                {
                    "batchcomplete": "",
                    "query": {
                        "redirects": [
                            {"from": "Intermitentní půst", "to": "Přerušovaný půst (dočasný)"}
                        ],
                        "pages": {
                            "1": {"pageid": 1, "ns": 0, "title": "Přerušovaný půst (dočasný)"}
                        },
                    },
                },
            ),
            (
                {"action": "query", "titles": "Přerušovaný půst (dočasný)"},
                {
                    "batchcomplete": "",
                    "query": {
                        "redirects": [
                            {"from": "Přerušovaný půst (dočasný)", "to": "Přerušovaný půst"}
                        ],
                        "pages": {"2": {"pageid": 2, "ns": 0, "title": "Přerušovaný půst"}},
                    },
                },
            ),
            (
                {"action": "query", "titles": "Přerušovaný půst"},
                {
                    "batchcomplete": "",
                    "query": {"pages": {"2": {"pageid": 2, "ns": 0, "title": "Přerušovaný půst"}}},
                },
            ),
        ]
    )
    _use_cassette(monkeypatch, cassette)

    result = resolve_cmd.run(
        topic="topic with redirects",
        qid=None,
        languages=["en", "cs"],
        related_qids=[],
        save_as=None,
        data_dir=tmp_path,
    )

    cassette.assert_exhausted()
    assert result.cluster is not None
    en_article = result.cluster.articles["en"]
    assert en_article.title == "United States"
    assert en_article.redirect_from == "USA"
    cs_article = result.cluster.articles["cs"]
    assert cs_article.title == "Přerušovaný půst"
    assert cs_article.redirect_from == "Intermitentní půst"


def test_resolve_no_qid_match_is_a_clean_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cassette = SequentialCassette(
        [
            (
                {"action": "wbsearchentities", "search": "asdkjfhalskdjfh"},
                {"searchinfo": {"search": "asdkjfhalskdjfh"}, "search": [], "success": 1},
            ),
        ]
    )
    _use_cassette(monkeypatch, cassette)

    with pytest.raises(CommandError) as exc_info:
        resolve_cmd.run(
            topic="asdkjfhalskdjfh",
            qid=None,
            languages=["en"],
            related_qids=[],
            save_as=None,
            data_dir=tmp_path,
        )
    cassette.assert_exhausted()
    assert exc_info.value.code == "no_qid_match"


def test_resolve_redirect_loop_exceeding_max_hops_is_a_clean_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from curiosity_radar.wikimedia.mediawiki_client import MAX_REDIRECT_HOPS

    steps: list[tuple[dict[str, str], dict]] = [
        (
            {"action": "wbgetentities", "ids": "Q_LOOP"},
            {
                "entities": {
                    "Q_LOOP": {
                        "type": "item",
                        "id": "Q_LOOP",
                        "sitelinks": {"enwiki": {"site": "enwiki", "title": "Hop0", "badges": []}},
                    }
                },
                "success": 1,
            },
        )
    ]
    for hop in range(MAX_REDIRECT_HOPS):
        steps.append(
            (
                {"action": "query", "titles": f"Hop{hop}"},
                {
                    "batchcomplete": "",
                    "query": {
                        "redirects": [{"from": f"Hop{hop}", "to": f"Hop{hop + 1}"}],
                        "pages": {"1": {"pageid": 1, "ns": 0, "title": f"Hop{hop + 1}"}},
                    },
                },
            )
        )
    cassette = SequentialCassette(steps)
    _use_cassette(monkeypatch, cassette)

    with pytest.raises(CommandError) as exc_info:
        resolve_cmd.run(
            topic=None,
            qid="Q_LOOP",
            languages=["en"],
            related_qids=[],
            save_as=None,
            data_dir=tmp_path,
        )
    cassette.assert_exhausted()
    assert exc_info.value.code == "redirect_resolution_failed"


def test_resolve_explicit_qid_skips_search(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cassette = SequentialCassette(
        [
            (
                {"action": "wbgetentities", "ids": "Q64"},
                {
                    "entities": {
                        "Q64": {
                            "type": "item",
                            "id": "Q64",
                            "sitelinks": {
                                "enwiki": {"site": "enwiki", "title": "Berlin", "badges": []}
                            },
                        }
                    },
                    "success": 1,
                },
            ),
            (
                {"action": "query", "titles": "Berlin"},
                {
                    "batchcomplete": "",
                    "query": {"pages": {"1": {"pageid": 1, "ns": 0, "title": "Berlin"}}},
                },
            ),
        ]
    )
    _use_cassette(monkeypatch, cassette)

    result = resolve_cmd.run(
        topic=None,
        qid="Q64",
        languages=["en"],
        related_qids=[],
        save_as=None,
        data_dir=tmp_path,
    )

    cassette.assert_exhausted()
    assert result.resolved_qid == "Q64"
    assert result.candidates == []
    assert result.ambiguous is False
