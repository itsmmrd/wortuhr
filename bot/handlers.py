from __future__ import annotations

import json
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
from bot.i18n import UI_ASK, language_label, t, topic_label, translation_label, ui_label
from bot.keyboards import (
    confirm_delete,
    content_types,
    days_keyboard,
    home as home_keyboard,
    item_list,
    languages,
    lesson as lesson_keyboard,
    levels,
    plan_actions,
    plans_menu,
    progress_menu,
    settings_menu,
    slot_choice,
    text_step,
    times_per_day,
    timezones,
    topics,
    translation_languages,
    ui_language_keyboard,
)
from bot.render import (
    esc,
    help_html,
    home_html,
    lesson_from_item,
    plan_html,
    progress_html,
)
from bot.schedule_logic import day_phrase, finalize_schedule, normalize_clock
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


def _saved_user(update: Update) -> User:
    user = db.get_user(update.effective_user.id)
    if user is None:
        raise RuntimeError("user missing after guard")
    return user


def ui_of(update: Update) -> str:
    user = update.effective_user
    if user is None:
        return "en"
    saved = db.get_user(user.id)
    code = saved.ui_language if saved else None
    return code if code in {"en", "fa"} else "en"


def say(update: Update, key: str, **kwargs: object) -> str:
    return t(ui_of(update), key, **kwargs)


async def deny(update: Update) -> None:
    if update.callback_query:
        await update.callback_query.answer("This bot is private.\nاین ربات خصوصی است.", show_alert=True)
    elif update.effective_message:
        await update.effective_message.reply_text("This Wortuhr bot is private.\nاین ربات وورتور خصوصی است.")


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


async def ask_ui_language(update: Update, context: ContextTypes.DEFAULT_TYPE, dest: str) -> None:
    context.user_data["ui_dest"] = dest
    await show(update, UI_ASK, ui_language_keyboard())


async def apply_ui_language(update: Update, context: ContextTypes.DEFAULT_TYPE, code: str) -> None:
    user = _saved_user(update)
    db.set_ui_language(user.telegram_id, code)
    dest = str(context.user_data.pop("ui_dest", "home"))
    user = _saved_user(update)
    if dest == "settings" and user.ready:
        await show_settings(update, context)
        return
    if not user.ready:
        await begin_onboard(update, context)
        return
    await show_home(update, context)


async def begin_onboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = _saved_user(update)
    if user.ui_language not in {"en", "fa"}:
        await ask_ui_language(update, context, "onboard")
        return
    context.user_data["wizard"] = {"action": "onboard", "step": "timezone"}
    await show_step(update, context)


async def show_home(update: Update, context: ContextTypes.DEFAULT_TYPE, notice: str = "") -> None:
    if notice:
        context.user_data["owner_notice"] = True
    user = db.get_user(update.effective_user.id)
    if user is None or user.ui_language not in {"en", "fa"}:
        await ask_ui_language(update, context, "home")
        return
    if not user.ready:
        await begin_onboard(update, context)
        return
    context.user_data.pop("wizard", None)
    prefix = ""
    if context.user_data.pop("owner_notice", False):
        prefix = say(update, "owner_notice")
    stats = db.counts(user.telegram_id)
    lang = user.ui_language
    await show(update, prefix + home_html(user.display_name, stats, lang), home_keyboard(lang))


async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("wizard", None)
    user = _saved_user(update)
    lang = ui_of(update)
    text = t(
        lang,
        "settings_body",
        tz=esc(user.timezone),
        tr=esc(translation_label(lang, user.translation_language)),
        ui=esc(ui_label(lang)),
    )
    await show(update, text, settings_menu(lang))


