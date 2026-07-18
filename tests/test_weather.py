from __future__ import annotations

import unittest
from pathlib import Path
import tempfile

from info_agent.report import render_markdown
from info_agent.weather import parse_jma_forecast
from info_agent.weather_cache import (
    load_weather_cache,
    remove_stale_weather_cache,
    save_weather_cache,
)


def _payload(hour: int = 5) -> list[dict]:
    return [
        {
            "reportDatetime": f"2026-07-18T{hour:02d}:00:00+09:00",
            "timeSeries": [
                {
                    "timeDefines": [
                        "2026-07-18T00:00:00+09:00",
                        "2026-07-19T00:00:00+09:00",
                    ],
                    "areas": [
                        {
                            "area": {"name": "東京地方", "code": "130010"},
                            "weathers": ["晴れ", "くもり"],
                        }
                    ],
                },
                {
                    "timeDefines": [
                        "2026-07-18T06:00:00+09:00",
                        "2026-07-18T12:00:00+09:00",
                        "2026-07-19T00:00:00+09:00",
                    ],
                    "areas": [
                        {
                            "area": {"name": "東京地方", "code": "130010"},
                            "pops": ["10", "20", "30"],
                        }
                    ],
                },
                {
                    "timeDefines": [
                        "2026-07-18T09:00:00+09:00",
                        "2026-07-19T00:00:00+09:00",
                        "2026-07-19T09:00:00+09:00",
                    ],
                    "areas": [
                        {
                            "area": {"name": "東京", "code": "44132"},
                            "temps": ["33", "25", "32"],
                        }
                    ],
                },
            ],
        }
    ]


class WeatherTest(unittest.TestCase):
    def test_parse_region_and_five_oclock_forecast(self) -> None:
        forecast = parse_jma_forecast(_payload(), "44132", 5)

        self.assertEqual(forecast.area_name, "東京地方")
        self.assertEqual(forecast.days[0].weather, "晴れ")
        self.assertEqual(forecast.days[0].precipitation, ("10", "20"))
        self.assertEqual(forecast.days[1].temperatures, ("25", "32"))

    def test_rejects_non_five_oclock_forecast(self) -> None:
        with self.assertRaisesRegex(ValueError, "5時発表"):
            parse_jma_forecast(_payload(11), "44132", 5)

    def test_render_weather_in_report(self) -> None:
        report = render_markdown("2026-07-18", [], [], parse_jma_forecast(_payload()))

        self.assertIn("## 天気予報（東京地方）", report)
        self.assertIn("- 2026-07-18: 晴れ", report)
        self.assertIn("降水確率 10 / 20%", report)
        self.assertLess(report.index("## 天気予報"), report.index("- New articles:"))

    def test_render_weather_first_when_fetch_failed(self) -> None:
        report = render_markdown("2026-07-18", [], ["気象庁 天気予報: error"])

        self.assertIn("天気予報を取得できませんでした", report)
        self.assertLess(report.index("## 天気予報"), report.index("- New articles:"))

    def test_save_and_load_weather_cache_for_report_date(self) -> None:
        forecast = parse_jma_forecast(_payload())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weather.json"
            save_weather_cache(path, forecast)

            loaded = load_weather_cache(path, "2026-07-18")

        self.assertEqual(loaded, forecast)

    def test_rejects_weather_cache_from_another_date(self) -> None:
        forecast = parse_jma_forecast(_payload())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weather.json"
            save_weather_cache(path, forecast)

            with self.assertRaisesRegex(ValueError, "日付が異なります"):
                load_weather_cache(path, "2026-07-19")

    def test_removes_previous_day_weather_cache(self) -> None:
        forecast = parse_jma_forecast(_payload())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weather.json"
            save_weather_cache(path, forecast)

            removed = remove_stale_weather_cache(path, "2026-07-19")

            self.assertTrue(removed)
            self.assertFalse(path.exists())

    def test_keeps_current_day_weather_cache(self) -> None:
        forecast = parse_jma_forecast(_payload())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weather.json"
            save_weather_cache(path, forecast)

            removed = remove_stale_weather_cache(path, "2026-07-18")

            self.assertFalse(removed)
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
