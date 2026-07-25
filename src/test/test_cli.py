from __future__ import annotations

from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from info_agent import cli, weather_cache
from info_agent.weather import WeatherForecast


class CliTest(unittest.TestCase):
    def test_daily_cli_passes_arguments_collects_and_emails(self) -> None:
        report = Path("out/report.md")
        collector = Mock()
        collector.run.return_value = report
        with patch("sys.argv", ["info-agent", "--date", "2026-07-18", "--include-seen"]), patch(
            "info_agent.cli.DailyCollector", return_value=collector
        ) as collector_class, patch("info_agent.cli.load_email_config_from_env", return_value="config"), patch(
            "info_agent.cli.send_report_email"
        ) as send:
            self.assertEqual(cli.main(), 0)
        self.assertTrue(collector_class.call_args.kwargs["include_seen"])
        send.assert_called_once_with(report, "2026-07-18", "config")

    def test_weather_cli_removes_fetches_validates_and_saves(self) -> None:
        today = date.today().isoformat()
        forecast = WeatherForecast("Tokyo", f"{today}T05:00:00+09:00", ())
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "weather.json"
            with patch("sys.argv", ["info-agent-weather", "--output", str(output)]), patch(
                "info_agent.weather_cache.remove_stale_weather_cache"
            ) as remove, patch("info_agent.weather_cache.fetch_jma_forecast", return_value=forecast), patch(
                "info_agent.weather_cache.save_weather_cache"
            ) as save:
                self.assertEqual(weather_cache.main(), 0)
        remove.assert_called_once_with(output, today)
        save.assert_called_once_with(output, forecast)

    def test_weather_cli_rejects_forecast_from_another_date(self) -> None:
        forecast = WeatherForecast("Tokyo", "2000-01-01T05:00:00+09:00", ())
        with patch("sys.argv", ["info-agent-weather"]), patch(
            "info_agent.weather_cache.remove_stale_weather_cache"
        ), patch("info_agent.weather_cache.fetch_jma_forecast", return_value=forecast), self.assertRaisesRegex(
            ValueError, "本日の天気予報"
        ):
            weather_cache.main()


if __name__ == "__main__":
    unittest.main()
