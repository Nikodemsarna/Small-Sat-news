"""End-to-end orchestration: fetch → filter → summarize → render → deliver."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import Settings
from .fetch import Article, fetch_all
from .filter import filter_articles
from .mailer import send_email
from .render import RenderedEdition, render_edition
from .sources import load_sources
from .summarize import summarize

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    article_count: int
    sent: bool
    skipped_reason: str | None
    edition: RenderedEdition | None


def _sample_articles(now: datetime) -> list[Article]:
    """Placeholder stories so a test edition always has content to send."""
    return [
        Article(
            title="Test edition — your Small-Sat News delivery is working",
            link="https://github.com/Nikodemsarna/Small-Sat-news",
            source="Small-Sat News (sample)",
            summary=(
                "This is a sample story. If you're reading it in your inbox, "
                "email delivery is configured correctly. Real editions replace "
                "this with live small-satellite news."
            ),
            published=now,
        ),
        Article(
            title="Sample: 6U cubesat demonstrates electric propulsion in orbit",
            link="https://github.com/Nikodemsarna/Small-Sat-news",
            source="Small-Sat News (sample)",
            summary=(
                "A second sample item so you can preview the layout, top-picks "
                "section, and formatting of a normal edition."
            ),
            published=now - timedelta(hours=3),
        ),
    ]


def build_edition(
    settings: Settings,
    now: datetime | None = None,
    sample_if_empty: bool = False,
) -> tuple[int, RenderedEdition | None]:
    """Run the pipeline up to (but not including) delivery.

    When ``sample_if_empty`` is True and no live stories are found, a couple of
    sample stories are used so a (test) edition can still be produced.
    """
    now = now or datetime.now(timezone.utc)
    sources = load_sources(settings.feeds_path)
    logger.info("Loaded %d source feeds.", len(sources))

    raw = fetch_all(sources)
    articles = filter_articles(
        raw,
        window_hours=settings.window_hours,
        max_articles=settings.max_articles,
        now=now,
    )
    if not articles:
        if not sample_if_empty:
            return 0, None
        logger.info("No live stories — using sample content for the test edition.")
        articles = _sample_articles(now)

    summary = summarize(articles, settings)
    edition = render_edition(articles, summary, settings.template_dir, now=now)
    return len(articles), edition


def run(
    settings: Settings,
    *,
    dry_run: bool = False,
    test_mode: bool = False,
    output_path: Path | None = None,
    now: datetime | None = None,
) -> RunResult:
    """Build and deliver today's edition.

    - ``dry_run``: render (and optionally write to ``output_path``) but do not send.
    - ``test_mode``: always send, even if there are no live stories (sample
      content is used as a fallback), and prefix the subject with ``[TEST]``.
    """
    count, edition = build_edition(settings, now=now, sample_if_empty=test_mode)

    if edition is None:
        logger.info("No small-satellite stories found — skipping delivery.")
        return RunResult(0, sent=False, skipped_reason="no_articles", edition=None)

    subject = f"[TEST] {edition.subject}" if test_mode else edition.subject

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(edition.html, encoding="utf-8")
        logger.info("Wrote rendered HTML to %s", output_path)

    if dry_run:
        logger.info("Dry run — not sending. Subject: %s", subject)
        return RunResult(count, sent=False, skipped_reason="dry_run", edition=edition)

    send_email(subject, edition.html, edition.text, settings)
    return RunResult(count, sent=True, skipped_reason=None, edition=edition)
