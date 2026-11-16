"""Tests for scripts/check_telegram.py.

Telegram and GitHub APIs are mocked; no real tokens are used.
Run from the repo root:  python -m unittest discover -s tests -v
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import check_telegram  # noqa: E402

OWNER_CHAT = 12345
OTHER_CHAT = 99999


def update(update_id, chat_id, text):
    return {"update_id": update_id, "message": {"message_id": update_id, "chat": {"id": chat_id}, "text": text}}


class CheckTelegramTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_CHAT_ID": str(OWNER_CHAT), "GITHUB_TOKEN": "gh-test"},
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.offset_path = Path(self.tmp.name) / "telegram_offset.json"

    def run_main(self, updates, dispatch_ok=True, initial_offset=0):
        """Run main() with a canned getUpdates result. Returns (rc, api_calls, dispatched)."""
        if initial_offset:
            self.offset_path.write_text(json.dumps(initial_offset))
        api_calls = []
        dispatched = []

        def fake_api(token, method, payload=None):
            api_calls.append((method, payload))
            if method.startswith("getUpdates"):
                return {"ok": True, "result": updates}
            if method == "sendMessage":
                return {"ok": True, "result": {}}
            raise AssertionError(f"unexpected method {method}")

        def fake_dispatch(github_token, topic):
            dispatched.append(topic)
            return dispatch_ok

        with (
            patch.object(check_telegram, "telegram_api", side_effect=fake_api),
            patch.object(check_telegram, "dispatch_workflow", side_effect=fake_dispatch),
        ):
            rc = check_telegram.main(offset_path=self.offset_path)
        return rc, api_calls, dispatched

    def sent_texts(self, api_calls):
        return [p["text"] for m, p in api_calls if m == "sendMessage"]

    def test_no_new_messages_exits_quietly(self):
        rc, api_calls, dispatched = self.run_main([])
        self.assertEqual(rc, 0)
        self.assertEqual(dispatched, [])
        self.assertFalse(self.offset_path.exists())

    def test_start_gets_help_reply_and_advances_offset(self):
        rc, api_calls, dispatched = self.run_main([update(10, OWNER_CHAT, "/start")])
        self.assertEqual(rc, 0)
        self.assertEqual(dispatched, [])
        self.assertIn("Kirim topik", self.sent_texts(api_calls)[0])
        self.assertEqual(json.loads(self.offset_path.read_text()), 10)

    def test_wrong_chat_is_ignored_but_skipped_past(self):
        rc, api_calls, dispatched = self.run_main([update(11, OTHER_CHAT, "secret topic")])
        self.assertEqual(rc, 0)
        self.assertEqual(dispatched, [])
        self.assertEqual(self.sent_texts(api_calls), [])
        self.assertEqual(json.loads(self.offset_path.read_text()), 11)

    def test_one_topic_per_run(self):
        rc, api_calls, dispatched = self.run_main(
            [update(20, OWNER_CHAT, "first topic"), update(21, OWNER_CHAT, "second topic")]
        )
        self.assertEqual(rc, 0)
        self.assertEqual(dispatched, ["first topic"])
        # Offset advances past only the processed update; the second
        # topic stays for the next poll.
        self.assertEqual(json.loads(self.offset_path.read_text()), 20)

    def test_dispatch_failure_does_not_advance_offset(self):
        rc, api_calls, dispatched = self.run_main(
            [update(30, OWNER_CHAT, "failing topic")], dispatch_ok=False
        )
        self.assertEqual(rc, 1)
        self.assertEqual(dispatched, ["failing topic"])
        self.assertFalse(self.offset_path.exists())

    def test_dispatch_failure_keeps_earlier_handled_offset(self):
        rc, api_calls, dispatched = self.run_main(
            [update(40, OWNER_CHAT, "/help"), update(41, OWNER_CHAT, "failing topic")],
            dispatch_ok=False,
        )
        self.assertEqual(rc, 1)
        # The /help reply was handled, so the offset advances past it —
        # but not past the failed topic.
        self.assertEqual(json.loads(self.offset_path.read_text()), 40)

    def test_topic_truncated_to_200_chars(self):
        long_topic = "x" * 300
        rc, api_calls, dispatched = self.run_main([update(50, OWNER_CHAT, long_topic)])
        self.assertEqual(rc, 0)
        self.assertEqual(len(dispatched[0]), 200)

    def test_getupdates_uses_stored_offset(self):
        rc, api_calls, dispatched = self.run_main([], initial_offset=41)
        get_updates_calls = [m for m, _ in api_calls if m.startswith("getUpdates")]
        self.assertEqual(len(get_updates_calls), 1)
        self.assertIn("offset=42", get_updates_calls[0])

    def test_acknowledgement_sent_before_dispatch(self):
        rc, api_calls, dispatched = self.run_main([update(60, OWNER_CHAT, "my topic")])
        texts = self.sent_texts(api_calls)
        self.assertEqual(len(texts), 1)
        self.assertIn("my topic", texts[0])
        self.assertEqual(dispatched, ["my topic"])


if __name__ == "__main__":
    unittest.main()
