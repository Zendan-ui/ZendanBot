"""Admin handlers: panels, products, receipt approval, settings, broadcast,
stats, ticket replies. All gated on settings.ADMIN_ID."""
from __future__ import annotations

import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func
from sqlalchemy.future import select

from app.bot import keyboards as kb
from app.bot.states import AdminSG
from app.config import settings
from app.database import async_session
from app.models import (
    AgentRequest, DEFAULT_SETTINGS, Category, Discount, GiftCode, Panel,
    Product, Receipt, Service, Ticket, User, get_setting, set_setting,
)
from app.panels.xui import test_connection as xui_test
from app.panels.marzban import test_connection as marzban_test
from app.panels.pasargad import test_connection as pasargad_test


async def panel_test_connection(ptype: str, url: str, user: str, pwd: str) -> bool:
    if ptype == "marzban":
        return await marzban_test(url, user, pwd)
    if ptype == "pasargad":
        return await pasargad_test(url, user, pwd)
    return await xui_test(url, user, pwd)
from app.security import sanitize_text

router = Router()
logger = logging.getLogger(__name__)


def is_admin(user_id) -> bool:
    return str(user_id) == str(settings.ADMIN_ID)


# Every handler in this router requires admin. aiogram lets us filter per-router.
@router.message.middleware
async def admin_only_mw(handler, event: Message, data):  # type: ignore
    if not is_admin(event.from_user.id):
        return  # silently ignore non-admins
    return await handler(event, data)


@router.callback_query.middleware
async def admin_only_cb_mw(handler, event: CallbackQuery, data):  # type: ignore
    if not is_admin(event.from_user.id):
        await event.answer("دسترسی ندارید.", show_alert=True)
        return
    return await handler(event, data)


# --------------------------------------------------------------------------- #
#  Stats
# --------------------------------------------------------------------------- #
@router.message(F.text == "📊 آمار")
async def admin_stats(message: Message):
    from datetime import timedelta
    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    async with async_session() as session:
        users = (await session.execute(select(func.count()).select_from(User))).scalar()
        new_users_24 = (await session.execute(
            select(func.count()).select_from(User).where(User.created_at >= day_ago))).scalar()
        agents = (await session.execute(
            select(func.count()).select_from(User).where(User.is_agent == True))).scalar()  # noqa: E712
        services = (await session.execute(select(func.count()).select_from(Service))).scalar()
        active = (await session.execute(
            select(func.count()).select_from(Service).where(Service.status == "active"))).scalar()
        revenue = (await session.execute(select(func.coalesce(func.sum(Service.price), 0)))).scalar()
        rev_24 = (await session.execute(select(func.coalesce(func.sum(Service.price), 0))
                  .where(Service.created_at >= day_ago))).scalar()
        rev_7 = (await session.execute(select(func.coalesce(func.sum(Service.price), 0))
                 .where(Service.created_at >= week_ago))).scalar()
        wallet_total = (await session.execute(select(func.coalesce(func.sum(User.balance), 0)))).scalar()
        pending = (await session.execute(
            select(func.count()).select_from(Receipt).where(Receipt.status == "pending"))).scalar()
        panels = (await session.execute(select(func.count()).select_from(Panel))).scalar()
        products = (await session.execute(select(func.count()).select_from(Product))).scalar()
    await message.answer(
        f"📊 <b>آمار ربات</b>\n\n"
        f"👥 کاربران: <b>{users}</b> (۲۴س: +{new_users_24})\n"
        f"🤝 نمایندگان: {agents}\n"
        f"📦 سرویس‌ها: {services} (فعال: {active})\n"
        f"🖥 پنل‌ها: {panels} | 🛍 محصولات: {products}\n\n"
        f"💰 فروش کل: <b>{revenue:,}</b> تومان\n"
        f"📅 فروش ۲۴ ساعت: {rev_24:,} تومان\n"
        f"🗓 فروش ۷ روز: {rev_7:,} تومان\n"
        f"👛 موجودی کل کیف‌پول‌ها: {wallet_total:,} تومان\n"
        f"💳 رسیدهای در انتظار: {pending}"
    )


