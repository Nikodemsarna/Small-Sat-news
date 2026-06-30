"""Render the edition into HTML (Jinja2) and a plain-text alternative."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .fetch import Article
from .summarize import EditionSummary


@dataclass
class RenderedItem:
    title: str
    link: str
    source: str
    summary: str
    relevance: str
    published_label: str


@dataclass
class RenderedEdition:
    subject: str
    date_label: str
    intro: str
    top_picks: list[RenderedItem]
    more: list[RenderedItem]
    count: int
    html: str
    text: str


def _published_label(article: Article) -> str:
    if article.published is None:
        return ""
    return article.published.strftime("%b %d, %H:%M UTC")


def _to_items(
    articles: list[Article], summary: EditionSummary, indices: list[int]
) -> list[RenderedItem]:
    items: list[RenderedItem] = []
    for i in indices:
        art = articles[i]
        items.append(
            RenderedItem(
                title=art.title,
                link=art.link,
                source=art.source,
                summary=summary.summaries[i] if i < len(summary.summaries) else art.summary,
                relevance=summary.relevances[i] if i < len(summary.relevances) else "medium",
                published_label=_published_label(art),
            )
        )
    return items


def render_edition(
    articles: list[Article],
    summary: EditionSummary,
    template_dir: Path,
    now: datetime | None = None,
) -> RenderedEdition:
    now = now or datetime.now(timezone.utc)
    today: date = now.date()
    date_label = today.strftime("%A, %B %d, %Y")
    count = len(articles)
    subject = f"Small-Sat News — {today.isoformat()}: {count} " + (
        "story" if count == 1 else "stories"
    )

    top_indices = summary.top_pick_indices
    top_set = set(top_indices)
    more_indices = [i for i in range(count) if i not in top_set]

    top_picks = _to_items(articles, summary, top_indices)
    more = _to_items(articles, summary, more_indices)

    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("email.html.j2")
    html = template.render(
        date_label=date_label,
        intro=summary.intro,
        top_picks=top_picks,
        more=more,
        count=count,
    )
    text = _render_text(date_label, summary.intro, top_picks, more)

    return RenderedEdition(
        subject=subject,
        date_label=date_label,
        intro=summary.intro,
        top_picks=top_picks,
        more=more,
        count=count,
        html=html,
        text=text,
    )


def _render_text(
    date_label: str,
    intro: str,
    top_picks: list[RenderedItem],
    more: list[RenderedItem],
) -> str:
    lines = ["SMALL-SAT NEWS", date_label, "=" * 40, ""]
    if intro:
        lines += [intro, ""]

    def block(title: str, items: list[RenderedItem]) -> None:
        if not items:
            return
        lines.append(title)
        lines.append("-" * len(title))
        for it in items:
            meta = it.source + (f" · {it.published_label}" if it.published_label else "")
            lines.append(f"• {it.title}  [{meta}]")
            if it.summary:
                lines.append(f"  {it.summary}")
            lines.append(f"  {it.link}")
            lines.append("")

    block("TOP PICKS", top_picks)
    block("MORE HEADLINES", more)
    lines.append("—")
    lines.append("Small-Sat News · daily small-satellite digest")
    return "\n".join(lines)
