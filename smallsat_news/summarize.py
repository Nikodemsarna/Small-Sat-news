"""Summarize filtered articles with a pluggable LLM provider.

Supported providers (auto-detected from whichever API key is set, or forced
via ``SMALLSAT_PROVIDER``):

  * ``gemini``    — Google Gemini (free tier via Google AI Studio)   [default]
  * ``groq``      — Groq (free tier, Llama models)
  * ``anthropic`` — Claude API (requires ``pip install anthropic``)

Each provider returns the same JSON shape: an editorial intro, a concise
per-article summary + relevance rating, and a "top picks" selection. If no key
is configured, it falls back to the article's own feed description.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

import requests

from .config import Settings
from .fetch import Article

logger = logging.getLogger(__name__)

_TIMEOUT = 90
_MAX_TOKENS = 8000

_SYSTEM_PROMPT = (
    "You are the editor of a focused daily newsletter on SMALL-SATELLITE "
    "development — cubesats, nanosats, microsats, smallsat constellations, "
    "rideshare launches, and the companies and agencies building them. "
    "You write for an informed space-industry audience: concise, factual, no "
    "hype, no marketing language. Summaries must be grounded only in the "
    "provided title and description — never invent specifics, numbers, or "
    "outcomes that are not present in the source text."
)

_JSON_SHAPE = (
    "Respond with ONE JSON object, no markdown, of exactly this shape:\n"
    "{\n"
    '  "intro": "2-3 sentence overview of the day\'s small-satellite news",\n'
    '  "articles": [{"index": <int>, "summary": "1-2 sentences", '
    '"relevance": "high|medium|low"}],\n'
    '  "top_picks": [<up to 5 article indices, most important first>]\n'
    "}\n"
    "Include exactly one articles entry per item, using its given index."
)

# JSON schema reused by providers that support structured output (Anthropic).
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
                    "relevance": {"type": "string", "enum": ["high", "medium", "low"]},
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


@dataclass
class EditionSummary:
    intro: str
    summaries: list[str]  # aligned to input article order
    relevances: list[str]
    top_pick_indices: list[int]


def _build_user_prompt(articles: list[Article]) -> str:
    lines = [
        "Here are today's small-satellite news items. For EACH item, write a "
        "1-2 sentence plain-English summary and rate its relevance to "
        "small-satellite development.",
        "",
        _JSON_SHAPE,
        "",
        "ITEMS:",
        "",
    ]
    for i, art in enumerate(articles):
        desc = art.summary or "(no description provided)"
        lines.append(f"[{i}] Source: {art.source}")
        lines.append(f"    Title: {art.title}")
        lines.append(f"    Description: {desc}")
        lines.append("")
    return "\n".join(lines)


def _extract_json(text: str) -> dict:
    """Parse a JSON object from model output, tolerating code fences/prose."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _payload_to_summary(data: dict, articles: list[Article]) -> EditionSummary:
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
    seen: set[int] = set()
    top_picks = [i for i in top if not (i in seen or seen.add(i))][:5]

    return EditionSummary(
        intro=(data.get("intro") or "").strip(),
        summaries=summaries,
        relevances=relevances,
        top_pick_indices=top_picks,
    )


def _fallback_summary(articles: list[Article]) -> EditionSummary:
    """Extractive fallback when no LLM provider is available."""
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
    """Produce an EditionSummary using the configured provider."""
    if not articles:
        return EditionSummary(intro="", summaries=[], relevances=[], top_pick_indices=[])

    if not settings.has_summarizer:
        logger.warning(
            "No summarization API key set — using extractive fallback summaries."
        )
        return _fallback_summary(articles)

    prompt = _build_user_prompt(articles)
    try:
        if settings.provider == "gemini":
            data = _call_gemini(prompt, settings)
        elif settings.provider == "groq":
            data = _call_groq(prompt, settings)
        elif settings.provider == "anthropic":
            data = _call_anthropic(prompt, settings)
        else:  # pragma: no cover - guarded by has_summarizer
            return _fallback_summary(articles)
    except Exception as exc:
        logger.error(
            "Summarization via %s failed (%s) — falling back.", settings.provider, exc
        )
        return _fallback_summary(articles)

    logger.info(
        "Summarized %d articles with %s (%s).",
        len(articles),
        settings.provider,
        settings.resolved_model,
    )
    return _payload_to_summary(data, articles)


# --- Providers --------------------------------------------------------------


def _call_gemini(prompt: str, settings: Settings) -> dict:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.resolved_model}:generateContent"
    )
    body = {
        "system_instruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.3,
            "maxOutputTokens": _MAX_TOKENS,
        },
    }
    resp = requests.post(
        url,
        params={"key": settings.gemini_api_key},
        json=body,
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return _extract_json(text)


def _call_groq(prompt: str, settings: Settings) -> dict:
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.groq_api_key}"},
        json={
            "model": settings.resolved_model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
            "max_tokens": _MAX_TOKENS,
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"]
    return _extract_json(text)


def _call_anthropic(prompt: str, settings: Settings) -> dict:
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "The 'anthropic' package is required for the Anthropic provider "
            "(pip install anthropic)."
        ) from exc

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.resolved_model,
        max_tokens=_MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        output_config={
            "format": {"type": "json_schema", "schema": _OUTPUT_SCHEMA},
            "effort": settings.effort,
        },
        messages=[{"role": "user", "content": prompt}],
    )
    text = next((b.text for b in response.content if b.type == "text"), "")
    return _extract_json(text)