@router.message(Command("backup"))
async def cmd_backup(message: Message):
    from app.cron import send_backup
    await message.answer("🗄 در حال تهیه بکاپ...")
    ok = await send_backup(message.bot)
    if not ok:
        await message.answer("بکاپ ناموفق بود (فقط برای دیتابیس SQLite در دسترس است).")


# --------------------------------------------------------------------------- #
#  Panels management
# --------------------------------------------------------------------------- #
@router.message(F.text == "🖥 مدیریت پنل‌ها")
async def admin_panels(message: Message):
    async with async_session() as session:
        panels = (await session.execute(select(Panel))).scalars().all()
    text = "🖥 <b>پنل‌ها:</b>\n\n"
    if panels:
        for p in panels:
            mark = "🟢" if p.is_active else "🔴"
            text += f"{mark} #{p.id} {p.name} ({p.type}) — {p.url}\n"
    else:
        text += "هیچ پنلی ثبت نشده است.\n"
    text += (
        "\n<b>افزودن پنل جدید:</b>\n"
        "<code>/addpanel نوع|نام|http://ip:port|یوزر|پسورد|inbound|دامنه_ساب</code>\n"
        "نوع: <b>xui</b> یا <b>marzban</b> یا <b>pasargad</b>\n"
        "مثال XUI:\n"
        "<code>/addpanel xui|آلمان|http://1.2.3.4:54321|admin|admin|1|sub.site.com:2096</code>\n"
        "مثال Marzban/Pasargad:\n"
        "<code>/addpanel marzban|فرانسه|https://panel.site.com|admin|pass</code>\n"
        "<code>/addpanel pasargad|تهران|https://pasargad.site.com|admin|pass</code>\n\n"
        "حذف پنل: <code>/delpanel آیدی</code>\n"
        "تست اتصال: <code>/testpanel آیدی</code>"
    )
    await message.answer(text)


@router.message(Command("addpanel"))
async def add_panel(message: Message):
    raw = message.text.split(maxsplit=1)
    if len(raw) < 2:
        await message.answer("فرمت: /addpanel نوع|نام|url|user|pass|inbound|sub")
        return
    parts = [x.strip() for x in raw[1].split("|")]
    if len(parts) < 5:
        await message.answer("حداقل: نوع|نام|url|user|pass لازم است.")
        return
    ptype = parts[0].lower()
    if ptype not in ("xui", "marzban", "pasargad"):
        await message.answer("نوع پنل باید xui یا marzban یا pasargad باشد.")
        return
    name, url, user, pwd = parts[1], parts[2], parts[3], parts[4]
    inbound = int(parts[5]) if len(parts) > 5 and parts[5].isdigit() else 1
    sub = parts[6] if len(parts) > 6 else ""

    await message.answer("⏳ در حال تست اتصال به پنل...")
    ok = await panel_test_connection(ptype, url, user, pwd)
    async with async_session() as session:
        panel = Panel(name=name, type=ptype, url=url, username=user, password=pwd,
                      inbound_id=inbound, sub_domain=sub, is_active=ok)
        session.add(panel)
        await session.commit()
        await session.refresh(panel)
    status = "✅ اتصال موفق و فعال شد." if ok else "⚠️ اتصال ناموفق بود؛ پنل غیرفعال ذخیره شد. اطلاعات را بررسی کنید."
    await message.answer(f"پنل #{panel.id} «{name}» ذخیره شد.\n{status}")


@router.message(Command("delpanel"))
async def del_panel(message: Message):
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("فرمت: /delpanel آیدی")
        return
    async with async_session() as session:
        panel = (await session.execute(select(Panel).where(Panel.id == int(args[1])))).scalar_one_or_none()
        if not panel:
            await message.answer("پنل یافت نشد.")
            return
        await session.delete(panel)
        await session.commit()
    await message.answer("✅ پنل حذف شد.")


@router.message(Command("testpanel"))
async def test_panel(message: Message):
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("فرمت: /testpanel آیدی")
        return
    async with async_session() as session:
        panel = (await session.execute(select(Panel).where(Panel.id == int(args[1])))).scalar_one_or_none()
    if not panel:
        await message.answer("پنل یافت نشد.")
        return
    await message.answer("⏳ در حال تست...")
    ok = await panel_test_connection(panel.type, panel.url, panel.username, panel.password)
    async with async_session() as session:
        p = (await session.execute(select(Panel).where(Panel.id == panel.id))).scalar_one_or_none()
        p.is_active = ok
        await session.commit()
    await message.answer("✅ اتصال موفق." if ok else "❌ اتصال ناموفق.")


