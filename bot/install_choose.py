"""Ask which Groq chat model to use. Run this in the foreground, not in $(...)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from bot.groq_http import GroqHTTPError, choose_chat_model


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Usage: python -m bot.install_choose RESULT_FILE")
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not token or not api_key:
        sys.exit("The Telegram token and Groq API key are required.")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/getMe",
        headers={"User-Agent": "Wortuhr/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        sys.exit(f"Telegram rejected the bot token ({exc.code}).")
    except Exception as exc:
        sys.exit(f"Could not reach Telegram: {exc}")
    if not payload.get("ok"):
        sys.exit("Telegram rejected the bot token.")
    username = str(payload.get("result", {}).get("username", ""))
    try:
        model = choose_chat_model(api_key, os.environ.get("SAVED_GROQ_MODEL", ""))
    except GroqHTTPError as exc:
        sys.exit(exc.message)
    Path(sys.argv[1]).write_text(f"{username}\n{model}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
