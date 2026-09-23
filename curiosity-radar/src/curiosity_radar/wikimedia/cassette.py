"""Deterministic cassette-playback HTTP transport (Milestone 11 — evals).

`tests/_cassette.py`'s `SequentialCassette` is fine for unit tests, where
the exact call order is known ahead of time because the test itself drives
every call. An eval run doesn't have that luxury: a live LLM decides which
commands to run and in what order, so the transport has to answer whatever
request actually arrives rather than assert on a fixed sequence — a
lookup, not a queue.

Activated by the `CURIOSITY_RADAR_CASSETTE_DIR` env var (read once, in
`wikimedia/http.py::build_client`, only when no explicit `transport` was
passed — so it never interferes with `tests/conftest.py`'s own transport
patching). Points at a directory containing a `manifest.json` mapping a
canonical request key to either an inline `"body"` or a `"file"` (a
sibling JSON file, for a real per-article month's worth of data without
bloating the manifest itself).

Per `CLAUDE.md`'s testing rules, this is how the eval milestone stays
reproducible: the same live-network prohibition unit tests already follow,
just satisfied via a directory an eval scenario ships instead of code a
test monkeypatches.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode

import httpx

MANIFEST_FILENAME = "manifest.json"

# An eval scenario (Milestone 11) fixes a topic's QID/sitelinks ahead of
# time, but not the exact `--topic` text a live model chooses to pass —
# that's the model's own paraphrase of the user's ask, not something a
# fixture can pin down word for word. `wbsearchentities`'s `search` param
# is the one query param this genuinely varies on, so it's excluded from
# the key on both the recording and playback side (both go through this
# same function) — any topic text resolves to the same fixed candidate
# list for that scenario. No other endpoint's params vary with model
# phrasing, so nothing else needs this treatment.
_WILDCARD_PARAMS_BY_ACTION = {"wbsearchentities": frozenset({"search"})}


def cassette_key(method: str, url: httpx.URL) -> str:
    """Canonical, order-independent key for a request: method + scheme +
    host + path, plus its query params sorted (so two requests differing
    only in query-param order — never actually significant to any of these
    APIs — still hit the same cassette entry). See `_WILDCARD_PARAMS_BY_
    ACTION` above for the one deliberate exception."""
    items = url.params.multi_items()
    action = dict(items).get("action", "")
    ignored = _WILDCARD_PARAMS_BY_ACTION.get(action, frozenset())
    query = urlencode(sorted((k, v) for k, v in items if k not in ignored))
    base = f"{method} {url.scheme}://{url.host}{url.path}"
    return f"{base}?{query}" if query else base


class CassetteMissError(RuntimeError):
    """Raised when a request has no recorded response — a harness/fixture
    gap, not a real network condition, so it's left as a plain exception
    (surfaces as the CLI's `internal_error` with the missing key logged to
    `<data-dir>/logs/`, per `SPEC.md` §3: never a raw traceback on stdout,
    but not worth a dedicated error code either)."""


def load_manifest(cassette_dir: Path) -> dict[str, dict]:
    manifest_path = cassette_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        raise FileNotFoundError(f"no {MANIFEST_FILENAME} under cassette dir {cassette_dir}")
    return json.loads(manifest_path.read_text())


def build_transport(cassette_dir: Path) -> httpx.MockTransport:
    manifest = load_manifest(cassette_dir)

    def _handler(request: httpx.Request) -> httpx.Response:
        key = cassette_key(request.method, request.url)
        entry = manifest.get(key)
        if entry is None:
            raise CassetteMissError(
                f"cassette miss under {cassette_dir}: no recorded response for {key!r}"
            )
        status = entry.get("status", 200)
        if "file" in entry:
            body = json.loads((cassette_dir / entry["file"]).read_text())
        else:
            body = entry.get("body", {})
        return httpx.Response(status, json=body)

    return httpx.MockTransport(_handler)
