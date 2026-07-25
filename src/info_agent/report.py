from __future__ import annotations

from collections import defaultdict
import re

from .rss import Entry
from .weather import WeatherForecast

_HTML_IMAGE_RE = re.compile(r"<(?:img|picture|source)\b[^>]*>", re.IGNORECASE)
_HTML_FIGURE_RE = re.compile(r"<figure\b[^>]*>.*?</figure>", re.IGNORECASE)
_MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*]\([^)]*\)")
CATEGORY_HEADING_PREFIX = "## "
SOURCE_HEADING_PREFIX = "### "


def render_markdown(
    report_date: str,
    entries: list[Entry],
    errors: list[str],
    weather: WeatherForecast | None = None,
) -> str:
    lines = [f"# Daily Info Report - {report_date}", ""]

    if weather is not None:
        published = weather.published_at.replace("T", " ")[:16]
        lines.extend([f"## 天気予報（{weather.area_name}）", "", f"- 発表: {published}"])
        for day in weather.days:
            details: list[str] = []
            if day.precipitation:
                details.append(f"降水確率 {' / '.join(day.precipitation)}%")
            if day.temperatures:
                details.append(f"気温 {' / '.join(day.temperatures)}℃")
            suffix = f"（{'、'.join(details)}）" if details else ""
            lines.append(f"- {day.date}: {day.weather}{suffix}")
        lines.append("")
    else:
        lines.extend(["## 天気予報", "", "- 天気予報を取得できませんでした。", ""])

    lines.extend(
        [
            f"- New articles: {len(entries)}",
            f"- Fetch errors: {len(errors)}",
            "",
        ]
    )

    grouped: dict[str, dict[str, list[Entry]]] = defaultdict(lambda: defaultdict(list))
    for entry in entries:
        grouped[entry.category][entry.source].append(entry)

    if not entries:
        lines.extend(["No new articles found.", ""])
    else:
        for category in sorted(grouped):
            lines.extend([f"{CATEGORY_HEADING_PREFIX}{category}", ""])
            for source in sorted(grouped[category]):
                lines.extend([f"{SOURCE_HEADING_PREFIX}{source}", ""])
                for entry in grouped[category][source]:
                    published = f" ({entry.published})" if entry.published else ""
                    lines.append(f"- [{_strip_images(entry.title)}]({entry.url}){published}")
                    summary = _strip_images(entry.summary)
                    if summary:
                        lines.append(f"  - {summary[:240]}")
                lines.append("")

    if errors:
        lines.extend(["## Fetch Errors", ""])
        for error in errors:
            lines.append(f"- {error}")
        lines.append("")

    return "\n".join(lines)


def _strip_images(value: str) -> str:
    text = _HTML_FIGURE_RE.sub("", value or "")
    text = _HTML_IMAGE_RE.sub("", text)
    text = _MARKDOWN_IMAGE_RE.sub("", text)
    return " ".join(text.split())
