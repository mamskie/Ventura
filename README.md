# Trend Desk

Static English-language blog that checks US Google Trends every six hours, writes a sourced explainer with Gemini, publishes to GitHub Pages, then reports the live article to Telegram.

## Publishing flow

1. GitHub Actions runs on a six-hour schedule or by manual dispatch.
2. The script reads the Google Trends Trending Now RSS feed and skips previously published topics.
3. It skips sensitive topic keywords, requires at least two related news URLs from different domains, and fetches readable source excerpts.
4. Gemini writes an original explainer using only the fetched excerpts. Articles without enough source material are skipped.
5. At most one article is generated per run and four per UTC day. The static article and processed-topic list are committed to this repository.
6. GitHub Pages deploys the updated site. Telegram receives the title and link only after deployment succeeds. Workflow failures are reported to Telegram when bot settings are present.

## Configure GitHub

In **Settings → Secrets and variables → Actions**, add these repository secrets:

| Secret | Value |
| --- | --- |
| `GEMINI_API_KEY` | API key created in Google AI Studio |
| `TELEGRAM_BOT_TOKEN` | Token from BotFather |
| `TELEGRAM_CHAT_ID` | Chat ID where reports should arrive |

These repository variables are optional overrides in the **Variables** tab:

| Variable | Value |
| --- | --- |
| `TRENDS_RSS_URL` | Optional RSS URL override. Defaults to the Google Trends US feed. |
| `SITE_URL` | Optional override. Without it, the workflow uses `https://mamskie.github.io/Ventura` automatically. |
| `GEMINI_MODEL` | Optional; defaults to `gemini-2.5-flash` |

Never put API keys or bot tokens in repository files. To get the Telegram chat ID, create the bot, open its chat, send `/start`, then inspect a recent update using the Bot API `getUpdates` endpoint. Do not paste the token into this repository or chat.

## Enable GitHub Pages

1. Open **Settings → Pages** and set **Build and deployment → Source** to **GitHub Actions**.
2. Add the three secrets above. Variables are optional; the workflow defaults to the US Trends feed, GitHub Pages URL, and `gemini-2.5-flash` model.
3. Open **Actions → Publish trend article → Run workflow** for the first run.
4. Check the Actions log and confirm the website deploys. Scheduled runs then happen every six hours (UTC).

The site URL will be `https://mamskie.github.io/Ventura/` unless a custom domain is connected. A custom domain is optional.

## Cost and editorial limits

- GitHub Pages and GitHub Actions are used for a low-cost trial. Account limits and service terms can change.
- Gemini use depends on the free quota available to the Google AI Studio project. The generator does not enable paid Google Search grounding; it uses excerpts fetched from the Trends feed's related news links.
- The workflow only publishes when it can read at least two source pages from different domains. Trend titles and external webpages are untrusted input.
- Automatic writing can still make mistakes. The keyword filter is a simple safeguard, not comprehensive editorial review.
- Four posts per day is a maximum, not a target. It may publish fewer or none if trends lack suitable sources.
- Monetization is not configured. Ad networks have their own review and traffic requirements.

