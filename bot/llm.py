from __future__ import annotations

import asyncio
import json
import logging
import re

from bot import config
from bot.constants import LEVEL_GUIDE
from bot.groq_http import GroqHTTPError, error_message, post_json

logger = logging.getLogger(__name__)


class LLMError(Exception):
    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


def load_json_object(text: str) -> dict:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end <= start:
            raise
        value = json.loads(raw[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def _clean_pair(entry: object, first: str, second: str) -> dict[str, str]:
    if not isinstance(entry, dict):
        raise ValueError("expected an object")
    left = str(entry.get(first, "")).strip()
    right = str(entry.get(second, "")).strip()
    if not left or not right:
        raise ValueError("missing text")
    return {first: left[:400], second: right[:400]}


def parse_card(content_type: str, raw: str) -> dict:
    data = load_json_object(raw)
    term = str(data.get("term", "")).strip()
    translation = str(data.get("translation", "")).strip()
    if not term or not translation:
        raise ValueError("missing term")
    note = str(data.get("note") or "").strip()[:240]
    if content_type == "word":
        sentences = data.get("sentences")
        if not isinstance(sentences, list) or len(sentences) < 3:
            raise ValueError("need 3 sentences")
        return {
            "term": term[:200],
            "translation": translation[:300],
            "note": note,
            "sentences": [_clean_pair(item, "text", "translation") for item in sentences[:3]],
        }
    contexts = data.get("contexts")
    if not isinstance(contexts, list) or len(contexts) < 3:
        raise ValueError("need 3 contexts")
    cleaned = []
    for item in contexts[:3]:
        if not isinstance(item, dict):
            raise ValueError("expected an object")
        situation = str(item.get("situation", "")).strip()
        text = str(item.get("text", "")).strip()
        translated = str(item.get("translation", "")).strip()
        if not situation or not text or not translated:
            raise ValueError("incomplete context")
        cleaned.append(
            {
                "situation": situation[:160],
                "text": text[:400],
                "translation": translated[:400],
            }
        )
    return {
        "term": term[:200],
        "translation": translation[:300],
        "note": note,
        "contexts": cleaned,
    }


def _duplicate(term: str, avoid: list[str]) -> bool:
    folded = term.casefold()
    return any(folded == item.casefold() for item in avoid)


def _prompt(
    *,
    content_type: str,
    language: str,
    level: str,
    topic: str,
    translation_language: str,
    avoid: list[str],
) -> str:
    avoid_text = " | ".join(avoid[:40]) if avoid else "(none)"
    guide = LEVEL_GUIDE.get(level, "natural language for this level")
    shared = f"""Target language: {language}
CEFR level: {level}
Level style: {guide}
Topic: {topic}
Translation language: {translation_language}
Do not use these terms: {avoid_text}

Stay inside the topic. If the topic is a job or a technical field, use language from that field.
Write the term in {language}. Write every translation in {translation_language}.
Keep examples practical and short. Reply with JSON only."""
    if content_type == "word":
        return shared + """

Create one vocabulary card. For languages that use articles, include the usual article with a noun.
Return JSON with exactly 3 sentences that use the term naturally:
{
  "term": "dictionary form in the target language",
  "translation": "short translation",
  "note": "optional one-line usage note, or an empty string",
  "sentences": [
    {"text": "practical sentence", "translation": "translation"},
    {"text": "practical sentence", "translation": "translation"},
    {"text": "practical sentence", "translation": "translation"}
  ]
}"""
    return shared + """

Create one real idiom or fixed expression, not a single ordinary word.
Return JSON with exactly 3 different real-life situations where a person would use it:
{
  "term": "the idiom in the target language",
  "translation": "what it means",
  "note": "literal meaning or a one-line note, or an empty string",
  "contexts": [
    {"situation": "where you would say this", "text": "example sentence", "translation": "translation"},
    {"situation": "a different place or moment", "text": "example sentence", "translation": "translation"},
    {"situation": "another different situation", "text": "example sentence", "translation": "translation"}
  ]
}"""


async def _chat(messages: list[dict[str, str]], *, json_mode: bool) -> str:
    body: dict = {
        "model": config.GROQ_MODEL,
        "temperature": 0.7,
        "max_tokens": 900,
        "messages": messages,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    try:
        status, text = await asyncio.to_thread(
            post_json,
            f"{config.GROQ_BASE_URL}/chat/completions",
            config.GROQ_API_KEY,
            body,
        )
    except GroqHTTPError as exc:
        raise LLMError(exc.message) from exc
    if status == 400 and json_mode:
        return await _chat(messages, json_mode=False)
    if status == 401:
        raise LLMError("Groq rejected the API key. Update it with sudo ./install.sh and restart the bot.")
    if status == 429:
        raise LLMError("Groq is rate-limiting requests. I will try again shortly.")
    if status >= 400:
        logger.warning("Groq error %s: %s", status, text[:500])
        if status == 403:
            raise LLMError(error_message(status, text))
        raise LLMError("Groq could not write this card. I will try again shortly.")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("Groq returned non-JSON: %s", text[:500])
        raise LLMError("Groq returned an unreadable card. I will try again shortly.") from exc
    try:
        return str(payload["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("Unexpected Groq payload: %s", str(payload)[:500])
        raise LLMError("Groq returned an unreadable card. I will try again shortly.") from exc


async def generate_card(
    *,
    content_type: str,
    language: str,
    level: str,
    topic: str,
    translation_language: str,
    avoid: list[str],
) -> dict:
    messages = [
        {
            "role": "system",
            "content": (
                "You write short language-learning cards. "
                "Reply with one JSON object and nothing else."
            ),
        },
        {
            "role": "user",
            "content": _prompt(
                content_type=content_type,
                language=language,
                level=level,
                topic=topic,
                translation_language=translation_language,
                avoid=avoid,
            ),
        },
    ]
    seen = list(avoid)
    last_error: Exception | None = None
    for _attempt in range(3):
        raw = await _chat(messages, json_mode=True)
        try:
            card = parse_card(content_type, raw)
        except (ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            logger.info("Could not parse Groq card: %s", exc)
            messages.append({"role": "assistant", "content": raw[:1500]})
            messages.append(
                {
                    "role": "user",
                    "content": "That was not valid for the schema. Reply again with JSON only.",
                }
            )
            continue
        if _duplicate(card["term"], seen):
            last_error = ValueError("duplicate term")
            seen.append(card["term"])
            messages.append({"role": "assistant", "content": raw[:1500]})
            messages.append(
                {
                    "role": "user",
                    "content": f"Choose a different term. Do not use: {card['term']}",
                }
            )
            continue
        return card
    logger.warning("Giving up on Groq card after retries: %s", last_error)
    raise LLMError("I could not prepare a fresh card just now. I will try again shortly.")


async def summarize_learned(items: list[dict], translation_language: str) -> str:
    lines = []
    for item in items[:30]:
        kind = "idiom" if item["content_type"] == "idiom" else "word"
        lines.append(
            f"- {item['term']} ({item['language']}, {kind}, {item['level']}): {item['translation']}"
        )
    messages = [
        {
            "role": "system",
            "content": "You help a language learner review. Be warm, concrete, and brief.",
        },
        {
            "role": "user",
            "content": (
                f"Write the recap in {translation_language}. "
                "Group words and idioms. Mention each item once, with its meaning. "
                "Stay under 180 words. Do not use markdown headings.\n\n"
                "Learned items:\n" + "\n".join(lines)
            ),
        },
    ]
    text = (await _chat(messages, json_mode=False)).strip()
    if not text:
        raise LLMError("I could not write a summary just now.")
    return text[:3500]
