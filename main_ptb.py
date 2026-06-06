"""
ZendanBot alternative entry point using python-telegram-bot.

Implements a subset of the bot (start, main menu, products, wallet,
tariffs, support, tutorial, referral, admin stats) on top of the same
database and models used by main.py.

Only one of main.py / main_ptb.py may run against the same bot token
at a time.
"""
import logging
import sys
from datetime import datetime

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from sqlalchemy.future import select

from app.config import settings
from app.database import init_db, async_session
from app.models import init_default_settings, User, Product, MarzbanPanel, Invoice
from app.topics import init_default_topics
from app.security import bot_rate_limiter, sanitize_text, is_authorized_admin

logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("zendanbot.ptb")


def _valid_token(token: str) -> bool:
    if not token or token in ("test_token", "your_telegram_bot_token", ""):
        return False
    if ":" not in token:
        return False
    left, _, right = token.partition(":")
    return left.isdigit() and len(right) >= 30


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🛍 خرید سرویس"), KeyboardButton("💊 تمدید سرویس")],
            [KeyboardButton("🎁 اکانت تست"), KeyboardButton("🎲 گردونه شانس")],
            [KeyboardButton("🛍 سرویس‌های خریداری شده"), KeyboardButton("💰 کیف پول")],
            [KeyboardButton("👥 زیرمجموعه‌گیری"), KeyboardButton("📋 لیست تعرفه‌ها")],
            [KeyboardButton("☎️ پشتیبانی"), KeyboardButton("📚 آموزش")],
            [KeyboardButton("🌏 تغییر زبان")],
        ],
        resize_keyboard=True,
    )


def admin_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📊 آمار ربات"), KeyboardButton("👤 مدیریت کاربر")],
            [KeyboardButton("🖥 مدیریت پنل"), KeyboardButton("🛍 مدیریت محصولات")],
            [KeyboardButton("💵 تایید رسیدها"), KeyboardButton("📨 ارسال پیام همگانی")],
            [KeyboardButton("🏠 بازگشت به منوی اصلی")],
        ],
        resize_keyboard=True,
    )


async def get_or_create_user(tg_user) -> User:
    user_id = str(tg_user.id)
    safe_username = sanitize_text(tg_user.username or "none")
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                id=user_id,
                username=safe_username,
                Balance=0,
                step="",
                lang="fa",
                agent="f",
                User_Status="active",
                register=str(int(datetime.now().timestamp())),
                limit_usertest=1,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        return user


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    if not bot_rate_limiter.is_allowed(user_id):
        await update.message.reply_text("لطفاً کمی صبر کنید و دوباره تلاش کنید.")
        return

    user = await get_or_create_user(update.effective_user)
    await update.message.reply_text(
        f"<b>خوش آمدید به {settings.BOT_FULL_NAME}</b>\n\n"
        f"{update.effective_user.first_name}\n"
        f"موجودی شما: <b>{user.Balance}</b> تومان",
        reply_markup=main_menu_kb(),
        parse_mode=ParseMode.HTML,
    )


async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized_admin(str(update.effective_user.id)):
        await update.message.reply_text("دسترسی ندارید.")
        return
    await update.message.reply_text("پنل مدیریت", reply_markup=admin_menu_kb())


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "<b>راهنما</b>\n\n"
        "/start - شروع و منوی اصلی\n"
        "/admin - پنل مدیریت (فقط ادمین)\n"
        "/help - این راهنما",
        parse_mode=ParseMode.HTML,
    )


async def on_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    async with async_session() as session:
        products = (await session.execute(select(Product).limit(30))).scalars().all()
    if not products:
        await update.message.reply_text("هنوز محصولی ثبت نشده است.")
        return
    text = "<b>لیست محصولات:</b>\n\n"
    for p in products:
        text += f"- {p.name_product} — {p.price_product or 0} تومان\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def on_wallet(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    async with async_session() as session:
        u = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    bal = u.Balance if u else 0
    await update.message.reply_text(
        f"<b>کیف پول</b>\n\nموجودی فعلی: <b>{bal}</b> تومان",
        parse_mode=ParseMode.HTML,
    )


async def on_support(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "<b>پشتیبانی</b>\n\nپیام خود را همین‌جا ارسال کنید.",
        parse_mode=ParseMode.HTML,
    )


async def on_tutorial(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "<b>آموزش اتصال</b>\n\n"
        "1) اپلیکیشن مناسب سیستم‌عامل خود را نصب کنید\n"
        "   اندروید: V2rayNG / NekoBox\n"
        "   iOS: Streisand / FoXray\n"
        "   ویندوز: v2rayN / Nekoray\n"
        "   مک: V2Box / FoXray\n\n"
        "2) لینک سابسکریپشن سرویس را کپی کنید.\n"
        "3) در اپلیکیشن از Import from Clipboard وارد کنید.",
        parse_mode=ParseMode.HTML,
    )


