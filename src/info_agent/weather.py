from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any
from urllib.request import Request, urlopen


JMA_FORECAST_URL = "https://www.jma.go.jp/bosai/forecast/data/forecast/130000.json"


@dataclass(frozen=True)
class WeatherDay:
    date: str
    weather: str
    precipitation: tuple[str, ...] = ()
    temperatures: tuple[str, ...] = ()


@dataclass(frozen=True)
class WeatherForecast:
    area_name: str
    published_at: str
    days: tuple[WeatherDay, ...]


def fetch_jma_forecast(region_code: str = "44132", publication_hour: int = 5) -> WeatherForecast:
    request = Request(JMA_FORECAST_URL, headers={"User-Agent": "M-Digest/0.1"})
    with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed HTTPS URL.
        payload = json.load(response)
    return parse_jma_forecast(payload, region_code, publication_hour)


def parse_jma_forecast(
    payload: Any, region_code: str = "44132", publication_hour: int = 5
) -> WeatherForecast:
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
        raise ValueError("気象庁の予報データ形式が不正です")

    forecast = payload[0]
    published = _parse_datetime(forecast.get("reportDatetime"))
    if published.hour != publication_hour:
        raise ValueError(
            f"{publication_hour}時発表の予報ではありません（取得値: {published:%Y-%m-%d %H:%M}）"
        )

    series = forecast.get("timeSeries")
    if not isinstance(series, list) or len(series) < 3:
        raise ValueError("気象庁の予報データに必要な時系列がありません")

    temperature_index, temperature_area = _find_area(series[2], region_code)
    weather_area = _area_at(series[0], temperature_index)
    precipitation_area = _area_at(series[1], temperature_index)

    weather_by_date = _values_by_date(series[0], weather_area, "weathers")
    precipitation_by_date = _values_by_date(series[1], precipitation_area, "pops")
    temperature_by_date = _values_by_date(series[2], temperature_area, "temps")

    days = tuple(
        WeatherDay(
            date=day,
            weather=values[0],
            precipitation=tuple(precipitation_by_date.get(day, ())),
            temperatures=tuple(temperature_by_date.get(day, ())),
        )
        for day, values in weather_by_date.items()
    )
    if not days:
        raise ValueError("対象地域の天気予報が空です")

    area = weather_area.get("area", {})
    return WeatherForecast(
        area_name=str(area.get("name", region_code)),
        published_at=published.isoformat(),
        days=days,
    )


def _parse_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("気象庁の予報データに発表時刻がありません")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"気象庁の発表時刻が不正です: {value}") from exc


def _find_area(series: dict[str, Any], code: str) -> tuple[int, dict[str, Any]]:
    areas = series.get("areas", [])
    for index, area in enumerate(areas):
        if str(area.get("area", {}).get("code", "")) == code:
            return index, area
    raise ValueError(f"地域コード {code} の予報が見つかりません")


def _area_at(series: dict[str, Any], index: int) -> dict[str, Any]:
    areas = series.get("areas", [])
    if not isinstance(areas, list) or index >= len(areas):
        raise ValueError("対象地域に対応する予報区域が見つかりません")
    return areas[index]


def _values_by_date(
    series: dict[str, Any], area: dict[str, Any], value_key: str
) -> dict[str, list[str]]:
    times = series.get("timeDefines", [])
    values = area.get(value_key, [])
    result: dict[str, list[str]] = {}
    for raw_time, raw_value in zip(times, values, strict=False):
        day = _parse_datetime(raw_time).date().isoformat()
        value = str(raw_value).strip()
        if value:
            result.setdefault(day, []).append(value)
    return result
