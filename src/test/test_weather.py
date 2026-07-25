from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from info_agent.weather import WeatherForecast, fetch_jma_forecast, parse_jma_forecast
from info_agent.weather_cache import load_weather_cache, remove_stale_weather_cache, save_weather_cache


def _payload(hour: int = 5):
    return [{
        "reportDatetime": f"2026-07-18T{hour:02d}:00:00+09:00",
        "timeSeries": [
            {"timeDefines": ["2026-07-18T00:00:00+09:00", "2026-07-19T00:00:00+09:00"], "areas": [
                {"area": {"name": "東京地方", "code": "130010"}, "weathers": ["晴れ", "くもり"]}
            ]},
            {"timeDefines": ["2026-07-18T06:00:00+09:00", "2026-07-18T12:00:00+09:00"], "areas": [
                {"area": {"name": "東京地方", "code": "130010"}, "pops": ["10", "20"]}
            ]},
            {"timeDefines": ["2026-07-18T09:00:00+09:00", "2026-07-19T09:00:00+09:00"], "areas": [
                {"area": {"name": "東京", "code": "44132"}, "temps": ["33", "32"]}
            ]},
        ],
    }]


class _JsonResponse:
    def __init__(self, payload) -> None:
        self.data = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, *args) -> bytes:
        return self.data


class WeatherTest(unittest.TestCase):
    def test_parses_weather_precipitation_and_temperature_by_date(self) -> None:
        forecast = parse_jma_forecast(_payload())
        self.assertEqual(forecast.area_name, "東京地方")
        self.assertEqual(forecast.published_at, "2026-07-18T05:00:00+09:00")
        self.assertEqual(forecast.days[0].precipitation, ("10", "20"))
        self.assertEqual(forecast.days[1].temperatures, ("32",))

    def test_fetches_fixed_jma_endpoint_and_parses_response(self) -> None:
        with patch("info_agent.weather.urlopen", return_value=_JsonResponse(_payload())) as urlopen:
            forecast = fetch_jma_forecast()
        self.assertEqual(forecast.area_name, "東京地方")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 20)

    def test_rejects_invalid_payload_hour_series_region_and_datetime(self) -> None:
        cases = [
            (None, "形式が不正"),
            (_payload(11), "5時発表"),
            ([{"reportDatetime": "bad", "timeSeries": []}], "発表時刻が不正"),
            ([{"reportDatetime": "2026-07-18T05:00:00+09:00", "timeSeries": []}], "時系列"),
            (_payload(), "地域コード"),
        ]
        for payload, message in cases:
            region = "missing" if message == "地域コード" else "44132"
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                parse_jma_forecast(payload, region)

    def test_cache_round_trip_and_date_validation(self) -> None:
        forecast = parse_jma_forecast(_payload())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state" / "weather.json"
            save_weather_cache(path, forecast)
            self.assertEqual(load_weather_cache(path, "2026-07-18"), forecast)
            with self.assertRaisesRegex(ValueError, "日付が異なります"):
                load_weather_cache(path, "2026-07-19")

    def test_cache_reports_missing_invalid_json_and_invalid_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weather.json"
            with self.assertRaisesRegex(ValueError, "ありません"):
                load_weather_cache(path, "2026-07-18")
            for content in ("{", "[]", '{"days": []}'):
                path.write_text(content, encoding="utf-8")
                with self.subTest(content=content), self.assertRaises(ValueError):
                    load_weather_cache(path, "2026-07-18")

    def test_remove_stale_cache_keeps_current_and_removes_stale_or_invalid(self) -> None:
        forecast = parse_jma_forecast(_payload())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weather.json"
            self.assertFalse(remove_stale_weather_cache(path, "2026-07-18"))
            save_weather_cache(path, forecast)
            self.assertFalse(remove_stale_weather_cache(path, "2026-07-18"))
            self.assertTrue(remove_stale_weather_cache(path, "2026-07-19"))
            path.write_text("invalid", encoding="utf-8")
            self.assertTrue(remove_stale_weather_cache(path, "2026-07-18"))


if __name__ == "__main__":
    unittest.main()
