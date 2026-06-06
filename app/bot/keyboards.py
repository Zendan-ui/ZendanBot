from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from app.database import async_session
from app.models import Product, MarzbanPanel
from sqlalchemy.future import select

def main_menu(lang: str = "fa") -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="🛍 خرید سرویس"),
        KeyboardButton(text="💊 تمدید سرویس")
    )
    builder.row(
        KeyboardButton(text="🎁 اکانت تست"),
        KeyboardButton(text="🎲 گردونه شانس")
    )
    builder.row(
        KeyboardButton(text="🛍 سرویس‌های خریداری شده"),
        KeyboardButton(text="💰 کیف پول")
    )
    builder.row(
        KeyboardButton(text="👥 زیرمجموعه‌گیری"),
        KeyboardButton(text="📋 لیست تعرفه‌ها")
    )
    builder.row(
        KeyboardButton(text="☎️ پشتیبانی"),
        KeyboardButton(text="📚 آموزش")
    )
    builder.row(KeyboardButton(text="🌏 تغییر زبان"))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)

async def products_keyboard() -> ReplyKeyboardMarkup:
    """Dynamic products keyboard from database"""
    builder = ReplyKeyboardBuilder()
    async with async_session() as session:
        products = (await session.execute(select(Product).limit(20))).scalars().all()
        for p in products:
            builder.button(text=p.name_product or f"محصول {p.id}")
        builder.adjust(2)
    builder.row(KeyboardButton(text="🏠 بازگشت به منوی اصلی"))
    return builder.as_markup(resize_keyboard=True)

async def panels_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    async with async_session() as session:
        panels = (await session.execute(select(MarzbanPanel).where(MarzbanPanel.status == "active").limit(15))).scalars().all()
        for p in panels:
            builder.button(text=p.name_panel or f"پنل {p.id}")
        builder.adjust(2)
    builder.row(KeyboardButton(text="🏠 بازگشت"))
    return builder.as_markup(resize_keyboard=True)

def payment_methods_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="💳 کارت به کارت"))
    builder.row(KeyboardButton(text="🌐 nowpayment"))
    builder.row(KeyboardButton(text="💎 آقای پرداخت"))
    builder.row(KeyboardButton(text="🟡 زرین‌پال"))
    builder.row(KeyboardButton(text="₿ ترون / کریپتو"))
    builder.row(KeyboardButton(text="⭐ استار تلگرام"))
    builder.row(KeyboardButton(text="🏠 بازگشت به منوی اصلی"))
    return builder.as_markup(resize_keyboard=True)

def admin_panel_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📊 آمار ربات"), KeyboardButton(text="👤 مدیریت کاربر"))
    builder.row(KeyboardButton(text="🖥 مدیریت پنل"), KeyboardButton(text="🛍 مدیریت محصولات"))
    builder.row(KeyboardButton(text="💵 تایید رسیدها"), KeyboardButton(text="📨 ارسال پیام همگانی"))
    builder.row(KeyboardButton(text="⚙️ تنظیمات پیشرفته"), KeyboardButton(text="📋 گزارشات کامل"))
    builder.row(KeyboardButton(text="🎁 هدیه همگانی"), KeyboardButton(text="🔄 کرون و اتوماسیون"))
    builder.row(KeyboardButton(text="🏠 بازگشت به منوی اصلی"))
    return builder.as_markup(resize_keyboard=True)

def confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ تایید و ادامه", callback_data="confirm_purchase")
    builder.button(text="❌ لغو", callback_data="cancel")
    builder.adjust(2)
    return builder.as_markup()
