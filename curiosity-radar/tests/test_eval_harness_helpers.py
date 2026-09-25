"""Guards on `evals/run_scenarios.py`'s two tool implementations — the
harness hands these to a live, occasionally-unreliable free model, so the
command allowlist and the reference-path traversal guard are worth their
own direct tests rather than only being exercised incidentally by a real
(non-deterministic, not-CI-run) eval pass.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest

from evals.run_scenarios import _call_openrouter, _read_reference, _run_command

_REAL_ENV = dict(os.environ)


def test_run_command_rejects_anything_not_starting_with_the_cli() -> None:
    result = json.loads(_run_command("rm -rf /", env={}))
    assert result["error"]["code"] == "command_not_allowed"


def test_run_command_rejects_a_prefix_trick() -> None:
    # Starts with the right words but isn't actually invoking the CLI as
    # its own command — shell metacharacters tacked on after it.
    result = json.loads(_run_command("echo 'uv run curiosity-radar'; rm -rf /", env={}))
    assert result["error"]["code"] == "command_not_allowed"


def test_run_command_does_not_let_shell_metacharacters_chain_a_second_command(
    tmp_path: Path,
) -> None:
    # A naive string-prefix check under shell=True would let this slip
    # through — it genuinely starts with the allowed command text, and
    # only a real shell interprets '&&' as chaining to a second command.
    # _run_command uses shell=False (argv passed directly, no shell in the
    # loop at all), so '&&'/the marker path are just inert literal
    # arguments to the curiosity-radar CLI — nothing here should ever
    # delete the marker file.
    marker = tmp_path / "marker.txt"
    marker.write_text("still here")
    _run_command(f"uv run curiosity-radar --help && rm {marker}", env=_REAL_ENV)
    assert marker.exists()


def test_run_command_rejects_unparseable_shell_syntax() -> None:
    result = json.loads(_run_command('uv run curiosity-radar --topic "unterminated', env={}))
    assert result["error"]["code"] == "command_not_allowed"


def test_run_command_allows_the_cli_itself() -> None:
    output = _run_command("uv run curiosity-radar --help", env=_REAL_ENV)
    assert "command_not_allowed" not in output


def test_read_reference_allows_a_references_markdown_file() -> None:
    content = _read_reference("references/error-catalog.md")
    assert "error.code" in content or "Error catalog" in content


def test_read_reference_allows_skill_md() -> None:
    content = _read_reference("SKILL.md")
    assert "curiosity-radar" in content


def test_read_reference_rejects_path_traversal_outside_references() -> None:
    result = _read_reference("../../../etc/passwd")
    assert result.startswith("Error:")


def test_read_reference_rejects_a_non_markdown_file_even_under_references() -> None:
    result = _read_reference("references/../pyproject.toml")
    assert result.startswith("Error:")


def test_read_reference_rejects_a_nonexistent_file() -> None:
    result = _read_reference("references/does-not-exist.md")
    assert result.startswith("Error:")


def test_call_openrouter_raises_on_an_http_200_provider_error_body(monkeypatch) -> None:
    # OpenRouter's free-tier providers can return HTTP 200 with an
    # {"error": {...}} body instead of "choices" when overloaded/rate-
    # limited (observed live running Milestone 11 against a free model) —
    # this must fail loudly with the provider's own message, not a bare
    # KeyError on 'choices'.
    def fake_post(*_args: object, **_kwargs: object) -> httpx.Response:
        return httpx.Response(
            200,
            json={"error": {"message": "Upstream error from Nvidia: Service overloaded"}},
            request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(RuntimeError, match="Service overloaded"):
        _call_openrouter("fake-key", "fake-model", [])
