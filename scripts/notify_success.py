import os
import urllib.parse
import urllib.request

message = f"Artikel baru tayang\n{os.environ['ARTICLE_TITLE']}\n{os.environ['ARTICLE_URL']}"
data = urllib.parse.urlencode({"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": message, "disable_web_page_preview": "true"}).encode()
req = urllib.request.Request(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage", data, {"Content-Type": "application/x-www-form-urlencoded"})
with urllib.request.urlopen(req, timeout=20) as response:
    response.read()

