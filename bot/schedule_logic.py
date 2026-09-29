from __future__ import annotations

import json
import random
import re
from datetime import datetime, time, timedelta


def normalize_clock(text: str) -> str | None:
    raw = text.strip().lower().replace(".", ":").replace(" ", "")
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", raw)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def clock_span_minutes(start: str, end: str) -> int:
    start_t = parse_hhmm(start)
    end_t = parse_hhmm(end)
    return (end_t.hour * 60 + end_t.minute) - (start_t.hour * 60 + start_t.minute)


def slot_needs_send(
    now: datetime,
    scheduled: datetime | None,
    *,
    sent: bool,
    attempts: int,
    grace_minutes: int = 20,
    retry_minutes: int = 120,
) -> bool:
    if sent or scheduled is None or attempts >= 3:
        return False
    late = (now - scheduled).total_seconds()
    if late < 0:
        return False
    limit = grace_minutes if attempts == 0 else retry_minutes
    return late <= limit * 60


def scheduled_today(now: datetime, hhmm: str) -> datetime:
    clock = parse_hhmm(hhmm)
    return now.replace(hour=clock.hour, minute=clock.minute, second=0, microsecond=0)


def choose_on_date(
    day,
    tzinfo,
    window_start: str,
    window_end: str,
    rng: random.Random,
) -> datetime:
    start = datetime.combine(day, parse_hhmm(window_start), tzinfo=tzinfo)
    end = datetime.combine(day, parse_hhmm(window_end), tzinfo=tzinfo)
    span = max(int((end - start).total_seconds() // 60), 0)
    return start + timedelta(minutes=rng.randint(0, span))


def choose_random_datetime(
    now: datetime,
    window_start: str,
    window_end: str,
    rng: random.Random | None = None,
) -> datetime:
    rng = rng or random.Random()
    start = datetime.combine(now.date(), parse_hhmm(window_start), tzinfo=now.tzinfo)
    end = datetime.combine(now.date(), parse_hhmm(window_end), tzinfo=now.tzinfo)
    earliest = max(now + timedelta(minutes=1), start)
    if earliest < end:
        span = int((end - earliest).total_seconds() // 60)
        return earliest + timedelta(minutes=rng.randint(0, max(span, 0)))
    tomorrow = now.date() + timedelta(days=1)
    return choose_on_date(tomorrow, now.tzinfo, window_start, window_end, rng)


def roll_forward_random(
    now: datetime,
    next_dt: datetime | None,
    window_start: str,
    window_end: str,
    sent_today: bool,
    rng: random.Random | None = None,
    retry_minutes: int = 120,
) -> datetime | None:
    """Return a replacement random time, or None when the stored time can stay."""
    rng = rng or random.Random()
    tomorrow = now.date() + timedelta(days=1)
    if next_dt is None:
        return choose_random_datetime(now, window_start, window_end, rng)
    if sent_today and next_dt.date() <= now.date():
        return choose_on_date(tomorrow, now.tzinfo, window_start, window_end, rng)
    if now > next_dt + timedelta(minutes=retry_minutes):
        return choose_on_date(tomorrow, now.tzinfo, window_start, window_end, rng)
    return None


WEEKDAYS = list(range(7))
DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
RANDOM_WINDOWS = {
    1: [("08:00", "21:00")],
    2: [("08:00", "12:30"), ("13:30", "21:00")],
    3: [("08:00", "11:30"), ("12:00", "16:00"), ("16:30", "21:00")],
}


def day_phrase(weekdays: list[int]) -> str:
    chosen = sorted(set(weekdays))
    if chosen == WEEKDAYS:
        return "Every day"
    if chosen == [0, 1, 2, 3, 4]:
        return "Weekdays"
    if chosen == [5, 6]:
        return "Weekend"
    return ", ".join(DAY_LABELS[day] for day in chosen)


def schedule_phrase(schedule: dict) -> str:
    slots = schedule.get("slots") or []
    parts = []
    for slot in slots:
        if slot.get("kind") == "random":
            parts.append("random")
        else:
            parts.append(str(slot.get("time") or ""))
    times = ", ".join(part for part in parts if part)
    count = len(slots)
    lesson = "1 lesson a day" if count == 1 else f"{count} lessons a day"
    return f"{day_phrase(schedule.get('weekdays') or [])} · {lesson} ({times})"


def short_when(schedule: dict) -> str:
    days = day_phrase(schedule.get("weekdays") or [])
    count = len(schedule.get("slots") or [])
    if days == "Every day":
        return f"{count}× daily"
    return f"{days} · {count}×"


def effective_schedule(plan) -> dict:
    raw = getattr(plan, "schedule_json", None)
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict) and data.get("weekdays") and data.get("slots"):
            return data
    mode = getattr(plan, "schedule_mode", "exact")
    if mode == "twice":
        slots = [
            {"kind": "exact", "time": plan.time_1},
            {"kind": "exact", "time": plan.time_2},
        ]
        names = ["time_1", "time_2"]
    elif mode == "random":
        slots = [
            {
                "kind": "random",
                "start": plan.window_start,
                "end": plan.window_end,
                "next": plan.next_random_at,
            }
        ]
        names = ["random"]
    else:
        slots = [{"kind": "exact", "time": plan.time_1 or "08:00"}]
        names = ["time_1"]
    return {"weekdays": WEEKDAYS.copy(), "slots": slots, "legacy_slots": names}


def random_window(index: int, count: int) -> tuple[str, str]:
    windows = RANDOM_WINDOWS[max(1, min(count, 3))]
    return windows[min(index, len(windows) - 1)]


def finalize_schedule(
    now: datetime,
    weekdays: list[int],
    slots: list[dict],
    rng: random.Random | None = None,
) -> dict:
    rng = rng or random.Random()
    chosen = sorted(set(weekdays))
    prepared = [dict(slot) for slot in slots]
    random_indexes = [index for index, slot in enumerate(prepared) if slot.get("kind") == "random"]
    for position, index in enumerate(random_indexes):
        start, end = random_window(position, len(random_indexes))
        prepared[index]["start"] = start
        prepared[index]["end"] = end
        prepared[index]["next"] = first_random(now, start, end, chosen, rng).isoformat(timespec="minutes")
    return {"weekdays": chosen, "slots": prepared}


def first_random(
    now: datetime,
    window_start: str,
    window_end: str,
    weekdays: list[int],
    rng: random.Random | None = None,
    *,
    after_day=None,
) -> datetime:
    rng = rng or random.Random()
    allowed = set(weekdays)
    if after_day is None and now.weekday() in allowed:
        picked = choose_random_datetime(now, window_start, window_end, rng)
        if picked.date() == now.date():
            return picked
    day = now.date() + timedelta(days=1) if after_day is None else after_day + timedelta(days=1)
    for _ in range(8):
        if day.weekday() in allowed:
            return choose_on_date(day, now.tzinfo, window_start, window_end, rng)
        day += timedelta(days=1)
    return choose_on_date(day, now.tzinfo, window_start, window_end, rng)


def prepare_due(
    now: datetime,
    schedule: dict,
    deliveries: dict[str, tuple[str | None, int]],
    *,
    grace_minutes: int = 20,
    retry_minutes: int = 120,
    rng: random.Random | None = None,
) -> tuple[dict, list[tuple[str, datetime]], bool]:
    rng = rng or random.Random()
    updated = {
        "weekdays": list(schedule.get("weekdays") or []),
        "slots": [dict(slot) for slot in schedule.get("slots") or []],
    }
    allowed = set(updated["weekdays"])
    names = schedule.get("legacy_slots") or []
    changed = False
    due: list[tuple[str, datetime]] = []
    for index, slot in enumerate(updated["slots"]):
        name = names[index] if index < len(names) else f"s{index}"
        status, attempts = deliveries.get(name, (None, 0))
        sent = status == "sent"
        if slot.get("kind") == "random" and slot.get("start") and slot.get("end"):
            current = _parse_stored(slot.get("next"), now.tzinfo)
            replace = current is None or current.weekday() not in allowed
            if sent and current is not None and current.date() <= now.date():
                replace = True
            if current is not None and now > current + timedelta(minutes=retry_minutes):
                replace = True
            if replace:
                after = now.date() if sent else None
                slot["next"] = first_random(
                    now,
                    slot["start"],
                    slot["end"],
                    updated["weekdays"],
                    rng,
                    after_day=after,
                ).isoformat(timespec="minutes")
                changed = True
                current = _parse_stored(slot.get("next"), now.tzinfo)
            if now.weekday() in allowed and current is not None and current.date() == now.date():
                if slot_needs_send(
                    now,
                    current,
                    sent=sent,
                    attempts=attempts,
                    grace_minutes=grace_minutes,
                    retry_minutes=retry_minutes,
                ):
                    due.append((name, current))
        elif slot.get("time") and now.weekday() in allowed:
            scheduled = scheduled_today(now, slot["time"])
            if slot_needs_send(
                now,
                scheduled,
                sent=sent,
                attempts=attempts,
                grace_minutes=grace_minutes,
                retry_minutes=retry_minutes,
            ):
                due.append((name, scheduled))
    return updated, due, changed


def _parse_stored(value: str | None, tzinfo) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=tzinfo)
    return parsed
