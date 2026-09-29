from __future__ import annotations

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
