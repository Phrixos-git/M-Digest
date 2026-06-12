from __future__ import annotations

from collections import defaultdict

from .rss import Entry


def render_markdown(report_date: str, entries: list[Entry], errors: list[str]) -> str:
    lines = [
        f"# Daily Info Report - {report_date}",
        "",
        f"- New articles: {len(entries)}",
        f"- Sources with errors: {len(errors)}",
        "",
    ]

    grouped: dict[str, list[Entry]] = defaultdict(list)
    for entry in entries:
        grouped[entry.category].append(entry)

    if not entries:
        lines.extend(["No new articles found.", ""])
    else:
        for category in sorted(grouped):
            lines.extend([f"## {category}", ""])
            for entry in grouped[category]:
                published = f" ({entry.published})" if entry.published else ""
                lines.append(f"- [{entry.title}]({entry.url}) - {entry.source}{published}")
                if entry.summary:
                    lines.append(f"  - {entry.summary[:240]}")
            lines.append("")

    if errors:
        lines.extend(["## Fetch Errors", ""])
        for error in errors:
            lines.append(f"- {error}")
        lines.append("")

    return "\n".join(lines)