# --------------------------------------------------------------------------- #
#  Products management
# --------------------------------------------------------------------------- #
@router.message(F.text == "🛍 مدیریت محصولات")
async def admin_products(message: Message):
    async with async_session() as session:
        products = (await session.execute(select(Product))).scalars().all()
    text = "🛍 <b>محصولات:</b>\n\n"
    if products:
        for p in products:
            mark = "🟢" if p.is_active else "🔴"
            vol = "نامحدود" if not p.volume_gb else f"{p.volume_gb}گیگ"
            text += f"{mark} #{p.id} {p.name} | {vol} | {p.days}روز | {p.price:,}ت\n"
    else:
        text += "محصولی ثبت نشده است.\n"
    text += (
        "\n<b>افزودن محصول:</b>\n"
        "<code>/addproduct نام|حجم_گیگ|روز|قیمت|panel_id|category_id</code>\n"
        "مثال: <code>/addproduct یک‌ماهه ۵۰گیگ|50|30|85000</code>\n"
        "(حجم ۰ یعنی نامحدود، panel_id و category_id اختیاری‌اند)\n\n"
        "حذف: <code>/delproduct آیدی</code>"
    )
    await message.answer(text)


@router.message(Command("addproduct"))
async def add_product(message: Message):
    raw = message.text.split(maxsplit=1)
    if len(raw) < 2:
        await message.answer("فرمت: /addproduct نام|حجم|روز|قیمت|panel_id|category_id")
        return
    parts = [x.strip() for x in raw[1].split("|")]
    if len(parts) < 4:
        await message.answer("حداقل: نام|حجم|روز|قیمت")
        return
    name = parts[0]
    try:
        vol = int(parts[1]); days = int(parts[2]); price = int(parts[3])
    except ValueError:
        await message.answer("حجم/روز/قیمت باید عدد باشند.")
        return
    panel_id = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else None
    category_id = int(parts[5]) if len(parts) > 5 and parts[5].isdigit() else None
    async with async_session() as session:
        prod = Product(name=name, volume_gb=vol, days=days, price=price,
                       panel_id=panel_id, category_id=category_id)
        session.add(prod)
        await session.commit()
        await session.refresh(prod)
    await message.answer(f"✅ محصول #{prod.id} ثبت شد.")


# --------------------------------------------------------------------------- #
#  Categories
# --------------------------------------------------------------------------- #
@router.message(F.text == "🗂 دسته‌بندی‌ها")
async def admin_categories(message: Message):
    async with async_session() as session:
        cats = (await session.execute(select(Category))).scalars().all()
    text = "🗂 <b>دسته‌بندی‌ها:</b>\n\n"
    if cats:
        for c in cats:
            mark = "🟢" if c.is_active else "🔴"
            text += f"{mark} #{c.id} {c.name}\n"
    else:
        text += "دسته‌ای ثبت نشده است.\n"
    text += ("\nافزودن: <code>/addcat نام</code>\n"
             "حذف: <code>/delcat آیدی</code>\n"
             "(محصول را با category_id به دسته وصل کنید)")
    await message.answer(text)


