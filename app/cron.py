"""Background automation (APScheduler).

Jobs:
  * expiry_reminder  - DM users whose service expires within N days (hourly check,
                       once per service per day).
  * mark_and_remove  - mark expired services; optionally delete them from the panel.
  * nightly_report   - send a daily summary to the report chat at 23:30.

Everything is settings-driven and safe to run with an empty database.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import func
from sqlalchemy.future import select

from app.database import async_session
from app.models import Panel, Service, User, get_setting
from app.panels.xui import XUIPanel
from app.reports import send_report

logger = logging.getLogger(__name__)

# remember (service_id, date) we already reminded to avoid spamming
_reminded: set[tuple[int, str]] = set()


async def _enabled() -> bool:
    return await get_setting("cron_enabled", "1") == "1"


# --------------------------------------------------------------------------- #
async def expiry_reminder(bot) -> None:
    if not await _enabled():
        return
    try:
        days = int(await get_setting("expire_reminder_days", "3") or 3)
    except ValueError:
        days = 3
    now = datetime.utcnow()
    horizon = now + timedelta(days=days)
    today = now.strftime("%Y-%m-%d")

    async with async_session() as session:
        services = (await session.execute(
            select(Service).where(
                Service.status == "active",
                Service.expire_at.isnot(None),
                Service.expire_at <= horizon,
                Service.expire_at > now,
            )
        )).scalars().all()

    for svc in services:
        key = (svc.id, today)
        if key in _reminded:
            continue
        remaining = (svc.expire_at - now).days
        try:
            await bot.send_message(
                svc.user_id,
                f"⏰ سرویس «{svc.product_name}» شما تا {max(remaining, 0)} روز دیگر منقضی می‌شود.\n"
                f"برای تمدید به «📦 سرویس‌های من» مراجعه کنید.",
            )
            _reminded.add(key)
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------------- #
async def mark_and_remove(bot) -> None:
    if not await _enabled():
        return
    now = datetime.utcnow()
    auto_remove = await get_setting("auto_remove_expired", "0") == "1"

    async with async_session() as session:
        expired = (await session.execute(
            select(Service).where(
                Service.status == "active",
                Service.expire_at.isnot(None),
                Service.expire_at <= now,
            )
        )).scalars().all()

    for svc in expired:
        async with async_session() as session:
            s = (await session.execute(select(Service).where(Service.id == svc.id))).scalar_one_or_none()
            if not s:
                continue
            s.status = "expired"
            await session.commit()
        # notify owner
        try:
            await bot.send_message(svc.user_id,
                                   f"⛔️ سرویس «{svc.product_name}» شما منقضی شد.")
        except Exception:  # noqa: BLE001
            pass
        # optionally delete from panel
        if auto_remove and svc.config_uuid:
            async with async_session() as session:
                panel = (await session.execute(
                    select(Panel).where(Panel.id == svc.panel_id)
                )).scalar_one_or_none()
            if panel and panel.type == "xui":
                try:
                    async with XUIPanel(panel.url, panel.username, panel.password,
                                        inbound_id=panel.inbound_id) as api:
                        await api.delete_client(svc.config_uuid)
                except Exception:  # noqa: BLE001
                    pass


# --------------------------------------------------------------------------- #
async def nightly_report(bot) -> None:
    if not await _enabled() or await get_setting("nightly_report", "1") != "1":
        return
    since = datetime.utcnow() - timedelta(days=1)
    async with async_session() as session:
        new_users = (await session.execute(
            select(func.count()).select_from(User).where(User.created_at >= since)
        )).scalar()
        new_services = (await session.execute(
            select(func.count()).select_from(Service).where(Service.created_at >= since)
        )).scalar()
        revenue = (await session.execute(
            select(func.coalesce(func.sum(Service.price), 0)).where(Service.created_at >= since)
        )).scalar()
        total_users = (await session.execute(select(func.count()).select_from(User))).scalar()
        active = (await session.execute(
            select(func.count()).select_from(Service).where(Service.status == "active")
        )).scalar()
    await send_report(
        bot, "night",
        "🌙 <b>گزارش شبانه</b>\n\n"
        f"👤 کاربران جدید (۲۴ ساعت): {new_users}\n"
        f"🛍 فروش جدید (۲۴ ساعت): {new_services} سرویس | {revenue:,} تومان\n"
        f"👥 کل کاربران: {total_users}\n"
        f"📦 سرویس‌های فعال: {active}",
    )


# --------------------------------------------------------------------------- #
async def send_backup(bot) -> bool:
    """Send the SQLite database file to the admin. Returns True on success."""
    from app.config import settings
    url = settings.DATABASE_URL
    if not url.startswith("sqlite"):
        return False
    # sqlite+aiosqlite:///./zendanbot.db  -> ./zendanbot.db
    path = url.split(":///", 1)[-1] if ":///" in url else url.split("://", 1)[-1]
    import os
    from datetime import datetime as _dt
    if not os.path.exists(path):
        return False
    try:
        from aiogram.types import FSInputFile
        stamp = _dt.utcnow().strftime("%Y%m%d-%H%M")
        await bot.send_document(
            settings.ADMIN_ID,
            FSInputFile(path, filename=f"backup-{stamp}.db"),
            caption=f"🗄 بکاپ خودکار دیتابیس — {stamp} UTC",
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("backup send failed: %s", exc)
        return False


async def daily_backup(bot) -> None:
    if not await _enabled() or await get_setting("auto_backup", "0") != "1":
        return
    await send_backup(bot)


def start_scheduler(bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(expiry_reminder, "interval", hours=1, args=[bot],
                      id="expiry_reminder", replace_existing=True)
    scheduler.add_job(mark_and_remove, "interval", minutes=30, args=[bot],
                      id="mark_and_remove", replace_existing=True)
    scheduler.add_job(nightly_report, "cron", hour=23, minute=30, args=[bot],
                      id="nightly_report", replace_existing=True)
    scheduler.add_job(daily_backup, "cron", hour=4, minute=0, args=[bot],
                      id="daily_backup", replace_existing=True)
    scheduler.start()
    logger.info("Scheduler started (reminders, cleanup, nightly report, backup).")
    return scheduler
