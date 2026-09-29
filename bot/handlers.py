from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from telegram import LinkPreviewOptions, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes

from bot import config, llm
from bot.constants import PAGE_SIZE, flag_for, language_name, topic_name
from bot.db import User, db
from bot.delivery import send_now
from bot.keyboards import (
    confirm_delete,
    content_types,
    home as home_keyboard,
    item_list,
    languages,
    lesson as lesson_keyboard,
    levels,
    plan_actions,
    plans_menu,
    progress_menu,
    schedule_modes,
    settings_menu,
    text_step,
    timezones,
    topics,
    translation_languages,
)
from bot.render import (
    esc,
    help_html,
    home_html,
    lesson_from_item,
    plan_html,
    progress_html,
)
from bot.schedule_logic import choose_random_datetime, clock_span_minutes, normalize_clock
from bot.timezones import resolve_timezone

logger = logging.getLogger(__name__)
_PREVIEW_OFF = LinkPreviewOptions(is_disabled=True)


def user_now(user: User) -> datetime:
    try:
        return datetime.now(ZoneInfo(user.timezone))
    except ZoneInfoNotFoundError:
        return datetime.now(ZoneInfo("Europe/Berlin"))


async def show(update: Update, text: str, markup) -> None:
    kwargs = {
        "text": text,
        "reply_markup": markup,
        "parse_mode": ParseMode.HTML,
        "link_preview_options": _PREVIEW_OFF,
    }
    query = update.callback_query
    if query and query.message:
        try:
            await query.edit_message_text(**kwargs)
            return
        except BadRequest as exc:
            if "message is not modified" in str(exc).lower():
                return
        await query.message.reply_text(**kwargs)
        return
    message = update.effective_message
    if message:
        await message.reply_text(**kwargs)


async def deny(update: Update) -> None:
    if update.callback_query:
        await update.callback_query.answer("This bot is private.", show_alert=True)
    elif update.effective_message:
        await update.effective_message.reply_text("This Wortuhr bot is private.")


async def guard(update: Update) -> bool:
    user = update.effective_user
    chat = update.effective_chat
    if user is None or chat is None or chat.type != "private":
        return False
    if not config.OPEN_SIGNUP:
        owner = db.get_setting("owner_id")
        if owner is None:
            db.set_setting("owner_id", str(user.id))
        elif owner != str(user.id):
            await deny(update)
            return False
    db.upsert_user(user.id, user.first_name or "")
    return True


def _saved_user(update: Update) -> User:
    user = db.get_user(update.effective_user.id)
    if user is None:
        raise RuntimeError("user missing after guard")
    return user


async def begin_onboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["wizard"] = {"action": "onboard", "step": "timezone"}
    await show(
        update,
        "<b>Wortuhr</b>\n\n"
        "I send words and idioms on a schedule you choose, with practical examples and translations.\n\n"
        "First, pick the timezone for those sending times.",
        timezones(back="home"),
    )


async def show_home(update: Update, context: ContextTypes.DEFAULT_TYPE, notice: str = "") -> None:
    if notice:
        context.user_data["owner_notice"] = True
    user = db.get_user(update.effective_user.id)
    if user is None or not user.ready:
        await begin_onboard(update, context)
        return
    context.user_data.pop("wizard", None)
    prefix = ""
    if context.user_data.pop("owner_notice", False):
        prefix = "You are the owner of this bot. Other Telegram accounts cannot use it.\n\n"
    stats = db.counts(user.telegram_id)
    await show(update, prefix + home_html(user.display_name, stats), home_keyboard())


async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("wizard", None)
    user = _saved_user(update)
    text = (
        "<b>Settings</b>\n\n"
        f"Timezone: <code>{esc(user.timezone)}</code>\n"
        f"Translations: {esc(user.translation_language)}\n\n"
        "Cards use this timezone and this translation language."
    )
    await show(update, text, settings_menu())


