"""`clock.py` (Milestone 11): the fake-today seam eval runs pin cache/
date-range logic against. Pure function, no cache/network involved."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from curiosity_radar import clock


def test_today_is_real_wall_clock_when_env_var_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(clock.FAKE_TODAY_ENV, raising=False)
    assert clock.today() == datetime.now(UTC).date()


def test_today_honors_fake_today_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(clock.FAKE_TODAY_ENV, "2026-01-15")
    assert clock.today() == date(2026, 1, 15)