@router.message(Command("addcat"))
async def add_cat(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("فرمت: /addcat نام")
        return
    async with async_session() as session:
        c = Category(name=parts[1].strip())
        session.add(c); await session.commit(); await session.refresh(c)
    await message.answer(f"✅ دسته #{c.id} ثبت شد.")


@router.message(Command("delcat"))
async def del_cat(message: Message):
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("فرمت: /delcat آیدی")
        return
    async with async_session() as session:
        c = (await session.execute(select(Category).where(Category.id == int(args[1])))).scalar_one_or_none()
        if not c:
            await message.answer("یافت نشد."); return
        await session.delete(c); await session.commit()
    await message.answer("✅ حذف شد.")


# --------------------------------------------------------------------------- #
#  Discount codes
# --------------------------------------------------------------------------- #
@router.message(F.text == "🎁 کدهای تخفیف")
async def admin_discounts(message: Message):
    async with async_session() as session:
        items = (await session.execute(select(Discount))).scalars().all()
    text = "🎁 <b>کدهای تخفیف:</b>\n\n"
    if items:
        for d in items:
            mark = "🟢" if d.is_active else "🔴"
            limit = "∞" if not d.max_uses else d.max_uses
            first = " (فقط خرید اول)" if d.first_purchase_only else ""
            text += f"{mark} <code>{d.code}</code> | {d.percent}٪ | {d.used}/{limit}{first}\n"
    else:
        text += "کدی ثبت نشده است.\n"
    text += ("\nافزودن: <code>/adddisc کد|درصد|تعداد_مجاز|first(اختیاری)</code>\n"
             "مثال: <code>/adddisc OFF20|20|100</code>\n"
             "حذف: <code>/deldisc کد</code>")
    await message.answer(text)


@router.message(Command("adddisc"))
async def add_disc(message: Message):
    raw = message.text.split(maxsplit=1)
    if len(raw) < 2:
        await message.answer("فرمت: /adddisc کد|درصد|تعداد|first")
        return
    p = [x.strip() for x in raw[1].split("|")]
    if len(p) < 2 or not p[1].isdigit():
        await message.answer("حداقل: کد|درصد")
        return
    code = p[0]; percent = max(0, min(100, int(p[1])))
    max_uses = int(p[2]) if len(p) > 2 and p[2].isdigit() else 0
    first = len(p) > 3 and p[3].lower() in ("first", "1", "true")
    async with async_session() as session:
        if (await session.execute(select(Discount).where(Discount.code == code))).scalar_one_or_none():
            await message.answer("این کد قبلاً وجود دارد."); return
        session.add(Discount(code=code, percent=percent, max_uses=max_uses,
                             first_purchase_only=first))
        await session.commit()
    await message.answer(f"✅ کد تخفیف {code} ثبت شد.")


@router.message(Command("deldisc"))
async def del_disc(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("فرمت: /deldisc کد"); return
    async with async_session() as session:
        d = (await session.execute(select(Discount).where(Discount.code == args[1].strip()))).scalar_one_or_none()
        if not d:
            await message.answer("یافت نشد."); return
        await session.delete(d); await session.commit()
    await message.answer("✅ حذف شد.")


# --------------------------------------------------------------------------- #
#  Gift codes
# --------------------------------------------------------------------------- #
@router.message(F.text == "🎟 کدهای هدیه")
async def admin_giftcodes(message: Message):
    async with async_session() as session:
        items = (await session.execute(select(GiftCode))).scalars().all()
    text = "🎟 <b>کدهای هدیه:</b>\n\n"
    if items:
        for g in items:
            mark = "🟢" if g.is_active else "🔴"
            limit = "∞" if not g.max_uses else g.max_uses
            text += f"{mark} <code>{g.code}</code> | {g.amount:,}ت | {g.used}/{limit}\n"
    else:
        text += "کدی ثبت نشده است.\n"
    text += ("\nافزودن: <code>/addgift کد|مبلغ|تعداد_مجاز</code>\n"
             "مثال: <code>/addgift WELCOME|5000|0</code> (۰=نامحدود)\n"
             "حذف: <code>/delgift کد</code>")
    await message.answer(text)


@router.message(Command("addgift"))
async def add_gift(message: Message):
    raw = message.text.split(maxsplit=1)
    if len(raw) < 2:
        await message.answer("فرمت: /addgift کد|مبلغ|تعداد"); return
    p = [x.strip() for x in raw[1].split("|")]
    if len(p) < 2 or not p[1].isdigit():
        await message.answer("حداقل: کد|مبلغ"); return
    code = p[0]; amount = int(p[1])
    max_uses = int(p[2]) if len(p) > 2 and p[2].isdigit() else 1
    async with async_session() as session:
        if (await session.execute(select(GiftCode).where(GiftCode.code == code))).scalar_one_or_none():
            await message.answer("این کد قبلاً وجود دارد."); return
        session.add(GiftCode(code=code, amount=amount, max_uses=max_uses))
        await session.commit()
    await message.answer(f"✅ کد هدیه {code} ثبت شد.")


@router.message(Command("gengift"))
async def gen_gift(message: Message):
    """Bulk-generate N single-use gift (charge) cards. /gengift تعداد|مبلغ"""
    import secrets
    raw = message.text.split(maxsplit=1)
    if len(raw) < 2:
        await message.answer("فرمت: /gengift تعداد|مبلغ\nمثال: /gengift 10|50000")
        return
    p = [x.strip() for x in raw[1].split("|")]
    if len(p) < 2 or not p[0].isdigit() or not p[1].isdigit():
        await message.answer("فرمت: /gengift تعداد|مبلغ")
        return
    count = min(int(p[0]), 100)
    amount = int(p[1])
    codes = []
    async with async_session() as session:
        for _ in range(count):
            code = "GC-" + secrets.token_hex(4).upper()
            session.add(GiftCode(code=code, amount=amount, max_uses=1))
            codes.append(code)
        await session.commit()
    listing = "\n".join(f"<code>{c}</code>" for c in codes)
    await message.answer(f"✅ {count} کارت شارژ {amount:,} تومانی ساخته شد:\n\n{listing}")


@router.message(Command("delgift"))
async def del_gift(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("فرمت: /delgift کد"); return
    async with async_session() as session:
        g = (await session.execute(select(GiftCode).where(GiftCode.code == args[1].strip()))).scalar_one_or_none()
        if not g:
            await message.answer("یافت نشد."); return
        await session.delete(g); await session.commit()
    await message.answer("✅ حذف شد.")


@router.message(Command("delproduct"))
async def del_product(message: Message):
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("فرمت: /delproduct آیدی")
        return
    async with async_session() as session:
        prod = (await session.execute(select(Product).where(Product.id == int(args[1])))).scalar_one_or_none()
        if not prod:
            await message.answer("محصول یافت نشد.")
            return
        await session.delete(prod)
        await session.commit()
    await message.answer("✅ محصول حذف شد.")


# --------------------------------------------------------------------------- #
#  Receipts approval
# --------------------------------------------------------------------------- #
@router.message(F.text == "💳 رسیدهای در انتظار")
async def admin_receipts(message: Message):
    async with async_session() as session:
        receipts = (await session.execute(
            select(Receipt).where(Receipt.status == "pending").order_by(Receipt.id)
        )).scalars().all()
    if not receipts:
        await message.answer("رسید در انتظاری وجود ندارد.")
        return
    for r in receipts:
        try:
            await message.answer_photo(
                r.photo_file_id,
                caption=f"💳 رسید #{r.id}\nکاربر: {r.user_id}\nمبلغ: {r.amount:,} تومان",
                reply_markup=kb.receipt_admin_inline(r.id),
            )
        except Exception:  # noqa: BLE001
            await message.answer(
                f"💳 رسید #{r.id} | کاربر {r.user_id} | {r.amount:,} تومان",
                reply_markup=kb.receipt_admin_inline(r.id),
            )


@router.callback_query(F.data.startswith("rcpt_ok:"))
async def receipt_approve(cb: CallbackQuery):
    rid = int(cb.data.split(":")[1])
    async with async_session() as session:
        r = (await session.execute(select(Receipt).where(Receipt.id == rid))).scalar_one_or_none()
        if not r or r.status != "pending":
            await cb.answer("قبلاً رسیدگی شده.", show_alert=True)
            return
        r.status = "approved"
        r.admin_id = cb.from_user.id
        r.handled_at = datetime.utcnow()
        user = (await session.execute(select(User).where(User.id == r.user_id))).scalar_one_or_none()
        if user:
            user.balance += r.amount
        await session.commit()
    await cb.message.edit_caption(
        caption=(cb.message.caption or "") + f"\n\n✅ تایید شد ({r.amount:,} تومان اضافه شد)."
    ) if cb.message.caption else cb.message.edit_text("✅ تایید شد.")
    await cb.answer("تایید شد ✅")
    from app.reports import send_report
    await send_report(cb.bot, "payment",
                      f"💳 شارژ کارت‌به‌کارت تایید شد: کاربر {r.user_id} - {r.amount:,} تومان")
    try:
        await cb.bot.send_message(
            r.user_id, f"✅ رسید شما تایید شد و {r.amount:,} تومان به کیف پولتان اضافه شد."
        )
    except Exception:  # noqa: BLE001
        pass


@router.callback_query(F.data.startswith("rcpt_no:"))
async def receipt_reject(cb: CallbackQuery):
    rid = int(cb.data.split(":")[1])
    async with async_session() as session:
        r = (await session.execute(select(Receipt).where(Receipt.id == rid))).scalar_one_or_none()
        if not r or r.status != "pending":
            await cb.answer("قبلاً رسیدگی شده.", show_alert=True)
            return
        r.status = "rejected"
        r.admin_id = cb.from_user.id
        r.handled_at = datetime.utcnow()
        await session.commit()
    if cb.message.caption:
        await cb.message.edit_caption(caption=(cb.message.caption or "") + "\n\n❌ رد شد.")
    else:
        await cb.message.edit_text("❌ رد شد.")
    await cb.answer("رد شد")
    try:
        await cb.bot.send_message(r.user_id, "❌ متأسفانه رسید شما تایید نشد. با پشتیبانی تماس بگیرید.")
    except Exception:  # noqa: BLE001
        pass


# --------------------------------------------------------------------------- #
#  User management
# --------------------------------------------------------------------------- #
@router.message(F.text == "👤 مدیریت کاربر")
async def admin_user_menu(message: Message, state: FSMContext):
    await message.answer("آیدی عددی کاربر را بفرستید:", reply_markup=kb.cancel_inline())
    await state.set_state(AdminSG.user_lookup)


@router.message(AdminSG.user_lookup)
async def admin_user_lookup(message: Message, state: FSMContext):
    raw = sanitize_text(message.text or "")
    if not raw.isdigit():
        await message.answer("آیدی عددی نامعتبر.")
        return
    await state.clear()
    uid = int(raw)
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == uid))).scalar_one_or_none()
        if not user:
            await message.answer("کاربر یافت نشد.")
            return
        svc_count = (await session.execute(
            select(func.count()).select_from(Service).where(Service.user_id == uid)
        )).scalar()
    await message.answer(
        f"👤 کاربر <code>{uid}</code>\n"
        f"یوزرنیم: @{user.username}\n"
        f"موجودی: {user.balance:,} تومان\n"
        f"سرویس‌ها: {svc_count}\n"
        f"وضعیت: {'مسدود 🔴' if user.is_blocked else 'فعال 🟢'}\n\n"
        f"شارژ دستی: <code>/addbalance {uid} مبلغ</code>\n"
        f"مسدود/آزاد: <code>/block {uid}</code> | <code>/unblock {uid}</code>"
    )


