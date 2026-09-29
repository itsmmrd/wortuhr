# Wortuhr

Words and idioms, on a clock you set.

Wortuhr is a Telegram bot for German, English, and any other language you choose. [Groq](https://console.groq.com/) writes each card. You choose the level, the topic, and when it arrives. The bot remembers what it sent, and you mark each card as learned or ready to repeat.

## What you can set

- Several plans at once
- Language: German, English, and others, or a language you type
- Level: A1, A2, B1, B2, C1, or C2
- Words or idioms
- A topic such as everyday life, work, a technical field, or a job you type yourself
- A schedule: one exact time, twice a day, or one random time inside a window you choose
- Edit, pause, or delete a plan
- The timezone and the language used for translations

A word card has the word, a translation, and 3 short practical sentences with translations. An idiom card has the idiom, its meaning, and 3 situations where you can use it, each with an example and a translation.

After a card arrives, tap **I learned this** or **Repeat again**. Progress shows a bar, the last 7 days, lists of learned words and idioms, and a short summary.

## Create the keys

1. In Telegram, open [@BotFather](https://t.me/BotFather), send `/newbot`, and copy the token.
2. Create a free API key at [console.groq.com/keys](https://console.groq.com/keys).

## Install on Ubuntu

```bash
git clone https://github.com/OWNER/wortuhr.git
cd wortuhr
sudo ./install.sh
```

The installer asks for the Telegram token and the Groq API key, checks both, and runs the bot as a systemd service from `/opt/wortuhr`.

Leave **Open signup** as no if the bot is only for you. The first person who sends `/start` becomes the owner. Other accounts are refused, so they cannot spend your Groq key.

On a later run, press Enter to keep the saved keys. The database of plans and cards is kept.

## Use it in Telegram

Send `/start` and follow the buttons.

- `/new` — create a plan
- `/plans` — edit the level, topic, or schedule, pause, delete, or send one card now
- `/progress` — bars, learned lists, and a summary
- `/review` — cards you marked to repeat
- `/settings` — timezone and translation language
- `/cancel` — leave the current step

Times use the timezone you pick in the bot.

## On the server

```bash
systemctl status wortuhr
journalctl -u wortuhr -f
sudo systemctl restart wortuhr
```

Update the code:

```bash
cd wortuhr
git pull
sudo ./install.sh
```

Cards and plans are stored in `/opt/wortuhr/data/wortuhr.db`. Copy that file if you want a backup.

The default Groq model is `llama-3.3-70b-versatile` on the free tier. You can choose another model id while installing, or edit `GROQ_MODEL` in `/opt/wortuhr/.env` and restart the service.

## Run it locally

Python 3.10 or newer:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m unittest discover -s tests -v
python -m bot
```

Put your Telegram token and Groq key in `.env`. That file is ignored by git.

## Remove

```bash
sudo systemctl disable --now wortuhr
sudo rm /etc/systemd/system/wortuhr.service
sudo systemctl daemon-reload
sudo rm -rf /opt/wortuhr
```
