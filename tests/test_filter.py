from datetime import datetime, timedelta, timezone

from smallsat_news.fetch import Article
from smallsat_news.filter import (
    filter_articles,
    is_recent,
    matches_smallsat,
)

NOW = datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)


def make(title="", summary="", link="https://example.com/a", published=NOW, source="Src"):
    return Article(title=title, link=link, source=source, summary=summary, published=published)


def test_matches_keywords():
    assert matches_smallsat(make(title="New cubesat constellation launches"))
    assert matches_smallsat(make(title="A small satellite milestone"))
    assert matches_smallsat(make(summary="The nanosatellite reached orbit"))
    assert matches_smallsat(make(title="SmallSats are booming"))


def test_does_not_match_unrelated():
    assert not matches_smallsat(make(title="Crewed Mars mission update"))
    assert not matches_smallsat(make(title="Geostationary broadcast satellite contract"))
    # Word boundaries: "satellite" alone must not trigger.
    assert not matches_smallsat(make(title="Large satellite reaches orbit"))


def test_recency_window():
    window = timedelta(hours=30)
    assert is_recent(make(published=NOW - timedelta(hours=10)), window, now=NOW)
    assert not is_recent(make(published=NOW - timedelta(hours=40)), window, now=NOW)
    # Undated entries are kept.
    assert is_recent(make(published=None), window, now=NOW)


def test_filter_dedup_and_cap():
    articles = [
        make(title="Cubesat A", link="https://x.com/1"),
        make(title="Cubesat A dup", link="https://x.com/1"),  # same link → dropped
        make(title="Nanosat B", link="https://x.com/2"),
        make(title="Irrelevant rocket", link="https://x.com/3"),  # no keyword
        make(title="Microsat C old", link="https://x.com/4",
             published=NOW - timedelta(hours=72)),  # too old
    ]
    kept = filter_articles(articles, window_hours=30, max_articles=10, now=NOW)
    titles = [a.title for a in kept]
    assert "Cubesat A" in titles
    assert "Nanosat B" in titles
    assert "Irrelevant rocket" not in titles
    assert "Microsat C old" not in titles
    assert len(kept) == 2


def test_filter_sorts_newest_first():
    articles = [
        make(title="Older cubesat", link="https://x.com/1",
             published=NOW - timedelta(hours=20)),
        make(title="Newer cubesat", link="https://x.com/2",
             published=NOW - timedelta(hours=2)),
    ]
    kept = filter_articles(articles, window_hours=30, max_articles=10, now=NOW)
    assert kept[0].title == "Newer cubesat"


def test_max_articles_cap():
    articles = [
        make(title=f"Cubesat {i}", link=f"https://x.com/{i}",
             published=NOW - timedelta(minutes=i))
        for i in range(10)
    ]
    kept = filter_articles(articles, window_hours=30, max_articles=3, now=NOW)
    assert len(kept) == 3
