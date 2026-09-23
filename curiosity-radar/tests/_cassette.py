"""A minimal ordered request/response fixture list for `httpx.MockTransport`.

Not a test module itself (no `test_` prefix) — a shared helper for cassette-
backed tests per CLAUDE.md: "All HTTP-touching tests run against recorded
fixtures... an httpx.MockTransport fed from saved JSON, in the spirit of
VCR." Each step must be consumed in order; a mismatch or an unexpected
extra/missing call raises, which doubles as an assertion that the code
under test makes exactly the expected HTTP calls.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx


class SequentialCassette:
    def __init__(self, steps: list[tuple[dict[str, str], dict]]) -> None:
        self._steps = list(steps)
        self.calls_made = 0

    def _handler(self, request: httpx.Request) -> httpx.Response:
        if not self._steps:
            raise AssertionError(f"unexpected extra HTTP request: {request.url}")
        expected_params, payload = self._steps.pop(0)
        actual = {k: v[0] for k, v in parse_qs(urlparse(str(request.url)).query).items()}
        for key, value in expected_params.items():
            if actual.get(key) != value:
                raise AssertionError(
                    f"cassette mismatch on {request.url}: expected {key}={value!r}, "
                    f"got {actual.get(key)!r}"
                )
        self.calls_made += 1
        return httpx.Response(200, json=payload)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handler)

    def assert_exhausted(self) -> None:
        assert not self._steps, f"{len(self._steps)} expected HTTP call(s) never made"