@router.message(Command("addbalance"))
async def add_balance(message: Message):
    args = message.text.split()
    if len(args) < 3 or not args[1].isdigit() or not args[2].lstrip("-").isdigit():
        await message.answer("فرمت: /addbalance آیدی مبلغ")
        return
    uid, amount = int(args[1]), int(args[2])
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == uid))).scalar_one_or_none()
        if not user:
            await message.answer("کاربر یافت نشد.")
            return
        user.balance += amount
        await session.commit()
        bal = user.balance
    await message.answer(f"✅ موجودی کاربر {uid} اکنون {bal:,} تومان است.")
    try:
        await message.bot.send_message(uid, f"💰 موجودی کیف پول شما {amount:,} تومان تغییر کرد.")
    except Exception:  # noqa: BLE001
        pass


@router.message(Command("block"))
async def block_user(message: Message):
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        return
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == int(args[1])))).scalar_one_or_none()
        if user:
            user.is_blocked = True
            await session.commit()
    await message.answer("✅ کاربر مسدود شد.")


@router.message(Command("unblock"))
async def unblock_user(message: Message):
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        return
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == int(args[1])))).scalar_one_or_none()
        if user:
            user.is_blocked = False
            await session.commit()
    await message.answer("✅ کاربر آزاد شد.")


