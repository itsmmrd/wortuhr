from __future__ import annotations

import asyncio
import logging
import sys

from telegram import BotCommand
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from bot import config
from bot.db import db
from bot.i18n import t
from bot.handlers import (
    cancel_cmd,
    help_cmd,
    new_cmd,
    on_callback,
    on_text,
    plans_cmd,
    progress_cmd,
    review_cmd,
    settings_cmd,
    start,
)
from bot.scheduler import tick

logger = logging.getLogger(__name__)


async def _scheduler_loop(application: Application) -> None:
    await asyncio.sleep(5)
    while True:
        try:
            await tick(application.bot)
        except Exception:
            logger.exception("scheduler tick failed")
        await asyncio.sleep(30)


async def post_init(application: Application) -> None:
    db.init()
    commands = [
        ("start", "cmd_start"),
        ("new", "cmd_new"),
        ("plans", "cmd_plans"),
        ("progress", "cmd_progress"),
        ("review", "cmd_review"),
        ("settings", "cmd_settings"),
        ("help", "cmd_help"),
        ("cancel", "cmd_cancel"),
    ]
    await application.bot.set_my_commands(
        [BotCommand(name, t("en", key)) for name, key in commands]
    )
    await application.bot.set_my_commands(
        [BotCommand(name, t("fa", key)) for name, key in commands],
        language_code="fa",
    )
    application.bot_data["scheduler"] = asyncio.create_task(_scheduler_loop(application))


async def post_shutdown(application: Application) -> None:
    task = application.bot_data.get("scheduler")
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def ensure_event_loop() -> None:
    """Python 3.14 no longer creates an event loop on get_event_loop()."""
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    if not config.TELEGRAM_BOT_TOKEN or not config.GROQ_API_KEY or not config.GROQ_MODEL:
        sys.exit("Set TELEGRAM_BOT_TOKEN, GROQ_API_KEY, and GROQ_MODEL in the environment or in .env.")
    application = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("new", new_cmd))
    application.add_handler(CommandHandler("plans", plans_cmd))
    application.add_handler(CommandHandler("progress", progress_cmd))
    application.add_handler(CommandHandler("review", review_cmd))
    application.add_handler(CommandHandler("settings", settings_cmd))
    application.add_handler(CommandHandler("cancel", cancel_cmd))
    application.add_handler(CallbackQueryHandler(on_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    logger.info("Wortuhr is starting with Groq model %s", config.GROQ_MODEL)
    ensure_event_loop()
    application.run_polling(drop_pending_updates=True)
