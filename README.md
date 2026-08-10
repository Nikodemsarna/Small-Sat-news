# 🪄 Vibe Coding Daily

A daily email newsletter that aggregates news from across the developer-tools
and AI press, filters it down to **vibe coding** — AI-assisted software
development (Copilot, Cursor, Claude Code, Codeium/Windsurf, Aider, Devin,
Replit Agent, Codex, and the practice itself) — summarizes each story with a
**free LLM API**, and emails a clean digest.

Built to run unattended on **GitHub Actions** — one scheduled job per day.

> This project reuses the infrastructure of an earlier small-satellite
> newsletter; the domain was pivoted to vibe coding. The repository name is
> unchanged.

---

## How it works

```
config/feeds.yaml          (dev-tools + AI portals, and targeted Hacker News searches)
        │
        ▼
 fetch  → pulls & parses all feeds concurrently (resilient to dead feeds)
        ▼
 filter → keeps only recent vibe-coding stories, de-duplicates
        ▼
 summarize → one batched LLM call: editorial intro + per-story summaries
             + relevance ratings + "top picks"
             (Gemini/Groq free tiers, or Claude; extractive fallback if no key)
        ▼
 render → responsive HTML email + plain-text alternative (Jinja2)
        ▼
 deliver → Resend API or SMTP, to your inbox
```

Each stage is a small module under [`vibecoding_news/`](vibecoding_news/). A
single edition is one LLM call per day, so running costs are negligible (free
on Gemini/Groq).

---

## Quick start (local)

```bash
pip install -r requirements.txt

# Preview today's edition without sending — writes the HTML so you can open it.
python -m vibecoding_news --dry-run --output output/edition.html
open output/edition.html        # or just inspect the file
```

`--dry-run` needs no API key (it falls back to extractive summaries and never
sends). Add a free `GEMINI_API_KEY` for real AI summaries (see below).

To actually send, configure a delivery provider (below) and drop `--dry-run`.
To force a send right now (with sample stories if none are live):

```bash
python -m vibecoding_news --test
```

---

## Configuration

All configuration is via environment variables — see
[`.env.example`](.env.example) for the full list. The important ones:

| Variable | Purpose | Default |
| --- | --- | --- |
| `GEMINI_API_KEY` | Google Gemini key (free) for summaries | _(falls back to extractive)_ |
| `GROQ_API_KEY` | Groq key (free) — alternative summarizer | — |
| `ANTHROPIC_API_KEY` | Claude key (paid) — alternative summarizer | — |
| `VIBE_PROVIDER` | Force `gemini` / `groq` / `anthropic` | _(auto-detected)_ |
| `NEWSLETTER_TO` | Recipient address | `nikodem.sarna@gmail.com` |
| `RESEND_API_KEY` | Use Resend for delivery | — |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` | Use SMTP for delivery | — |
| `NEWSLETTER_FROM` | From address | `Vibe Coding Daily <onboarding@resend.dev>` |
| `VIBE_MODEL` | Override model | _(provider default)_ |
| `VIBE_WINDOW_HOURS` | How far back "recent" reaches | `48` |
| `VIBE_MAX_ARTICLES` | Cap on stories per edition | `25` |

### Summaries: pick a provider (free options)

The provider is auto-detected from whichever key you set:

- **Google Gemini** (recommended, free): key at
  [aistudio.google.com/apikey](https://aistudio.google.com/apikey). Default
  model `gemini-2.0-flash`.
- **Groq** (free, fast): key at [console.groq.com/keys](https://console.groq.com/keys).
  Default model `llama-3.3-70b-versatile`.
- **Anthropic / Claude** (paid): set `ANTHROPIC_API_KEY` and
  `pip install anthropic`. Default model `claude-opus-4-8`.

Gemini and Groq run over plain HTTP — no extra Python dependency. With no key at
all, summaries fall back to each article's own feed description.

### Delivery: pick one provider

- **Resend** (simplest): create a key at [resend.com](https://resend.com) and set
  `RESEND_API_KEY`. Free tier sends from `onboarding@resend.dev` to any address.
- **SMTP** (e.g. Gmail): create an [App Password](https://support.google.com/accounts/answer/185833)
  and set `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USER=you@gmail.com`,
  `SMTP_PASSWORD=<app password>`. **All four are required** for SMTP.

If `RESEND_API_KEY` is set it is used; otherwise SMTP is used if `SMTP_HOST` is set.

---

## Deploy on GitHub Actions (daily, hands-off)

The workflow in [`.github/workflows/daily-newsletter.yml`](.github/workflows/daily-newsletter.yml)
runs every morning at **07:30 UTC** (editable cron) and can also be triggered
manually — with an optional **dry run** or **test email**.

1. Push this repo to GitHub.
2. In **Settings → Secrets and variables → Actions**, add the secrets you need:
   - a summarizer key — `GEMINI_API_KEY` (free) or `GROQ_API_KEY` (free) or `ANTHROPIC_API_KEY`
   - **either** `RESEND_API_KEY` **or** `SMTP_HOST` + `SMTP_PORT` + `SMTP_USER` + `SMTP_PASSWORD`
   - optionally `NEWSLETTER_TO`, `NEWSLETTER_FROM`
   - optionally, as **Variables**: `VIBE_PROVIDER`, `VIBE_MODEL`, `VIBE_WINDOW_HOURS`, `VIBE_MAX_ARTICLES`
3. Use **Run workflow** with **"Send a TEST email"** checked to verify delivery end to end.

The job runs the test suite before sending, and uploads the rendered edition as
an artifact every run for easy inspection.

---

## Adding or changing sources

Edit [`config/feeds.yaml`](config/feeds.yaml) — each entry is a `name` and an
RSS/Atom `url`. The Hacker News entries use [hnrss.org](https://hnrss.org)
search feeds, which are a reliable way to target the topic precisely. Feeds that
fail on a given day are logged and skipped.

To change what counts as a vibe-coding story, edit `VIBE_KEYWORDS` in
[`vibecoding_news/filter.py`](vibecoding_news/filter.py).

---

## Tests

```bash
python -m pytest -q
```

Covers the keyword/recency/dedup filtering, provider detection, and the
HTML/text rendering. No network or API key required.

---

## Project layout

```
vibecoding_news/
  config.py      env-driven settings
  sources.py     load feeds.yaml
  fetch.py       concurrent RSS fetch + normalize
  filter.py      vibe-coding keyword + recency filter + dedup
  summarize.py   LLM summaries — Gemini / Groq / Claude (+ extractive fallback)
  render.py      HTML + plain-text rendering
  mailer.py      Resend / SMTP delivery
  newsletter.py  pipeline orchestration
  __main__.py    CLI entry point
templates/       Jinja2 email templates
config/feeds.yaml
tests/
.github/workflows/daily-newsletter.yml
```
