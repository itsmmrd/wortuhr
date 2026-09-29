from __future__ import annotations

import html
import json
from datetime import date, datetime, timedelta

from bot.constants import flag_for
from bot.db import Item, Plan
from bot.schedule_logic import effective_schedule, schedule_phrase


def esc(value: object) -> str:
    return html.escape(str(value), quote=False)


def bar(current: int, total: int, width: int = 16) -> str:
    if total <= 0:
        return "░" * width
    current = max(0, min(current, total))
    filled = round(width * current / total)
    return "█" * filled + "░" * (width - filled)


def activity_block(counts: dict[str, int], today: date) -> str:
    lines = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        amount = counts.get(day.isoformat(), 0)
        mark = "█" * min(amount, 8) if amount else "·"
        lines.append(f"{day.strftime('%a')} {mark} {amount}")
    return "\n".join(lines)


def schedule_label(plan: Plan) -> str:
    return schedule_phrase(effective_schedule(plan))


def _when_phrase(now: datetime, target: datetime) -> str:
    if target.date() == now.date():
        return f"today at {target:%H:%M}"
    if target.date() == now.date() + timedelta(days=1):
        return f"tomorrow at {target:%H:%M}"
    return target.strftime("%d %b at %H:%M")


def plan_html(plan: Plan, now: datetime) -> str:
    kind = "words" if plan.content_type == "word" else "idioms"
    flag = flag_for(plan.language)
    status = "active" if plan.active else "paused"
    schedule = effective_schedule(plan)
    lines = [
        f"{flag} <b>{esc(plan.language)} {esc(kind)}</b>",
        f"Level {esc(plan.level)} · {esc(plan.topic)}",
        esc(schedule_phrase(schedule)),
    ]
    upcoming = []
    for slot in schedule.get("slots") or []:
        if slot.get("kind") == "random" and slot.get("next"):
            target = datetime.fromisoformat(slot["next"])
            if target.tzinfo is None:
                target = target.replace(tzinfo=now.tzinfo)
            upcoming.append(target)
    if upcoming:
        lines.append(f"Next random send: {esc(_when_phrase(now, min(upcoming)))}")
    lines.append(f"Status: {status}")
    return "\n".join(lines)


def lesson_html(
    *,
    language: str,
    level: str,
    topic: str,
    content_type: str,
    term: str,
    translation: str,
    payload: dict,
    footer: str | None = None,
) -> str:
    flag = flag_for(language)
    kind = "Word" if content_type == "word" else "Idiom"
    lines = [
        f"{flag} <b>{esc(language)}</b> · {esc(level)} · {esc(topic)}",
        f"<b>{kind}</b>",
        "",
        f"<b>{esc(term)}</b>",
        esc(translation),
    ]
    note = str(payload.get("note") or "").strip()
    if note:
        lines.append(f"<i>{esc(note)}</i>")
    if content_type == "word":
        lines.extend(["", "<b>In a sentence</b>"])
        for index, sentence in enumerate(payload.get("sentences") or [], start=1):
            lines.append(f"{index}. {esc(sentence.get('text', ''))}")
            lines.append(f"    {esc(sentence.get('translation', ''))}")
    else:
        lines.extend(["", "<b>Where you can use it</b>"])
        for index, context in enumerate(payload.get("contexts") or [], start=1):
            lines.append(f"{index}. <i>{esc(context.get('situation', ''))}</i>")
            lines.append(f"    {esc(context.get('text', ''))}")
            lines.append(f"    {esc(context.get('translation', ''))}")
    if footer:
        lines.extend(["", esc(footer)])
    return "\n".join(lines)


def lesson_from_item(item: Item, footer: str | None = None) -> str:
    payload = json.loads(item.payload_json)
    return lesson_html(
        language=item.language,
        level=item.level,
        topic=item.topic,
        content_type=item.content_type,
        term=item.term,
        translation=item.translation,
        payload=payload,
        footer=footer,
    )


def progress_html(stats: dict[str, int], counts: dict[str, int], today: date) -> str:
    learned = stats["learned"]
    sent = stats["sent"]
    lines = [
        "<b>Progress</b>",
        "",
        f"Learned <b>{learned}</b>",
        f"To repeat <b>{stats['repeat']}</b>",
        f"Sent <b>{sent}</b>",
        "",
        f"Words {bar(stats['words_learned'], stats['words_sent'])} "
        f"{stats['words_learned']}/{stats['words_sent']}",
        f"Idioms {bar(stats['idioms_learned'], stats['idioms_sent'])} "
        f"{stats['idioms_learned']}/{stats['idioms_sent']}",
        "",
        "<b>Last 7 days</b>",
        activity_block(counts, today),
        "",
        f"Overall {bar(learned, sent)} {learned}/{sent}",
    ]
    if sent == 0:
        lines.append("")
        lines.append("Your first card will start the bars.")
    return "\n".join(lines)


def help_html() -> str:
    return "\n".join(
        [
            "<b>Wortuhr</b>",
            "",
            "A plan is a schedule. You can keep several at once.",
            "Each plan has a language, a level from A1 to C2, words or idioms, and a topic.",
            "A topic can be everyday life, a job, a technical field, or anything you type.",
            "",
            "<b>When cards arrive</b>",
            "Choose the days, how many times a day, then a clock time or a random time for each one.",
            "A word card has the word, its translation, and 3 short practical sentences.",
            "An idiom card has the idiom, its meaning, and 3 situations where you can use it.",
            "",
            "<b>After a card</b>",
            "Tap <b>I learned this</b> or <b>Repeat again</b>.",
            "Progress keeps the list, a bar, the last 7 days, and a short summary.",
            "",
            "<b>Commands</b>",
            "/new — create a plan",
            "/plans — edit, pause, or delete a plan",
            "/progress — bars, lists, and a summary",
            "/review — cards you marked to repeat",
            "/settings — timezone and translation language",
            "/cancel — leave the current step",
        ]
    )


def home_html(display_name: str, stats: dict[str, int]) -> str:
    greeting = f"Hello {esc(display_name)}." if display_name else "Hello."
    return "\n".join(
        [
            f"<b>Wortuhr</b>",
            greeting,
            "",
            "I send words or idioms on the clock you set, with practical examples and translations.",
            "You can run several plans: German A2 work words at 08:00, English idioms at a random afternoon time, and more.",
            "",
            f"Learned <b>{stats['learned']}</b> · to repeat <b>{stats['repeat']}</b>",
        ]
    )
