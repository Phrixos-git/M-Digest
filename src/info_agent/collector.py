from __future__ import annotations

from pathlib import Path

from .config import load_sources
from .dedupe import SeenStore, entry_key
from .report import CATEGORY_HEADING_PREFIX, SOURCE_HEADING_PREFIX, render_markdown
from .rss import Entry, fetch_entries
from .weather_cache import load_weather_cache


class DailyCollector:
    def __init__(
        self,
        config_path: Path,
        output_dir: Path,
        state_path: Path,
        report_date: str,
        limit_per_source: int,
        include_seen: bool = False,
        weather_cache_path: Path = Path("outputs/state/weather.json"),
    ) -> None:
        self.config_path = config_path
        self.output_dir = output_dir
        self.state_path = state_path
        self.report_date = report_date
        self.limit_per_source = limit_per_source
        self.include_seen = include_seen
        self.weather_cache_path = weather_cache_path

    def run(self) -> Path:
        sources = [source for source in load_sources(self.config_path) if source.enabled]
        seen = SeenStore(self.state_path)
        entries: list[Entry] = []
        report_keys: set[str] = set()
        errors: list[str] = []

        weather = None
        try:
            weather = load_weather_cache(self.weather_cache_path, self.report_date)
        except Exception as exc:  # noqa: BLE001 - report should survive weather failures.
            errors.append(f"気象庁 天気予報: {exc}")

        if self.include_seen:
            missing_keys = seen.missing_entry_keys()
            if missing_keys:
                for entry in _entries_from_existing_reports(self.output_dir, missing_keys):
                    seen.backfill(entry)
            enabled_sources = {(source.name, source.category) for source in sources}
            for entry in seen.entries():
                if _is_enabled_entry(entry, enabled_sources):
                    _append_once(entries, report_keys, entry)

        for source in sources:
            try:
                fetched = fetch_entries(source, limit=self.limit_per_source)
            except Exception as exc:  # noqa: BLE001 - daily report should survive individual source failures.
                errors.append(f"{source.name}: {exc}")
                continue

            for entry in _filter_entries_by_keywords(fetched, source.keywords):
                if self.include_seen or not seen.contains(entry):
                    _append_once(entries, report_keys, entry)
                seen.add(entry)

        self.output_dir.mkdir(parents=True, exist_ok=True)
        report_path = self.output_dir / f"{self.report_date}.md"
        report_path.write_text(
            render_markdown(self.report_date, entries, errors, weather), encoding="utf-8"
        )
        seen.save()
        return report_path


def _filter_entries_by_keywords(entries: list[Entry], keywords: tuple[str, ...]) -> list[Entry]:
    if not keywords:
        return entries

    normalized_keywords = tuple(keyword.casefold() for keyword in keywords)
    matched = [
        entry
        for entry in entries
        if any(keyword in _entry_search_text(entry) for keyword in normalized_keywords)
    ]
    return matched or entries


def _entry_search_text(entry: Entry) -> str:
    return f"{entry.title}\n{entry.summary}".casefold()


def _append_once(entries: list[Entry], report_keys: set[str], entry: Entry) -> None:
    key = entry_key(entry)
    if key in report_keys:
        return
    entries.append(entry)
    report_keys.add(key)


def _is_enabled_entry(entry: Entry, enabled_sources: set[tuple[str, str]]) -> bool:
    if (entry.source, entry.category) in enabled_sources:
        return True
    return entry.category == "general" and any(entry.source == source for source, _ in enabled_sources)


def _entries_from_existing_reports(
    output_dir: Path, wanted_keys: set[str] | None = None
) -> list[Entry]:
    if not output_dir.exists() or wanted_keys == set():
        return []

    entries: list[Entry] = []
    category = "general"
    source = ""
    for report_path in sorted(output_dir.glob("*.md")):
        pending: Entry | None = None
        lines = report_path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if line and set(line) == {"="} and index > 0:
                source = lines[index - 1].strip()
                category = "general"
                pending = None
                continue
            if line.startswith(CATEGORY_HEADING_PREFIX):
                category = line[len(CATEGORY_HEADING_PREFIX) :].strip() or "general"
                source = ""
                pending = None
                continue
            if line.startswith(SOURCE_HEADING_PREFIX):
                source = line[len(SOURCE_HEADING_PREFIX) :].strip()
                pending = None
                continue
            if line.startswith("- ["):
                parsed = _entry_from_report_line(line, category, source)
                if parsed is not None and (wanted_keys is None or entry_key(parsed) in wanted_keys):
                    entries.append(parsed)
                    pending = parsed
                    if wanted_keys is not None:
                        wanted_keys.discard(entry_key(parsed))
                continue
            if pending is not None and line.startswith("  - "):
                entries[-1] = Entry(
                    source=pending.source,
                    category=pending.category,
                    title=pending.title,
                    url=pending.url,
                    published=pending.published,
                    summary=line[4:].strip(),
                )
                pending = entries[-1]
        if wanted_keys == set():
            break
    return entries


def _entry_from_report_line(line: str, category: str, source: str = "") -> Entry | None:
    title_end = line.find("](")
    url_end = line.find(")", title_end + 2)
    if not line.startswith("- [") or title_end == -1 or url_end == -1:
        return None

    title = line[3:title_end].strip()
    url = line[title_end + 2 : url_end].strip()
    remainder = line[url_end + 1 :].strip()
    published = ""

    if remainder.startswith("- "):
        source_and_date = remainder[2:].strip()
        source = source_and_date
        if source_and_date.endswith(")") and " (" in source_and_date:
            source, published = source_and_date.rsplit(" (", 1)
            published = published[:-1]
    elif remainder.startswith("(") and remainder.endswith(")"):
        published = remainder[1:-1]
    elif remainder:
        published = remainder

    if not title or not url or not source:
        return None
    return Entry(source=source.strip(), category=category, title=title, url=url, published=published, summary="")
