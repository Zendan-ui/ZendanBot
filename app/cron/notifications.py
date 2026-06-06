from apscheduler.schedulers.asyncio import AsyncIOScheduler
import logging
from app.database import async_session
from app.models import User, Invoice
from sqlalchemy.future import select
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

async def check_expired_services():
    """Cron job equivalent to original cronbot for notifications and auto actions."""
    async with async_session() as session:
        # Example: find invoices nearing expiry
        now = datetime.utcnow()
        result = await session.execute(
            select(Invoice).where(Invoice.Status == "active")
        )
        invoices = result.scalars().all()
        
        for inv in invoices:
            # Parse time, check days left, send notification via bot
            # Full logic: volume warnings, time warnings, auto remove after X days, etc.
            logger.info(f"Checking invoice {inv.id_invoice} for user {inv.id_user}")
            # await bot.send_message(...) if needed (inject bot instance)

        # Similar for other crons: uptime, lottery, backup, etc.

def start_scheduler(bot):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_expired_services, "interval", hours=6)
    # Add more jobs: daily report, remove expired, etc.
    scheduler.start()
    logger.info("Cron scheduler started.")
    return scheduler
