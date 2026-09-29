from __future__ import annotations

import html
import json
from datetime import date, datetime, timedelta

from bot.constants import flag_for
from bot.db import Item, Plan
from bot.i18n import language_label, localize, t, topic_label
from bot.schedule_logic import effective_schedule, schedule_phrase


def esc(value: object) -> str:
    return html.escape(str(value), quote=False)


def bar(current: int, total: int, width: int = 16) -> str:
    if total <= 0:
        return "░" * width
    current = max(0, min(current, total))
    filled = round(width * current / total)
    return "█" * filled + "░" * (width - filled)


_MONTHS_FA = [
    "ژانویه",
    "فوریه",
    "مارس",
    "آوریل",
    "مه",
    "ژوئن",
    "ژوئیه",
    "اوت",
    "سپتامبر",
    "اکتبر",
    "نوامبر",
    "دسامبر",
]


def activity_block(counts: dict[str, int], today: date, lang: str = "en") -> str:
    lines = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        amount = counts.get(day.isoformat(), 0)
        mark = "█" * min(amount, 8) if amount else "·"
        lines.append(localize(lang, f"{t(lang, f'wday.{day.weekday()}')} {mark} {amount}"))
    return "\n".join(lines)


def schedule_label(plan: Plan, lang: str = "en") -> str:
    return schedule_phrase(effective_schedule(plan), lang)


def _when_phrase(now: datetime, target: datetime, lang: str = "en") -> str:
    clock = f"{target:%H:%M}"
    if target.date() == now.date():
        return t(lang, "when_today", time=clock)
    if target.date() == now.date() + timedelta(days=1):
        return t(lang, "when_tomorrow", time=clock)
    if lang == "fa":
        return t(lang, "when_date", day=target.day, month=_MONTHS_FA[target.month - 1], time=clock)
    return target.strftime("%d %b at %H:%M")


def plan_html(plan: Plan, now: datetime, lang: str = "en") -> str:
    kind = t(lang, "words") if plan.content_type == "word" else t(lang, "idioms")
    flag = flag_for(plan.language)
    status = t(lang, "active") if plan.active else t(lang, "paused")
    schedule = effective_schedule(plan)
    lines = [
        f"{flag} <b>{esc(language_label(lang, plan.language))} {esc(kind)}</b>",
        t(lang, "level_mid", level=esc(plan.level), topic=esc(topic_label(lang, plan.topic))),
        esc(schedule_phrase(schedule, lang)),
    ]
    upcoming = []
    for slot in schedule.get("slots") or []:
        if slot.get("kind") == "random" and slot.get("next"):
            target = datetime.fromisoformat(slot["next"])
            if target.tzinfo is None:
                target = target.replace(tzinfo=now.tzinfo)
            upcoming.append(target)
    if upcoming:
        when = _when_phrase(now, min(upcoming), lang)
        lines.append(esc(t(lang, "next_random", when=when)))
    lines.append(f"{t(lang, 'status_label')}: {status}")
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
    lang: str = "en",
) -> str:
    flag = flag_for(language)
    kind = t(lang, "word_title") if content_type == "word" else t(lang, "idiom_title")
    lines = [
        f"{flag} <b>{esc(language_label(lang, language))}</b> · {esc(level)} · {esc(topic_label(lang, topic))}",
        f"<b>{kind}</b>",
        "",
        f"<b>{esc(term)}</b>",
        esc(translation),
    ]
    note = str(payload.get("note") or "").strip()
    if note:
        lines.append(f"<i>{esc(note)}</i>")
    if content_type == "word":
        lines.extend(["", f"<b>{t(lang, 'in_sentence')}</b>"])
        for index, sentence in enumerate(payload.get("sentences") or [], start=1):
            lines.append(f"{index}. {esc(sentence.get('text', ''))}")
            lines.append(f"    {esc(sentence.get('translation', ''))}")
    else:
        lines.extend(["", f"<b>{t(lang, 'where_use')}</b>"])
        for index, context in enumerate(payload.get("contexts") or [], start=1):
            lines.append(f"{index}. <i>{esc(context.get('situation', ''))}</i>")
            lines.append(f"    {esc(context.get('text', ''))}")
            lines.append(f"    {esc(context.get('translation', ''))}")
    if footer:
        lines.extend(["", esc(footer)])
    return "\n".join(lines)


def lesson_from_item(item: Item, footer: str | None = None, lang: str = "en") -> str:
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
        lang=lang,
    )


def progress_html(stats: dict[str, int], counts: dict[str, int], today: date, lang: str = "en") -> str:
    learned = stats["learned"]
    sent = stats["sent"]
    lines = [
        t(lang, "progress_title"),
        "",
        t(lang, "learned_line", n=learned),
        t(lang, "repeat_line", n=stats["repeat"]),
        t(lang, "sent_line", n=sent),
        "",
        t(lang, "words_bar", bar=bar(stats["words_learned"], stats["words_sent"]), learned=stats["words_learned"], sent=stats["words_sent"]),
        t(lang, "idioms_bar", bar=bar(stats["idioms_learned"], stats["idioms_sent"]), learned=stats["idioms_learned"], sent=stats["idioms_sent"]),
        "",
        t(lang, "last_7"),
        activity_block(counts, today, lang),
        "",
        t(lang, "overall", bar=bar(learned, sent), learned=learned, sent=sent),
    ]
    if sent == 0:
        lines.append("")
        lines.append(t(lang, "first_card"))
    return "\n".join(lines)


def help_html(lang: str = "en") -> str:
    return t(lang, "help_body")


def home_html(display_name: str, stats: dict[str, int], lang: str = "en") -> str:
    greeting = t(lang, "hello_name", name=esc(display_name)) if display_name else t(lang, "hello")
    return "\n".join(
        [
            "<b>Wortuhr</b>",
            greeting,
            "",
            t(lang, "home_body"),
            t(lang, "home_extra"),
            "",
            t(lang, "home_stats", learned=stats["learned"], repeat=stats["repeat"]),
        ]
    )
