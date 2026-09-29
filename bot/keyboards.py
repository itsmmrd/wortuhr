from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.constants import (
    LANGUAGES,
    LEVELS,
    PAGE_SIZE,
    TIMEZONES,
    TOPICS,
    TRANSLATION_LANGUAGES,
)
from bot.db import Item, Plan
from bot.i18n import language_label, t, topic_label, translation_label
from bot.schedule_logic import effective_schedule, short_when


def _grid(buttons: list[InlineKeyboardButton], per_row: int) -> list[list[InlineKeyboardButton]]:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for button in buttons:
        row.append(button)
        if len(row) == per_row:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


def with_nav(
    rows: list[list[InlineKeyboardButton]],
    *,
    back: str | None = None,
    lang: str = "en",
) -> InlineKeyboardMarkup:
    if back:
        rows.append([InlineKeyboardButton(t(lang, "back"), callback_data=back)])
    rows.append([InlineKeyboardButton(t(lang, "cancel"), callback_data="home")])
    return InlineKeyboardMarkup(rows)


def ui_language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("English", callback_data="ui:en"),
                InlineKeyboardButton("فارسی", callback_data="ui:fa"),
            ]
        ]
    )


def home(lang: str = "en") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(t(lang, "new_plan"), callback_data="pnew"),
                InlineKeyboardButton(t(lang, "my_plans"), callback_data="plans"),
            ],
            [
                InlineKeyboardButton(t(lang, "progress"), callback_data="prog"),
                InlineKeyboardButton(t(lang, "review"), callback_data="review"),
            ],
            [
                InlineKeyboardButton(t(lang, "settings"), callback_data="settings"),
                InlineKeyboardButton(t(lang, "help"), callback_data="help"),
            ],
        ]
    )


def languages(lang: str = "en") -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(f"{flag} {language_label(lang, name)}", callback_data=f"w:lang:{code}")
        for name, code, flag in LANGUAGES
    ]
    buttons.append(InlineKeyboardButton(t(lang, "other_language"), callback_data="w:lang:custom"))
    return with_nav(_grid(buttons, 2), lang=lang)


def levels(lang: str = "en") -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(level, callback_data=f"w:level:{level}") for level in LEVELS]
    return with_nav(_grid(buttons, 3), back="w:back", lang=lang)


def content_types(lang: str = "en") -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(t(lang, "words"), callback_data="w:type:word"),
            InlineKeyboardButton(t(lang, "idioms"), callback_data="w:type:idiom"),
        ]
    ]
    return with_nav(rows, back="w:back", lang=lang)


def topics(lang: str = "en") -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(topic_label(lang, name), callback_data=f"w:topic:{code}") for name, code in TOPICS
    ]
    buttons.append(InlineKeyboardButton(t(lang, "other_topic"), callback_data="w:topic:custom"))
    return with_nav(_grid(buttons, 2), back="w:back", lang=lang)


def days_keyboard(selected: list[int], lang: str = "en") -> InlineKeyboardMarkup:
    chosen = set(selected)
    buttons = [
        InlineKeyboardButton(
            ("✓ " if index in chosen else "") + t(lang, f"wday.{index}"),
            callback_data=f"w:day:{index}",
        )
        for index in range(7)
    ]
    per_row = 2 if lang == "fa" else 4
    rows = _grid(buttons, per_row)
    rows.append(
        [
            InlineKeyboardButton(t(lang, "every_day"), callback_data="w:day:all"),
            InlineKeyboardButton(t(lang, "weekdays"), callback_data="w:day:week"),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(t(lang, "weekend_days"), callback_data="w:day:end"),
            InlineKeyboardButton(t(lang, "done"), callback_data="w:day:done"),
        ]
    )
    return with_nav(rows, back="w:back", lang=lang)


def times_per_day(lang: str = "en") -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(str(count), callback_data=f"w:count:{count}") for count in (1, 2, 3)]
    return with_nav([buttons], back="w:back", lang=lang)


def slot_choice(lang: str = "en") -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(t(lang, "set_time"), callback_data="w:slot:exact")],
        [InlineKeyboardButton(t(lang, "pick_random"), callback_data="w:slot:random")],
    ]
    return with_nav(rows, back="w:back", lang=lang)


def text_step(lang: str = "en") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(t(lang, "back"), callback_data="w:back")],
            [InlineKeyboardButton(t(lang, "cancel"), callback_data="home")],
        ]
    )


def timezones(*, back: str = "home", lang: str = "en") -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(label, callback_data=f"tz:{zone}") for label, zone in TIMEZONES
    ]
    buttons.append(InlineKeyboardButton(t(lang, "other_timezone"), callback_data="tz:custom"))
    return InlineKeyboardMarkup(_grid(buttons, 2) + [[InlineKeyboardButton(t(lang, "back"), callback_data=back)]])


