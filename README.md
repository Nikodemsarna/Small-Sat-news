# 🛰️ Small-Sat News

A daily email newsletter that aggregates news from across the space-sector and
satellite press, filters it down to **small-satellite development** (cubesats,
nanosats, microsats, smallsat constellations, rideshare launches), summarizes
each story with the **Claude API**, and emails a clean digest.

Built to run unattended on **GitHub Actions** — one scheduled job per day.

---

## How it works

```
config/feeds.yaml          (every space-news portal with an RSS feed)
        │
        ▼
 fetch  → pulls & parses all feeds concurrently (resilient to dead feeds)
        ▼
 filter → keeps only recent small-satellite stories, de-duplicates
        ▼
 summarize → one batched Claude call: editorial intro + per-story summaries
             + relevance ratings + "top picks"   (extractive fallback if no key)
        ▼
 render → responsive HTML email + plain-text alternative (Jinja2)
        ▼
 deliver → Resend API or SMTP, to your inbox
```

Each stage is a small module under [`smallsat_news/`](smallsat_news/). A single
edition is one Claude API call per day, so running costs are negligible.

---

## Quick start (local)

```bash
pip install -r requirements.txt

# Preview today's edition without sending — writes the HTML so you can open it.
python -m smallsat_news --dry-run --output output/edition.html
open output/edition.html        # or just inspect the file
```

`--dry-run` needs no API key (it falls back to extractive summaries and never
sends). Add `ANTHROPIC_API_KEY` to your environment for real AI summaries.

To actually send, configure a delivery provider (below) and drop `--dry-run`.

---

## Configuration

All configuration is via environment variables — see
[`.env.example`](.env.example) for the full list. The important ones:

| Variable | Purpose | Default |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | Claude API key for summaries | _(falls back to extractive)_ |
| `NEWSLETTER_TO` | Recipient address | `nikodem.sarna@gmail.com` |
| `RESEND_API_KEY` | Use Resend for delivery | — |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` | Use SMTP for delivery | — |
| `NEWSLETTER_FROM` | From address | `Small-Sat News <onboarding@resend.dev>` |
| `SMALLSAT_MODEL` | Claude model | `claude-opus-4-8` |
| `SMALLSAT_EFFORT` | Reasoning effort (`low`–`max`) | `medium` |
| `SMALLSAT_WINDOW_HOURS` | How far back "recent" reaches | `30` |
| `SMALLSAT_MAX_ARTICLES` | Cap on stories per edition | `25` |

### Delivery: pick one provider

- **Resend** (recommended — one key, no SMTP setup): create a key at
  [resend.com](https://resend.com) and set `RESEND_API_KEY`. The free tier sends
  from `onboarding@resend.dev` to any address; verify a domain to use your own
  `From`.
- **SMTP** (e.g. Gmail): create an [App Password](https://support.google.com/accounts/answer/185833)
  and set `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USER`, `SMTP_PASSWORD`.

If `RESEND_API_KEY` is set it is used; otherwise SMTP is used if `SMTP_HOST` is set.

---

## Deploy on GitHub Actions (daily, hands-off)

The workflow in [`.github/workflows/daily-newsletter.yml`](.github/workflows/daily-newsletter.yml)
runs every morning at **07:30 UTC** (editable cron) and can also be triggered
manually (with an optional dry run).

1. Push this repo to GitHub.
2. In **Settings → Secrets and variables → Actions**, add the secrets you need:
   - `ANTHROPIC_API_KEY`
   - **either** `RESEND_API_KEY` **or** `SMTP_HOST` + `SMTP_PORT` + `SMTP_USER` + `SMTP_PASSWORD`
   - optionally `NEWSLETTER_TO`, `NEWSLETTER_FROM`
   - optionally, as **Variables**: `SMALLSAT_MODEL`, `SMALLSAT_EFFORT`, `SMALLSAT_WINDOW_HOURS`, `SMALLSAT_MAX_ARTICLES`
3. (Optional) Trigger **Run workflow** once with *dry run* checked to preview —
   the rendered HTML is uploaded as a build artifact.

The job runs the test suite before sending, and uploads the rendered edition as
an artifact every run for easy inspection.

---

## Adding or changing sources

Edit [`config/feeds.yaml`](config/feeds.yaml) — each entry is just a `name` and
an RSS/Atom `url`. Feeds that fail on a given day are logged and skipped, so the
newsletter never breaks because one portal is down.

To change what counts as a small-satellite story, edit `SMALLSAT_KEYWORDS` in
[`smallsat_news/filter.py`](smallsat_news/filter.py).

---

## Tests

```bash
python -m pytest -q
```

Covers the keyword/recency/dedup filtering and the HTML/text rendering. No
network or API key required.

---

## Project layout

```
smallsat_news/
  config.py      env-driven settings
  sources.py     load feeds.yaml
  fetch.py       concurrent RSS fetch + normalize
  filter.py      smallsat keyword + recency filter + dedup
  summarize.py   Claude API summaries (+ extractive fallback)
  render.py      HTML + plain-text rendering
  mailer.py      Resend / SMTP delivery
  newsletter.py  pipeline orchestration
  __main__.py    CLI entry point
templates/       Jinja2 email templates
config/feeds.yaml
tests/
.github/workflows/daily-newsletter.yml
```
