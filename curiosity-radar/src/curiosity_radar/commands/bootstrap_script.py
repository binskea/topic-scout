"""`bootstrap-script`: generate a self-contained, stdlib-only local pageview
fetcher for a saved project's resolved articles (SPEC.md §3.8).

Exists for the situation SPEC.md §9 item 8 documents: this environment's
egress to Wikimedia can be persistently rate-limited (a shared egress IP
under load) for minutes at a stretch, in which case `fetch` cannot make
progress no matter how long the agent retries. Rather than retry forever,
`SKILL.md` instructs the agent to stop after a few genuine attempts spread
over a few minutes and hand the user a script that fetches the exact same
AQS endpoints from their own machine (normal internet access, no shared
IP) and writes results directly into `cache/store.py`'s own cache layout
— so once the user runs it and returns the resulting `cache/` folder,
`fetch` on the resolved project sees every closed month already cached and
makes zero (or near-zero, for the still-open current month) further
network calls.

The generated script deliberately duplicates (never imports)
`cache/store.py`'s month-key/closed-month/zero-fill logic and
`wikimedia/aqs_client.py`'s URL-building — the same "mirror, not reuse"
approach `evals/generate_cassettes.py` already takes for the same reason:
it has to run with zero project dependencies (stdlib only) on a machine
that may not have `uv`, this repo, or any Python packages installed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from curiosity_radar import project_state
from curiosity_radar.cache import store
from curiosity_radar.cache.paths import resolve_data_dir
from curiosity_radar.commands.fetch import AQS_EARLIEST_DATE
from curiosity_radar.errors import CommandError
from curiosity_radar.schemas import BootstrapScriptResult, DateRange
from curiosity_radar.wikimedia.aqs_client import ACCESS, AGENT, AQS_BASE
from curiosity_radar.wikimedia.http import USER_AGENT

_BODY = """

def slug(component: str) -> str:
    return quote(component, safe="")


def month_key(d: date) -> str:
    return d.strftime("%Y-%m")


def month_bounds(year_month: str) -> tuple[date, date]:
    year_str, month_str = year_month.split("-")
    year, month = int(year_str), int(month_str)
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return start, end


def iter_months(start: date, end: date) -> list[str]:
    months = []
    cur = date(start.year, start.month, 1)
    while cur <= end:
        months.append(month_key(cur))
        cur = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)
    return months


def is_closed_month(year_month: str, today: date, grace_days: int = GRACE_DAYS) -> bool:
    _, month_end = month_bounds(year_month)
    return (today - month_end).days > grace_days


def zero_fill(items: list[dict], start: date, end: date) -> list[dict]:
    by_day = {}
    for item in items:
        ts = item["timestamp"]  # "YYYYMMDD00"
        by_day[date(int(ts[0:4]), int(ts[4:6]), int(ts[6:8]))] = item["views"]
    days = []
    cur = start
    while cur <= end:
        days.append({"date": cur.isoformat(), "views": by_day.get(cur, 0)})
        cur += timedelta(days=1)
    return days


def http_get_json(url: str, retries: int = 5) -> dict:
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = Request(url, headers={"User-Agent": UA})
            with urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 404:
                return {"items": []}  # AQS's "no data for this range" shape
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries:
                wait = 5 * attempt
                print(f"    ...HTTP {exc.code}, retrying in {wait}s ({attempt}/{retries})")
                time.sleep(wait)
                last_err = exc
                continue
            raise
        except URLError as exc:
            if attempt < retries:
                print(f"    ...network error ({exc}), retrying in 5s")
                time.sleep(5)
                last_err = exc
                continue
            raise
    raise RuntimeError(f"giving up after {retries} attempts") from last_err


def fetch_per_article(wiki: str, title: str, start: date, end: date) -> list[dict]:
    url = (
        f"{AQS_BASE}/per-article/{wiki}/{ACCESS}/{AGENT}/{quote(title, safe='')}"
        f"/daily/{start.strftime('%Y%m%d')}/{end.strftime('%Y%m%d')}"
    )
    return http_get_json(url).get("items", [])


