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
from bot.schedule_logic import DAY_LABELS, effective_schedule, short_when


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


def with_nav(rows: list[list[InlineKeyboardButton]], *, back: str | None = None) -> InlineKeyboardMarkup:
    if back:
        rows.append([InlineKeyboardButton("Back", callback_data=back)])
    rows.append([InlineKeyboardButton("Cancel", callback_data="home")])
    return InlineKeyboardMarkup(rows)


def home() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("New plan", callback_data="pnew"),
                InlineKeyboardButton("My plans", callback_data="plans"),
            ],
            [
                InlineKeyboardButton("Progress", callback_data="prog"),
                InlineKeyboardButton("Review", callback_data="review"),
            ],
            [
                InlineKeyboardButton("Settings", callback_data="settings"),
                InlineKeyboardButton("Help", callback_data="help"),
            ],
        ]
    )


def languages() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(f"{flag} {name}", callback_data=f"w:lang:{code}")
        for name, code, flag in LANGUAGES
    ]
    buttons.append(InlineKeyboardButton("Other language", callback_data="w:lang:custom"))
    return with_nav(_grid(buttons, 2))


def levels() -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(level, callback_data=f"w:level:{level}") for level in LEVELS]
    return with_nav(_grid(buttons, 3), back="w:back")


def content_types() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("Words", callback_data="w:type:word"),
            InlineKeyboardButton("Idioms", callback_data="w:type:idiom"),
        ]
    ]
    return with_nav(rows, back="w:back")


def topics() -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(name, callback_data=f"w:topic:{code}") for name, code in TOPICS]
    buttons.append(InlineKeyboardButton("Other topic", callback_data="w:topic:custom"))
    return with_nav(_grid(buttons, 2), back="w:back")


def days_keyboard(selected: list[int]) -> InlineKeyboardMarkup:
    chosen = set(selected)
    buttons = [
        InlineKeyboardButton(("✓ " if index in chosen else "") + DAY_LABELS[index], callback_data=f"w:day:{index}")
        for index in range(7)
    ]
    rows = _grid(buttons, 4)
    rows.append(
        [
            InlineKeyboardButton("Every day", callback_data="w:day:all"),
            InlineKeyboardButton("Weekdays", callback_data="w:day:week"),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton("Weekend", callback_data="w:day:end"),
            InlineKeyboardButton("Done", callback_data="w:day:done"),
        ]
    )
    return with_nav(rows, back="w:back")


def times_per_day() -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(str(count), callback_data=f"w:count:{count}") for count in (1, 2, 3)]
    return with_nav([buttons], back="w:back")


def slot_choice() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("Set a time", callback_data="w:slot:exact")],
        [InlineKeyboardButton("Pick a random time", callback_data="w:slot:random")],
    ]
    return with_nav(rows, back="w:back")


def text_step() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Back", callback_data="w:back")],
            [InlineKeyboardButton("Cancel", callback_data="home")],
        ]
    )


def timezones(*, back: str = "home") -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(label, callback_data=f"tz:{zone}") for label, zone in TIMEZONES
    ]
    buttons.append(InlineKeyboardButton("Other timezone", callback_data="tz:custom"))
    return InlineKeyboardMarkup(_grid(buttons, 2) + [[InlineKeyboardButton("Back", callback_data=back)]])


def translation_languages(*, back: str = "w:back") -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(name, callback_data=f"tr:{name}") for name in TRANSLATION_LANGUAGES
    ]
    buttons.append(InlineKeyboardButton("Other language", callback_data="tr:custom"))
    return InlineKeyboardMarkup(_grid(buttons, 2) + [[InlineKeyboardButton("Back", callback_data=back)]])


def settings_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Timezone", callback_data="set:tz")],
            [InlineKeyboardButton("Translation language", callback_data="set:tr")],
            [InlineKeyboardButton("Home", callback_data="home")],
        ]
    )


def plan_button_label(plan: Plan) -> str:
    kind = "words" if plan.content_type == "word" else "idioms"
    when = short_when(effective_schedule(plan))
    paused = " · paused" if not plan.active else ""
    return f"{plan.language} {plan.level} {kind} · {when}{paused}"[:60]


def plans_menu(plans: list[Plan]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(plan_button_label(plan), callback_data=f"popen:{plan.id}")]
        for plan in plans[:20]
    ]
    rows.append([InlineKeyboardButton("New plan", callback_data="pnew")])
    rows.append([InlineKeyboardButton("Home", callback_data="home")])
    return InlineKeyboardMarkup(rows)


def plan_actions(plan: Plan) -> InlineKeyboardMarkup:
    pause_label = "Resume" if not plan.active else "Pause"
    pause_data = f"presume:{plan.id}" if not plan.active else f"ppause:{plan.id}"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Send one now", callback_data=f"pnow:{plan.id}")],
            [
                InlineKeyboardButton("Edit level", callback_data=f"pedit:level:{plan.id}"),
                InlineKeyboardButton("Edit topic", callback_data=f"pedit:topic:{plan.id}"),
            ],
            [InlineKeyboardButton("Edit schedule", callback_data=f"pedit:sched:{plan.id}")],
            [InlineKeyboardButton(pause_label, callback_data=pause_data)],
            [InlineKeyboardButton("Delete", callback_data=f"pdel:{plan.id}")],
            [InlineKeyboardButton("My plans", callback_data="plans")],
        ]
    )


def confirm_delete(plan_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Delete plan", callback_data=f"pdelok:{plan_id}")],
            [InlineKeyboardButton("Keep it", callback_data=f"popen:{plan_id}")],
        ]
    )


def lesson(item_id: int, status: str = "new") -> InlineKeyboardMarkup:
    if status == "learned":
        learned, repeat = "Learned ✓", "Repeat again"
    elif status == "repeat":
        learned, repeat = "I learned this", "Repeat ✓"
    else:
        learned, repeat = "I learned this", "Repeat again"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(learned, callback_data=f"learn:{item_id}"),
                InlineKeyboardButton(repeat, callback_data=f"repeat:{item_id}"),
            ]
        ]
    )


def progress_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Learned words", callback_data="list:words:0")],
            [InlineKeyboardButton("Learned idioms", callback_data="list:idioms:0")],
            [InlineKeyboardButton("Needs repeat", callback_data="list:repeat:0")],
            [InlineKeyboardButton("Summary", callback_data="sum")],
            [InlineKeyboardButton("Home", callback_data="home")],
        ]
    )


def item_label(item: Item) -> str:
    label = f"{item.term} — {item.translation}"
    return label[:60]


def item_list(items: list[Item], kind: str, page: int, total: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(item_label(item), callback_data=f"item:{item.id}")]
        for item in items
    ]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("Previous", callback_data=f"list:{kind}:{page - 1}"))
    if (page + 1) * PAGE_SIZE < total:
        nav.append(InlineKeyboardButton("Next", callback_data=f"list:{kind}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("Progress", callback_data="prog")])
    return InlineKeyboardMarkup(rows)
