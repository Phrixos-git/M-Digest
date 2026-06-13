from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .rss import Entry

TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "igshid", "ref"}


class SeenStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.keys = set[str]()
        self.entries_by_key: dict[str, Entry] = {}
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            self.keys = set(data.get("keys", []))
            self.entries_by_key = {
                key: entry
                for key, value in data.get("entries", {}).items()
                if key in self.keys and (entry := _entry_from_json(value)) is not None
            }

    def contains(self, entry: Entry) -> bool:
        return entry_key(entry) in self.keys

    def add(self, entry: Entry) -> None:
        key = entry_key(entry)
        self.keys.add(key)
        self.entries_by_key[key] = entry

    def entries(self) -> list[Entry]:
        return [self.entries_by_key[key] for key in sorted(self.entries_by_key)]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "keys": sorted(self.keys),
            "entries": {
                key: _entry_to_json(entry)
                for key, entry in sorted(self.entries_by_key.items())
                if key in self.keys
            },
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def entry_key(entry: Entry) -> str:
    canonical = canonical_url(entry.url)
    title = " ".join(entry.title.lower().split())
    raw = f"{canonical}\n{title}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _entry_to_json(entry: Entry) -> dict[str, str]:
    return {
        "source": entry.source,
        "category": entry.category,
        "title": entry.title,
        "url": entry.url,
        "published": entry.published,
        "summary": entry.summary,
    }


def _entry_from_json(value: object) -> Entry | None:
    if not isinstance(value, dict):
        return None
    try:
        return Entry(
            source=str(value["source"]),
            category=str(value["category"]),
            title=str(value["title"]),
            url=str(value["url"]),
            published=str(value.get("published", "")),
            summary=str(value.get("summary", "")),
        )
    except KeyError:
        return None


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key not in TRACKING_KEYS and not key.startswith(TRACKING_PREFIXES)
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))