def fetch_aggregate(wiki: str, start: date, end: date) -> list[dict]:
    url = (
        f"{AQS_BASE}/aggregate/{wiki}/{ACCESS}/{AGENT}"
        f"/daily/{start.strftime('%Y%m%d')}/{end.strftime('%Y%m%d')}"
    )
    return http_get_json(url).get("items", [])


def save_month(directory: Path, year_month: str, days: list[dict], closed: bool) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    fname = f"{year_month}.json" if closed else "current.json"
    payload = {"year_month": year_month, "days": days}
    (directory / fname).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def ensure_series(wiki: str, article_slot: str, fetch_fn, start: date, end: date) -> None:
    directory = OUT_ROOT / slug(wiki) / slug(article_slot) / "daily"
    for year_month in iter_months(start, end):
        month_start, month_end = month_bounds(year_month)
        closed = is_closed_month(year_month, end)
        target_end = month_end if closed else min(month_end, end)
        closed_file = directory / f"{year_month}.json"
        if closed and closed_file.exists():
            print(f"  {year_month}: already fetched, skipping")
            continue
        print(f"  {year_month} ({'closed' if closed else 'current, will refresh'})...")
        items = fetch_fn(wiki, month_start, target_end)
        days = zero_fill(items, month_start, target_end)
        save_month(directory, year_month, days, closed)
        time.sleep(SLEEP_BETWEEN_REQUESTS)


def main() -> None:
    effective_start = max(START, EARLIEST_DATE)
    if effective_start > START:
        print(
            f"NOTE: requested start {START.isoformat()} predates AQS history; "
            f"clamped to {effective_start.isoformat()}."
        )
    print(f"Date range: {effective_start.isoformat()} .. {END.isoformat()}")
    print()
    print(f"== Per-article pageviews ({len(ARTICLES)} article(s)) ==")
    for wiki, title in ARTICLES:
        print(f"-- {wiki}: {title} --")
        fetch_fn = lambda w, s, e, t=title: fetch_per_article(w, t, s, e)  # noqa: E731
        ensure_series(wiki, title, fetch_fn, effective_start, END)

    print()
    print(f"== Aggregate (site-wide) pageviews, for normalization ({len(WIKIS)} wiki(s)) ==")
    for wiki in WIKIS:
        print(f"-- {wiki} aggregate --")
        ensure_series(wiki, AGGREGATE_SLOT, fetch_aggregate, effective_start, END)

    print()
    archive_path = make_archive(ARCHIVE_STEM, "zip", root_dir=".", base_dir="cache")
    print(f"Done. Zipped everything into: {archive_path}")
    print("Send that file back, or unzip it into your curiosity-radar data-dir's cache/ folder.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\\nInterrupted -- rerun the script, already-fetched closed months are skipped.")
        sys.exit(1)
"""


def _header(
    *,
    project: str,
    generated_at: str,
    ua: str,
    aqs_base: str,
    access: str,
    agent: str,
    grace_days: int,
    aggregate_slot: str,
    earliest_date: str,
    start: str,
    end: str,
    articles: list[tuple[str, str]],
    wikis: list[str],
) -> str:
    archive_stem = project.replace("/", "_")
    return f'''#!/usr/bin/env python3
"""
Local pageview fetcher for curiosity-radar project '{project}'.
Generated {generated_at} by `curiosity-radar bootstrap-script --project {project}`.

No dependencies beyond the Python 3 standard library -- no uv, no git, no
pip install. Run it on a machine with normal (not shared/rate-limited)
internet access. It mirrors curiosity-radar's own cache layout
(cache/raw/<wiki>/<article-slot>/daily/<YYYY-MM>.json, or current.json for
the still-open month, plus a `{aggregate_slot}` slot per wiki used for
normalization) so the output can be dropped straight into this project's
data-dir under cache/ and picked up by `fetch --project {project}` with
zero (or near-zero) further network calls.

Usage:
    python3 {project}_local_fetch.py

