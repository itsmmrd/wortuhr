"""Talk to Groq through curl.

Groq sits behind Cloudflare, which answers Python's HTTP client with 403
even when the API key is valid. curl is accepted.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TextIO


class GroqHTTPError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def error_message(status: int, body: str) -> str:
    detail = _json_message(body)
    if status == 401:
        return "Groq rejected the API key."
    if status == 403 and detail:
        return f"Groq refused this key: {detail}"
    if status == 403:
        return (
            "Groq refused the request (403). "
            "Check the API key, or pick another model in the Groq console."
        )
    if status == 404 and detail:
        return f"Groq could not find that model: {detail}"
    if status == 429:
        return "Groq is rate-limiting requests. Try again shortly."
    if detail:
        return f"Groq could not respond: {detail}"
    return f"Groq check failed ({status})."


_NON_CHAT = ("whisper", "orpheus", "tts", "prompt-guard", "playai", "llama-guard", "safeguard")


def chat_model_ids(payload: dict) -> list[str]:
    rows = payload.get("data")
    if not isinstance(rows, list):
        return []
    found: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("active") is False:
            continue
        model_id = str(row.get("id") or "").strip()
        folded = model_id.casefold()
        if not model_id or any(part in folded for part in _NON_CHAT):
            continue
        found.append(model_id)
    return sorted(set(found), key=str.casefold)


def preferred_model_index(models: list[str], saved: str = "") -> int:
    if saved and saved in models:
        return models.index(saved)
    folded = [model_id.casefold() for model_id in models]
    for hint in ("70b", "versatile", "8b-instant", "gpt-oss-120b", "gpt-oss-20b"):
        for index, model_id in enumerate(folded):
            if hint in model_id:
                return index
    return 0


def list_chat_models(api_key: str, base_url: str = "https://api.groq.com/openai/v1") -> list[str]:
    status, body = request(f"{base_url.rstrip('/')}/models", api_key, method="GET", timeout=30)
    if status == 401:
        raise GroqHTTPError("Groq rejected the API key.")
    if status != 200:
        raise GroqHTTPError(error_message(status, body))
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise GroqHTTPError("Groq returned an unreadable model list.") from exc
    if not isinstance(payload, dict):
        raise GroqHTTPError("Groq returned an unreadable model list.")
    models = chat_model_ids(payload)
    if not models:
        raise GroqHTTPError("Groq returned no chat models for this key.")
    return models


def read_model_choice(
    models: list[str],
    saved: str = "",
    reader: TextIO | None = None,
    writer: TextIO | None = None,
) -> str:
    if not models:
        raise GroqHTTPError("Groq returned no chat models for this key.")
    source = reader or sys.stdin
    output = writer or sys.stdout
    default_index = preferred_model_index(models, saved.strip())
    output.write("\nGroq accepted the API key. Choose a chat model:\n\n")
    for number, model_id in enumerate(models, start=1):
        note = ""
        if saved and model_id == saved:
            note = "  (saved)"
        elif number == default_index + 1:
            note = "  (suggested)"
        output.write(f"  {number:2}. {model_id}{note}\n")
    while True:
        output.write(f"\nModel number [{default_index + 1}]: ")
        output.flush()
        answer = source.readline()
        if not answer:
            raise GroqHTTPError("No model selected.")
        answer = answer.strip()
        if not answer:
            return models[default_index]
        if answer.isdigit() and 1 <= int(answer) <= len(models):
            return models[int(answer) - 1]
        output.write("Enter a number from the list.\n")


def choose_chat_model(api_key: str, saved: str = "", base_url: str = "https://api.groq.com/openai/v1") -> str:
    models = list_chat_models(api_key, base_url)
    while True:
        chosen = read_model_choice(models, saved)
        problem = verify_key(api_key, chosen, base_url)
        if problem is None:
            print(f"Using {chosen}", flush=True)
            return chosen
        print(f"\n{problem}\nPick another model.", flush=True)


def post_json(url: str, api_key: str, payload: dict, *, timeout: int = 50) -> tuple[int, str]:
    return request(url, api_key, method="POST", payload=payload, timeout=timeout)


def request(
    url: str,
    api_key: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    timeout: int = 50,
) -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        body_path = directory / "body.json"
        config_path = directory / "curl.cfg"
        output_path = directory / "out"
        lines = [
            "silent",
            "show-error",
            f"url = {_quote(url)}",
            f"header = {_quote('Authorization: Bearer ' + api_key)}",
            'header = "Accept: application/json"',
            'header = "User-Agent: Wortuhr/1.0"',
            f"output = {_quote(str(output_path))}",
            'connect-timeout = "20"',
            f"max-time = {_quote(str(timeout))}",
            'write-out = "%{http_code}"',
        ]
        if method != "GET":
            lines.insert(2, f"request = {_quote(method)}")
        if payload is not None:
            body_path.write_text(json.dumps(payload), encoding="utf-8")
            lines.append('header = "Content-Type: application/json"')
            lines.append(f"data = {_quote('@' + str(body_path))}")
        config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        config_path.chmod(0o600)
        try:
            completed = subprocess.run(
                ["curl", "--config", str(config_path)],
                capture_output=True,
                text=True,
                timeout=timeout + 5,
                check=False,
            )
        except FileNotFoundError as exc:
            raise GroqHTTPError("curl is required to reach Groq. Install it and run the installer again.") from exc
        except subprocess.TimeoutExpired as exc:
            raise GroqHTTPError("Groq did not answer in time.") from exc
        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            if api_key and api_key in stderr:
                stderr = "curl failed"
            raise GroqHTTPError(stderr or "Could not reach Groq.")
        raw_status = (completed.stdout or "").strip()
        try:
            status = int(raw_status)
        except ValueError as exc:
            raise GroqHTTPError("Groq returned an unreadable response.") from exc
        text = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
        return status, text


def verify_key(api_key: str, model: str, base_url: str = "https://api.groq.com/openai/v1") -> str | None:
    """Return an error message, or None when a short completion succeeds."""
    try:
        status, body = post_json(
            f"{base_url.rstrip('/')}/chat/completions",
            api_key,
            {
                "model": model,
                "messages": [{"role": "user", "content": "Reply with the word ok."}],
                "max_tokens": 8,
                "temperature": 0,
            },
            timeout=30,
        )
    except GroqHTTPError as exc:
        return exc.message
    if status == 200:
        return None
    return error_message(status, body)


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _json_message(body: str) -> str:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict):
        return ""
    error = payload.get("error")
    if isinstance(error, dict):
        message = str(error.get("message") or "").strip()
        return message[:300]
    if isinstance(error, str):
        return error.strip()[:300]
    return ""
