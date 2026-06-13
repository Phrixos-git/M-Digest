from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Iterable
from urllib.request import Request, urlopen
from xml.etree import ElementTree
from xml.etree.ElementTree import ParseError

from .config import Source


@dataclass(frozen=True)
class Entry:
    source: str
    category: str
    title: str
    url: str
    published: str
    summary: str


def fetch_entries(source: Source, limit: int = 5, timeout: int = 20) -> list[Entry]:
    request = Request(
        source.url,
        headers={
            "User-Agent": "info-agent/0.1 (+https://localhost.invalid; RSS daily report)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.5",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        body = response.read()

    if _looks_like_html(body):
        raise ValueError("expected RSS/Atom XML but received HTML")

    try:
        root = ElementTree.fromstring(body)
    except ParseError as exc:
        raise ValueError(f"invalid RSS/Atom XML: {exc}") from exc

    entries = list(_parse_rss(root, source))
    if not entries:
        entries = list(_parse_atom(root, source))
    return entries[:limit]


def _looks_like_html(body: bytes) -> bool:
    prefix = body.lstrip()[:100].lower()
    return prefix.startswith(b"<!doctype html") or prefix.startswith(b"<html")


def _parse_rss(root: ElementTree.Element, source: Source) -> Iterable[Entry]:
    for item in root.findall(".//item"):
        title = _clean(_text(item, "title"))
        url = _clean(_text(item, "link")) or _clean(_text(item, "guid"))
        if not title or not url:
            continue
        yield Entry(
            source=source.name,
            category=source.category,
            title=title,
            url=url,
            published=_format_date(_text(item, "pubDate") or _text(item, "dc:date")),
            summary=_clean(_text(item, "description")),
        )


def _parse_atom(root: ElementTree.Element, source: Source) -> Iterable[Entry]:
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for item in root.findall(".//atom:entry", ns) or root.findall(".//entry"):
        title = _clean(_find_text(item, ["atom:title", "title"], ns))
        url = _atom_link(item, ns)
        if not title or not url:
            continue
        yield Entry(
            source=source.name,
            category=source.category,
            title=title,
            url=url,
            published=_format_date(_find_text(item, ["atom:published", "atom:updated", "published", "updated"], ns)),
            summary=_clean(_find_text(item, ["atom:summary", "atom:content", "summary", "content"], ns)),
        )


def _text(item: ElementTree.Element, tag: str) -> str:
    if ":" in tag:
        suffix = tag.split(":", 1)[1]
        found = item.find(f".//{{*}}{suffix}")
    else:
        found = item.find(tag)
    return found.text if found is not None and found.text else ""


def _find_text(item: ElementTree.Element, tags: list[str], ns: dict[str, str]) -> str:
    for tag in tags:
        found = item.find(tag, ns)
        if found is not None and found.text:
            return found.text
    return ""


def _atom_link(item: ElementTree.Element, ns: dict[str, str]) -> str:
    links = item.findall("atom:link", ns) or item.findall("link")
    for link in links:
        rel = link.attrib.get("rel", "alternate")
        href = link.attrib.get("href", "")
        if href and rel == "alternate":
            return href
    return links[0].attrib.get("href", "") if links else ""


def _clean(value: str) -> str:
    text = unescape(value or "")
    text = " ".join(text.replace("\n", " ").replace("\r", " ").split())
    return text


def _format_date(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