async def on_tariffs(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    async with async_session() as session:
        products = (await session.execute(select(Product).limit(50))).scalars().all()
    if not products:
        await update.message.reply_text("هنوز تعرفه‌ای ثبت نشده است.")
        return
    text = "<b>لیست تعرفه‌ها:</b>\n\n"
    for p in products:
        text += f"- {p.name_product} — {p.price_product or 0} تومان\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def on_my_services(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    async with async_session() as session:
        invs = (await session.execute(
            select(Invoice).where(Invoice.id_user == user_id)
        )).scalars().all()
    if not invs:
        await update.message.reply_text("هنوز سرویسی نخریده‌اید.")
        return
    text = "<b>سرویس‌های شما:</b>\n\n"
    for inv in invs[:20]:
        text += (
            f"- <code>{inv.username}</code> | "
            f"{inv.name_product or '-'} | "
            f"وضعیت: {inv.Status}\n"
        )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def on_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("منوی اصلی", reply_markup=main_menu_kb())


async def on_test_account(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "<b>اکانت تست</b>\n\nاین قابلیت در نسخه‌ی PTB پیاده نشده است.",
        parse_mode=ParseMode.HTML,
    )


async def on_referral(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    bot_username = settings.BOT_USERNAME
    link = f"https://t.me/{bot_username}?start={user_id}"
    await update.message.reply_text(
        f"<b>زیرمجموعه‌گیری</b>\n\n"
        f"لینک دعوت شما:\n<code>{link}</code>",
        parse_mode=ParseMode.HTML,
    )


async def on_admin_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized_admin(str(update.effective_user.id)):
        return
    async with async_session() as session:
        users = len((await session.execute(select(User))).scalars().all())
        prods = len((await session.execute(select(Product))).scalars().all())
        panels = len((await session.execute(select(MarzbanPanel))).scalars().all())
        invs = (await session.execute(select(Invoice))).scalars().all()
        active = sum(1 for i in invs if i.Status == "active")
    await update.message.reply_text(
        f"<b>آمار</b>\n\n"
        f"کاربران: <b>{users}</b>\n"
        f"محصولات: <b>{prods}</b>\n"
        f"پنل‌ها: <b>{panels}</b>\n"
        f"کل فاکتورها: <b>{len(invs)}</b>\n"
        f"سرویس‌های فعال: <b>{active}</b>",
        parse_mode=ParseMode.HTML,
    )


async def on_admin_placeholder(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized_admin(str(update.effective_user.id)):
        return
    await update.message.reply_text(
        "این قابلیت در نسخه‌ی PTB پیاده نشده است.",
        parse_mode=ParseMode.HTML,
    )


async def on_unknown_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if is_authorized_admin(str(update.effective_user.id)):
        return
    await update.message.reply_text("لطفاً از دکمه‌های منوی پایین استفاده کنید یا /start بزنید.")


async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("handler error: %s", ctx.error)


async def post_init(app: Application) -> None:
    await init_db()
    await init_default_settings()
    await init_default_topics()
    logger.info("Database and defaults are ready.")
    try:
        await app.bot.delete_webhook(drop_pending_updates=False)
        logger.info("Webhook cleared.")
    except Exception as exc:
        logger.warning("delete_webhook failed: %s", exc)
    me = await app.bot.get_me()
    logger.info("Logged in as @%s (id=%s)", me.username, me.id)


def main() -> None:
    logger.info("Starting %s v%s (PTB build)", settings.BOT_FULL_NAME, settings.VERSION)

    if not _valid_token(settings.BOT_TOKEN):
        logger.error("BOT_TOKEN is empty or invalid. Edit .env and set a real token.")
        sys.exit(1)

    app = (
        Application.builder()
        .token(settings.BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("panel", cmd_admin))

    app.add_handler(MessageHandler(filters.Regex(r"^🛍 خرید سرویس$"), on_buy))
    app.add_handler(MessageHandler(filters.Regex(r"^💊 تمدید سرویس$"), on_tariffs))
    app.add_handler(MessageHandler(filters.Regex(r"^🎁 اکانت تست$"), on_test_account))
    app.add_handler(MessageHandler(filters.Regex(r"^🎲 گردونه شانس$"), on_admin_placeholder))
    app.add_handler(MessageHandler(filters.Regex(r"^🛍 سرویس‌های خریداری شده$"), on_my_services))
    app.add_handler(MessageHandler(filters.Regex(r"^💰 کیف پول$"), on_wallet))
    app.add_handler(MessageHandler(filters.Regex(r"^👥 زیرمجموعه‌گیری$"), on_referral))
    app.add_handler(MessageHandler(filters.Regex(r"^📋 لیست تعرفه‌ها$"), on_tariffs))
    app.add_handler(MessageHandler(filters.Regex(r"^☎️ پشتیبانی$"), on_support))
    app.add_handler(MessageHandler(filters.Regex(r"^📚 آموزش$"), on_tutorial))
    app.add_handler(MessageHandler(filters.Regex(r"^🌏 تغییر زبان$"), on_admin_placeholder))
    app.add_handler(MessageHandler(filters.Regex(r"^🏠 بازگشت به منوی اصلی$"), on_back))

    app.add_handler(MessageHandler(filters.Regex(r"^📊 آمار ربات$"), on_admin_stats))
    app.add_handler(MessageHandler(
        filters.Regex(r"^(👤 مدیریت کاربر|🖥 مدیریت پنل|🛍 مدیریت محصولات|💵 تایید رسیدها|📨 ارسال پیام همگانی)$"),
        on_admin_placeholder,
    ))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_unknown_text))
    app.add_error_handler(on_error)

    logger.info("Polling started. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=False, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopped.")