async def show_plans(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("wizard", None)
    user = _saved_user(update)
    plans = db.list_plans(user.telegram_id)
    if not plans:
        text = "<b>My plans</b>\n\nYou have no plans yet. A plan is one schedule: language, level, topic, and time."
    else:
        text = "<b>My plans</b>\n\nOpen a plan to edit it, pause it, or delete it."
    await show(update, text, plans_menu(plans))


async def show_plan(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_id: int) -> None:
    context.user_data.pop("wizard", None)
    user = _saved_user(update)
    plan = db.get_plan(plan_id, user.telegram_id)
    if plan is None:
        await show_plans(update, context)
        return
    await show(update, plan_html(plan, user_now(user)), plan_actions(plan))


async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("wizard", None)
    user = _saved_user(update)
    stats = db.counts(user.telegram_id)
    today = user_now(user).date()
    counts = db.activity_counts(user.telegram_id, (today - timedelta(days=6)).isoformat())
    await show(update, progress_html(stats, counts, today), progress_menu())


def _list_query(kind: str) -> tuple[str, dict, str]:
    if kind == "words":
        return (
            "Learned words",
            {"content_type": "word", "status": "learned"},
            "Words you mark with <b>I learned this</b> will collect here.",
        )
    if kind == "idioms":
        return (
            "Learned idioms",
            {"content_type": "idiom", "status": "learned"},
            "Idioms you mark with <b>I learned this</b> will collect here.",
        )
    return (
        "Needs repeat",
        {"status": "repeat"},
        "When a card arrives, tap <b>Repeat again</b> and it will collect here.",
    )


async def show_list(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str, page: int) -> None:
    user = _saved_user(update)
    title, filters, empty = _list_query(kind)
    total = db.count_items(user.telegram_id, **filters)
    if total == 0:
        await show(update, f"<b>{title}</b>\n\n{empty}", progress_menu())
        return
    pages = max((total - 1) // PAGE_SIZE, 0)
    page = min(max(page, 0), pages)
    items = db.list_items(user.telegram_id, limit=PAGE_SIZE, offset=page * PAGE_SIZE, **filters)
    start = page * PAGE_SIZE + 1
    end = start + len(items) - 1
    text = f"<b>{title}</b>\n\n{start}–{end} of {total}\nTap one to open the card."
    await show(update, text, item_list(items, kind, page, total))


def _lead(wizard: dict) -> str:
    if wizard.get("action") != "create":
        return ""
    lines = ["<b>New plan</b>"]
    if wizard.get("language"):
        lines.append(f"{flag_for(wizard['language'])} {esc(wizard['language'])}")
    if wizard.get("level"):
        lines.append(f"Level {esc(wizard['level'])}")
    if wizard.get("content_type"):
        lines.append("Words" if wizard["content_type"] == "word" else "Idioms")
    if wizard.get("topic"):
        lines.append(esc(wizard["topic"]))
    if wizard.get("schedule_mode") == "exact" and wizard.get("time_1"):
        lines.append(f"Every day at {esc(wizard['time_1'])}")
    elif wizard.get("schedule_mode") == "twice" and wizard.get("time_1"):
        lines.append(f"First time {esc(wizard['time_1'])}")
    elif wizard.get("schedule_mode") == "random" and wizard.get("window_start"):
        lines.append(f"Window from {esc(wizard['window_start'])}")
    return "\n".join(lines) + "\n\n"


def _previous_step(wizard: dict) -> str:
    step = wizard.get("step")
    action = wizard.get("action")
    if action == "edit" and step in {"level", "topic", "mode"}:
        return "plan"
    if action == "settings" and step in {"timezone", "translation", "custom_timezone", "custom_translation"}:
        return "settings"
    if action == "onboard" and step == "custom_timezone":
        return "timezone"
    if action == "onboard" and step == "translation":
        return "timezone"
    if action == "onboard" and step == "custom_translation":
        return "translation"
    mapping = {
        "language": "home",
        "level": "language",
        "type": "level",
        "topic": "type",
        "mode": "topic",
        "custom_language": "language",
        "custom_topic": "topic",
        "time_1": "mode",
        "time_2": "time_1",
        "window_start": "mode",
        "window_end": "window_start",
    }
    return mapping.get(step, "home")


async def show_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    wizard = context.user_data.get("wizard")
    if not wizard:
        await show_home(update, context)
        return
    step = wizard.get("step")
    lead = _lead(wizard)
    if step == "language":
        await show(update, lead + "Which language do you want to learn?", languages())
    elif step == "level":
        question = "Choose a new level." if wizard.get("action") == "edit" else "Which level, from A1 to C2?"
        await show(update, lead + question, levels())
    elif step == "type":
        await show(update, lead + "Words or idioms?", content_types())
    elif step == "topic":
        question = (
            "Choose a new topic, or type your own."
            if wizard.get("action") == "edit"
            else "Choose a topic, or type your own. A job or a technical field is fine."
        )
        await show(update, lead + question, topics())
    elif step == "mode":
        await show(
            update,
            lead + "When should I send it?\nExact time, twice a day, or a random time inside a window.",
            schedule_modes(),
        )
    elif step == "timezone":
        back = "home" if wizard.get("action") == "onboard" else "settings"
        await show(update, "Choose the timezone for sending times.", timezones(back=back))
    elif step == "translation":
        back = "w:back" if wizard.get("action") == "onboard" else "settings"
        await show(
            update,
            "Which language should the translations use?",
            translation_languages(back=back),
        )
    elif step == "time_1" and wizard.get("schedule_mode") == "twice":
        await show(update, lead + "Send the first time, for example 08:00.", text_step())
    elif step == "time_1":
        await show(update, lead + "Send the time in 24-hour form, for example 08:30.", text_step())
    elif step == "time_2":
        await show(update, lead + "Send the second time, for example 20:00.", text_step())
    elif step == "window_start":
        await show(update, lead + "Send the start of the random window, for example 09:00.", text_step())
    elif step == "window_end":
        await show(
            update,
            lead + "Send the end of the window, for example 18:00. Leave at least 30 minutes.",
            text_step(),
        )
    elif step == "custom_language":
        await show(update, lead + "Type the language you want to learn. For example: Swedish.", text_step())
    elif step == "custom_topic":
        await show(
            update,
            lead + "Type a topic, for example nursing, electrical engineering, or job interviews.",
            text_step(),
        )
    elif step == "custom_timezone":
        await show(update, "Send a timezone, for example Europe/Berlin or Tehran.", text_step())
    elif step == "custom_translation":
        await show(update, "Send the language for translations, for example Persian.", text_step())
    else:
        await show_home(update, context)


async def begin_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["wizard"] = {"action": "create", "step": "language"}
    await show_step(update, context)


async def begin_edit(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_id: int, edit: str) -> None:
    user = _saved_user(update)
    plan = db.get_plan(plan_id, user.telegram_id)
    if plan is None:
        await show_plans(update, context)
        return
    step = {"level": "level", "topic": "topic", "sched": "mode"}[edit]
    context.user_data["wizard"] = {
        "action": "edit",
        "edit": edit,
        "step": step,
        "plan_id": plan_id,
        "language": plan.language,
        "level": plan.level,
        "content_type": plan.content_type,
        "topic": plan.topic,
        "schedule_mode": plan.schedule_mode,
    }
    await show_step(update, context)


def _schedule_fields(wizard: dict, user: User) -> dict:
    mode = wizard["schedule_mode"]
    fields = {
        "schedule_mode": mode,
        "time_1": wizard.get("time_1") if mode in {"exact", "twice"} else None,
        "time_2": wizard.get("time_2") if mode == "twice" else None,
        "window_start": wizard.get("window_start") if mode == "random" else None,
        "window_end": wizard.get("window_end") if mode == "random" else None,
        "next_random_at": None,
    }
    if mode == "random":
        nxt = choose_random_datetime(user_now(user), fields["window_start"], fields["window_end"])
        fields["next_random_at"] = nxt.isoformat(timespec="minutes")
    return fields


async def finish_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    wizard = context.user_data.get("wizard") or {}
    user = _saved_user(update)
    fields = _schedule_fields(wizard, user)
    if wizard.get("action") == "create":
        plan = db.create_plan(
            user_id=user.telegram_id,
            language=wizard["language"],
            level=wizard["level"],
            content_type=wizard["content_type"],
            topic=wizard["topic"],
            **fields,
        )
        plan_id = plan.id
    else:
        plan_id = int(wizard["plan_id"])
        db.update_plan(plan_id, user.telegram_id, **fields)
    context.user_data.pop("wizard", None)
    await show_plan(update, context, plan_id)


async def _after_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = _saved_user(update)
    wizard = context.user_data.get("wizard") or {}
    if wizard.get("action") == "onboard" or not user.ready:
        context.user_data["wizard"] = {"action": "onboard", "step": "translation"}
        await show_step(update, context)
        return
    context.user_data.pop("wizard", None)
    await show_settings(update, context)


async def _after_translation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = _saved_user(update)
    wizard = context.user_data.get("wizard") or {}
    if wizard.get("action") == "onboard" or not user.ready:
        db.set_ready(user.telegram_id)
        context.user_data.pop("wizard", None)
        await show_home(update, context)
        return
    context.user_data.pop("wizard", None)
    await show_settings(update, context)


async def ready_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> User | None:
    user = _saved_user(update)
    if not user.ready:
        await begin_onboard(update, context)
        return None
    return user


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.effective_chat.type != "private":
        return
    before = db.get_setting("owner_id")
    if not await guard(update):
        return
    user = update.effective_user
    claimed = (
        not config.OPEN_SIGNUP
        and before is None
        and user is not None
        and db.get_setting("owner_id") == str(user.id)
    )
    notice = "You are the owner of this bot. Other Telegram accounts cannot use it." if claimed else ""
    await show_home(update, context, notice=notice)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update):
        return
    await show(update, help_html(), home_keyboard())


async def new_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update) or await ready_user(update, context) is None:
        return
    await begin_create(update, context)


