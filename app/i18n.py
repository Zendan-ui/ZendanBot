"""Tiny i18n layer (fa / en).

Usage:
    from app.i18n import t
    await message.answer(t("welcome_back", lang))

Persian is the default/source language. Missing keys fall back to the key
itself so nothing ever crashes.
"""
from __future__ import annotations

from sqlalchemy.future import select

from app.database import async_session
from app.models import User

DEFAULT_LANG = "fa"
LANGS = ("fa", "en")

TR: dict[str, dict[str, str]] = {
    "fa": {
        "lang_name": "🇮🇷 فارسی",
        "choose_lang": "🌐 زبان خود را انتخاب کنید:",
        "lang_set": "✅ زبان روی فارسی تنظیم شد.",
        "main_menu": "🏠 منوی اصلی",
        "wallet_title": "💰 کیف پول شما",
        "balance": "موجودی",
        "toman": "تومان",
        "no_products": "فعلاً محصولی برای فروش موجود نیست.",
        "choose_plan": "🛍 یکی از پلن‌ها را انتخاب کنید:",
        "choose_cat": "🗂 یک دسته را انتخاب کنید:",
        "no_services": "شما هنوز سرویسی ندارید. از «🛍 خرید سرویس» اقدام کنید.",
        "my_services": "📦 سرویس‌های شما:",
        "buy_success": "✅ خرید موفق",
        "insufficient": "موجودی کافی نیست. ابتدا کیف پول را شارژ کنید.",
        "connect_link": "🔗 لینک اتصال",
        "cancelled": "لغو شد.",
        "not_understood": "متوجه نشدم 🤔 لطفاً از دکمه‌های منو استفاده کنید.",
        "test_ready": "🎁 اکانت تست شما آماده شد",
        "test_disabled": "دریافت اکانت تست در حال حاضر غیرفعال است.",
        "test_used": "شما قبلاً سهمیه اکانت تست خود را دریافت کرده‌اید.",
        "support_prompt": "☎️ پیام خود را بنویسید تا برای پشتیبانی ارسال شود:",
        "support_saved": "✅ پیام شما ثبت شد. به‌زودی پاسخ داده می‌شود.",
    },
    "en": {
        "lang_name": "🇬🇧 English",
        "choose_lang": "🌐 Choose your language:",
        "lang_set": "✅ Language set to English.",
        "main_menu": "🏠 Main menu",
        "wallet_title": "💰 Your wallet",
        "balance": "Balance",
        "toman": "Toman",
        "no_products": "No products available right now.",
        "choose_plan": "🛍 Choose a plan:",
        "choose_cat": "🗂 Choose a category:",
        "no_services": "You have no services yet. Use “🛍 Buy service”.",
        "my_services": "📦 Your services:",
        "buy_success": "✅ Purchase successful",
        "insufficient": "Insufficient balance. Please top up your wallet first.",
        "connect_link": "🔗 Connection link",
        "cancelled": "Cancelled.",
        "not_understood": "I didn't get that 🤔 Please use the menu buttons.",
        "test_ready": "🎁 Your test account is ready",
        "test_disabled": "Test accounts are currently disabled.",
        "test_used": "You have already used your test account quota.",
        "support_prompt": "☎️ Type your message to send to support:",
        "support_saved": "✅ Your message has been saved. We'll reply soon.",
    },
}


def t(key: str, lang: str = DEFAULT_LANG) -> str:
    lang = lang if lang in LANGS else DEFAULT_LANG
    return TR.get(lang, TR[DEFAULT_LANG]).get(key) or TR[DEFAULT_LANG].get(key, key)


async def get_lang(user_id: int) -> str:
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user and user.lang in LANGS:
        return user.lang
    return DEFAULT_LANG


async def set_lang(user_id: int, lang: str) -> None:
    if lang not in LANGS:
        return
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if user:
            user.lang = lang
            await session.commit()
