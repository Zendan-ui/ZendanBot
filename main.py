"""ZendanBot entry point. Long-polling mode."""
import asyncio
import logging
import sys
import traceback

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings
from app.database import init_db
from app.models import init_default_settings
from app.bot.handlers import router as bot_router
from app.bot.advanced import router as advanced_router
from app.topics import init_default_topics
from app.cron.automation import start_all_crons

logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("zendanbot")


def _valid_token(token: str) -> bool:
    if not token or token in ("test_token", "your_telegram_bot_token", ""):
        return False
    if ":" not in token:
        return False
    left, _, right = token.partition(":")
    return left.isdigit() and len(right) >= 30


async def main() -> None:
    logger.info("Starting %s v%s", settings.BOT_FULL_NAME, settings.VERSION)

    if not _valid_token(settings.BOT_TOKEN):
        logger.error("BOT_TOKEN is empty or invalid. Edit .env and set a real token from @BotFather.")
        sys.exit(1)

    try:
        await init_db()
        await init_default_settings()
        await init_default_topics()
        logger.info("Database and defaults are ready.")
    except Exception as exc:
        logger.error("Database init failed: %s", exc)
        logger.error(traceback.format_exc())
        sys.exit(1)

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(bot_router)
    dp.include_router(advanced_router)

    try:
        me = await bot.get_me()
        logger.info("Logged in as @%s (id=%s)", me.username, me.id)
    except Exception as exc:
        logger.error("Cannot reach Telegram with this token: %s", exc)
        logger.error("Check that BOT_TOKEN is correct and that the server is not blocked.")
        await bot.session.close()
        sys.exit(1)

    try:
        await bot.delete_webhook(drop_pending_updates=False)
        logger.info("Webhook cleared; polling mode is active.")
    except Exception as exc:
        logger.warning("delete_webhook failed: %s", exc)

    try:
        start_all_crons(bot)
        logger.info("Cron engine started.")
    except Exception as exc:
        logger.warning("Cron engine not started: %s", exc)

    logger.info("Bot is running. Press Ctrl+C to stop.")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopped.")
    except Exception as exc:
        logger.error("Fatal error: %s", exc)
        logger.error(traceback.format_exc())
        sys.exit(1)