async def plans_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update) or await ready_user(update, context) is None:
        return
    await show_plans(update, context)


async def progress_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update) or await ready_user(update, context) is None:
        return
    await show_progress(update, context)


async def review_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update) or await ready_user(update, context) is None:
        return
    await show_list(update, context, "repeat", 0)


async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update) or await ready_user(update, context) is None:
        return
    await show_settings(update, context)


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update):
        return
    context.user_data.pop("wizard", None)
    await show_home(update, context)


def _parse_int(data: str, index: int) -> int | None:
    parts = data.split(":")
    if len(parts) <= index:
        return None
    try:
        return int(parts[index])
    except ValueError:
        return None


async def _go_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    wizard = context.user_data.get("wizard")
    if not wizard:
        await show_home(update, context)
        return
    target = _previous_step(wizard)
    if target == "home":
        await show_home(update, context)
    elif target == "plan":
        plan_id = int(wizard.get("plan_id") or 0)
        context.user_data.pop("wizard", None)
        await show_plan(update, context, plan_id)
    elif target == "settings":
        await show_settings(update, context)
    else:
        wizard["step"] = target
        await show_step(update, context)


async def _on_mark(update: Update, item_id: int, status: str) -> None:
    query = update.callback_query
    user = _saved_user(update)
    if query is None or not db.set_item_status(item_id, user.telegram_id, status):
        if query:
            await query.answer("That card is not in your saved list.", show_alert=True)
        return
    label = "Marked as learned" if status == "learned" else "Saved to repeat"
    await query.answer(label)
    try:
        await query.edit_message_reply_markup(reply_markup=lesson_keyboard(item_id, status))
    except BadRequest as exc:
        if "not modified" not in str(exc).lower():
            raise


