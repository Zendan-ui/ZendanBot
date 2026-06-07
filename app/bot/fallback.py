"""Catch-all router included LAST. Guarantees every message gets a response,
so buttons never appear "dead". Also enforces block + maintenance."""
from aiogram import Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.future import select

from app.bot import keyboards as kb
from app.config import settings
from app.database import async_session
from app.models import User, get_setting

router = Router()


def _is_admin(uid) -> bool:
    return str(uid) == str(settings.ADMIN_ID)


@router.message()
async def fallback_message(message: Message):
    # blocked users
    async with async_session() as session:
        user = (await session.execute(
            select(User).where(User.id == message.from_user.id)
        )).scalar_one_or_none()
    if user and user.is_blocked:
        await message.answer("⛔️ دسترسی شما به ربات مسدود شده است.")
        return
    if await get_setting("bot_status", "on") != "on" and not _is_admin(message.from_user.id):
        await message.answer("🛠 ربات در دست تعمیر است.")
        return
    await message.answer(
        "متوجه نشدم 🤔 لطفاً از دکمه‌های منو استفاده کنید.",
        reply_markup=kb.main_menu(),
    )


@router.callback_query()
async def fallback_callback(cb: CallbackQuery):
    # stale buttons (e.g. after restart) — acknowledge instead of hanging
    await cb.answer("این دکمه منقضی شده. لطفاً دوباره از منو شروع کنید.", show_alert=True)
