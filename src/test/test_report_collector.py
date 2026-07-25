from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from info_agent.collector import (
    DailyCollector,
    _entries_from_existing_reports,
    _filter_entries_by_keywords,
)
from info_agent.dedupe import entry_key
from info_agent.report import render_markdown
from info_agent.rss import Entry
from info_agent.weather import WeatherDay, WeatherForecast


def _entry(
    title: str = "Python news",
    url: str = "https://example.com/1",
    source: str = "Feed",
    category: str = "Tech",
) -> Entry:
    return Entry(source, category, title, url, "2026-07-18 00:00 UTC", "Useful summary")


class ReportTest(unittest.TestCase):
    def test_renders_category_then_source_and_strips_images(self) -> None:
        entries = [
            Entry("Z Feed", "B", "Title ![x](image.png)", "https://example.com/1", "date", "<figure>x</figure>Text"),
            _entry(source="A Feed", category="A"),
        ]
        report = render_markdown("2026-07-18", entries, ["failed"])
        self.assertLess(report.index("## A"), report.index("### A Feed"))
        self.assertLess(report.index("## A"), report.index("## B"))
        self.assertIn("### Z Feed", report)
        self.assertNotIn("image.png", report)
        self.assertNotIn("<figure>", report)
        self.assertIn("## Fetch Errors", report)

    def test_renders_weather_fallback_and_empty_articles(self) -> None:
        report = render_markdown("2026-07-18", [], [])
        self.assertIn("天気予報を取得できませんでした", report)
        self.assertIn("No new articles found.", report)

    def test_renders_weather_details_before_articles(self) -> None:
        weather = WeatherForecast(
            "東京地方",
            "2026-07-18T05:00:00+09:00",
            (WeatherDay("2026-07-18", "晴れ", ("10", "20"), ("25", "33")),),
        )
        report = render_markdown("2026-07-18", [_entry()], [], weather)
        self.assertIn("天気予報（東京地方）", report)
        self.assertIn("降水確率 10 / 20%", report)
        self.assertIn("気温 25 / 33℃", report)
        self.assertLess(report.index("## 天気予報"), report.index("## Tech"))


class CollectorHelperTest(unittest.TestCase):
    def test_keyword_filter_matches_case_insensitively_and_falls_back(self) -> None:
        matching = _entry(title="PYTHON release")
        other = _entry(title="Other", url="https://example.com/2")
        self.assertEqual(_filter_entries_by_keywords([matching, other], ("python",)), [matching])
        self.assertEqual(_filter_entries_by_keywords([other], ("missing",)), [other])
        self.assertEqual(_filter_entries_by_keywords([other], ()), [other])

    def test_reads_current_category_source_format_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "2026-07-18.md").write_text(
                "## Tech\n\n### Feed\n\n- [Title](https://example.com/1) (date)\n  - Summary\n",
                encoding="utf-8",
            )
            entries = _entries_from_existing_reports(output)
        self.assertEqual(entries, [Entry("Feed", "Tech", "Title", "https://example.com/1", "date", "Summary")])

    def test_reads_legacy_source_format_for_migration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "old.md").write_text(
                "Feed\n====\n\n- [Title](https://example.com/1) (date)\n",
                encoding="utf-8",
            )
            entries = _entries_from_existing_reports(output)
        self.assertEqual(entries[0].source, "Feed")
        self.assertEqual(entries[0].category, "general")

    def test_reads_only_requested_legacy_keys(self) -> None:
        wanted = Entry("Feed", "Tech", "Wanted", "https://example.com/w", "", "")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "report.md").write_text(
                "## Tech\n### Feed\n- [Ignored](https://example.com/i)\n- [Wanted](https://example.com/w)\n",
                encoding="utf-8",
            )
            entries = _entries_from_existing_reports(output, {entry_key(wanted)})
        self.assertEqual([entry.title for entry in entries], ["Wanted"])


