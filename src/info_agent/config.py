from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Source:
    name: str
    url: str
    category: str = "general"
    enabled: bool = True
    keywords: tuple[str, ...] = ()


def load_sources(path: Path) -> list[Source]:
    data = _parse_minimal_yaml(path.read_text(encoding="utf-8"))
    raw_topics = data.get("topics")
    if isinstance(raw_topics, list):
        return _load_topic_sources(raw_topics)

    raw_sources = data.get("sources")
    if not isinstance(raw_sources, list):
        raise ValueError(f"{path} must contain a top-level 'topics' or 'sources' list")

    sources: list[Source] = []
    for index, item in enumerate(raw_sources, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"source #{index} must be a mapping")
        name = str(item.get("name", "")).strip()
        url = str(item.get("url", "")).strip()
        if not name or not url:
            raise ValueError(f"source #{index} must include name and url")
        sources.append(
            Source(
                name=name,
                url=url,
                category=str(item.get("category", "general")).strip() or "general",
                enabled=_as_bool(item.get("enabled", True)),
                keywords=tuple(_as_str_list(item.get("keywords", []))),
            )
        )
    return sources


def _load_topic_sources(raw_topics: list[Any]) -> list[Source]:
    sources: list[Source] = []
    for topic_index, topic in enumerate(raw_topics, start=1):
        if not isinstance(topic, dict):
            raise ValueError(f"topic #{topic_index} must be a mapping")

        topic_name = str(topic.get("name", f"topic_{topic_index}")).strip()
        label = str(topic.get("label", topic_name)).strip() or topic_name
        keywords = tuple(_as_str_list(topic.get("keywords", [])))
        topic_enabled = _as_bool(topic.get("enabled", True))
        raw_feeds = topic.get("feeds", [])

        if not isinstance(raw_feeds, list):
            raise ValueError(f"topic #{topic_index} feeds must be a list")

        for feed_index, feed in enumerate(raw_feeds, start=1):
            if not isinstance(feed, dict):
                raise ValueError(f"topic #{topic_index} feed #{feed_index} must be a mapping")
            name = str(feed.get("name", "")).strip()
            url = str(feed.get("url", "")).strip()
            if not name or not url:
                raise ValueError(f"topic #{topic_index} feed #{feed_index} must include name and url")
            sources.append(
                Source(
                    name=name,
                    url=url,
                    category=label,
                    enabled=topic_enabled and _as_bool(feed.get("enabled", True)),
                    keywords=keywords,
                )
            )
    return sources


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return [str(value).strip()] if str(value).strip() else []
    return [str(item).strip() for item in value if str(item).strip()]


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() not in {"false", "no", "0", "off"}
    return bool(value)


def _parse_minimal_yaml(text: str) -> dict[str, Any]:
    """Parse the small YAML subset used by config/sources.yaml.

    Supported shape:
      sources:
        - name: value
          url: value
          enabled: true
      topics:
        - name: value
          feeds:
            - name: value
              url: value
          keywords:
            - value
    """
    lines = _yaml_lines(text)
    if not lines:
        return {}
    parsed, index = _parse_yaml_block(lines, 0, lines[0][0])
    if index != len(lines) or not isinstance(parsed, dict):
        raise ValueError("unsupported YAML document")
    return parsed


def _yaml_lines(text: str) -> list[tuple[int, str, str]]:
    lines: list[tuple[int, str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        lines.append((indent, line.strip(), raw_line))
    return lines


def _parse_yaml_block(
    lines: list[tuple[int, str, str]], index: int, indent: int
) -> tuple[Any, int]:
    if index >= len(lines):
        return {}, index

    current_indent, stripped, _raw_line = lines[index]
    if current_indent != indent:
        raise ValueError(f"unsupported YAML indentation: {lines[index][2]}")

    if stripped.startswith("- "):
        return _parse_yaml_list(lines, index, indent)
    return _parse_yaml_mapping(lines, index, indent)


def _parse_yaml_list(
    lines: list[tuple[int, str, str]], index: int, indent: int
) -> tuple[list[Any], int]:
    values: list[Any] = []
    while index < len(lines):
        current_indent, stripped, raw_line = lines[index]
        if current_indent < indent:
            break
        if current_indent != indent or not stripped.startswith("- "):
            break

        remainder = stripped[2:].strip()
        index += 1
        if not remainder:
            value, index = _parse_yaml_block(lines, index, indent + 2)
            values.append(value)
            continue

        if ":" not in remainder:
            values.append(_parse_scalar(remainder))
            continue

        key, raw_value = _split_key_value(remainder, raw_line)
        item: dict[str, Any] = {}
        item[key] = _parse_scalar(raw_value) if raw_value else None

        while index < len(lines) and lines[index][0] > indent:
            child_indent, child_stripped, child_raw_line = lines[index]
            if child_indent != indent + 2 or child_stripped.startswith("- "):
                raise ValueError(f"unsupported YAML line: {child_raw_line}")

            child_key, child_raw_value = _split_key_value(child_stripped, child_raw_line)
            index += 1
            if child_raw_value:
                item[child_key] = _parse_scalar(child_raw_value)
            else:
                child_value, index = _parse_yaml_block(lines, index, child_indent + 2)
                item[child_key] = child_value

        values.append(item)

    return values, index


def _parse_yaml_mapping(
    lines: list[tuple[int, str, str]], index: int, indent: int
) -> tuple[dict[str, Any], int]:
    mapping: dict[str, Any] = {}
    while index < len(lines):
        current_indent, stripped, raw_line = lines[index]
        if current_indent < indent:
            break
        if current_indent != indent or stripped.startswith("- "):
            break

        key, raw_value = _split_key_value(stripped, raw_line)
        index += 1
        if raw_value:
            mapping[key] = _parse_scalar(raw_value)
        else:
            value, index = _parse_yaml_block(lines, index, indent + 2)
            mapping[key] = value

    return mapping, index


def _split_key_value(line: str, raw_line: str) -> tuple[str, str]:
    if ":" not in line:
        raise ValueError(f"expected key: value in line: {raw_line}")
    key, value = line.split(":", 1)
    return key.strip(), value.strip()


def _parse_scalar(value: str) -> Any:
    if value == "[]":
        return []
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value
