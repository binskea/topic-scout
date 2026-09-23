"""Raw pageview cache: key scheme, read/write, closed-month logic (SPEC.md §4).

Cache key is `(wiki, article-title-post-redirect, granularity, calendar
month)` — **not** keyed by our own saved-project slug, so two saved
projects that happen to reference the same wiki article naturally share
one cached file instead of duplicating fetches (SPEC.md §4: "overlapping
requests across projects/date-ranges/follow-ups naturally share files").
The project-aggregate series reuses the same scheme under a reserved
`_aggregate` article slot.

A closed month's file is written once and never re-fetched automatically;
the current (and, while inside the grace window, still-settling) month is
always refetched into `current.json`, overwriting it in place.
"""

from __future__ import annotations

import json
from calendar import monthrange
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

GRACE_PERIOD_DAYS = 2  # [UNVERIFIED-LIVE] placeholder for AQS's exact data-settling lag
AGGREGATE_SLOT = "_aggregate"


@dataclass
class DayPoint:
    date: str  # YYYY-MM-DD
    views: int


FetchRange = Callable[[date, date], Awaitable[list[dict]]]


def _slug(component: str) -> str:
    """Percent-encode a wiki/article-title component into one safe path segment."""
    return quote(component, safe="")


def raw_dir(data_dir: Path, wiki: str, article_slot: str, granularity: str) -> Path:
    return data_dir / "cache" / "raw" / _slug(wiki) / _slug(article_slot) / granularity


def month_key(d: date) -> str:
    return d.strftime("%Y-%m")


def month_bounds(year_month: str) -> tuple[date, date]:
    year_str, month_str = year_month.split("-")
    year, month = int(year_str), int(month_str)
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return start, end


def is_closed_month(year_month: str, *, today: date, grace_days: int = GRACE_PERIOD_DAYS) -> bool:
    _, month_end = month_bounds(year_month)
    return (today - month_end).days > grace_days


def iter_months(start: date, end: date) -> list[str]:
    months = []
    cur = date(start.year, start.month, 1)
    while cur <= end:
        months.append(month_key(cur))
        cur = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)
    return months


def _month_file(directory: Path, year_month: str, *, closed: bool) -> Path:
    return directory / (f"{year_month}.json" if closed else "current.json")


def load_cached_month(directory: Path, year_month: str, *, closed: bool) -> list[DayPoint] | None:
    path = _month_file(directory, year_month, closed=closed)
    if not path.exists():
        return None
    payload = json.loads(path.read_text())
    return [DayPoint(**d) for d in payload["days"]]


def save_month(directory: Path, year_month: str, days: list[DayPoint], *, closed: bool) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    path = _month_file(directory, year_month, closed=closed)
    payload = {"year_month": year_month, "days": [{"date": d.date, "views": d.views} for d in days]}
    path.write_text(json.dumps(payload, indent=2))


def zero_fill(items: list[dict], start: date, end: date) -> list[DayPoint]:
    """Turn AQS's items (only days with data, per confirmed behavior) into a
    complete daily series over [start, end], filling any omitted day with 0."""
    views_by_day: dict[date, int] = {}
    for item in items:
        ts = item["timestamp"]  # "YYYYMMDD00"
        views_by_day[date(int(ts[0:4]), int(ts[4:6]), int(ts[6:8]))] = item["views"]
    days = []
    cur = start
    while cur <= end:
        days.append(DayPoint(date=cur.isoformat(), views=views_by_day.get(cur, 0)))
        cur += timedelta(days=1)
    return days


async def ensure_series(
    data_dir: Path,
    *,
    wiki: str,
    article_slot: str,
    granularity: str,
    start: date,
    end: date,
    today: date,
    fetch_range: FetchRange,
) -> tuple[list[DayPoint], int, set[str]]:
    """Ensure cache coverage for [start, end], fetching only what's missing.

    Closed months are read from cache when present and otherwise fetched
    **in full** (not just the requested sub-range) so later, differently-
    bounded requests for the same month are cache hits too. The open/current
    month is always refetched, up to `end`. Returns the day series sliced to
    [start, end], the number of HTTP requests made, and the set of calendar
    months ("YYYY-MM") that required a fresh fetch this call.
    """
    directory = raw_dir(data_dir, wiki, article_slot, granularity)
    all_days: list[DayPoint] = []
    requests_made = 0
    fresh_months: set[str] = set()

    for year_month in iter_months(start, end):
        month_start, month_end = month_bounds(year_month)
        closed = is_closed_month(year_month, today=today)

        if closed:
            cached = load_cached_month(directory, year_month, closed=True)
            if cached is None:
                items = await fetch_range(month_start, month_end)
                requests_made += 1
                cached = zero_fill(items, month_start, month_end)
                save_month(directory, year_month, cached, closed=True)
                fresh_months.add(year_month)
        else:
            effective_end = min(month_end, end)
            items = await fetch_range(month_start, effective_end)
            requests_made += 1
            cached = zero_fill(items, month_start, effective_end)
            save_month(directory, year_month, cached, closed=False)
            fresh_months.add(year_month)

        sub_start, sub_end = max(month_start, start), min(month_end, end)
        all_days.extend(d for d in cached if sub_start.isoformat() <= d.date <= sub_end.isoformat())

    return all_days, requests_made, fresh_months


def read_cached_range(
    data_dir: Path,
    wiki: str,
    article_slot: str,
    granularity: str,
    start: date,
    end: date,
    today: date,
) -> dict[str, int]:
    """Read-only counterpart to `ensure_series`, used by `analyze` (SPEC.md:
    "reads exclusively from cache/raw/" — never fetches). A month with no
    cached file at all (never fetched) is simply absent from the result,
    not zero-filled — that's different from a fetched month's internal
    zero-fill for AQS-omitted days.

    Tries both the closed-month filename and `current.json` for each month,
    since a month can close between one `fetch` and the next `analyze`
    without a fresh `fetch` re-running to "promote" its file.
    """
    directory = raw_dir(data_dir, wiki, article_slot, granularity)
    result: dict[str, int] = {}
    for year_month in iter_months(start, end):
        closed = is_closed_month(year_month, today=today)
        cached = load_cached_month(directory, year_month, closed=closed)
        if cached is None:
            cached = load_cached_month(directory, year_month, closed=not closed)
        if cached is None:
            continue
        for point in cached:
            if start.isoformat() <= point.date <= end.isoformat():
                result[point.date] = point.views
    return result