async def _on_send_now(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_id: int) -> None:
    query = update.callback_query
    if query is None or query.message is None:
        return
    await query.answer("Writing your card…")
    user = _saved_user(update)
    plan = db.get_plan(plan_id, user.telegram_id)
    if plan is None:
        await query.message.reply_text("That plan is gone.")
        return
    placeholder = await query.message.reply_text("Writing your card…")
    try:
        await send_now(context.bot, plan, user, user_now(user).date().isoformat())
    except Forbidden:
        db.pause_user_plans(user.telegram_id)
        await placeholder.edit_text("Telegram refused the message, so I paused your plans.")
        return
    except llm.LLMError as exc:
        await placeholder.edit_text(exc.user_message)
        return
    except Exception:
        logger.exception("send now failed")
        await placeholder.edit_text("I could not send a card just now.")
        return
    try:
        await placeholder.delete()
    except BadRequest:
        pass


async def _on_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.message is None:
        return
    user = _saved_user(update)
    items = db.learned_for_summary(user.telegram_id)
    if not items:
        await query.message.reply_text(
            "Mark a few cards with I learned this, then ask for a summary."
        )
        return
    placeholder = await query.message.reply_text("Writing your summary…")
    payload = [
        {
            "term": item.term,
            "translation": item.translation,
            "language": item.language,
            "level": item.level,
            "content_type": item.content_type,
        }
        for item in items
    ]
    try:
        text = await llm.summarize_learned(payload, user.translation_language)
    except llm.LLMError as exc:
        await placeholder.edit_text(exc.user_message)
        return
    except Exception:
        logger.exception("summary failed")
        await placeholder.edit_text("I could not write a summary just now.")
        return
    await placeholder.edit_text(
        f"<b>What you have learned</b>\n\n{esc(text)}",
        parse_mode=ParseMode.HTML,
    )


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    data = query.data or ""
    if not await guard(update):
        return
    user = _saved_user(update)
    try:
        if data.startswith("learn:") or data.startswith("repeat:"):
            item_id = _parse_int(data, 1)
            if item_id is None:
                await query.answer()
                return
            await _on_mark(update, item_id, "learned" if data.startswith("learn:") else "repeat")
            return
        if data.startswith("pnow:"):
            plan_id = _parse_int(data, 1)
            if plan_id is None:
                await query.answer()
                return
            await _on_send_now(update, context, plan_id)
            return
        await query.answer()
        if not user.ready and data not in {"home", "w:back", "tz:custom", "tr:custom"} and not data.startswith(("tz:", "tr:")):
            await begin_onboard(update, context)
            return
        await _route(update, context, data, user)
    except Exception:
        logger.exception("callback failed: %s", data)
        try:
            await query.answer()
        except Exception:
            pass
        if query.message:
            await query.message.reply_text("Something went wrong. Send /start to open the menu.")


