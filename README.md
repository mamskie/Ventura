# Trend Desk

An independent trend publication: source-led briefings on the topics
capturing attention across the United States, published to GitHub Pages
at https://mamskie.github.io/Ventura/

## How publishing works

Articles are written by Yoshi (Muse) and pushed directly to `main`:

- `site/articles/` — one HTML page per story
- `site/index.html` — homepage, rebuilt from the article files
- `site/processed.json` — topics already covered
- `site/sitemap.xml` — regenerated with every publish

GitHub Pages is configured to deploy from the `main` branch (root), so
every push to `main` triggers a fresh deployment automatically.

The old GitHub Actions automation (`publish.yml`, Gemini generation,
Telegram bot) is retired; `publish.yml` remains only as a dormant manual
fallback (`workflow_dispatch`).
