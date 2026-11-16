"""Tests for scripts/publish.py round-2 changes.

All HTTP/Gemini calls are mocked; no real API key is needed.
Run from the repo root:  python -m unittest discover -s tests -v
"""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "12345")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import publish  # noqa: E402


def words(n: int) -> str:
    return " ".join(["word"] * n)


def part_text(heading: str, total_words: int, paragraphs: int = 4) -> str:
    per = total_words // paragraphs
    body = "\n\n".join(words(per) for _ in range(paragraphs))
    return f"{heading}\n\n{body}"


class ChunkedGenerationTests(unittest.TestCase):
    def setUp(self):
        self.sources = [
            {"url": "https://example.com/a", "title": "A", "publisher": "Pub A", "excerpt": "excerpt a"},
            {"url": "https://example.com/b", "title": "B", "publisher": "Pub B", "excerpt": "excerpt b"},
        ]

    def fake_gemini(self, part1_words=440, part2_words=440, part3_words=440):
        def _generate(prompt):
            if "Write the opening" in prompt:
                return part_text("# Test Topic Title", part1_words)
            if "deep-dive section" in prompt:
                return part_text("## The Deep Dive", part2_words)
            if "closing section" in prompt:
                return part_text("## Why It Matters", part3_words)
            raise AssertionError(f"unexpected prompt: {prompt[:80]}")

        return _generate

    def test_parts_combined_in_order_and_long_enough(self):
        with patch.object(publish, "gemini_generate", side_effect=self.fake_gemini()):
            article = publish.call_gemini("Test Topic", self.sources)
        self.assertIsNotNone(article)
        self.assertTrue(article.startswith("# Test Topic Title"))
        self.assertLess(article.index("## The Deep Dive"), article.index("## Why It Matters"))
        total = len(article.split())
        self.assertGreaterEqual(total, 1000)
        self.assertLessEqual(total, 1600)
        paragraphs = [p for p in article.split("\n\n") if len(p.split()) >= 35]
        self.assertGreaterEqual(len(paragraphs), 6)

    def test_per_part_retry_retries_only_that_part(self):
        calls = {"part1": 0, "part2": 0, "part3": 0}

        def _generate(prompt):
            if "Write the opening" in prompt:
                calls["part1"] += 1
                return part_text("# Test Topic Title", 440)
            if "deep-dive section" in prompt:
                calls["part2"] += 1
                if calls["part2"] == 1:
                    return "too short"
                return part_text("## The Deep Dive", 440)
            if "closing section" in prompt:
                calls["part3"] += 1
                return part_text("## Why It Matters", 440)
            raise AssertionError("unexpected prompt")

        with patch.object(publish, "gemini_generate", side_effect=_generate):
            article = publish.call_gemini("Test Topic", self.sources)
        self.assertIsNotNone(article)
        self.assertEqual(calls, {"part1": 1, "part2": 2, "part3": 1})

    def test_part_still_failing_after_retries_skips_trend(self):
        def _generate(prompt):
            if "Write the opening" in prompt:
                return part_text("# Test Topic Title", 440)
            if "deep-dive section" in prompt:
                return part_text("## The Deep Dive", 440)
            return "truncated"

        with patch.object(publish, "gemini_generate", side_effect=_generate):
            article = publish.call_gemini("Test Topic", self.sources)
        self.assertIsNone(article)

    def test_whole_article_validation_rejects_short_total(self):
        # Each part passes the per-part minimum (250) but the total is
        # under 1000 words, so the combined article must be rejected.
        with patch.object(publish, "gemini_generate", side_effect=self.fake_gemini(440, 260, 260)):
            article = publish.call_gemini("Test Topic", self.sources)
        self.assertIsNone(article)

    def test_part1_must_start_with_title(self):
        def _generate(prompt):
            if "Write the opening" in prompt:
                return part_text("No title here", 440)
            return part_text("## Heading", 440)

        with patch.object(publish, "gemini_generate", side_effect=_generate):
            self.assertIsNone(publish.call_gemini("Test Topic", self.sources))