async def _route(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str, user: User) -> None:
    wizard = context.user_data.get("wizard") or {}
    if data == "home":
        await show_home(update, context)
    elif data == "help":
        await show(update, help_html(), home_keyboard())
    elif data == "plans":
        await show_plans(update, context)
    elif data == "pnew":
        await begin_create(update, context)
    elif data == "prog":
        await show_progress(update, context)
    elif data == "review":
        await show_list(update, context, "repeat", 0)
    elif data == "settings":
        await show_settings(update, context)
    elif data == "set:tz":
        context.user_data["wizard"] = {"action": "settings", "step": "timezone"}
        await show_step(update, context)
    elif data == "set:tr":
        context.user_data["wizard"] = {"action": "settings", "step": "translation"}
        await show_step(update, context)
    elif data == "w:back":
        await _go_back(update, context)
    elif data == "tz:custom":
        action = "onboard" if wizard.get("action") == "onboard" or not user.ready else "settings"
        context.user_data["wizard"] = {"action": action, "step": "custom_timezone"}
        await show_step(update, context)
    elif data.startswith("tz:"):
        zone = data.split(":", 1)[1]
        if resolve_timezone(zone) is None:
            await show_step(update, context)
            return
        db.set_timezone(user.telegram_id, zone)
        if wizard.get("action") not in {"onboard", "settings"} and user.ready:
            await show_step(update, context)
            return
        await _after_timezone(update, context)
    elif data == "tr:custom":
        action = "onboard" if wizard.get("action") == "onboard" or not user.ready else "settings"
        kept = {"action": action, "step": "custom_translation"}
        context.user_data["wizard"] = kept
        await show_step(update, context)
    elif data.startswith("tr:"):
        language = data.split(":", 1)[1]
        if len(language) > 40:
            return
        db.set_translation_language(user.telegram_id, language)
        if wizard.get("action") not in {"onboard", "settings"} and user.ready:
            await show_step(update, context)
            return
        await _after_translation(update, context)
    elif data == "sum":
        await _on_summary(update, context)
    elif data.startswith("list:"):
        parts = data.split(":")
        if len(parts) != 3 or parts[1] not in {"words", "idioms", "repeat"}:
            return
        page = _parse_int(data, 2) or 0
        await show_list(update, context, parts[1], page)
    elif data.startswith("item:"):
        await _open_item(update, _parse_int(data, 1))
    elif data.startswith("popen:"):
        plan_id = _parse_int(data, 1)
        if plan_id is not None:
            await show_plan(update, context, plan_id)
    elif data.startswith("ppause:"):
        plan_id = _parse_int(data, 1)
        if plan_id is not None:
            db.set_plan_active(plan_id, user.telegram_id, False)
            await show_plan(update, context, plan_id)
    elif data.startswith("presume:"):
        plan_id = _parse_int(data, 1)
        if plan_id is not None:
            db.set_plan_active(plan_id, user.telegram_id, True)
            await show_plan(update, context, plan_id)
    elif data.startswith("pdelok:"):
        plan_id = _parse_int(data, 1)
        if plan_id is not None:
            db.delete_plan(plan_id, user.telegram_id)
        await show_plans(update, context)
    elif data.startswith("pdel:"):
        plan_id = _parse_int(data, 1)
        plan = db.get_plan(plan_id, user.telegram_id) if plan_id is not None else None
        if plan is None:
            await show_plans(update, context)
            return
        text = (
            plan_html(plan, user_now(user))
            + "\n\nDelete this plan? Cards you already received stay in your progress."
        )
        await show(update, text, confirm_delete(plan_id))
    elif data.startswith("pedit:"):
        parts = data.split(":")
        if len(parts) != 3 or parts[1] not in {"level", "topic", "sched"}:
            return
        plan_id = _parse_int(data, 2)
        if plan_id is not None:
            await begin_edit(update, context, plan_id, parts[1])
    elif data.startswith("w:"):
        await _on_wizard(update, context, data)
    else:
        await show_home(update, context)