class DailyCollectorTest(unittest.TestCase):
    def _paths(self, directory: str) -> tuple[Path, Path, Path, Path]:
        root = Path(directory)
        config = root / "sources.yaml"
        config.write_text(
            "topics:\n  - name: tech\n    label: Tech\n    feeds:\n      - name: Feed\n        url: https://example.com/feed\n    keywords:\n      - Python\n",
            encoding="utf-8",
        )
        return config, root / "daily", root / "seen.json", root / "weather.json"

    def test_collects_filters_deduplicates_writes_report_and_state(self) -> None:
        duplicate = _entry()
        other = _entry("Python other", "https://example.com/2")
        with tempfile.TemporaryDirectory() as directory:
            config, output, state, weather = self._paths(directory)
            collector = DailyCollector(config, output, state, "2026-07-18", 5, weather_cache_path=weather)
            with patch("info_agent.collector.fetch_entries", return_value=[duplicate, duplicate, other]), patch(
                "info_agent.collector.load_weather_cache", side_effect=ValueError("missing")
            ):
                report_path = collector.run()
            report = report_path.read_text(encoding="utf-8")
            state_data = json.loads(state.read_text(encoding="utf-8"))
        self.assertEqual(report.count("https://example.com/1"), 1)
        self.assertIn("## Tech", report)
        self.assertIn("気象庁 天気予報: missing", report)
        self.assertEqual(len(state_data["keys"]), 2)

    def test_skips_seen_entry_but_preserves_it_in_state(self) -> None:
        seen_entry = _entry()
        with tempfile.TemporaryDirectory() as directory:
            config, output, state, weather = self._paths(directory)
            state.write_text(json.dumps({"keys": [entry_key(seen_entry)], "entries": {}}), encoding="utf-8")
            collector = DailyCollector(config, output, state, "2026-07-18", 5, weather_cache_path=weather)
            with patch("info_agent.collector.fetch_entries", return_value=[seen_entry]), patch(
                "info_agent.collector.load_weather_cache", return_value=None
            ):
                report = collector.run().read_text(encoding="utf-8")
        self.assertIn("No new articles", report)

    def test_include_seen_backfills_only_missing_legacy_entry(self) -> None:
        legacy = _entry()
        existing = _entry("Python existing", "https://example.com/2")
        with tempfile.TemporaryDirectory() as directory:
            config, output, state, weather = self._paths(directory)
            output.mkdir()
            (output / "old.md").write_text(render_markdown("2026-07-17", [legacy], []), encoding="utf-8")
            state.write_text(
                json.dumps({"keys": [entry_key(legacy), entry_key(existing)], "entries": {
                    entry_key(existing): {
                        "source": existing.source, "category": existing.category, "title": existing.title,
                        "url": existing.url, "published": existing.published, "summary": existing.summary,
                    }
                }}), encoding="utf-8"
            )
            collector = DailyCollector(config, output, state, "2026-07-18", 5, include_seen=True, weather_cache_path=weather)
            with patch("info_agent.collector.fetch_entries", return_value=[]), patch(
                "info_agent.collector.load_weather_cache", return_value=None
            ):
                report = collector.run().read_text(encoding="utf-8")
            saved = json.loads(state.read_text(encoding="utf-8"))
        self.assertIn(legacy.title, report)
        self.assertIn(existing.title, report)
        self.assertEqual(len(saved["entries"]), 2)

    def test_include_seen_does_not_scan_reports_when_no_data_is_missing(self) -> None:
        existing = _entry()
        with tempfile.TemporaryDirectory() as directory:
            config, output, state, weather = self._paths(directory)
            state.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "keys": [entry_key(existing)],
                "entries": {entry_key(existing): {
                    "source": existing.source, "category": existing.category, "title": existing.title,
                    "url": existing.url, "published": existing.published, "summary": existing.summary,
                }},
            }
            state.write_text(json.dumps(payload), encoding="utf-8")
            collector = DailyCollector(config, output, state, "2026-07-18", 5, include_seen=True, weather_cache_path=weather)
            with patch("info_agent.collector._entries_from_existing_reports") as scan, patch(
                "info_agent.collector.fetch_entries", return_value=[]
            ), patch("info_agent.collector.load_weather_cache", return_value=None):
                collector.run()
        scan.assert_not_called()

    def test_source_failure_is_reported_without_stopping_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, output, state, weather = self._paths(directory)
            collector = DailyCollector(config, output, state, "2026-07-18", 5, weather_cache_path=weather)
            with patch("info_agent.collector.fetch_entries", side_effect=RuntimeError("offline")), patch(
                "info_agent.collector.load_weather_cache", return_value=None
            ):
                report = collector.run().read_text(encoding="utf-8")
        self.assertIn("Feed: offline", report)


if __name__ == "__main__":
    unittest.main()
