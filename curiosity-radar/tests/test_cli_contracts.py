"""Asserts every command's JSON output against its `schemas.py` model.

`resolve` (Milestone 2), `fetch` (Milestone 3), and `analyze` (Milestone 6)
are real now — see `tests/test_resolve.py`/`test_fetch_and_cache.py`/
`test_analyze.py` for their own behavioral coverage; `chart`/`report`/
`verify` are still stubs (see `commands/*.py`) pending their own
milestones. Either way, these tests only prove the CLI is wired correctly
and every command's output is schema-valid — a schema change that isn't
reflected here is exactly the drift this file exists to catch.
`conftest.py`'s autouse fixture keeps every `resolve`/`fetch` call here off
the live network (`analyze` never touches the network at all).
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from curiosity_radar.cli import app
from curiosity_radar.schemas import (
    AnalyzeResult,
    ChartResult,
    ErrorResponse,
    FetchResult,
    ProjectListResult,
    ProjectShowResult,
    ReportResult,
    ResolveResult,
    VerifyResult,
)

runner = CliRunner()


def invoke(data_dir: Path, *args: str) -> tuple[int, dict]:
    result = runner.invoke(app, [*args, "--data-dir", str(data_dir)])
    assert result.exit_code in (0, 1), result.output
    payload = json.loads(result.output)
    return result.exit_code, payload


def test_resolve_returns_schema_valid_json(tmp_path: Path) -> None:
    code, payload = invoke(
        tmp_path, "resolve", "--topic", "intermittent fasting", "--languages", "pl,cs"
    )
    assert code == 0
    ResolveResult.model_validate(payload)


def test_resolve_help() -> None:
    result = runner.invoke(app, ["resolve", "--help"])
    assert result.exit_code == 0


def test_resolve_without_topic_or_qid_is_a_clean_error(tmp_path: Path) -> None:
    code, payload = invoke(tmp_path, "resolve", "--languages", "en")
    assert code == 1
    ErrorResponse.model_validate(payload)


def test_fetch_bootstraps_a_project_and_returns_schema_valid_json(tmp_path: Path) -> None:
    code, payload = invoke(
        tmp_path,
        "fetch",
        "--project",
        "demo",
        "--topic",
        "intermittent fasting",
        "--languages",
        "pl,cs",
    )
    assert code == 0
    FetchResult.model_validate(payload)


def test_fetch_help() -> None:
    result = runner.invoke(app, ["fetch", "--help"])
    assert result.exit_code == 0


def test_fetch_unknown_project_is_a_clean_error(tmp_path: Path) -> None:
    code, payload = invoke(tmp_path, "fetch", "--project", "nope")
    assert code == 1
    ErrorResponse.model_validate(payload)


def test_analyze_returns_schema_valid_json(tmp_path: Path) -> None:
    invoke(
        tmp_path,
        "resolve",
        "--topic",
        "astronomy",
        "--languages",
        "uk",
        "--save-as",
        "demo",
    )
    code, payload = invoke(tmp_path, "analyze", "--project", "demo")
    assert code == 0
    AnalyzeResult.model_validate(payload)


def test_analyze_help() -> None:
    result = runner.invoke(app, ["analyze", "--help"])
    assert result.exit_code == 0


def test_chart_returns_schema_valid_json(tmp_path: Path) -> None:
    invoke(tmp_path, "resolve", "--topic", "astronomy", "--languages", "uk", "--save-as", "demo")
    code, payload = invoke(tmp_path, "chart", "--project", "demo")
    assert code == 0
    ChartResult.model_validate(payload)


def test_chart_help() -> None:
    result = runner.invoke(app, ["chart", "--help"])
    assert result.exit_code == 0


def test_report_returns_schema_valid_json(tmp_path: Path) -> None:
    invoke(tmp_path, "resolve", "--topic", "astronomy", "--languages", "uk", "--save-as", "demo")
    code, payload = invoke(tmp_path, "report", "--project", "demo")
    assert code == 0
    ReportResult.model_validate(payload)


def test_report_help() -> None:
    result = runner.invoke(app, ["report", "--help"])
    assert result.exit_code == 0


def test_verify_returns_schema_valid_json(tmp_path: Path) -> None:
    invoke(tmp_path, "resolve", "--topic", "astronomy", "--languages", "uk", "--save-as", "demo")
    code, payload = invoke(tmp_path, "verify", "--project", "demo")
    assert code == 0
    VerifyResult.model_validate(payload)


def test_verify_help() -> None:
    result = runner.invoke(app, ["verify", "--help"])
    assert result.exit_code == 0


def test_project_list_show_set_fork_roundtrip(tmp_path: Path) -> None:
    invoke(
        tmp_path,
        "resolve",
        "--topic",
        "learning English",
        "--languages",
        "en,pl",
        "--save-as",
        "demo",
    )

    code, payload = invoke(tmp_path, "project", "list")
    assert code == 0
    ProjectListResult.model_validate(payload)
    assert len(payload["projects"]) == 1

    code, payload = invoke(tmp_path, "project", "show", "--project", "demo")
    assert code == 0
    ProjectShowResult.model_validate(payload)
    assert payload["languages"] == ["en", "pl"]

    code, payload = invoke(tmp_path, "project", "set", "--project", "demo", "--add-language", "cs")
    assert code == 0
    ProjectShowResult.model_validate(payload)
    assert "cs" in payload["languages"]
    assert payload["stale"]["fetch_stale"] is True

    code, payload = invoke(tmp_path, "project", "fork", "--project", "demo", "--as", "demo-fork")
    assert code == 0
    ProjectShowResult.model_validate(payload)
    assert payload["project"] == "demo-fork"


def test_project_show_unknown_project_is_a_clean_error(tmp_path: Path) -> None:
    code, payload = invoke(tmp_path, "project", "show", "--project", "nope")
    assert code == 1
    ErrorResponse.model_validate(payload)


def test_project_help() -> None:
    for args in (["project", "--help"], ["project", "list", "--help"]):
        result = runner.invoke(app, args)
        assert result.exit_code == 0


def test_top_level_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
