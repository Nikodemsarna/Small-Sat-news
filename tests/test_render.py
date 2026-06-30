from datetime import datetime, timezone

from smallsat_news.config import Settings
from smallsat_news.fetch import Article
from smallsat_news.render import render_edition
from smallsat_news.summarize import EditionSummary

NOW = datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)


def test_render_edition_smoke():
    articles = [
        Article(
            title="New cubesat constellation announced",
            link="https://example.com/1",
            source="SpaceNews",
            summary="A company unveiled a 12-satellite cubesat constellation.",
            published=NOW,
        ),
        Article(
            title="Nanosat propulsion milestone",
            link="https://example.com/2",
            source="Payload",
            summary="A startup demonstrated electric propulsion on a 6U nanosat.",
            published=NOW,
        ),
    ]
    summary = EditionSummary(
        intro="Two notable small-satellite developments today.",
        summaries=["Cubesat constellation unveiled.", "Nanosat propulsion demonstrated."],
        relevances=["high", "medium"],
        top_pick_indices=[0],
    )
    settings = Settings()
    edition = render_edition(articles, summary, settings.template_dir, now=NOW)

    assert edition.count == 2
    assert "2026-06-30" in edition.subject
    assert len(edition.top_picks) == 1
    assert len(edition.more) == 1
    # HTML contains the titles and links.
    assert "New cubesat constellation announced" in edition.html
    assert "https://example.com/2" in edition.html
    assert "Top Picks" in edition.html
    # Plain-text alternative is populated.
    assert "TOP PICKS" in edition.text
    assert "Nanosat propulsion milestone" in edition.text


def test_render_handles_no_top_picks():
    articles = [
        Article(
            title="Smallsat rideshare manifest grows",
            link="https://example.com/3",
            source="SatNews",
            summary="More payloads added to an upcoming smallsat rideshare.",
            published=NOW,
        )
    ]
    summary = EditionSummary(
        intro="",
        summaries=["Rideshare manifest expanded."],
        relevances=["medium"],
        top_pick_indices=[],
    )
    settings = Settings()
    edition = render_edition(articles, summary, settings.template_dir, now=NOW)
    assert edition.count == 1
    assert len(edition.top_picks) == 0
    assert len(edition.more) == 1
    assert "Smallsat rideshare manifest grows" in edition.html