# --------------------------------------------------------------------------- #
#  Agent (reseller) requests
# --------------------------------------------------------------------------- #
@router.message(F.text == "🤝 درخواست‌های نمایندگی")
async def admin_agent_requests(message: Message):
    async with async_session() as session:
        reqs = (await session.execute(
            select(AgentRequest).where(AgentRequest.status == "pending").order_by(AgentRequest.id)
        )).scalars().all()
    if not reqs:
        await message.answer("درخواست نمایندگی در انتظاری وجود ندارد.")
        return
    text = "🤝 <b>درخواست‌های نمایندگی:</b>\n\n"
    for r in reqs:
        text += (f"#{r.id} | کاربر {r.user_id}\n{r.note}\n"
                 f"تایید: <code>/agentok {r.id} [درصد]</code> | رد: <code>/agentno {r.id}</code>\n\n")
    await message.answer(text)


@router.message(Command("agentok"))
async def agent_approve(message: Message):
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("فرمت: /agentok آیدی_درخواست [درصد]")
        return
    rid = int(args[1])
    percent = int(args[2]) if len(args) > 2 and args[2].isdigit() else \
        int(await get_setting("agent_default_discount", "10") or 10)
    percent = max(0, min(90, percent))
    async with async_session() as session:
        req = (await session.execute(select(AgentRequest).where(AgentRequest.id == rid))).scalar_one_or_none()
        if not req or req.status != "pending":
            await message.answer("درخواست یافت نشد یا قبلاً رسیدگی شده.")
            return
        req.status = "approved"
        user = (await session.execute(select(User).where(User.id == req.user_id))).scalar_one_or_none()
        if user:
            user.is_agent = True
            user.agent_discount = percent
        await session.commit()
        target = req.user_id
    await message.answer(f"✅ کاربر {target} نماینده شد با تخفیف {percent}٪.")
    try:
        await message.bot.send_message(
            target, f"🎉 درخواست نمایندگی شما تایید شد! از این پس روی همه خریدها {percent}٪ تخفیف دارید."
        )
    except Exception:  # noqa: BLE001
        pass


