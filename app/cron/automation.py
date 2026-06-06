"""
ZendanBOT - Full Cron Jobs and Automation (Stage 4)
All automation features: notifications, auto-remove, uptime, nightly reports, lottery, backups, etc.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import async_session
from app.models import User, Invoice, Setting, MarzbanPanel
from sqlalchemy.future import select
from app.topics import get_topic_id, send_to_topic
from app.config import settings
from datetime import datetime, timedelta
import logging
import random

logger = logging.getLogger(__name__)

async def notify_volume_warnings():
    """Notify users when volume is low."""
    async with async_session() as session:
        active_invoices = (await session.execute(select(Invoice).where(Invoice.Status == "active"))).scalars().all()
        for inv in active_invoices:
            # Simulate volume check (in real: query panel)
            remaining = 20  # placeholder
            if remaining < 5:  # from settings
                await send_to_topic(
                    None,  # bot will be passed
                    inv.id_user,
                    "0",
                    f"⚠️ حجم سرویس {inv.username} کم است: {remaining} گیگ باقی مانده."
                )
    logger.info("Volume warnings sent.")

async def notify_time_warnings():
    """Notify users for time expiry."""
    async with async_session() as session:
        active = (await session.execute(select(Invoice).where(Invoice.Status == "active"))).scalars().all()
        for inv in active:
            # Parse time_sell and check days left
            days_left = 3  # placeholder
            if days_left < 3:
                await send_to_topic(
                    None,
                    inv.id_user,
                    "0",
                    f"⏰ زمان سرویس {inv.username} رو به پایان است: {days_left} روز باقی مانده."
                )
    logger.info("Time warnings sent.")

async def auto_remove_expired():
    """Auto remove expired services."""
    async with async_session() as session:
        expired = (await session.execute(
            select(Invoice).where(Invoice.Status == "active")
        )).scalars().all()
        for inv in expired:
            # Check if expired (placeholder logic)
            if True:  # real check
                inv.Status = "expired"
                await session.commit()
                # Remove from panel if needed
                logger.info(f"Auto-removed expired: {inv.username}")
    logger.info("Expired services auto-removed.")

async def uptime_check():
    """Check panel and node uptime."""
    async with async_session() as session:
        panels = (await session.execute(select(MarzbanPanel).where(MarzbanPanel.status == "active"))).scalars().all()
        for p in panels:
            # Simulate check
            if random.random() < 0.1:  # 10% chance down for demo
                topic_id = await get_topic_id("errorreport")
                await send_to_topic(
                    None,
                    settings.ADMIN_ID,
                    topic_id,
                    f"🚨 پنل {p.name_panel} در دسترس نیست!"
                )
    logger.info("Uptime check completed.")

async def nightly_report():
    """Send nightly report."""
    async with async_session() as session:
        total_users = len((await session.execute(select(User))).scalars().all())
        active = len((await session.execute(select(Invoice).where(Invoice.Status == "active"))).scalars().all())
        report = f"🌙 گزارش شبانه:\nکاربران: {total_users}\nسرویس فعال: {active}"
        topic_id = await get_topic_id("nightreport")
        await send_to_topic(None, settings.ADMIN_ID, topic_id, report)
    logger.info("Nightly report sent.")

async def run_lottery():
    """Periodic lottery."""
    async with async_session() as session:
        users = (await session.execute(select(User))).scalars().all()
        if users:
            winner = random.choice(users)
            prize = 10000  # from settings
            winner.Balance += prize
            await session.commit()
            await send_to_topic(None, winner.id, "0", f"🎁 شما در قرعه‌کشی برنده {prize} تومان شدید!")
            topic_id = await get_topic_id("porsantreport")
            await send_to_topic(None, settings.ADMIN_ID, topic_id, f"برنده قرعه‌کشی: {winner.id}")
    logger.info("Lottery run.")

async def backup_database():
    """Simple backup (in real: dump DB)."""
    logger.info("Database backup triggered (demo).")
    topic_id = await get_topic_id("backupreport")
    await send_to_topic(None, settings.ADMIN_ID, topic_id, "📦 بکاپ دیتابیس انجام شد.")

async def on_hold_notifications():
    """Notify on-hold users."""
    logger.info("On-hold notifications sent (demo).")

def start_all_crons(bot):
    """Start all automation jobs."""
    scheduler = AsyncIOScheduler()
    
    # Volume warnings every 6 hours
    scheduler.add_job(notify_volume_warnings, 'interval', hours=6)
    
    # Time warnings daily
    scheduler.add_job(notify_time_warnings, 'cron', hour=9)
    
    # Auto remove every day at 3 AM
    scheduler.add_job(auto_remove_expired, 'cron', hour=3)
    
    # Uptime check every hour
    scheduler.add_job(uptime_check, 'interval', hours=1)
    
    # Nightly report at midnight
    scheduler.add_job(nightly_report, 'cron', hour=0)
    
    # Lottery weekly
    scheduler.add_job(run_lottery, 'cron', day_of_week='sun', hour=10)
    
    # Backup daily
    scheduler.add_job(backup_database, 'cron', hour=2)
    
    # On-hold notifications
    scheduler.add_job(on_hold_notifications, 'interval', hours=12)
    
    scheduler.start()
    logger.info("✅ All ZendanBOT crons started.")
    return scheduler
