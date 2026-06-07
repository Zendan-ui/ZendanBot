"""ZendanBot entry point — long-polling mode."""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.admin import router as admin_router
from app.bot.fallback import router as fallback_router
from app.bot.glass import router as glass_router
from app.bot.handlers import router as user_router
from app.config import settings
from app.database import init_db
from app.models import init_default_settings

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

    await init_db()
    await init_default_settings()
    logger.info("Database and defaults ready.")

    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # order matters: admin first (its middleware restricts to admin),
    # then user, then catch-all fallback LAST.
    dp.include_router(glass_router)
    dp.include_router(admin_router)
    dp.include_router(user_router)
    dp.include_router(fallback_router)

    try:
        me = await bot.get_me()
        logger.info("Logged in as @%s (id=%s)", me.username, me.id)
        if not settings.BOT_USERNAME or settings.BOT_USERNAME == "testbot":
            settings.BOT_USERNAME = me.username or settings.BOT_USERNAME
    except Exception as exc:  # noqa: BLE001
        logger.error("Cannot reach Telegram with this token: %s", exc)
        await bot.session.close()
        sys.exit(1)

    await bot.delete_webhook(drop_pending_updates=True)

    try:
        from app.cron import start_scheduler
        scheduler = start_scheduler(bot)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Scheduler not started: %s", exc)
        scheduler = None

    logger.info("Bot is running. Press Ctrl+C to stop.")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        if scheduler:
            scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopped.")
