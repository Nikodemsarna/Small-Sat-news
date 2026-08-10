from datetime import datetime, timezone

from vibecoding_news.config import Settings
from vibecoding_news.fetch import Article
from vibecoding_news.render import render_edition
from vibecoding_news.summarize import EditionSummary

NOW = datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)


def test_render_edition_smoke():
    articles = [
        Article(
            title="Cursor ships agent mode for autonomous edits",
            link="https://example.com/1",
            source="Hacker News",
            summary="The AI editor added a mode that plans and applies multi-file changes.",
            published=NOW,
        ),
        Article(
            title="Aider adds repo-map improvements",
            link="https://example.com/2",
            source="Simon Willison",
            summary="The open-source AI pair programmer improved how it maps large repos.",
            published=NOW,
        ),
    ]
    summary = EditionSummary(
        intro="Two notable vibe-coding developments today.",
        summaries=["Cursor added an autonomous agent mode.", "Aider improved repo mapping."],
        relevances=["high", "medium"],
        top_pick_indices=[0],
    )
    settings = Settings()
    edition = render_edition(articles, summary, settings.template_dir, now=NOW)

    assert edition.count == 2
    assert "2026-06-30" in edition.subject
    assert "Vibe Coding Daily" in edition.subject
    assert len(edition.top_picks) == 1
    assert len(edition.more) == 1
    # HTML contains the titles and links.
    assert "Cursor ships agent mode for autonomous edits" in edition.html
    assert "https://example.com/2" in edition.html
    assert "Top Picks" in edition.html
    # Plain-text alternative is populated.
    assert "TOP PICKS" in edition.text
    assert "Aider adds repo-map improvements" in edition.text


def test_render_handles_no_top_picks():
    articles = [
        Article(
            title="GitHub Copilot usage grows among enterprises",
            link="https://example.com/3",
            source="The Verge",
            summary="Adoption of the AI coding assistant expanded across large teams.",
            published=NOW,
        )
    ]
    summary = EditionSummary(
        intro="",
        summaries=["Copilot enterprise adoption grew."],
        relevances=["medium"],
        top_pick_indices=[],
    )
    settings = Settings()
    edition = render_edition(articles, summary, settings.template_dir, now=NOW)
    assert edition.count == 1
    assert len(edition.top_picks) == 0
    assert len(edition.more) == 1
    assert "GitHub Copilot usage grows among enterprises" in edition.html
