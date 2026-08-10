from datetime import datetime, timedelta, timezone

from vibecoding_news.fetch import Article
from vibecoding_news.filter import (
    filter_articles,
    is_recent,
    matches_topic,
)

NOW = datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)


def make(title="", summary="", link="https://example.com/a", published=NOW, source="Src"):
    return Article(title=title, link=link, source=source, summary=summary, published=published)


def test_matches_keywords():
    assert matches_topic(make(title="A guide to vibe coding with agents"))
    assert matches_topic(make(title="GitHub Copilot ships new agent mode"))
    assert matches_topic(make(summary="They used Cursor AI to refactor the repo"))
    assert matches_topic(make(title="Claude Code lands autonomous PRs"))
    assert matches_topic(make(title="New AI coding assistant benchmarks on SWE-bench"))


def test_does_not_match_unrelated():
    assert not matches_topic(make(title="Fed raises interest rates"))
    assert not matches_topic(make(title="New smartphone camera review"))
    # Word boundaries: "code" alone must not trigger.
    assert not matches_topic(make(title="Building code inspections for a new office"))


def test_recency_window():
    window = timedelta(hours=48)
    assert is_recent(make(published=NOW - timedelta(hours=10)), window, now=NOW)
    assert not is_recent(make(published=NOW - timedelta(hours=60)), window, now=NOW)
    # Undated entries are kept.
    assert is_recent(make(published=None), window, now=NOW)


def test_filter_dedup_and_cap():
    articles = [
        make(title="Copilot update A", link="https://x.com/1"),
        make(title="Copilot update A dup", link="https://x.com/1"),  # same link → dropped
        make(title="Cursor AI raises round", link="https://x.com/2"),
        make(title="Irrelevant gadget news", link="https://x.com/3"),  # no keyword
        make(title="Old Aider release", link="https://x.com/4",
             published=NOW - timedelta(hours=72)),  # too old
    ]
    kept = filter_articles(articles, window_hours=48, max_articles=10, now=NOW)
    titles = [a.title for a in kept]
    assert "Copilot update A" in titles
    assert "Cursor AI raises round" in titles
    assert "Irrelevant gadget news" not in titles
    assert "Old Aider release" not in titles
    assert len(kept) == 2


def test_filter_sorts_newest_first():
    articles = [
        make(title="Older copilot news", link="https://x.com/1",
             published=NOW - timedelta(hours=20)),
        make(title="Newer copilot news", link="https://x.com/2",
             published=NOW - timedelta(hours=2)),
    ]
    kept = filter_articles(articles, window_hours=48, max_articles=10, now=NOW)
    assert kept[0].title == "Newer copilot news"


def test_max_articles_cap():
    articles = [
        make(title=f"Copilot item {i}", link=f"https://x.com/{i}",
             published=NOW - timedelta(minutes=i))
        for i in range(10)
    ]
    kept = filter_articles(articles, window_hours=48, max_articles=3, now=NOW)
    assert len(kept) == 3
