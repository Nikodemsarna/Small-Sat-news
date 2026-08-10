"""Filter aggregated articles down to recent vibe-coding stories."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from .fetch import Article

logger = logging.getLogger(__name__)

# Keywords that mark a story as "vibe coding" — AI-assisted software
# development: the practice, the assistants/agents, and the tools. Matched
# case-insensitively with word boundaries against the title + summary.
VIBE_KEYWORDS: tuple[str, ...] = (
    # The practice / concept
    "vibe coding",
    "vibe-coding",
    "vibecoding",
    "vibe coder",
    "vibe coders",
    "ai coding",
    "ai-assisted",
    "ai assisted",
    "ai pair programming",
    "pair programmer",
    "agentic coding",
    "autonomous coding",
    "coding agent",
    "coding agents",
    "coding assistant",
    "coding assistants",
    "code generation",
    "codegen",
    "software engineering agent",
    "swe agent",
    "swe-agent",
    "ai developer tools",
    "llm coding",
    "prompt engineering",
    # Assistants / agents / products
    "github copilot",
    "copilot",
    "cursor ai",
    "claude code",
    "codeium",
    "windsurf",
    "aider",
    "devin",
    "replit agent",
    "bolt.new",
    "v0.dev",
    "lovable",
    "codewhisperer",
    "amazon q developer",
    "tabnine",
    "sourcegraph cody",
    "openai codex",
    "codex cli",
    "gemini code assist",
    "swe-bench",
)

_KEYWORD_RE = re.compile(
    r"(?<!\w)(?:%s)(?!\w)" % "|".join(re.escape(k) for k in VIBE_KEYWORDS),
    re.IGNORECASE,
)


def matches_topic(article: Article) -> bool:
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
        if not matches_topic(article):
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
        "Filtered %d vibe-coding stories from %d entries (window=%dh)",
        len(kept),
        len(articles),
        window_hours,
    )
    return kept[:max_articles]
