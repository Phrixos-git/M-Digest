from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date
import json
from pathlib import Path
from typing import Any

from .weather import WeatherDay, WeatherForecast, fetch_jma_forecast


def save_weather_cache(path: Path, forecast: WeatherForecast) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(forecast), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_weather_cache(path: Path, report_date: str) -> WeatherForecast:
    try:
        forecast = _read_weather_cache(path)
    except FileNotFoundError as exc:
        raise ValueError(f"天気キャッシュがありません: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"天気キャッシュが不正です: {path}") from exc
    published_date = forecast.published_at[:10]
    if published_date != report_date:
        raise ValueError(
            f"天気キャッシュの日付が異なります（対象: {report_date}、取得値: {published_date}）"
        )
    return forecast


def remove_stale_weather_cache(path: Path, current_date: str) -> bool:
    if not path.exists():
        return False
    try:
        forecast = _read_weather_cache(path)
    except (json.JSONDecodeError, ValueError):
        path.unlink()
        return True

    if forecast.published_at[:10] == current_date:
        return False
    path.unlink()
    return True


def _read_weather_cache(path: Path) -> WeatherForecast:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _forecast_from_dict(payload)


def _forecast_from_dict(payload: Any) -> WeatherForecast:
    if not isinstance(payload, dict):
        raise ValueError("天気キャッシュの形式が不正です")
    try:
        raw_days = payload["days"]
        days = tuple(
            WeatherDay(
                date=str(day["date"]),
                weather=str(day["weather"]),
                precipitation=tuple(str(value) for value in day.get("precipitation", [])),
                temperatures=tuple(str(value) for value in day.get("temperatures", [])),
            )
            for day in raw_days
        )
        return WeatherForecast(
            area_name=str(payload["area_name"]),
            published_at=str(payload["published_at"]),
            days=days,
        )
    except (KeyError, TypeError) as exc:
        raise ValueError("天気キャッシュの形式が不正です") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch and cache the JMA 05:00 forecast.")
    parser.add_argument("--output", default="outputs/state/weather.json")
    args = parser.parse_args()

    expected_date = date.today().isoformat()
    output_path = Path(args.output)
    remove_stale_weather_cache(output_path, expected_date)

    forecast = fetch_jma_forecast(region_code="44132", publication_hour=5)
    if forecast.published_at[:10] != expected_date:
        raise ValueError(
            f"本日の天気予報ではありません（取得値: {forecast.published_at[:10]}）"
        )
    save_weather_cache(output_path, forecast)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
