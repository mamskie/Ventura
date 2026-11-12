import os
import urllib.parse
import urllib.request

token = os.getenv("TELEGRAM_BOT_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID")
if token and chat_id:
    run_url = os.getenv("GITHUB_SERVER_URL", "https://github.com") + "/" + os.environ["GITHUB_REPOSITORY"] + "/actions/runs/" + os.environ["GITHUB_RUN_ID"]
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": f"Otomasi blog gagal berjalan. Detail workflow: {run_url}", "disable_web_page_preview": "true"}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data, {"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=20) as response:
        response.read()

