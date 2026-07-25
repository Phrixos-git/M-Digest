from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from info_agent.config import load_sources
from info_agent.utils import parse_bool


class ParseBoolTest(unittest.TestCase):
    def test_false_values(self) -> None:
        for value in (False, "false", " NO ", "0", "Off"):
            with self.subTest(value=value):
                self.assertFalse(parse_bool(value))

    def test_true_values(self) -> None:
        for value in (True, "true", "yes", "1", "", 1):
            with self.subTest(value=value):
                self.assertTrue(parse_bool(value))


class ConfigTest(unittest.TestCase):
    def _load(self, text: str):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sources.yaml"
            path.write_text(text, encoding="utf-8")
            return load_sources(path)

    def test_loads_topics_and_combines_enabled_flags(self) -> None:
        sources = self._load(
            """topics:
  - name: dev
    label: Development
    enabled: true
    feeds:
      - name: Enabled
        url: https://example.com/a
      - name: Disabled
        url: https://example.com/b
        enabled: false
    keywords:
      - Python
      - Linux
"""
        )
        self.assertEqual([source.name for source in sources], ["Enabled", "Disabled"])
        self.assertEqual(sources[0].category, "Development")
        self.assertEqual(sources[0].keywords, ("Python", "Linux"))
        self.assertTrue(sources[0].enabled)
        self.assertFalse(sources[1].enabled)

    def test_disabled_topic_disables_its_feeds(self) -> None:
        source = self._load(
            """topics:
  - name: dev
    enabled: false
    feeds:
      - name: Feed
        url: https://example.com/feed
"""
        )[0]
        self.assertFalse(source.enabled)
        self.assertEqual(source.category, "dev")

    def test_rejects_legacy_sources_format(self) -> None:
        with self.assertRaisesRegex(ValueError, "top-level 'topics'"):
            self._load("sources:\n  - name: Feed\n    url: https://example.com\n")

    def test_rejects_invalid_topic_feed_and_required_fields(self) -> None:
        invalid_documents = (
            "topics:\n  - value\n",
            "topics:\n  - name: dev\n    feeds: invalid\n",
            "topics:\n  - name: dev\n    feeds:\n      - value\n",
            "topics:\n  - name: dev\n    feeds:\n      - name: Feed\n",
        )
        for document in invalid_documents:
            with self.subTest(document=document), self.assertRaises(ValueError):
                self._load(document)


if __name__ == "__main__":
    unittest.main()
