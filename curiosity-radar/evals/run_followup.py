"""Continue an already-run `evals.run_scenarios` conversation with one more
user turn, to exercise PLAN.md Milestone 11 criterion (c): a same-session
follow-up tweak stays cheap (no unnecessary refetching) and produces a
coherent updated answer.

`run_scenarios.py` runs each scenario as a single fresh conversation and
does not itself send a follow-up turn (`evals/README.md` calls this "worth
trying by hand"); this script is that by-hand step, made reproducible: it
reloads a scenario's saved `transcript.json`, appends a new user message,
and continues the tool-calling loop against the *same* `--data-dir` and
cassette/fake-today environment, so cached raw pageview data is available
and a compliant answer should not need `fetch` again.

Usage:
    export OPENROUTER_API_KEY=...
    uv run curiosity-radar --data-dir ... resolve/fetch/...   # or just:
    uv run python -m evals.run_scenarios --scenario 02_astronomy_uk  # base run first
    uv run python -m evals.run_followup --scenario 02_astronomy_uk \\
        --prompt "Виключи спайк ... і скажи, чи висновок тримається."

Writes `evals/results/<scenario-slug>/followup_transcript.json` and prints
the commands the model issued plus its final answer.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from evals.run_scenarios import DEFAULT_MODEL as _DEFAULT_MODEL
from evals.run_scenarios import MAX_TURNS as _MAX_TURNS
from evals.run_scenarios import (
    RESULTS_ROOT,
    ROOT,
    SKILL_MD,
    _call_openrouter,
    _read_reference,
    _run_command,
)
from evals.scenarios import SCENARIOS


def _run_followup(*, scenario_slug: str, prompt: str, api_key: str, model: str) -> dict:
    scenario = next((s for s in SCENARIOS if s.slug == scenario_slug), None)
    if scenario is None:
        raise SystemExit(f"No scenario matches '{scenario_slug}'.")

    result_dir = RESULTS_ROOT / scenario.slug
    data_dir = result_dir / "data"
    base_transcript_path = result_dir / "transcript.json"
    if not data_dir.exists() or not base_transcript_path.exists():
        raise SystemExit(
            f"No base run found for '{scenario.slug}' — run "
            f"`uv run python -m evals.run_scenarios --scenario {scenario.slug}` first."
        )

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
    prior_transcript = json.loads(base_transcript_path.read_text())["transcript"]
    messages: list[dict] = [{"role": "system", "content": system_prompt}, *prior_transcript]
    messages.append({"role": "user", "content": prompt})

    transcript: list[dict] = [{"role": "user", "content": prompt}]
    commands_run: list[str] = []

    for _turn in range(_MAX_TURNS):
        response = _call_openrouter(api_key, model, messages)
        message = response["choices"][0]["message"]
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
            tool_message = {"role": "tool", "tool_call_id": call["id"], "content": tool_result}
            messages.append(tool_message)
            transcript.append(tool_message)

    final_answer = next(
        (m.get("content") for m in reversed(messages) if m.get("role") == "assistant"), None
    )
    refetched = any(" fetch " in f" {c} " or c.rstrip().endswith(" fetch") for c in commands_run)

    run = {
        "scenario": scenario.slug,
        "model": model,
        "followup_prompt": prompt,
        "commands_run": commands_run,
        "refetched": refetched,
        "final_answer": final_answer,
        "transcript": transcript,
    }
    (result_dir / "followup_transcript.json").write_text(json.dumps(run, indent=2))
    return run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True, help="Scenario slug with a base run.")
    parser.add_argument("--prompt", required=True, help="The follow-up user message.")
    parser.add_argument("--model", default=None, help="OpenRouter model id.")
    args = parser.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("OPENROUTER_API_KEY is not set.", file=sys.stderr)
        raise SystemExit(1)

    model = args.model or os.environ.get("CURIOSITY_RADAR_EVAL_MODEL", _DEFAULT_MODEL)
    run = _run_followup(
        scenario_slug=args.scenario, prompt=args.prompt, api_key=api_key, model=model
    )

    print(f"=== follow-up: {run['scenario']} ({model}) ===")
    for c in run["commands_run"]:
        print(f"  - {c}")
    print(f"  refetched: {run['refetched']}")
    print(f"  -> evals/results/{run['scenario']}/followup_transcript.json")
    print()
    print(run["final_answer"] or "(model never produced a final answer within MAX_TURNS)")


if __name__ == "__main__":
    main()
