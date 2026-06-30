"""End-to-end orchestration: fetch → filter → summarize → render → deliver."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import Settings
from .fetch import fetch_all
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


def build_edition(settings: Settings, now: datetime | None = None) -> tuple[int, RenderedEdition | None]:
    """Run the pipeline up to (but not including) delivery."""
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
        return 0, None

    summary = summarize(articles, settings)
    edition = render_edition(articles, summary, settings.template_dir, now=now)
    return len(articles), edition


def run(
    settings: Settings,
    *,
    dry_run: bool = False,
    output_path: Path | None = None,
    now: datetime | None = None,
) -> RunResult:
    """Build and deliver today's edition.

    When ``dry_run`` is True, the edition is rendered and (optionally) written
    to ``output_path`` but not emailed.
    """
    count, edition = build_edition(settings, now=now)

    if edition is None:
        if settings.skip_if_empty:
            logger.info("No small-satellite stories found — skipping delivery.")
            return RunResult(0, sent=False, skipped_reason="no_articles", edition=None)
        # Fall through with an empty edition is not meaningful; treat as skip.
        return RunResult(0, sent=False, skipped_reason="no_articles", edition=None)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(edition.html, encoding="utf-8")
        logger.info("Wrote rendered HTML to %s", output_path)

    if dry_run:
        logger.info("Dry run — not sending. Subject: %s", edition.subject)
        return RunResult(count, sent=False, skipped_reason="dry_run", edition=edition)

    send_email(edition.subject, edition.html, edition.text, settings)
    return RunResult(count, sent=True, skipped_reason=None, edition=edition)
