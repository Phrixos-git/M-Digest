from __future__ import annotations

from email.message import EmailMessage
import unittest
from unittest.mock import patch

from info_agent.config import Source
from info_agent.rss import fetch_entries


class _Response:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return self.body


class RssTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = Source("Example", "https://example.com/feed", "Tech")

    def test_fetches_rss_cleans_text_formats_date_and_applies_limit(self) -> None:
        body = b"""<rss><channel>
          <item><title>A &amp;amp; B\n news</title><link>https://example.com/1</link>
            <pubDate>Sat, 18 Jul 2026 05:00:00 +0900</pubDate><description> first\n summary </description></item>
          <item><title>Second</title><guid>https://example.com/2</guid></item>
        </channel></rss>"""
        with patch("info_agent.rss.urlopen", return_value=_Response(body)):
            entries = fetch_entries(self.source, limit=1)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].title, "A & B news")
        self.assertEqual(entries[0].summary, "first summary")
        self.assertEqual(entries[0].published, "2026-07-17 20:00 UTC")
        self.assertEqual((entries[0].source, entries[0].category), ("Example", "Tech"))

    def test_falls_back_to_atom_and_selects_alternate_link(self) -> None:
        body = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry>
          <title>Atom</title><link rel="self" href="https://example.com/self"/>
          <link href="https://example.com/article"/><updated>2026-07-18T05:00:00Z</updated>
          <summary>Summary</summary></entry></feed>"""
        with patch("info_agent.rss.urlopen", return_value=_Response(body)):
            entry = fetch_entries(self.source)[0]
        self.assertEqual(entry.url, "https://example.com/article")
        self.assertEqual(entry.published, "2026-07-18 05:00 UTC")

    def test_skips_entries_without_title_or_url(self) -> None:
        body = b"<rss><channel><item><title>Missing URL</title></item></channel></rss>"
        with patch("info_agent.rss.urlopen", return_value=_Response(body)):
            self.assertEqual(fetch_entries(self.source), [])

    def test_rejects_html_and_invalid_xml(self) -> None:
        for body, message in ((b"<!doctype html><p>x", "received HTML"), (b"<rss>", "invalid RSS")):
            with self.subTest(body=body), patch("info_agent.rss.urlopen", return_value=_Response(body)):
                with self.assertRaisesRegex(ValueError, message):
                    fetch_entries(self.source)


if __name__ == "__main__":
    unittest.main()
