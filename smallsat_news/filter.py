"""Filter aggregated articles down to recent small-satellite stories."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from .fetch import Article

logger = logging.getLogger(__name__)

# Keywords that mark a story as small-satellite related. Matched case-insensitively
# with word boundaries against the title + summary. Keep this list focused on
# small-satellite development to honor the "small satellites only" scope.
SMALLSAT_KEYWORDS: tuple[str, ...] = (
    "small satellite",
    "small satellites",
    "small-satellite",
    "small-satellites",
    "small sat",
    "small sats",
    "small-sat",
    "small-sats",
    "smallsat",
    "smallsats",
    "cubesat",
    "cubesats",
    "nanosat",
    "nanosats",
    "nanosatellite",
    "nanosatellites",
    "microsat",
    "microsats",
    "microsatellite",
    "microsatellites",
    "picosat",
    "picosatellite",
    "femtosat",
    "smallsat launch",
    "rideshare",
    "cubesat constellation",
)

# Phrases such as "3U cubesat" / "6U" form factors — handled by the cubesat
# keyword already, so no special-casing needed here.

_KEYWORD_RE = re.compile(
    r"(?<!\w)(?:%s)(?!\w)" % "|".join(re.escape(k) for k in SMALLSAT_KEYWORDS),
    re.IGNORECASE,
)


def matches_smallsat(article: Article) -> bool:
    haystack = f"{article.title}\n{article.summary}"
    return bool(_KEYWORD_RE.search(haystack))


def is_recent(article: Article, window: timedelta, now: datetime | None = None) -> bool:
    """Recent if published within the window. Undated entries are kept."""
    if article.published is None:
        return True
    now = now or datetime.now(timezone.utc)
    return article.published >= (now - window)


def filter_articles(
    articles: list[Article],
    window_hours: int,
    max_articles: int,
    now: datetime | None = None,
) -> list[Article]:
    """Apply recency + keyword filters, de-duplicate, sort, and cap the list."""
    now = now or datetime.now(timezone.utc)
    window = timedelta(hours=window_hours)

    seen: set[str] = set()
    kept: list[Article] = []
    for article in articles:
        if not matches_smallsat(article):
            continue
        if not is_recent(article, window, now=now):
            continue
        key = article.dedup_key
        if key in seen:
            continue
        seen.add(key)
        kept.append(article)

    # Newest first; undated entries sink to the bottom.
    kept.sort(
        key=lambda a: a.published or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    logger.info(
        "Filtered %d small-satellite stories from %d entries (window=%dh)",
        len(kept),
        len(articles),
        window_hours,
    )
    return kept[:max_articles]
