from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta

from telegram import LinkPreviewOptions
from telegram.constants import ParseMode
from telegram.error import Forbidden

from bot import llm
from bot.db import Database, Plan, User, db
from bot.keyboards import lesson as lesson_keyboard
from bot.render import lesson_html, schedule_label
from bot.schedule_logic import choose_on_date

logger = logging.getLogger(__name__)
_locks: dict[int, asyncio.Lock] = {}
_PREVIEW_OFF = LinkPreviewOptions(is_disabled=True)


def lock_for(user_id: int) -> asyncio.Lock:
    lock = _locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _locks[user_id] = lock
    return lock


def _payload(card: dict, content_type: str) -> dict:
    if content_type == "word":
        return {"note": card.get("note", ""), "sentences": card["sentences"]}
    return {"note": card.get("note", ""), "contexts": card["contexts"]}


async def create_item(
    database: Database,
    *,
    user: User,
    plan: Plan,
    local_day: str,
) -> tuple[int, str]:
    language = plan.language
    level = plan.level
    topic = plan.topic
    content_type = plan.content_type
    async with lock_for(user.telegram_id):
        avoid = database.recent_terms(user.telegram_id, language, content_type)
        card = await llm.generate_card(
            content_type=content_type,
            language=language,
            level=level,
            topic=topic,
            translation_language=user.translation_language,
            avoid=avoid,
        )
        payload = _payload(card, content_type)
        item = database.add_item(
            user_id=user.telegram_id,
            plan_id=plan.id,
            content_type=content_type,
            language=language,
            level=level,
            topic=topic,
            term=card["term"],
            translation=card["translation"],
            payload_json=json.dumps(payload, ensure_ascii=False),
            local_day=local_day,
        )
    footer = f"Plan: {language} · {level} · {topic} · {schedule_label(plan)}"
    text = lesson_html(
        language=language,
        level=level,
        topic=topic,
        content_type=content_type,
        term=card["term"],
        translation=card["translation"],
        payload=payload,
        footer=footer,
    )
    return item.id, text


async def send_card(bot, chat_id: int, item_id: int, text: str) -> None:
    await bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=lesson_keyboard(item_id),
        link_preview_options=_PREVIEW_OFF,
    )


async def send_now(bot, plan: Plan, user: User, local_day: str) -> None:
    item_id, text = await create_item(db, user=user, plan=plan, local_day=local_day)
    try:
        await send_card(bot, user.telegram_id, item_id, text)
    except Exception:
        db.delete_item(item_id)
        raise


def _schedule_next_random(plan: Plan, now: datetime) -> None:
    if not plan.window_start or not plan.window_end:
        return
    tomorrow = now.date() + timedelta(days=1)
    nxt = choose_on_date(tomorrow, now.tzinfo, plan.window_start, plan.window_end, random.Random())
    db.update_plan(plan.id, next_random_at=nxt.isoformat(timespec="minutes"))


async def send_scheduled(bot, plan: Plan, user: User, slot: str, today: str, now: datetime) -> None:
    attempt = db.claim_delivery(plan.id, slot, today)
    if attempt is None:
        return
    item_id: int | None = None
    sent_to_user = False
    logger.info("Sending %s card for plan %s (%s)", plan.content_type, plan.id, slot)
    try:
        item_id, text = await create_item(db, user=user, plan=plan, local_day=today)
        await send_card(bot, user.telegram_id, item_id, text)
        sent_to_user = True
        db.finish_delivery(plan.id, slot, today, item_id)
        if plan.schedule_mode == "random":
            _schedule_next_random(plan, now)
    except Forbidden:
        logger.info("User %s blocked the bot. Pausing plans.", user.telegram_id)
        if sent_to_user:
            db.finish_delivery(plan.id, slot, today, item_id)
            return
        if item_id is not None:
            db.delete_item(item_id)
        db.pause_user_plans(user.telegram_id)
        db.finish_delivery(plan.id, slot, today, None)
    except Exception as exc:
        if sent_to_user:
            logger.exception("Card was sent but follow-up bookkeeping failed for plan %s", plan.id)
            try:
                db.finish_delivery(plan.id, slot, today, item_id)
            except Exception:
                logger.exception("Could not mark delivery sent for plan %s", plan.id)
            return
        logger.exception("Scheduled send failed for plan %s", plan.id)
        if item_id is not None:
            db.delete_item(item_id)
        db.release_delivery(plan.id, slot, today)
        if attempt in {1, 3}:
            kind = "idiom" if plan.content_type == "idiom" else "word"
            if attempt == 3:
                notice = (
                    f"I could not prepare today's {plan.language} {kind}. "
                    "The next one will follow your plan."
                )
            else:
                notice = (
                    f"I could not prepare your {plan.language} {kind} just now. "
                    "I will try again shortly."
                )
            user_message = getattr(exc, "user_message", None)
            if attempt == 1 and user_message and "API key" in user_message:
                notice = user_message
            try:
                await bot.send_message(chat_id=user.telegram_id, text=notice)
            except Exception:
                logger.info("Could not notify user %s about a failed card", user.telegram_id)