@router.message(Command("agentno"))
async def agent_reject(message: Message):
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("فرمت: /agentno آیدی_درخواست")
        return
    async with async_session() as session:
        req = (await session.execute(select(AgentRequest).where(AgentRequest.id == int(args[1])))).scalar_one_or_none()
        if not req or req.status != "pending":
            await message.answer("درخواست یافت نشد یا قبلاً رسیدگی شده.")
            return
        req.status = "rejected"
        await session.commit()
        target = req.user_id
    await message.answer("✅ درخواست رد شد.")
    try:
        await message.bot.send_message(target, "❌ متأسفانه درخواست نمایندگی شما تایید نشد.")
    except Exception:  # noqa: BLE001
        pass


# --------------------------------------------------------------------------- #
#  Broadcast
# --------------------------------------------------------------------------- #
@router.message(F.text == "📨 پیام همگانی")
async def broadcast_start(message: Message, state: FSMContext):
    await message.answer("متن پیام همگانی را ارسال کنید:", reply_markup=kb.cancel_inline())
    await state.set_state(AdminSG.broadcast)


@router.message(AdminSG.broadcast)
async def broadcast_send(message: Message, state: FSMContext):
    await state.clear()
    text = message.text or ""
    async with async_session() as session:
        users = (await session.execute(select(User.id).where(User.is_blocked == False))).scalars().all()  # noqa: E712
    sent = 0
    failed = 0
    for uid in users:
        try:
            await message.bot.send_message(uid, text)
            sent += 1
        except Exception:  # noqa: BLE001
            failed += 1
    await message.answer(f"✅ ارسال شد به {sent} نفر (ناموفق: {failed}).", reply_markup=kb.admin_menu())


