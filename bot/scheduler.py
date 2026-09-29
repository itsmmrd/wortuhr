from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bot import config
from bot.db import Plan, db
from bot.delivery import send_scheduled
from bot.schedule_logic import (
    roll_forward_random,
    scheduled_today,
    slot_needs_send,
)

logger = logging.getLogger(__name__)


def _parse_dt(value: str | None, tzinfo) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tzinfo)
    return parsed


async def consider_plan(bot, plan: Plan) -> None:
    user = db.get_user(plan.user_id)
    if user is None or not user.ready:
        return
    try:
        zone = ZoneInfo(user.timezone)
    except ZoneInfoNotFoundError:
        logger.error("User %s has an unknown timezone %s", user.telegram_id, user.timezone)
        return
    now = datetime.now(zone)
    today = now.date().isoformat()

    if plan.schedule_mode == "random" and plan.window_start and plan.window_end:
        status, _attempts = db.delivery_info(plan.id, "random", today)
        current = _parse_dt(plan.next_random_at, zone)
        replacement = roll_forward_random(
            now,
            current,
            plan.window_start,
            plan.window_end,
            status == "sent",
            retry_minutes=config.RETRY_MINUTES,
        )
        if replacement is not None:
            iso = replacement.isoformat(timespec="minutes")
            db.update_plan(plan.id, next_random_at=iso)
            plan.next_random_at = iso

    slots: list[tuple[str, datetime]] = []
    if plan.schedule_mode == "exact" and plan.time_1:
        slots.append(("time_1", scheduled_today(now, plan.time_1)))
    elif plan.schedule_mode == "twice":
        if plan.time_1:
            slots.append(("time_1", scheduled_today(now, plan.time_1)))
        if plan.time_2:
            slots.append(("time_2", scheduled_today(now, plan.time_2)))
    elif plan.schedule_mode == "random" and plan.next_random_at:
        scheduled = _parse_dt(plan.next_random_at, zone)
        if scheduled is not None:
            slots.append(("random", scheduled))

    for slot, scheduled in slots:
        if scheduled.date() != now.date():
            continue
        status, attempts = db.delivery_info(plan.id, slot, today)
        if not slot_needs_send(
            now,
            scheduled,
            sent=status == "sent",
            attempts=attempts,
            grace_minutes=config.GRACE_MINUTES,
            retry_minutes=config.RETRY_MINUTES,
        ):
            continue
        await send_scheduled(bot, plan, user, slot, today, now)


async def tick(bot) -> None:
    for plan in db.list_active_plans():
        try:
            await consider_plan(bot, plan)
        except Exception:
            logger.exception("Scheduler failed for plan %s", plan.id)