def translation_languages(*, back: str = "w:back", lang: str = "en") -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(translation_label(lang, name), callback_data=f"tr:{name}")
        for name in TRANSLATION_LANGUAGES
    ]
    buttons.append(InlineKeyboardButton(t(lang, "other_language"), callback_data="tr:custom"))
    return InlineKeyboardMarkup(_grid(buttons, 2) + [[InlineKeyboardButton(t(lang, "back"), callback_data=back)]])


def settings_menu(lang: str = "en") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(t(lang, "bot_language"), callback_data="set:ui")],
            [InlineKeyboardButton(t(lang, "timezone"), callback_data="set:tz")],
            [InlineKeyboardButton(t(lang, "translation_language"), callback_data="set:tr")],
            [InlineKeyboardButton(t(lang, "home"), callback_data="home")],
        ]
    )


def plan_button_label(plan: Plan, lang: str = "en") -> str:
    kind = t(lang, "words") if plan.content_type == "word" else t(lang, "idioms")
    language = language_label(lang, plan.language)
    when = short_when(effective_schedule(plan), lang)
    paused = t(lang, "paused_suffix") if not plan.active else ""
    return f"{language} {plan.level} {kind} · {when}{paused}"[:60]


def plans_menu(plans: list[Plan], lang: str = "en") -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(plan_button_label(plan, lang), callback_data=f"popen:{plan.id}")]
        for plan in plans[:20]
    ]
    rows.append([InlineKeyboardButton(t(lang, "new_plan"), callback_data="pnew")])
    rows.append([InlineKeyboardButton(t(lang, "home"), callback_data="home")])
    return InlineKeyboardMarkup(rows)


def plan_actions(plan: Plan, lang: str = "en") -> InlineKeyboardMarkup:
    pause_label = t(lang, "resume") if not plan.active else t(lang, "pause")
    pause_data = f"presume:{plan.id}" if not plan.active else f"ppause:{plan.id}"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(t(lang, "send_one"), callback_data=f"pnow:{plan.id}")],
            [
                InlineKeyboardButton(t(lang, "edit_level"), callback_data=f"pedit:level:{plan.id}"),
                InlineKeyboardButton(t(lang, "edit_topic"), callback_data=f"pedit:topic:{plan.id}"),
            ],
            [InlineKeyboardButton(t(lang, "edit_schedule"), callback_data=f"pedit:sched:{plan.id}")],
            [InlineKeyboardButton(pause_label, callback_data=pause_data)],
            [InlineKeyboardButton(t(lang, "delete"), callback_data=f"pdel:{plan.id}")],
            [InlineKeyboardButton(t(lang, "my_plans"), callback_data="plans")],
        ]
    )


def confirm_delete(plan_id: int, lang: str = "en") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(t(lang, "delete_plan"), callback_data=f"pdelok:{plan_id}")],
            [InlineKeyboardButton(t(lang, "keep_it"), callback_data=f"popen:{plan_id}")],
        ]
    )


def lesson(item_id: int, status: str = "new", lang: str = "en") -> InlineKeyboardMarkup:
    if status == "learned":
        learned, repeat = t(lang, "learned_check"), t(lang, "repeat_again")
    elif status == "repeat":
        learned, repeat = t(lang, "i_learned"), t(lang, "repeat_check")
    else:
        learned, repeat = t(lang, "i_learned"), t(lang, "repeat_again")
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(learned, callback_data=f"learn:{item_id}"),
                InlineKeyboardButton(repeat, callback_data=f"repeat:{item_id}"),
            ]
        ]
    )


def progress_menu(lang: str = "en") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(t(lang, "learned_words"), callback_data="list:words:0")],
            [InlineKeyboardButton(t(lang, "learned_idioms"), callback_data="list:idioms:0")],
            [InlineKeyboardButton(t(lang, "needs_repeat"), callback_data="list:repeat:0")],
            [InlineKeyboardButton(t(lang, "summary"), callback_data="sum")],
            [InlineKeyboardButton(t(lang, "home"), callback_data="home")],
        ]
    )


def item_label(item: Item) -> str:
    label = f"{item.term} — {item.translation}"
    return label[:60]


def item_list(items: list[Item], kind: str, page: int, total: int, lang: str = "en") -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(item_label(item), callback_data=f"item:{item.id}")]
        for item in items
    ]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(t(lang, "previous"), callback_data=f"list:{kind}:{page - 1}"))
    if (page + 1) * PAGE_SIZE < total:
        nav.append(InlineKeyboardButton(t(lang, "next"), callback_data=f"list:{kind}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(t(lang, "progress"), callback_data="prog")])
    return InlineKeyboardMarkup(rows)
