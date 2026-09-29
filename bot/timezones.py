from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bot.constants import TIMEZONES

_ALIASES = {
    "berlin": "Europe/Berlin",
    "germany": "Europe/Berlin",
    "vienna": "Europe/Vienna",
    "zurich": "Europe/Zurich",
    "paris": "Europe/Paris",
    "amsterdam": "Europe/Amsterdam",
    "london": "Europe/London",
    "uk": "Europe/London",
    "madrid": "Europe/Madrid",
    "istanbul": "Europe/Istanbul",
    "tehran": "Asia/Tehran",
    "iran": "Asia/Tehran",
    "dubai": "Asia/Dubai",
    "new york": "America/New_York",
    "newyork": "America/New_York",
    "los angeles": "America/Los_Angeles",
    "la": "America/Los_Angeles",
    "utc": "UTC",
    "gmt": "UTC",
}


def resolve_timezone(text: str) -> str | None:
    raw = text.strip()
    if not raw:
        return None
    known = {zone for _label, zone in TIMEZONES}
    if raw in known:
        return raw
    key = raw.casefold()
    compact = key.replace("_", " ")
    if key in _ALIASES:
        return _ALIASES[key]
    if compact in _ALIASES:
        return _ALIASES[compact]
    for label, zone in TIMEZONES:
        if key == label.casefold() or key == zone.casefold():
            return zone
    try:
        ZoneInfo(raw)
    except ZoneInfoNotFoundError:
        return None
    return raw