When it's done, zip the ./cache/ folder it created (the script also does
this automatically -> ./{archive_stem}_cache.zip) and send that file back.
"""

from __future__ import annotations

import json
import sys
import time
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path
from shutil import make_archive
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

UA = {ua!r}
AQS_BASE = {aqs_base!r}
ACCESS = {access!r}
AGENT = {agent!r}
AGGREGATE_SLOT = {aggregate_slot!r}
GRACE_DAYS = {grace_days!r}  # matches curiosity-radar's cache/store.py
EARLIEST_DATE = date.fromisoformat({earliest_date!r})
OUT_ROOT = Path("./cache/raw")
ARCHIVE_STEM = {archive_stem!r}

# Resolved live by `resolve` and saved in this project's state -- one entry
# per (wiki, article title) actually needed, including a redirect alias
# where one was found (its traffic is tracked separately by AQS).
ARTICLES: list[tuple[str, str]] = {articles!r}
WIKIS: list[str] = {wikis!r}

START = date.fromisoformat({start!r})
END = date.today()
SLEEP_BETWEEN_REQUESTS = 0.3  # be polite; you have no rate-limit problem to worry about
'''


def run(*, project: str, data_dir: Path | None) -> BootstrapScriptResult:
    data_root = resolve_data_dir(data_dir)
    state = project_state.load(data_root, project)
    if state is None:
        raise CommandError(
            "project_not_found",
            f"No saved project '{project}'.",
            "Run resolve --save-as first, or check `project list`.",
        )

    resolved = [
        (lang, article)
        for lang, article in state.articles.items()
        if article.exists and article.title
    ]
    if not resolved:
        raise CommandError(
            "project_not_resolved",
            f"Project '{project}' has no resolved articles yet.",
            "Run resolve --save-as first -- bootstrap-script needs at least one "
            "language with a real article on file, even if fetch never completed.",
        )

    article_entries: list[tuple[str, str]] = []
    for _, article in resolved:
        assert article.title is not None
        article_entries.append((article.wiki, article.title))
        if article.redirect_from:
            article_entries.append((article.wiki, article.redirect_from))
    seen: set[tuple[str, str]] = set()
    articles_ordered: list[tuple[str, str]] = []
    for pair in article_entries:
        if pair not in seen:
            seen.add(pair)
            articles_ordered.append(pair)

    wikis = sorted({article.wiki for _, article in resolved})

    header = _header(
        project=project,
        generated_at=datetime.now(UTC).isoformat(),
        ua=USER_AGENT,
        aqs_base=AQS_BASE,
        access=ACCESS,
        agent=AGENT,
        grace_days=store.GRACE_PERIOD_DAYS,
        aggregate_slot=store.AGGREGATE_SLOT,
        earliest_date=AQS_EARLIEST_DATE.isoformat(),
        start=state.date_range_start,
        end=state.date_range_end,
        articles=articles_ordered,
        wikis=wikis,
    )

    scripts_dir = data_root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    script_path = scripts_dir / f"{project}_local_fetch.py"
    script_path.write_text(header + _BODY)

    instructions = [
        f"Скопіюйте {script_path} на машину зі звичайним "
        "(не спільним/обмеженим) доступом до інтернету.",
        "Там виконайте: python3 <ім'я_файлу>.py -- потрібна лише стандартна бібліотека Python 3, "
        "нічого встановлювати не треба.",
        f"Скрипт створить ./cache/ і сам заархівує її в ./{project}_cache.zip.",
        f"Поверніть цей zip. Розпакуйте його вміст (папку cache/) у {data_root} тут, "
        f"зливши з тим, що вже є -- потім `fetch --project {project}` знайде закриті місяці "
        "вже в кеші (мінімум нових HTTP-запитів) і можна продовжувати analyze/chart/report/verify.",
    ]

    return BootstrapScriptResult(
        project=project,
        script_path=str(script_path),
        languages=[lang for lang, _ in resolved],
        articles_covered=len(articles_ordered),
        date_range=DateRange(start=state.date_range_start, end=state.date_range_end),
        instructions=instructions,
    )
