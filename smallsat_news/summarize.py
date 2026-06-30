"""Summarize filtered articles with the Claude API.

One batched call per edition produces an editorial intro, a concise per-article
summary, a relevance rating, and a "top picks" selection. Falls back to the
article's own feed description if no API key is configured.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from .config import Settings
from .fetch import Article

logger = logging.getLogger(__name__)

# Structured-output schema. Keep to basic JSON-Schema types (no min/max length,
# etc.) per the Claude structured-outputs constraints.
_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "intro": {"type": "string"},
        "articles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "summary": {"type": "string"},
                    "relevance": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                },
                "required": ["index", "summary", "relevance"],
                "additionalProperties": False,
            },
        },
        "top_picks": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["intro", "articles", "top_picks"],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = (
    "You are the editor of a focused daily newsletter on SMALL-SATELLITE "
    "development — cubesats, nanosats, microsats, smallsat constellations, "
    "rideshare launches, and the companies and agencies building them. "
    "You write for an informed space-industry audience: concise, factual, no "
    "hype, no marketing language. Summaries must be grounded only in the "
    "provided title and description — never invent specifics, numbers, or "
    "outcomes that are not present in the source text."
)

_MAX_TOKENS = 8000


@dataclass
class EditionSummary:
    intro: str
    # Per-article fields, aligned to the input article order.
    summaries: list[str]
    relevances: list[str]
    top_pick_indices: list[int]


def _build_user_prompt(articles: list[Article]) -> str:
    lines = [
        "Here are today's small-satellite news items. For EACH item, write a "
        "1–2 sentence plain-English summary and rate its relevance to "
        "small-satellite development (high/medium/low).",
        "",
        "Also write a 2–3 sentence editorial intro summarizing the day's "
        "small-satellite developments, and select the indices of up to 5 "
        "'top picks' (most significant stories), most important first.",
        "",
        "Return one entry per item using its given index.",
        "",
    ]
    for i, art in enumerate(articles):
        desc = art.summary or "(no description provided)"
        lines.append(f"[{i}] Source: {art.source}")
        lines.append(f"    Title: {art.title}")
        lines.append(f"    Description: {desc}")
        lines.append("")
    return "\n".join(lines)


def _fallback_summary(articles: list[Article]) -> EditionSummary:
    """Extractive fallback when no Claude API key is available."""
    summaries = [
        (a.summary[:300] + "…") if len(a.summary) > 300 else (a.summary or a.title)
        for a in articles
    ]
    intro = (
        f"{len(articles)} small-satellite "
        f"{'story' if len(articles) == 1 else 'stories'} from across the "
        "space-sector press today."
    )
    return EditionSummary(
        intro=intro,
        summaries=summaries,
        relevances=["medium"] * len(articles),
        top_pick_indices=list(range(min(5, len(articles)))),
    )


def summarize(articles: list[Article], settings: Settings) -> EditionSummary:
    """Produce an EditionSummary, using Claude when configured."""
    if not articles:
        return EditionSummary(intro="", summaries=[], relevances=[], top_pick_indices=[])

    if not settings.has_summarizer:
        logger.warning("ANTHROPIC_API_KEY not set — using extractive fallback summaries.")
        return _fallback_summary(articles)

    try:
        return _summarize_with_claude(articles, settings)
    except Exception as exc:  # never let summarization failure kill the newsletter
        logger.error("Claude summarization failed (%s) — falling back.", exc)
        return _fallback_summary(articles)


def _summarize_with_claude(articles: list[Article], settings: Settings) -> EditionSummary:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.model,
        max_tokens=_MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        output_config={
            "format": {"type": "json_schema", "schema": _OUTPUT_SCHEMA},
            "effort": settings.effort,
        },
        messages=[{"role": "user", "content": _build_user_prompt(articles)}],
    )

    text = next((b.text for b in response.content if b.type == "text"), "")
    data = json.loads(text)

    n = len(articles)
    summaries = [a.summary or a.title for a in articles]
    relevances = ["medium"] * n
    for item in data.get("articles", []):
        idx = item.get("index")
        if isinstance(idx, int) and 0 <= idx < n:
            summaries[idx] = item.get("summary") or summaries[idx]
            rel = item.get("relevance")
            if rel in {"high", "medium", "low"}:
                relevances[idx] = rel

    top = [i for i in data.get("top_picks", []) if isinstance(i, int) and 0 <= i < n]
    # De-duplicate while preserving order.
    seen: set[int] = set()
    top_picks = [i for i in top if not (i in seen or seen.add(i))][:5]

    logger.info("Summarized %d articles with %s.", n, settings.model)
    return EditionSummary(
        intro=data.get("intro", "").strip(),
        summaries=summaries,
        relevances=relevances,
        top_pick_indices=top_picks,
    )
