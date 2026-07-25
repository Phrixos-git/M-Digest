from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from info_agent.dedupe import SeenStore, canonical_url, entry_key
from info_agent.rss import Entry


def _entry(url: str = "https://Example.com/news/?utm_source=x&id=1#part") -> Entry:
    return Entry("Source", "Category", "  Sample   TITLE ", url, "date", "summary")


class DedupeTest(unittest.TestCase):
    def test_canonical_url_removes_tracking_fragment_and_trailing_slash(self) -> None:
        self.assertEqual(canonical_url(_entry().url), "https://example.com/news?id=1")

    def test_entry_key_normalizes_title_and_url(self) -> None:
        first = _entry()
        second = Entry("Other", "Other", "sample title", "https://example.com/news?id=1", "", "")
        self.assertEqual(entry_key(first), entry_key(second))

    def test_store_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state" / "seen.json"
            store = SeenStore(path)
            store.add(_entry())
            store.save()
            loaded = SeenStore(path)
        self.assertTrue(loaded.contains(_entry()))
        self.assertEqual(loaded.entries(), [_entry()])
        self.assertEqual(loaded.missing_entry_keys(), set())

    def test_backfill_only_fills_known_key_without_entry_data(self) -> None:
        entry = _entry()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "seen.json"
            path.write_text(json.dumps({"keys": [entry_key(entry)]}), encoding="utf-8")
            store = SeenStore(path)
            self.assertEqual(store.missing_entry_keys(), {entry_key(entry)})
            self.assertTrue(store.backfill(entry))
            self.assertFalse(store.backfill(entry))
            self.assertFalse(store.backfill(_entry("https://example.com/other")))
        self.assertEqual(store.entries(), [entry])


if __name__ == "__main__":
    unittest.main()
