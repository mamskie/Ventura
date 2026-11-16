"""Poll Telegram for user topics and dispatch the publish workflow.

Runs every 10 minutes from .github/workflows/telegram_topics.yml.
Reads the last processed update id from .github/telegram_offset.json
(a repo file outside site/, so committing it never triggers the
publish workflow). Only messages from TELEGRAM_CHAT_ID are accepted;
everyone else is ignored. Only the FIRST new topic per run is
dispatched, so two polls can never start concurrent publish runs.
On dispatch failure the offset is NOT advanced, so the next poll
retries the same topic. Secrets are never logged.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFFSET_FILE = ROOT / ".github" / "telegram_offset.json"
REPOSITORY = os.getenv("GITHUB_REPOSITORY", "mamskie/Ventura")
MAX_TOPIC_CHARS = 200
HELP_TEXT = (
    "Halo! Kirim topik opo ae nang kene, tak gawekno artikel-e.\n"
    "Conto: Timnas Indonesia vs Jepang\n"
    "Artikel-e bakal tayang nang Trend Desk, terus tak kabari link-e."
)


def telegram_api(token: str, method: str, payload: dict | None = None):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(payload).encode() if payload else None
    headers = {"Content-Type": "application/x-www-form-urlencoded"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode("utf-8", errors="ignore"))


def send_message(token: str, chat_id: int, text: str) -> None:
    telegram_api(token, "sendMessage", {"chat_id": str(chat_id), "text": text, "disable_web_page_preview": "true"})


def get_updates(token: str, offset: int) -> list:
    params = urllib.parse.urlencode({"offset": offset, "timeout": 5})
    payload = telegram_api(token, f"getUpdates?{params}")
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram getUpdates failed: {payload}")
    return payload.get("result", [])


def dispatch_workflow(github_token: str, topic: str) -> bool:
    url = f"https://api.github.com/repos/{REPOSITORY}/actions/workflows/publish.yml/dispatches"
    body = json.dumps({"ref": "main", "inputs": {"topic": topic}}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.status == 204
    except urllib.error.HTTPError as exc:
        print(f"GitHub dispatch failed: HTTP {exc.code}", file=sys.stderr)
        return False
    except Exception as exc:  # noqa: BLE001 - dispatch is best-effort, offset stays
        print(f"GitHub dispatch failed: {exc}", file=sys.stderr)
        return False


def load_offset(path: Path) -> int:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return int(value)
    except (OSError, ValueError, TypeError):
        return 0


def save_offset(path: Path, value: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def main(offset_path: Path = OFFSET_FILE) -> int:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = int(os.environ["TELEGRAM_CHAT_ID"])
    github_token = os.environ["GITHUB_TOKEN"]
    offset = load_offset(offset_path)
    updates = get_updates(token, offset + 1)
    if not updates:
        print("No new Telegram updates")
        return 0
    new_offset = offset
    dispatched = False
    for update in sorted(updates, key=lambda u: u.get("update_id", 0)):
        update_id = update.get("update_id", 0)
        message = update.get("message") or {}
        text = (message.get("text") or "").strip()
        chat = message.get("chat") or {}
        if not text or chat.get("id") != chat_id:
            # Not a message from the owner — skip past it.
            new_offset = max(new_offset, update_id)
            continue
        if text in {"/start", "/help"}:
            send_message(token, chat_id, HELP_TEXT)
            new_offset = max(new_offset, update_id)
            continue
        if dispatched:
            # One topic per run; leave later topics for the next poll.
            break
        topic = text[:MAX_TOPIC_CHARS]
        print(f"New topic from Telegram (update {update_id}): {topic[:80]!r}")
        send_message(token, chat_id, f"Siap, tak golekno sumber + artikel kanggo topik:\n{topic}")
        if dispatch_workflow(github_token, topic):
            print(f"Dispatched publish workflow for topic {topic[:80]!r}")
            new_offset = max(new_offset, update_id)
            dispatched = True
        else:
            print(f"Dispatch failed for update {update_id}; offset NOT advanced, will retry next poll", file=sys.stderr)
            if new_offset > offset:
                save_offset(offset_path, new_offset)
            return 1
    if new_offset > offset:
        save_offset(offset_path, new_offset)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
