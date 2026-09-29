from __future__ import annotations

import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bot import config
from bot.db import Plan, db
from bot.delivery import send_scheduled
from bot.schedule_logic import effective_schedule, prepare_due

logger = logging.getLogger(__name__)


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
    schedule = effective_schedule(plan)
    names = schedule.get("legacy_slots") or [f"s{index}" for index in range(len(schedule.get("slots") or []))]
    deliveries = {name: db.delivery_info(plan.id, name, today) for name in names}
    updated, due, changed = prepare_due(
        now,
        schedule,
        deliveries,
        grace_minutes=config.GRACE_MINUTES,
        retry_minutes=config.RETRY_MINUTES,
    )
    if changed and plan.schedule_json:
        encoded = json.dumps(updated)
        db.update_plan(plan.id, schedule_json=encoded)
        plan.schedule_json = encoded
    elif changed and plan.schedule_mode == "random" and updated["slots"]:
        nxt = updated["slots"][0].get("next")
        if nxt:
            db.update_plan(plan.id, next_random_at=nxt)
            plan.next_random_at = nxt

    for slot, _scheduled in due:
        await send_scheduled(bot, plan, user, slot, today, now)


async def tick(bot) -> None:
    for plan in db.list_active_plans():
        try:
            await consider_plan(bot, plan)
        except Exception:
            logger.exception("Scheduler failed for plan %s", plan.id)
