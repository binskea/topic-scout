"""A single seam for "today" wherever it drives cache/date-range logic
(closed-vs-open month, the default 730-day lookback) — so an eval run
(Milestone 11) can pin the clock to match cassette data recorded for a
fixed date, without threading a fake date through every call site by hand.

Unset by default: normal runtime behavior is real wall time, unaffected.
Deliberately not used for informational-only timestamps (`created_at`,
`generated_at`, a report's filename date) — those are fine to vary run to
run and are never matched against cassette data or `verify`-checked
(`references/report-template.md` on why `generated_at` isn't a claim).
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime

FAKE_TODAY_ENV = "CURIOSITY_RADAR_FAKE_TODAY"  # YYYY-MM-DD


def today() -> date:
    fake = os.environ.get(FAKE_TODAY_ENV)
    if fake:
        return date.fromisoformat(fake)
    return datetime.now(UTC).date()