# --------------------------------------------------------------------------- #
#  Settings
# --------------------------------------------------------------------------- #
SETTING_LABELS = {
    "card_number": "شماره کارت",
    "card_holder": "نام صاحب کارت",
    "support_id": "آیدی پشتیبانی (@username)",
    "report_chat_id": "آیدی گروه گزارش",
    "channel_id": "کانال عضویت اجباری",
    "test_enabled": "اکانت تست (0/1)",
    "test_volume_gb": "حجم اکانت تست (گیگ)",
    "test_days": "روز اکانت تست",
    "test_limit_per_user": "سقف تست هر کاربر",
    "referral_gift": "هدیه زیرمجموعه",
    "wheel_enabled": "گردونه شانس (0/1)",
    "min_charge": "حداقل شارژ",
    "max_charge": "حداکثر شارژ",
    "bot_status": "وضعیت ربات (on/off)",
    "welcome_text": "متن خوش‌آمد",
    "rules_text": "متن قوانین",
    "help_text": "متن آموزش",
    "join_enabled": "عضویت اجباری (0/1)",
    "join_channels": "کانال‌های اجباری (با , جدا کنید)",
    "custom_enabled": "سرویس دلخواه (0/1)",
    "custom_price_per_gb": "قیمت هر گیگ (دلخواه)",
    "custom_price_per_day": "قیمت هر روز (دلخواه)",
    "custom_min_gb": "حداقل گیگ دلخواه",
    "custom_max_gb": "حداکثر گیگ دلخواه",
    "custom_min_days": "حداقل روز دلخواه",
    "custom_max_days": "حداکثر روز دلخواه",
    "custom_panel_id": "پنل ثابت دلخواه (0=انتخاب کاربر)",
    "discount_enabled": "کد تخفیف (0/1)",
    "giftcode_enabled": "کد هدیه (0/1)",
    "agent_enabled": "سیستم نمایندگی (0/1)",
    "agent_request_price": "هزینه درخواست نمایندگی",
    "agent_default_discount": "تخفیف پیش‌فرض نماینده (٪)",
    "zarinpal_enabled": "زرین‌پال (0/1)",
    "zarinpal_merchant": "مرچنت زرین‌پال",
    "aqayepardakht_enabled": "آقای‌پرداخت (0/1)",
    "aqayepardakht_pin": "پین آقای‌پرداخت",
    "nowpayments_enabled": "NowPayments (0/1)",
    "nowpayments_api_key": "API key نوپیمنتس",
    "report_chat_id": "آیدی گروه گزارش",
    "topic_buy": "تاپیک خرید",
    "topic_payment": "تاپیک پرداخت",
    "topic_support": "تاپیک پشتیبانی",
    "topic_agent": "تاپیک نمایندگی",
    "topic_night": "تاپیک گزارش شبانه",
    "cron_enabled": "اتوماسیون/کرون (0/1)",
    "expire_reminder_days": "یادآوری انقضا (روز قبل)",
    "nightly_report": "گزارش شبانه (0/1)",
    "auto_remove_expired": "حذف خودکار منقضی‌ها (0/1)",
    "auto_backup": "بکاپ خودکار روزانه (0/1)",
}


@router.message(F.text == "⚙️ تنظیمات")
async def admin_settings(message: Message):
    lines = ["⚙️ <b>تنظیمات فعلی</b>\n"]
    for key, label in SETTING_LABELS.items():
        val = await get_setting(key, "")
        short = (val[:40] + "…") if len(val) > 40 else val
        lines.append(f"• <b>{label}</b> [<code>{key}</code>]: {short}")
    lines.append("\nبرای تغییر:\n<code>/set کلید مقدار</code>")
    lines.append("مثال: <code>/set card_number 6037-9911-1234-5678</code>")
    await message.answer("\n".join(lines))


@router.message(Command("set"))
async def set_value(message: Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("فرمت: /set کلید مقدار")
        return
    key, value = parts[1], parts[2]
    if key not in DEFAULT_SETTINGS:
        await message.answer(f"کلید نامعتبر. کلیدهای مجاز:\n" + ", ".join(DEFAULT_SETTINGS.keys()))
        return
    await set_setting(key, value)
    await message.answer(f"✅ <code>{key}</code> به‌روزرسانی شد.")


# --------------------------------------------------------------------------- #
#  Ticket reply
# --------------------------------------------------------------------------- #
@router.message(Command("reply"))
async def reply_ticket(message: Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3 or not parts[1].isdigit():
        await message.answer("فرمت: /reply آیدی_تیکت متن")
        return
    tid, answer = int(parts[1]), parts[2]
    async with async_session() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.id == tid))).scalar_one_or_none()
        if not ticket:
            await message.answer("تیکت یافت نشد.")
            return
        ticket.answer = answer
        ticket.status = "answered"
        await session.commit()
        target = ticket.user_id
    try:
        await message.bot.send_message(target, f"☎️ پاسخ پشتیبانی:\n\n{answer}")
        await message.answer("✅ پاسخ ارسال شد.")
    except Exception:  # noqa: BLE001
        await message.answer("ثبت شد ولی ارسال به کاربر ناموفق بود.")
