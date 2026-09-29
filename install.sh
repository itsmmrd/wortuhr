#!/usr/bin/env bash
# Install Wortuhr on Ubuntu and ask for the Groq API key.
set -euo pipefail

APP_DIR="/opt/wortuhr"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this installer as root: sudo ./install.sh"
  exit 1
fi

if [[ ! -f /etc/os-release ]]; then
  echo "This installer supports Ubuntu."
  exit 1
fi
# shellcheck disable=SC1091
. /etc/os-release
if [[ "${ID:-}" != "ubuntu" && "${ID:-}" != "debian" ]]; then
  echo "This installer supports Ubuntu."
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-venv python3-pip ca-certificates tzdata curl rsync

python3 - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10 or newer is required.")
PY

mkdir -p "$APP_DIR"
if [[ "$SRC" != "$APP_DIR" ]]; then
  rsync -a --delete \
    --exclude .git \
    --exclude .venv \
    --exclude data \
    --exclude .env \
    --exclude __pycache__ \
    "$SRC"/ "$APP_DIR"/
fi

ENV_FILE="$APP_DIR/.env"
existing_token=""
existing_key=""
existing_model=""
existing_open="0"
if [[ -f "$ENV_FILE" ]]; then
  existing_token="$(grep -E '^TELEGRAM_BOT_TOKEN=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
  existing_key="$(grep -E '^GROQ_API_KEY=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
  existing_model="$(grep -E '^GROQ_MODEL=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
  existing_open="$(grep -E '^OPEN_SIGNUP=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
  existing_open="${existing_open:-0}"
fi

cat <<'EOF'

Wortuhr needs two keys. They stay in /opt/wortuhr/.env on this server
and are not written into git.

  1. Telegram bot token from @BotFather (send /newbot)
  2. Groq API key from https://console.groq.com/keys
     A free Groq key is enough for a personal study plan.

EOF

if [[ -n "$existing_token" ]]; then
  read -rp "Telegram bot token [press Enter to keep the saved token]: " TELEGRAM_BOT_TOKEN
  TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-$existing_token}"
else
  read -rp "Telegram bot token: " TELEGRAM_BOT_TOKEN
fi
if [[ -z "${TELEGRAM_BOT_TOKEN}" ]]; then
  echo "The Telegram bot token is required."
  exit 1
fi
if [[ ! "$TELEGRAM_BOT_TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]+$ ]]; then
  echo "That does not look like a Telegram bot token from BotFather."
  exit 1
fi

if [[ -n "$existing_key" ]]; then
  read -rsp "Groq API key [press Enter to keep the saved key]: " GROQ_API_KEY
  echo
  GROQ_API_KEY="${GROQ_API_KEY:-$existing_key}"
else
  read -rsp "Groq API key: " GROQ_API_KEY
  echo
fi
if [[ -z "${GROQ_API_KEY}" ]]; then
  echo "The Groq API key is required."
  exit 1
fi
if [[ "$GROQ_API_KEY" == *$'\n'* || "$GROQ_API_KEY" == *'"'* ]]; then
  echo "The Groq API key contains a character this installer cannot store safely."
  exit 1
fi

export TELEGRAM_BOT_TOKEN GROQ_API_KEY SAVED_GROQ_MODEL="$existing_model"

echo
echo "Checking the Telegram token and the Groq API key..."
CHECK_RESULT="$(python3 - <<'PY'
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, "/opt/wortuhr")
from bot.groq_http import GroqHTTPError, choose_chat_model

token = os.environ["TELEGRAM_BOT_TOKEN"]
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

try:
    model = choose_chat_model(os.environ["GROQ_API_KEY"], os.environ.get("SAVED_GROQ_MODEL", ""))
except GroqHTTPError as exc:
    sys.exit(exc.message)

print(payload.get("result", {}).get("username", ""))
print(model)
PY
)"
BOT_USERNAME="$(printf '%s\n' "$CHECK_RESULT" | sed -n '1p')"
GROQ_MODEL="$(printf '%s\n' "$CHECK_RESULT" | sed -n '2p')"
if [[ -z "$GROQ_MODEL" || "$GROQ_MODEL" == *" "* ]]; then
  echo "No Groq model was selected."
  exit 1
fi

echo
echo "Allow anyone who finds the bot to spend your Groq key?"
echo "Leave this as no if the bot is only for you. The first /start becomes the owner."
if [[ "$existing_open" == "1" ]]; then
  read -rp "Open signup? Currently yes [y/N]: " OPEN_ANSWER
else
  read -rp "Open signup? [y/N]: " OPEN_ANSWER
fi
case "${OPEN_ANSWER:-}" in
  y|Y|yes|YES) OPEN_SIGNUP="1" ;;
  *) OPEN_SIGNUP="0" ;;
esac

export GROQ_MODEL OPEN_SIGNUP

echo "Telegram bot @${BOT_USERNAME} accepted the token."
echo "Groq model: ${GROQ_MODEL}"

umask 077
python3 - <<'PY'
import os
from pathlib import Path

path = Path("/opt/wortuhr/.env")
lines = [
    f"TELEGRAM_BOT_TOKEN={os.environ['TELEGRAM_BOT_TOKEN']}",
    f"GROQ_API_KEY={os.environ['GROQ_API_KEY']}",
    f"GROQ_MODEL={os.environ['GROQ_MODEL']}",
    f"OPEN_SIGNUP={os.environ['OPEN_SIGNUP']}",
    "",
]
path.write_text("\n".join(lines), encoding="utf-8")
os.chmod(path, 0o600)
PY

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

if ! id -u wortuhr >/dev/null 2>&1; then
  login_shell="/usr/sbin/nologin"
  if [[ ! -x "$login_shell" ]]; then
    login_shell="/bin/false"
  fi
  useradd --system --home-dir "$APP_DIR" --shell "$login_shell" wortuhr
fi

mkdir -p "$APP_DIR/data"
chown -R wortuhr:wortuhr "$APP_DIR"
chmod 600 "$APP_DIR/.env"

cat > /etc/systemd/system/wortuhr.service <<EOF
[Unit]
Description=Wortuhr Telegram language bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=wortuhr
Group=wortuhr
WorkingDirectory=${APP_DIR}
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/.venv/bin/python -m bot
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable wortuhr
systemctl restart wortuhr
sleep 2

if ! systemctl is-active --quiet wortuhr; then
  echo "Wortuhr did not stay running. Recent logs:"
  journalctl -u wortuhr -n 40 --no-pager || true
  exit 1
fi

cat <<EOF

Wortuhr is installed and running.
Open Telegram and send /start to @${BOT_USERNAME}.

Logs:    journalctl -u wortuhr -f
Restart: systemctl restart wortuhr
Update:  git pull && sudo ./install.sh

Your plans and learned cards are stored in ${APP_DIR}/data/wortuhr.db
EOF
