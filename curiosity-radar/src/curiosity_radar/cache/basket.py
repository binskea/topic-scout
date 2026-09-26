"""Per-wiki cache of placebo-basket candidate metadata (SPEC.md §9 item 1).

Which articles + Wikidata category QIDs are available to sample the
placebo basket from, sourced live at most once per calendar month during
`fetch` — a Wikidata lookup per candidate isn't cheap enough to repeat on
every `fetch`, and a wiki's set of top-viewed articles doesn't meaningfully
change day to day, so a monthly refresh is enough. Keyed by wiki only (not
by project/topic), the same "overlapping requests naturally share files"
philosophy SPEC.md §4 already applies to raw pageview data.

The candidates' own pageview *series* are **not** stored here — they're
cached under the ordinary raw-pageview scheme in `cache/store.py`, since a
candidate is just another cached article, keyed the same way.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from pydantic import BaseModel


class BasketCandidateMeta(BaseModel):
    title: str
    category_qids: list[str] = []


class BasketCacheFile(BaseModel):
    sourced_month: str  # "YYYY-MM"
    candidates: list[BasketCandidateMeta] = []


def _path(data_dir: Path, wiki: str) -> Path:
    return data_dir / "cache" / "basket" / f"{quote(wiki, safe='')}.json"


def load(data_dir: Path, wiki: str) -> BasketCacheFile | None:
    path = _path(data_dir, wiki)
    if not path.exists():
        return None
    return BasketCacheFile.model_validate_json(path.read_text())


def save(data_dir: Path, wiki: str, cache_file: BasketCacheFile) -> None:
    path = _path(data_dir, wiki)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cache_file.model_dump_json(indent=2))


def needs_refresh(cache_file: BasketCacheFile | None, current_month: str) -> bool:
    return cache_file is None or cache_file.sourced_month != current_month