class OpenverseTests(unittest.TestCase):
    def test_keywords_strip_filler_words(self):
        self.assertEqual(
            publish.openverse_keywords(
                "Understanding the Latest Kenneth Walker Search Trend: What to Know About His Week 10 Status"
            ),
            ["kenneth", "walker", "10"],
        )
        self.assertEqual(
            publish.openverse_keywords(
                "Complete Viewing Guide and Matchup Details for the Minnesota Vikings and Green Bay Packers Game"
            ),
            ["minnesota", "vikings", "green", "bay", "packers", "game"],
        )

    def test_search_openverse_parses_results(self):
        payload = {
            "results": [
                {"url": "https://live.staticflickr.com/1/img_b.jpg", "creator": "Jane Doe"},
                {"url": "not-a-url", "creator": "Nobody"},
                {"url": "https://example.com/img.png", "creator": ""},
            ]
        }
        with patch.object(publish, "request", return_value=json.dumps(payload).encode()):
            candidates = publish.search_openverse_image("american football")
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]["creator"], "Jane Doe")

    def test_og_image_takes_precedence_over_openverse(self):
        sources = [{"url": "https://example.com/a", "image_url": "https://example.com/og.jpg", "publisher": "Pub"}]
        with (
            patch.object(publish, "download_image", return_value=(b"x" * 5000, ".jpg")),
            patch.object(publish, "search_openverse_image") as mock_search,
            patch.object(publish, "IMAGES", Path("/tmp/test-images-og")),
        ):
            image = publish.pick_source_image(sources, "test-slug", keywords="some topic")
        mock_search.assert_not_called()
        self.assertEqual(image["credit"], "Pub")
        self.assertTrue(image["rel"].startswith("images/test-slug"))

    def test_openverse_fallback_when_no_og_image(self):
        sources = [{"url": "https://example.com/a", "publisher": "Pub"}]
        candidates = [{"url": "https://live.staticflickr.com/1/img_b.jpg", "creator": "Jane Doe"}]
        with (
            patch.object(publish, "download_image", return_value=(b"x" * 5000, ".jpg")),
            patch.object(publish, "search_openverse_image", return_value=candidates),
            patch.object(publish, "IMAGES", Path("/tmp/test-images-ov")),
        ):
            image = publish.pick_source_image(sources, "test-slug", keywords="american football")
        self.assertEqual(image["credit"], "Jane Doe via Openverse")
        self.assertTrue(image["rel"].endswith(".jpg"))

    def test_openverse_fallback_when_og_download_fails(self):
        sources = [{"url": "https://example.com/a", "image_url": "https://example.com/og.jpg", "publisher": "Pub"}]
        candidates = [{"url": "https://live.staticflickr.com/1/img_b.jpg", "creator": ""}]

        def _download(url, user_agent=None):
            return None if "og.jpg" in url else (b"x" * 5000, ".png")

        with (
            patch.object(publish, "download_image", side_effect=_download),
            patch.object(publish, "search_openverse_image", return_value=candidates),
            patch.object(publish, "IMAGES", Path("/tmp/test-images-ov2")),
        ):
            image = publish.pick_source_image(sources, "test-slug", keywords="american football")
        self.assertEqual(image["credit"], "Openverse")
        self.assertTrue(image["rel"].endswith(".png"))

    def test_no_image_anywhere_returns_none(self):
        sources = [{"url": "https://example.com/a", "publisher": "Pub"}]
        with (
            patch.object(publish, "search_openverse_image", return_value=[]),
            patch.object(publish, "IMAGES", Path("/tmp/test-images-none")),
        ):
            self.assertIsNone(publish.pick_source_image(sources, "test-slug", keywords="american football"))

    def test_progressive_shortening_of_openverse_queries(self):
        tried = []

        def _search(query):
            tried.append(query)
            if query == "kenneth walker":
                return [{"url": "https://example.com/img.jpg", "creator": "Ann"}]
            return []

        sources = [{"url": "https://example.com/a"}]
        with (
            patch.object(publish, "search_openverse_image", side_effect=_search),
            patch.object(publish, "download_image", return_value=(b"x" * 5000, ".jpg")),
            patch.object(publish, "IMAGES", Path("/tmp/test-images-short")),
        ):
            image = publish.pick_source_image(sources, "test-slug", keywords="Kenneth Walker Football Star")
        self.assertEqual(
            tried,
            ["kenneth walker football star", "kenneth walker football", "kenneth walker"],
        )
        self.assertEqual(image["credit"], "Ann via Openverse")

    def test_openverse_download_uses_browser_ua(self):
        # Flickr's CDN 403s bot user-agents; Openverse downloads must
        # use a browser UA, while og:image downloads keep the bot UA.
        sources = [{"url": "https://example.com/a"}]
        candidates = [{"url": "https://live.staticflickr.com/1/img_b.jpg", "creator": "Jane"}]
        with (
            patch.object(publish, "download_image", return_value=(b"x" * 5000, ".jpg")) as mock_dl,
            patch.object(publish, "search_openverse_image", return_value=candidates),
            patch.object(publish, "IMAGES", Path("/tmp/test-images-ua")),
        ):
            publish.pick_source_image(sources, "test-slug", keywords="american football")
        mock_dl.assert_called_once()
        _, kwargs = mock_dl.call_args
        self.assertEqual(kwargs.get("user_agent"), publish.BROWSER_USER_AGENT)

    def test_og_download_uses_bot_ua(self):
        sources = [{"url": "https://example.com/a", "image_url": "https://example.com/og.jpg", "publisher": "Pub"}]
        with (
            patch.object(publish, "download_image", return_value=(b"x" * 5000, ".jpg")) as mock_dl,
            patch.object(publish, "IMAGES", Path("/tmp/test-images-ua2")),
        ):
            publish.pick_source_image(sources, "test-slug", keywords="american football")
        _, kwargs = mock_dl.call_args
        self.assertEqual(kwargs.get("user_agent", publish.USER_AGENT), publish.USER_AGENT)

    def test_single_word_fallback_skips_pure_numbers(self):
        tried = []

        def _search(query):
            tried.append(query)
            if query == "nfl":
                return [{"url": "https://example.com/img.jpg", "creator": "Ann"}]
            return []

        sources = [{"url": "https://example.com/a"}]
        with (
            patch.object(publish, "search_openverse_image", side_effect=_search),
            patch.object(publish, "download_image", return_value=(b"x" * 5000, ".jpg")),
            patch.object(publish, "IMAGES", Path("/tmp/test-images-single")),
        ):
            image = publish.pick_source_image(sources, "test-slug", keywords="NFL Week 10 Slate")
        self.assertEqual(tried, ["nfl 10 slate", "nfl 10", "nfl"])
        self.assertIsNotNone(image)


