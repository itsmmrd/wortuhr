"""Talk to Groq through curl.

Groq sits behind Cloudflare, which answers Python's HTTP client with 403
even when the API key is valid. curl is accepted.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


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


def post_json(url: str, api_key: str, payload: dict, *, timeout: int = 50) -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        body_path = directory / "body.json"
        config_path = directory / "curl.cfg"
        output_path = directory / "out"
        body_path.write_text(json.dumps(payload), encoding="utf-8")
        config_path.write_text(
            "\n".join(
                [
                    "silent",
                    "show-error",
                    'request = "POST"',
                    f"url = {_quote(url)}",
                    f"header = {_quote('Authorization: Bearer ' + api_key)}",
                    'header = "Content-Type: application/json"',
                    'header = "User-Agent: Wortuhr/1.0"',
                    f"data = {_quote('@' + str(body_path))}",
                    f"output = {_quote(str(output_path))}",
                    'connect-timeout = "20"',
                    f"max-time = {_quote(str(timeout))}",
                    'write-out = "%{http_code}"',
                    "",
                ]
            ),
            encoding="utf-8",
        )
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
