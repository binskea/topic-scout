"""Milestone 11 eval harness: drives a real LLM (default: a free OpenRouter
model, per `TASK.md`'s explicit allowance) through the `curiosity-radar`
skill against the 3 `TASK.md` example queries, using cassette-backed data
(`evals/cassettes/`, `CURIOSITY_RADAR_CASSETTE_DIR`) — never live Wikimedia
calls, per `CLAUDE.md`'s testing rules.

Usage:
    export OPENROUTER_API_KEY=...          # required
    uv run python -m evals.run_scenarios                    # all 3 scenarios
    uv run python -m evals.run_scenarios --scenario 02_astronomy_uk
    uv run python -m evals.run_scenarios --model "some/other-model:free"

Each scenario gets an isolated `--data-dir` and a fresh conversation. The
model sees `SKILL.md` verbatim as its system prompt (the same instructions
a real agent invoking this skill would get) plus two tools: `run_command`
(shells out to `uv run curiosity-radar ...` only — nothing else is
permitted) and `read_reference` (reads a file under `references/` or
`SKILL.md` itself, mirroring how an agent would consult
`references/*.md` per `SKILL.md`'s own pointers). The loop ends when the
model replies with no further tool calls, or after `MAX_TURNS` — whichever
comes first.

Full transcripts (every message, tool call, and tool result) and any
generated PDF are saved under `evals/results/<scenario-slug>/`, for the
human review `PLAN.md` Milestone 11 calls for — this harness does not
itself grade a run.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from evals.scenarios import SCENARIOS, Scenario

ROOT = Path(__file__).resolve().parents[1]  # curiosity-radar/
RESULTS_ROOT = ROOT / "evals" / "results"
REFERENCES_ROOT = ROOT / "references"
SKILL_MD = ROOT / "SKILL.md"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# OpenRouter's free-tier lineup churns; this one was confirmed live and
# tool-calling-capable during the Milestone 11 run recorded under
# evals/results/ (2026-09-25). If it 404s or is retired, pick a current
# free, tool-calling model from https://openrouter.ai/models?max_price=0
# and pass --model.
DEFAULT_MODEL = "inclusionai/ling-3.0-flash-sante:free"
MAX_TURNS = 16
COMMAND_TIMEOUT_SECONDS = 60

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Run a curiosity-radar CLI command and get its JSON stdout back. "
                "The command must start with 'uv run curiosity-radar'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": 'e.g. \'uv run curiosity-radar resolve --topic "..." '
                        "--languages pl,cs --save-as my-project'",
                    }
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_reference",
            "description": (
                "Read a skill reference file by its relative path, e.g. "
                "'references/error-catalog.md' or 'SKILL.md'."
            ),
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
]


def _run_command(command: str, *, env: dict[str, str]) -> str:
    # No shell=True: this command text comes from a live, occasionally
    # unreliable free-tier model, so it's parsed into an argv list and
    # matched structurally (first three tokens must be exactly "uv run
    # curiosity-radar") rather than by a string-prefix check, which a
    # shell would happily let something like '... && rm -rf /' slip past.
    try:
        args = shlex.split(command)
    except ValueError:
        args = []
    if args[:3] != ["uv", "run", "curiosity-radar"]:
        return json.dumps(
            {
                "error": {
                    "code": "command_not_allowed",
                    "message": "Only 'uv run curiosity-radar ...' commands may be run here.",
                }
            }
        )
    try:
        result = subprocess.run(
            args,
            shell=False,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return json.dumps({"error": {"code": "timeout", "message": "Command timed out."}})
    except OSError as exc:
        return json.dumps({"error": {"code": "exec_failed", "message": str(exc)}})
    output = result.stdout.strip() or result.stderr.strip()
    return output[:8000]


def _read_reference(path: str) -> str:
    candidate = (ROOT / path).resolve()
    allowed_roots = (REFERENCES_ROOT.resolve(), SKILL_MD.resolve())
    is_allowed = candidate == allowed_roots[1] or (
        candidate.is_relative_to(allowed_roots[0]) and candidate.suffix == ".md"
    )
    if not is_allowed or not candidate.exists():
        return f"Error: '{path}' is not a readable reference file."
    return candidate.read_text()[:20000]


def _call_openrouter(api_key: str, model: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
    response = httpx.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/binskea/topic-scout",
            "X-Title": "curiosity-radar eval",
        },
        json={"model": model, "messages": messages, "tools": TOOLS, "tool_choice": "auto"},
        timeout=120,
    )
    response.raise_for_status()
    body: dict[str, Any] = response.json()
    if "choices" not in body:
        # OpenRouter can return HTTP 200 with an {"error": {...}} body when
        # the upstream free-tier provider is overloaded/rate-limited —
        # observed live during the Milestone 11 run. Fail with the actual
        # provider message instead of a confusing KeyError on 'choices'.
        raise RuntimeError(f"OpenRouter returned no choices: {body.get('error', body)}")
    return body


def _run_scenario(scenario: Scenario, *, api_key: str, model: str) -> dict[str, Any]:
    result_dir = RESULTS_ROOT / scenario.slug
    data_dir = result_dir / "data"
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    env = {
        **os.environ,
        "CURIOSITY_RADAR_CASSETTE_DIR": str(ROOT / "evals" / "cassettes" / scenario.slug),
        "CURIOSITY_RADAR_FAKE_TODAY": scenario.fake_today,
        "CURIOSITY_RADAR_DATA_DIR": str(data_dir),
    }

    system_prompt = (
        "You are an AI agent with access to the curiosity-radar Agent Skill below. "
        "Follow its instructions to answer the user's request, using the run_command "
        "and read_reference tools. Always pass --data-dir "
        f"{data_dir} explicitly on every curiosity-radar command. When you have a "
        "final answer, reply with plain text and no further tool calls.\n\n"
        "--- SKILL.md ---\n" + SKILL_MD.read_text()
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": scenario.prompt},
    ]

    transcript: list[dict[str, Any]] = [{"role": "user", "content": scenario.prompt}]
    commands_run: list[str] = []

    for _turn in range(MAX_TURNS):
        response = _call_openrouter(api_key, model, messages)
        choice = response["choices"][0]
        message = choice["message"]
        messages.append(message)
        transcript.append(message)

        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            break

        for call in tool_calls:
            fn = call["function"]
            args = json.loads(fn["arguments"] or "{}")
            if fn["name"] == "run_command":
                commands_run.append(args.get("command", ""))
                tool_result = _run_command(args.get("command", ""), env=env)
            elif fn["name"] == "read_reference":
                tool_result = _read_reference(args.get("path", ""))
            else:
                tool_result = f"Error: unknown tool '{fn['name']}'."
            tool_message = {
                "role": "tool",
                "tool_call_id": call["id"],
                "content": tool_result,
            }
            messages.append(tool_message)
            transcript.append(tool_message)
    else:
        transcript.append(
            {"role": "system", "content": f"[harness] stopped after {MAX_TURNS} turns"}
        )

    final_answer = next(
        (m.get("content") for m in reversed(messages) if m.get("role") == "assistant"), None
    )

    generated_pdfs = sorted((data_dir / "reports").glob("*.pdf")) if data_dir.exists() else []
    for pdf in generated_pdfs:
        shutil.copy(pdf, result_dir / pdf.name)

    return {
        "scenario": scenario.slug,
        "model": model,
        "prompt": scenario.prompt,
        "generated_at": datetime.now(UTC).isoformat(),
        "commands_run": commands_run,
        "final_answer": final_answer,
        "generated_pdfs": [str(p.relative_to(ROOT)) for p in generated_pdfs],
        "review_criteria": list(scenario.review_criteria),
        "transcript": transcript,
    }


def _write_results(scenario: Scenario, run: dict[str, Any]) -> None:
    result_dir = RESULTS_ROOT / scenario.slug
    result_dir.mkdir(parents=True, exist_ok=True)
    (result_dir / "transcript.json").write_text(json.dumps(run, indent=2))

    command_lines = [f"- `{c}`" for c in run["commands_run"]] or ["(none)"]
    pdf_lines = [f"- `{p}`" for p in run["generated_pdfs"]] or ["(none)"]
    criteria_lines = [f"- [ ] {c}" for c in run["review_criteria"]]
    lines = [
        f"# {scenario.slug}",
        "",
        f"**Model:** {run['model']}  ",
        f"**Run at:** {run['generated_at']}",
        "",
        "## Prompt",
        "",
        run["prompt"],
        "",
        "## Commands run",
        "",
        *command_lines,
        "",
        "## Final answer",
        "",
        run["final_answer"] or "(model never produced a final answer within MAX_TURNS)",
        "",
        "## Generated PDFs",
        "",
        *pdf_lines,
        "",
        "## Review checklist (PLAN.md Milestone 11)",
        "",
        *criteria_lines,
    ]
    (result_dir / "transcript.md").write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", help="Run only this scenario slug.")
    parser.add_argument("--model", default=None, help="OpenRouter model id.")
    args = parser.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print(
            "OPENROUTER_API_KEY is not set. Add it to this environment's settings "
            "(cloud environment menu -> Edit -> API credentials, or as an env var) "
            "and start a new session.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    model = args.model or os.environ.get("CURIOSITY_RADAR_EVAL_MODEL", DEFAULT_MODEL)
    scenarios = [s for s in SCENARIOS if args.scenario in (None, s.slug)]
    if not scenarios:
        print(f"No scenario matches '{args.scenario}'.", file=sys.stderr)
        raise SystemExit(1)

    for scenario in scenarios:
        print(f"=== {scenario.slug} ({model}) ===")
        run = _run_scenario(scenario, api_key=api_key, model=model)
        _write_results(scenario, run)
        print(f"  commands run: {len(run['commands_run'])}")
        print(f"  PDFs: {run['generated_pdfs']}")
        print(f"  -> evals/results/{scenario.slug}/transcript.md")


if __name__ == "__main__":
    main()
