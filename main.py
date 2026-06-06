import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from contextlib import asynccontextmanager

from app.config import settings
from app.database import init_db, init_default_settings
from app.bot.handlers import router as bot_router
from app.security import *
from app.topics import init_default_topics
from app.cron.automation import start_all_crons

# Logging
logging.basicConfig(level=logging.INFO if settings.DEBUG else logging.WARNING)
logger = logging.getLogger(__name__)

# Aiogram setup
bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(bot_router)

async def main():
    logger.info(f"🚀 Starting {settings.BOT_FULL_NAME} v{settings.VERSION}")
    logger.info("🔒 Enterprise Security Layer activated.")

    await init_db()
    await init_default_settings()
    await init_default_topics()
    logger.info("✅ Secure database, configuration, and topic groups ready.")

    # Start full cron and automation system
    scheduler = start_all_crons(bot)
    logger.info("⏰ Full Automation & Cron Engine started (all jobs active).")

    # Start bot (polling for dev, webhook for prod)
    if settings.WEBHOOK_URL:
        await bot.set_webhook(settings.WEBHOOK_URL)
        logger.info(f"🌐 Secure Webhook activated: {settings.WEBHOOK_URL}")
        # For webhook, you would run with uvicorn and handle updates separately
        # Here we keep polling for simplicity in pure bot mode
    else:
        logger.info("📡 Bot started in polling mode (development).")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
