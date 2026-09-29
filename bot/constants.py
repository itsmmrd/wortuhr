from __future__ import annotations

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

LANGUAGES: list[tuple[str, str, str]] = [
    ("German", "de", "🇩🇪"),
    ("English", "en", "🇬🇧"),
    ("Spanish", "es", "🇪🇸"),
    ("French", "fr", "🇫🇷"),
    ("Italian", "it", "🇮🇹"),
    ("Portuguese", "pt", "🇵🇹"),
    ("Dutch", "nl", "🇳🇱"),
    ("Polish", "pl", "🇵🇱"),
    ("Turkish", "tr", "🇹🇷"),
    ("Russian", "ru", "🇷🇺"),
    ("Persian", "fa", "🇮🇷"),
    ("Arabic", "ar", "🇸🇦"),
    ("Chinese", "zh", "🇨🇳"),
    ("Japanese", "ja", "🇯🇵"),
]

TOPICS: list[tuple[str, str]] = [
    ("Everyday life", "everyday"),
    ("Travel", "travel"),
    ("Food and cooking", "food"),
    ("Work and jobs", "work"),
    ("Technical", "technical"),
    ("School and study", "study"),
    ("Health", "health"),
    ("Home and family", "home"),
]

TRANSLATION_LANGUAGES = [
    "English",
    "German",
    "Spanish",
    "French",
    "Italian",
    "Portuguese",
    "Dutch",
    "Polish",
    "Turkish",
    "Russian",
    "Persian",
    "Arabic",
    "Chinese",
    "Japanese",
]

TIMEZONES: list[tuple[str, str]] = [
    ("Berlin", "Europe/Berlin"),
    ("Vienna", "Europe/Vienna"),
    ("Zurich", "Europe/Zurich"),
    ("Paris", "Europe/Paris"),
    ("Amsterdam", "Europe/Amsterdam"),
    ("London", "Europe/London"),
    ("Madrid", "Europe/Madrid"),
    ("Istanbul", "Europe/Istanbul"),
    ("Tehran", "Asia/Tehran"),
    ("Dubai", "Asia/Dubai"),
    ("New York", "America/New_York"),
    ("Los Angeles", "America/Los_Angeles"),
    ("UTC", "UTC"),
]

PAGE_SIZE = 5

LEVEL_GUIDE = {
    "A1": "very common, concrete words and sentences of about 4 to 8 words",
    "A2": "everyday situations and sentences under 12 words",
    "B1": "clear connected everyday language",
    "B2": "natural phrasing with some nuance",
    "C1": "precise, idiomatic language that stays clear",
    "C2": "native-like language, including register when it matters",
}


def language_name(code: str) -> str | None:
    for name, short, _flag in LANGUAGES:
        if short == code:
            return name
    return None


def topic_name(code: str) -> str | None:
    for name, short in TOPICS:
        if short == code:
            return name
    return None


def flag_for(language: str) -> str:
    for name, _short, flag in LANGUAGES:
        if name.casefold() == language.casefold():
            return flag
    return "🌐"