async def show_plans(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("wizard", None)
    user = _saved_user(update)
    lang = ui_of(update)
    plans = db.list_plans(user.telegram_id)
    text = say(update, "plans_open" if plans else "plans_empty")
    await show(update, text, plans_menu(plans, lang))


async def show_plan(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_id: int) -> None:
    context.user_data.pop("wizard", None)
    user = _saved_user(update)
    plan = db.get_plan(plan_id, user.telegram_id)
    if plan is None:
        await show_plans(update, context)
        return
    lang = ui_of(update)
    await show(update, plan_html(plan, user_now(user), lang), plan_actions(plan, lang))


async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("wizard", None)
    user = _saved_user(update)
    lang = ui_of(update)
    stats = db.counts(user.telegram_id)
    today = user_now(user).date()
    counts = db.activity_counts(user.telegram_id, (today - timedelta(days=6)).isoformat())
    await show(update, progress_html(stats, counts, today, lang), progress_menu(lang))


def _list_query(kind: str, lang: str) -> tuple[str, dict, str]:
    if kind == "words":
        return (
            t(lang, "learned_words"),
            {"content_type": "word", "status": "learned"},
            t(lang, "empty_words"),
        )
    if kind == "idioms":
        return (
            t(lang, "learned_idioms"),
            {"content_type": "idiom", "status": "learned"},
            t(lang, "empty_idioms"),
        )
    return (
        t(lang, "needs_repeat"),
        {"status": "repeat"},
        t(lang, "empty_repeat"),
    )


async def show_list(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str, page: int) -> None:
    user = _saved_user(update)
    lang = ui_of(update)
    title, filters, empty = _list_query(kind, lang)
    total = db.count_items(user.telegram_id, **filters)
    if total == 0:
        await show(update, f"<b>{title}</b>\n\n{empty}", progress_menu(lang))
        return
    pages = max((total - 1) // PAGE_SIZE, 0)
    page = min(max(page, 0), pages)
    items = db.list_items(user.telegram_id, limit=PAGE_SIZE, offset=page * PAGE_SIZE, **filters)
    start = page * PAGE_SIZE + 1
    end = start + len(items) - 1
    text = f"<b>{title}</b>\n\n{t(lang, 'list_range', start=start, end=end, total=total)}"
    await show(update, text, item_list(items, kind, page, total, lang))


def _lead(wizard: dict, lang: str) -> str:
    if wizard.get("action") != "create":
        return ""
    lines = [t(lang, "new_plan_title")]
    if wizard.get("language"):
        lines.append(f"{flag_for(wizard['language'])} {esc(language_label(lang, wizard['language']))}")
    if wizard.get("level"):
        lines.append(t(lang, "level_line", level=esc(wizard["level"])))
    if wizard.get("content_type"):
        lines.append(t(lang, "words" if wizard["content_type"] == "word" else "idioms"))
    if wizard.get("topic"):
        lines.append(esc(topic_label(lang, wizard["topic"])))
    if wizard.get("weekdays"):
        lines.append(esc(day_phrase(wizard["weekdays"], lang)))
    if wizard.get("times_per_day"):
        count = int(wizard["times_per_day"])
        lines.append(t(lang, "once_a_day") if count == 1 else t(lang, "times_a_day", n=count))
    return "\n".join(lines) + "\n\n"


def _previous_step(wizard: dict) -> str:
    step = wizard.get("step")
    action = wizard.get("action")
    if action == "edit" and step in {"level", "topic", "days"}:
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
        "days": "topic",
        "count": "days",
        "slot_kind": "count",
        "slot_time": "count",
        "custom_language": "language",
        "custom_topic": "topic",
    }
    return mapping.get(step, "home")


async def show_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    wizard = context.user_data.get("wizard")
    if not wizard:
        await show_home(update, context)
        return
    step = wizard.get("step")
    lang = ui_of(update)
    lead = _lead(wizard, lang)
    if step == "language":
        await show(update, lead + say(update, "which_learn"), languages(lang))
    elif step == "level":
        question = say(update, "new_level" if wizard.get("action") == "edit" else "which_level")
        await show(update, lead + question, levels(lang))
    elif step == "type":
        await show(update, lead + say(update, "words_or_idioms"), content_types(lang))
    elif step == "topic":
        question = say(update, "new_topic" if wizard.get("action") == "edit" else "which_topic")
        await show(update, lead + question, topics(lang))
    elif step == "days":
        selected = list(wizard.get("weekdays") or [])
        count = len(selected)
        if wizard.pop("need_day", None):
            note = say(update, "pick_day")
        elif count == 1:
            note = say(update, "days_one")
        elif count:
            note = say(update, "days_many", n=count)
        else:
            note = ""
        await show(update, lead + note + say(update, "which_days"), days_keyboard(selected, lang))
    elif step == "count":
        await show(update, lead + say(update, "how_many"), times_per_day(lang))
    elif step == "slot_kind":
        index = int(wizard.get("slot_index") or 0) + 1
        total = int(wizard.get("times_per_day") or 1)
        await show(update, lead + say(update, "lesson_choice", i=index, n=total), slot_choice(lang))
    elif step == "slot_time":
        index = int(wizard.get("slot_index") or 0) + 1
        await show(update, lead + say(update, "send_clock", i=index), text_step(lang))
    elif step == "timezone":
        back = "home" if wizard.get("action") == "onboard" else "settings"
        intro = say(update, "onboard_intro") if wizard.get("action") == "onboard" else say(update, "tz_prompt")
        await show(update, intro, timezones(back=back, lang=lang))
    elif step == "translation":
        back = "w:back" if wizard.get("action") == "onboard" else "settings"
        await show(update, say(update, "tr_prompt"), translation_languages(back=back, lang=lang))
    elif step == "custom_language":
        await show(update, lead + say(update, "type_language"), text_step(lang))
    elif step == "custom_topic":
        await show(update, lead + say(update, "type_topic"), text_step(lang))
    elif step == "custom_timezone":
        await show(update, say(update, "tz_custom"), text_step(lang))
    elif step == "custom_translation":
        await show(update, say(update, "tr_custom"), text_step(lang))
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
    step = {"level": "level", "topic": "topic", "sched": "days"}[edit]
    context.user_data["wizard"] = {
        "action": "edit",
        "edit": edit,
        "step": step,
        "plan_id": plan_id,
        "language": plan.language,
        "level": plan.level,
        "content_type": plan.content_type,
        "topic": plan.topic,
        "weekdays": [],
        "slots": [],
        "slot_index": 0,
    }
    await show_step(update, context)


def _begin_days(wizard: dict) -> None:
    wizard["step"] = "days"
    wizard["weekdays"] = []
    wizard["slots"] = []
    wizard["slot_index"] = 0
    wizard.pop("times_per_day", None)


def _schedule_fields(wizard: dict, user: User) -> dict:
    schedule = finalize_schedule(user_now(user), wizard["weekdays"], wizard["slots"])
    first = schedule["slots"][0]
    return {
        "schedule_mode": "custom",
        "schedule_json": json.dumps(schedule),
        "time_1": first.get("time") if first.get("kind") == "exact" else None,
        "time_2": None,
        "window_start": first.get("start") if first.get("kind") == "random" else None,
        "window_end": first.get("end") if first.get("kind") == "random" else None,
        "next_random_at": first.get("next") if first.get("kind") == "random" else None,
    }


async def _after_slot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    wizard = context.user_data["wizard"]
    wizard["slot_index"] = len(wizard.get("slots") or [])
    if wizard["slot_index"] >= int(wizard.get("times_per_day") or 1):
        await finish_schedule(update, context)
        return
    wizard["step"] = "slot_kind"
    await show_step(update, context)


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
    if user.ui_language not in {"en", "fa"}:
        await ask_ui_language(update, context, "home" if user.ready else "onboard")
        return None
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
    if not await guard(update) or await ready_user(update, context) is None:
        return
    lang = ui_of(update)
    await show(update, help_html(lang), home_keyboard(lang))


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
    if not await guard(update) or await ready_user(update, context) is None:
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
        if wizard.get("step") in {"slot_kind", "slot_time"} and target == "count":
            wizard["slots"] = []
            wizard["slot_index"] = 0
        wizard["step"] = target
        await show_step(update, context)


async def _on_mark(update: Update, item_id: int, status: str) -> None:
    query = update.callback_query
    user = _saved_user(update)
    if query is None or not db.set_item_status(item_id, user.telegram_id, status):
        if query:
            await query.answer(say(update, "not_in_list"), show_alert=True)
        return
    label = say(update, "marked_learned" if status == "learned" else "marked_repeat")
    await query.answer(label)
    try:
        await query.edit_message_reply_markup(reply_markup=lesson_keyboard(item_id, status, ui_of(update)))
    except BadRequest as exc:
        if "not modified" not in str(exc).lower():
            raise


async def _on_send_now(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_id: int) -> None:
    query = update.callback_query
    if query is None or query.message is None:
        return
    await query.answer(say(update, "writing"))
    user = _saved_user(update)
    plan = db.get_plan(plan_id, user.telegram_id)
    if plan is None:
        await query.message.reply_text(say(update, "plan_gone"))
        return
    placeholder = await query.message.reply_text(say(update, "writing"))
    try:
        await send_now(context.bot, plan, user, user_now(user).date().isoformat())
    except Forbidden:
        db.pause_user_plans(user.telegram_id)
        await placeholder.edit_text(say(update, "refused"))
        return
    except llm.LLMError as exc:
        await placeholder.edit_text(exc.user_message)
        return
    except Exception:
        logger.exception("send now failed")
        await placeholder.edit_text(say(update, "no_card"))
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
        await query.message.reply_text(say(update, "summary_need"))
        return
    placeholder = await query.message.reply_text(say(update, "summary_wait"))
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
        text = await llm.summarize_learned(payload, user.translation_language, ui_of(update))
    except llm.LLMError as exc:
        await placeholder.edit_text(exc.user_message)
        return
    except Exception:
        logger.exception("summary failed")
        await placeholder.edit_text(say(update, "summary_fail"))
        return
    await placeholder.edit_text(
        say(update, "summary_title", text=esc(text)),
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
        if data.startswith("ui:"):
            code = data.split(":", 1)[1]
            if code in {"en", "fa"}:
                await apply_ui_language(update, context, code)
            return
        if user.ui_language not in {"en", "fa"}:
            await ask_ui_language(update, context, "home" if user.ready else "onboard")
            return
        if not user.ready and data not in {"home", "w:back", "tz:custom", "tr:custom"} and not data.startswith(("tz:", "tr:", "ui:")):
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
            await query.message.reply_text(say(update, "wrong"))


async def _route(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str, user: User) -> None:
    wizard = context.user_data.get("wizard") or {}
    if data == "home":
        await show_home(update, context)
    elif data == "help":
        lang = ui_of(update)
        await show(update, help_html(lang), home_keyboard(lang))
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
    elif data == "set:ui":
        await ask_ui_language(update, context, "settings")
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
        lang = ui_of(update)
        text = plan_html(plan, user_now(user), lang) + say(update, "delete_ask")
        await show(update, text, confirm_delete(plan_id, lang))
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
        await query.message.reply_text(say(update, "card_gone"))
        return
    lang = ui_of(update)
    await query.message.reply_text(
        lesson_from_item(item, lang=lang),
        parse_mode=ParseMode.HTML,
        reply_markup=lesson_keyboard(item.id, item.status, lang),
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
        _begin_days(wizard)
        await show_step(update, context)
    elif kind == "day":
        if wizard.get("step") != "days":
            await show_step(update, context)
            return
        choice = parts[2] if len(parts) > 2 else ""
        selected = set(wizard.get("weekdays") or [])
        if choice == "all":
            selected = set(range(7))
        elif choice == "week":
            selected = {0, 1, 2, 3, 4}
        elif choice == "end":
            selected = {5, 6}
        elif choice == "done":
            if not selected:
                wizard["need_day"] = True
                await show_step(update, context)
                return
            wizard["weekdays"] = sorted(selected)
            wizard["step"] = "count"
            await show_step(update, context)
            return
        elif choice.isdigit() and int(choice) in range(7):
            day = int(choice)
            if day in selected:
                selected.remove(day)
            else:
                selected.add(day)
        else:
            await show_step(update, context)
            return
        wizard["weekdays"] = sorted(selected)
        await show_step(update, context)
    elif kind == "count":
        if wizard.get("step") != "count":
            await show_step(update, context)
            return
        raw = parts[2] if len(parts) > 2 else ""
        if raw not in {"1", "2", "3"}:
            await show_step(update, context)
            return
        wizard["times_per_day"] = int(raw)
        wizard["slots"] = []
        wizard["slot_index"] = 0
        wizard["step"] = "slot_kind"
        await show_step(update, context)
    elif kind == "slot":
        if wizard.get("step") != "slot_kind":
            await show_step(update, context)
            return
        choice = parts[2] if len(parts) > 2 else ""
        if choice == "exact":
            wizard["step"] = "slot_time"
            await show_step(update, context)
            return
        if choice != "random":
            await show_step(update, context)
            return
        wizard.setdefault("slots", []).append({"kind": "random"})
        await _after_slot(update, context)
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
        user = _saved_user(update)
        if user.ui_language not in {"en", "fa"}:
            await ask_ui_language(update, context, "home" if user.ready else "onboard")
            return
        await message.reply_text(say(update, "use_menu"))
        return
    text = message.text.strip()
    step = wizard.get("step")
    user = _saved_user(update)
    if step == "custom_language":
        if not text or len(text) > 40:
            await message.reply_text(say(update, "name_short"))
            return
        wizard["language"] = text
        wizard["step"] = "level"
        await show_step(update, context)
        return
    if step == "custom_topic":
        if not text or len(text) > 80:
            await message.reply_text(say(update, "topic_short"))
            return
        wizard["topic"] = text
        if wizard.get("action") == "edit":
            db.update_plan(int(wizard["plan_id"]), user.telegram_id, topic=text)
            await show_plan(update, context, int(wizard["plan_id"]))
            return
        _begin_days(wizard)
        await show_step(update, context)
        return
    if step == "custom_timezone":
        zone = resolve_timezone(text)
        if zone is None:
            await message.reply_text(say(update, "tz_unknown"))
            return
        db.set_timezone(user.telegram_id, zone)
        await _after_timezone(update, context)
        return
    if step == "custom_translation":
        if not text or len(text) > 40:
            await message.reply_text(say(update, "name_short"))
            return
        db.set_translation_language(user.telegram_id, text)
        await _after_translation(update, context)
        return
    if step == "slot_time":
        clock = normalize_clock(text)
        if clock is None:
            await message.reply_text(say(update, "time_bad"))
            return
        taken = [slot.get("time") for slot in wizard.get("slots") or [] if slot.get("kind") == "exact"]
        if clock in taken:
            await message.reply_text(say(update, "time_taken"))
            return
        wizard.setdefault("slots", []).append({"kind": "exact", "time": clock})
        await _after_slot(update, context)
        return
    await message.reply_text(say(update, "use_menu"))