class TopicModeTests(unittest.TestCase):
    def test_search_news_parses_rss(self):
        rss = b"""<?xml version="1.0"?><rss version="2.0"><channel>
        <item><title>Team Wins Big</title><link>https://news.google.com/rss/articles/abc</link><source url="https://example.com">Example News</source></item>
        <item><title>Second Story</title><link>https://example.com/direct</link><source url="https://other.com">Other News</source></item>
        </channel></rss>"""
        with (
            patch.object(publish, "request", return_value=rss),
            patch.object(publish, "resolve_url", side_effect=lambda u: u),
        ):
            items = publish.search_news("team wins")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["title"], "Team Wins Big")
        self.assertEqual(items[0]["publisher"], "Example News")
        self.assertEqual(items[1]["url"], "https://example.com/direct")

    def test_publish_topic_requires_two_sources(self):
        with patch.object(publish, "search_news", return_value=[{"title": "Only One"}]):
            with self.assertRaisesRegex(RuntimeError, "at least 2 news sources"):
                publish.publish_topic("some topic", set(), Path("/tmp/processed.json"))

    def test_publish_topic_raises_when_publish_fails(self):
        sources = [{"title": "A"}, {"title": "B"}]
        with (
            patch.object(publish, "search_news", return_value=sources),
            patch.object(publish, "try_publish", return_value=False),
        ):
            with self.assertRaisesRegex(RuntimeError, "Could not publish"):
                publish.publish_topic("some topic", set(), Path("/tmp/processed.json"))

    def test_publish_topic_succeeds(self):
        sources = [{"title": "A"}, {"title": "B"}]
        with (
            patch.object(publish, "search_news", return_value=sources),
            patch.object(publish, "try_publish", return_value=True),
        ):
            publish.publish_topic("some topic", set(), Path("/tmp/processed.json"))

    def test_main_topic_mode_bypasses_daily_cap(self):
        with (
            patch.dict(os.environ, {"TOPIC": "  some topic  "}),
            patch.object(publish, "publish_topic") as mock_topic,
            patch.object(publish, "count_today") as mock_count,
        ):
            publish.main()
        mock_topic.assert_called_once()
        mock_count.assert_not_called()
        # Topic is stripped before publish_topic is called.
        self.assertEqual(mock_topic.call_args.args[0], "some topic")

    def test_main_empty_topic_is_scheduled_mode(self):
        with (
            patch.dict(os.environ, {"TOPIC": "   "}),
            patch.object(publish, "publish_topic") as mock_topic,
            patch.object(publish, "count_today", return_value=99),
        ):
            publish.main()
        mock_topic.assert_not_called()


if __name__ == "__main__":
    unittest.main()