async def _open_item(update: Update, item_id: int | None) -> None:
    query = update.callback_query
    if query is None or query.message is None or item_id is None:
        return
    item = db.get_item(item_id, update.effective_user.id)
    if item is None:
        await query.message.reply_text("That card is no longer saved.")
        return
    await query.message.reply_text(
        lesson_from_item(item),
        parse_mode=ParseMode.HTML,
        reply_markup=lesson_keyboard(item.id, item.status),
        link_preview_options=_PREVIEW_OFF,
    )


async def _on_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
    wizard = context.user_data.get("wizard")
    if not wizard or wizard.get("action") not in {"create", "edit"}:
        await show_home(update, context)
        return
    parts = data.split(":")
    kind = parts[1] if len(parts) > 1 else ""
    expected = {
        "lang": "language",
        "level": "level",
        "type": "type",
        "topic": "topic",
        "mode": "mode",
    }.get(kind)
    if expected and wizard.get("step") != expected:
        await show_step(update, context)
        return
    if kind == "lang":
        code = parts[2] if len(parts) > 2 else ""
        if code == "custom":
            wizard["step"] = "custom_language"
        else:
            name = language_name(code)
            if name is None:
                await show_step(update, context)
                return
            wizard["language"] = name
            wizard["step"] = "level"
        await show_step(update, context)
    elif kind == "level":
        level = parts[2] if len(parts) > 2 else ""
        if level not in {"A1", "A2", "B1", "B2", "C1", "C2"}:
            await show_step(update, context)
            return
        wizard["level"] = level
        if wizard.get("action") == "edit":
            db.update_plan(int(wizard["plan_id"]), _saved_user(update).telegram_id, level=level)
            await show_plan(update, context, int(wizard["plan_id"]))
            return
        wizard["step"] = "type"
        await show_step(update, context)
    elif kind == "type":
        content_type = parts[2] if len(parts) > 2 else ""
        if content_type not in {"word", "idiom"}:
            await show_step(update, context)
            return
        wizard["content_type"] = content_type
        wizard["step"] = "topic"
        await show_step(update, context)
    elif kind == "topic":
        code = parts[2] if len(parts) > 2 else ""
        if code == "custom":
            wizard["step"] = "custom_topic"
            await show_step(update, context)
            return
        name = topic_name(code)
        if name is None:
            await show_step(update, context)
            return
        wizard["topic"] = name
        if wizard.get("action") == "edit":
            db.update_plan(int(wizard["plan_id"]), _saved_user(update).telegram_id, topic=name)
            await show_plan(update, context, int(wizard["plan_id"]))
            return
        wizard["step"] = "mode"
        await show_step(update, context)
    elif kind == "mode":
        mode = parts[2] if len(parts) > 2 else ""
        if mode not in {"exact", "twice", "random"}:
            await show_step(update, context)
            return
        wizard["schedule_mode"] = mode
        wizard["time_1"] = None
        wizard["time_2"] = None
        wizard["window_start"] = None
        wizard["window_end"] = None
        wizard["step"] = "window_start" if mode == "random" else "time_1"
        await show_step(update, context)
    else:
        await show_step(update, context)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update):
        return
    wizard = context.user_data.get("wizard")
    message = update.message
    if message is None:
        return
    if not wizard:
        await message.reply_text("Use the menu, or send /start.")
        return
    text = message.text.strip()
    step = wizard.get("step")
    user = _saved_user(update)
    if step == "custom_language":
        if not text or len(text) > 40:
            await message.reply_text("Send a language name, up to 40 characters.")
            return
        wizard["language"] = text
        wizard["step"] = "level"
        await show_step(update, context)
        return
    if step == "custom_topic":
        if not text or len(text) > 80:
            await message.reply_text("Send a topic, up to 80 characters.")
            return
        wizard["topic"] = text
        if wizard.get("action") == "edit":
            db.update_plan(int(wizard["plan_id"]), user.telegram_id, topic=text)
            await show_plan(update, context, int(wizard["plan_id"]))
            return
        wizard["step"] = "mode"
        await show_step(update, context)
        return
    if step == "custom_timezone":
        zone = resolve_timezone(text)
        if zone is None:
            await message.reply_text("I don't know that timezone. Try Europe/Berlin or Asia/Tehran.")
            return
        db.set_timezone(user.telegram_id, zone)
        await _after_timezone(update, context)
        return
    if step == "custom_translation":
        if not text or len(text) > 40:
            await message.reply_text("Send a language name, up to 40 characters.")
            return
        db.set_translation_language(user.telegram_id, text)
        await _after_translation(update, context)
        return
    if step in {"time_1", "time_2", "window_start", "window_end"}:
        clock = normalize_clock(text)
        if clock is None:
            await message.reply_text("Use a time like 08:30.")
            return
        if step == "time_2" and clock == wizard.get("time_1"):
            await message.reply_text("Choose a different second time.")
            return
        if step == "window_end":
            start = wizard.get("window_start")
            if not start or clock_span_minutes(start, clock) < 30:
                await message.reply_text("The window needs at least 30 minutes, and the end must be later.")
                return
        wizard[step if step != "window_end" else "window_end"] = clock
        if step == "time_1":
            wizard["time_1"] = clock
            if wizard.get("schedule_mode") == "twice":
                wizard["step"] = "time_2"
                await show_step(update, context)
                return
            await finish_schedule(update, context)
            return
        if step == "time_2":
            wizard["time_2"] = clock
            await finish_schedule(update, context)
            return
        if step == "window_start":
            wizard["window_start"] = clock
            wizard["step"] = "window_end"
            await show_step(update, context)
            return
        wizard["window_end"] = clock
        await finish_schedule(update, context)
        return
    await message.reply_text("Use the buttons below, or send /cancel.")
