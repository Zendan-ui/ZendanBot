"""Glass admin panel — a fully inline (button-driven) admin UI.

Open with /admin . Every action is a tap; for the few inputs that need text
(setting values, broadcast, add forms) we reuse the existing command system and
show the exact command to copy. This complements the command-based panel
(/panel) so the admin can work either way.

All callbacks are prefixed with "g:" and gated to the admin via this router's
middleware.
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)
from sqlalchemy import func
from sqlalchemy.future import select

from app.config import settings
from app.database import async_session
from app.models import (
    AgentRequest, Category, Discount, GiftCode, Panel, Product, Receipt,
    Service, User, get_setting, set_setting,
)

router = Router()
logger = logging.getLogger(__name__)


def is_admin(uid) -> bool:
    return str(uid) == str(settings.ADMIN_ID)


@router.message.middleware
async def _mw_msg(handler, event: Message, data):  # type: ignore
    if not is_admin(event.from_user.id):
        return
    return await handler(event, data)


@router.callback_query.middleware
async def _mw_cb(handler, event: CallbackQuery, data):  # type: ignore
    if not is_admin(event.from_user.id):
        await event.answer("دسترسی ندارید.", show_alert=True)
        return
    return await handler(event, data)


def _btn(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


# --------------------------------------------------------------------------- #
#  Home
# --------------------------------------------------------------------------- #
def home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_btn("📊 آمار", "g:stats"), _btn("🖥 پنل‌ها", "g:panels")],
        [_btn("🛍 محصولات", "g:products"), _btn("🗂 دسته‌ها", "g:cats")],
        [_btn("🎁 کد تخفیف", "g:discs"), _btn("🎟 کد هدیه", "g:gifts")],
        [_btn("💳 رسیدها", "g:receipts"), _btn("🤝 نمایندگی", "g:agents")],
        [_btn("👤 کاربران", "g:users"), _btn("📨 پیام همگانی", "g:broadcast")],
        [_btn("⚙️ تنظیمات", "g:settings:0"), _btn("🗄 بکاپ", "g:backup")],
        [_btn("🧹 ریست دیتابیس", "g:reset")],
    ])


HOME_TEXT = "🪟 <b>پنل مدیریت شیشه‌ای</b>\n\nیک بخش را انتخاب کنید:"


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(HOME_TEXT, reply_markup=home_kb())


@router.message(F.text == "🪟 پنل شیشه‌ای")
async def open_glass(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(HOME_TEXT, reply_markup=home_kb())


@router.message(Command("resetdb"))
async def cmd_resetdb(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [_btn("⚠️ بله، ریست کن", "g:reset_yes")],
        [_btn("🔙 انصراف", "g:home")],
    ])
    await message.answer(
        "🧹 ریست کامل دیتابیس؟ همه داده‌ها پاک می‌شوند.", reply_markup=kb)


@router.callback_query(F.data == "g:home")
async def cb_home(cb: CallbackQuery):
    await cb.message.edit_text(HOME_TEXT, reply_markup=home_kb())
    await cb.answer()


def back_kb(to: str = "g:home") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("🔙 بازگشت", to)]])


# --------------------------------------------------------------------------- #
#  Stats
# --------------------------------------------------------------------------- #
@router.callback_query(F.data == "g:stats")
async def cb_stats(cb: CallbackQuery):
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    day = now - timedelta(days=1)
    async with async_session() as s:
        users = (await s.execute(select(func.count()).select_from(User))).scalar()
        new24 = (await s.execute(select(func.count()).select_from(User)
                 .where(User.created_at >= day))).scalar()
        agents = (await s.execute(select(func.count()).select_from(User)
                  .where(User.is_agent == True))).scalar()  # noqa: E712
        svc = (await s.execute(select(func.count()).select_from(Service))).scalar()
        active = (await s.execute(select(func.count()).select_from(Service)
                  .where(Service.status == "active"))).scalar()
        rev = (await s.execute(select(func.coalesce(func.sum(Service.price), 0)))).scalar()
        rev24 = (await s.execute(select(func.coalesce(func.sum(Service.price), 0))
                 .where(Service.created_at >= day))).scalar()
        wallet = (await s.execute(select(func.coalesce(func.sum(User.balance), 0)))).scalar()
        pend = (await s.execute(select(func.count()).select_from(Receipt)
                .where(Receipt.status == "pending"))).scalar()
    await cb.message.edit_text(
        f"📊 <b>آمار</b>\n\n"
        f"👥 کاربران: <b>{users}</b> (۲۴س +{new24})\n"
        f"🤝 نمایندگان: {agents}\n"
        f"📦 سرویس‌ها: {svc} (فعال {active})\n"
        f"💰 فروش کل: <b>{rev:,}</b> ت | ۲۴س: {rev24:,} ت\n"
        f"👛 کیف‌پول‌ها: {wallet:,} ت\n"
        f"💳 رسید در انتظار: {pend}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [_btn("📈 نمودار فروش ۷ روز", "g:chart")],
            [_btn("🔙 بازگشت", "g:home")],
        ]),
    )
    await cb.answer()


@router.callback_query(F.data == "g:chart")
async def cb_chart(cb: CallbackQuery):
    await cb.answer("در حال رسم نمودار...")
    try:
        from aiogram.types import BufferedInputFile
        from app.chart import sales_chart_png
        png = await sales_chart_png()
        await cb.message.answer_photo(
            BufferedInputFile(png, filename="chart.png"),
            caption="📈 نمودار فروش ۷ روز اخیر",
        )
    except Exception as exc:  # noqa: BLE001
        await cb.message.answer(f"رسم نمودار ناموفق بود: {exc}")


# --------------------------------------------------------------------------- #
#  Panels
# --------------------------------------------------------------------------- #
@router.callback_query(F.data == "g:panels")
async def cb_panels(cb: CallbackQuery):
    async with async_session() as s:
        panels = (await s.execute(select(Panel))).scalars().all()
    rows = []
    for p in panels:
        mark = "🟢" if p.is_active else "🔴"
        rows.append([_btn(f"{mark} #{p.id} {p.name} ({p.type})", f"g:panel:{p.id}")])
    rows.append([_btn("➕ افزودن پنل", "g:help:addpanel")])
    rows.append([_btn("🔙 بازگشت", "g:home")])
    await cb.message.edit_text(
        "🖥 <b>پنل‌ها</b>\nروی هر پنل بزنید تا فعال/غیرفعال یا حذف شود." if panels
        else "🖥 پنلی ثبت نشده. «افزودن پنل» را بزنید.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await cb.answer()


async def _render_panel(cb: CallbackQuery, pid: int):
    async with async_session() as s:
        p = (await s.execute(select(Panel).where(Panel.id == pid))).scalar_one_or_none()
    if not p:
        await cb.answer("یافت نشد.", show_alert=True)
        return
    mark = "🟢 فعال" if p.is_active else "🔴 غیرفعال"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [_btn("🔁 تغییر وضعیت", f"g:paneltoggle:{pid}"),
         _btn("📡 تست اتصال", f"g:paneltest:{pid}")],
        [_btn("🗑 حذف", f"g:paneldel:{pid}")],
        [_btn("🔙 بازگشت", "g:panels")],
    ])
    await cb.message.edit_text(
        f"🖥 <b>{p.name}</b> (#{p.id})\nنوع: {p.type}\nآدرس: {p.url}\nوضعیت: {mark}",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("g:panel:"))
async def cb_panel(cb: CallbackQuery):
    await _render_panel(cb, int(cb.data.split(":")[2]))
    await cb.answer()


@router.callback_query(F.data.startswith("g:paneltoggle:"))
async def cb_panel_toggle(cb: CallbackQuery):
    pid = int(cb.data.split(":")[2])
    async with async_session() as s:
        p = (await s.execute(select(Panel).where(Panel.id == pid))).scalar_one_or_none()
        if p:
            p.is_active = not p.is_active
            await s.commit()
    await cb.answer("تغییر کرد ✅")
    await _render_panel(cb, pid)


@router.callback_query(F.data.startswith("g:paneltest:"))
async def cb_panel_test(cb: CallbackQuery):
    pid = int(cb.data.split(":")[2])
    await cb.answer("در حال تست...")
    from app.bot.admin import panel_test_connection
    async with async_session() as s:
        p = (await s.execute(select(Panel).where(Panel.id == pid))).scalar_one_or_none()
    if not p:
        return
    ok = await panel_test_connection(p.type, p.url, p.username, p.password)
    async with async_session() as s:
        pp = (await s.execute(select(Panel).where(Panel.id == pid))).scalar_one()
        pp.is_active = ok
        await s.commit()
    await cb.message.answer("✅ اتصال موفق." if ok else "❌ اتصال ناموفق.")


@router.callback_query(F.data.startswith("g:paneldel:"))
async def cb_panel_del(cb: CallbackQuery):
    pid = int(cb.data.split(":")[2])
    async with async_session() as s:
        p = (await s.execute(select(Panel).where(Panel.id == pid))).scalar_one_or_none()
        if p:
            await s.delete(p)
            await s.commit()
    await cb.answer("حذف شد")
    await cb_panels(cb)


# --------------------------------------------------------------------------- #
#  Products
# --------------------------------------------------------------------------- #
@router.callback_query(F.data == "g:products")
async def cb_products(cb: CallbackQuery):
    async with async_session() as s:
        items = (await s.execute(select(Product))).scalars().all()
    rows = []
    for p in items:
        mark = "🟢" if p.is_active else "🔴"
        vol = "نامحدود" if not p.volume_gb else f"{p.volume_gb}گ"
        rows.append([_btn(f"{mark} {p.name} | {vol} | {p.price:,}ت", f"g:product:{p.id}")])
    rows.append([_btn("➕ افزودن محصول", "g:help:addproduct")])
    rows.append([_btn("🔙 بازگشت", "g:home")])
    await cb.message.edit_text(
        "🛍 <b>محصولات</b>" if items else "🛍 محصولی ثبت نشده.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await cb.answer()


async def _render_product(cb: CallbackQuery, pid: int):
    async with async_session() as s:
        p = (await s.execute(select(Product).where(Product.id == pid))).scalar_one_or_none()
    if not p:
        await cb.answer("یافت نشد.", show_alert=True)
        return
    vol = "نامحدود" if not p.volume_gb else f"{p.volume_gb} گیگ"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [_btn("🔁 فعال/غیرفعال", f"g:producttoggle:{pid}"), _btn("🗑 حذف", f"g:productdel:{pid}")],
        [_btn("🔙 بازگشت", "g:products")],
    ])
    await cb.message.edit_text(
        f"🛍 <b>{p.name}</b> (#{p.id})\nحجم: {vol} | مدت: {p.days} روز\nقیمت: {p.price:,} تومان\n"
        f"وضعیت: {'فعال 🟢' if p.is_active else 'غیرفعال 🔴'}",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("g:product:"))
async def cb_product(cb: CallbackQuery):
    await _render_product(cb, int(cb.data.split(":")[2]))
    await cb.answer()


@router.callback_query(F.data.startswith("g:producttoggle:"))
async def cb_product_toggle(cb: CallbackQuery):
    pid = int(cb.data.split(":")[2])
    async with async_session() as s:
        p = (await s.execute(select(Product).where(Product.id == pid))).scalar_one_or_none()
        if p:
            p.is_active = not p.is_active
            await s.commit()
    await cb.answer("تغییر کرد ✅")
    await _render_product(cb, pid)


@router.callback_query(F.data.startswith("g:productdel:"))
async def cb_product_del(cb: CallbackQuery):
    pid = int(cb.data.split(":")[2])
    async with async_session() as s:
        p = (await s.execute(select(Product).where(Product.id == pid))).scalar_one_or_none()
        if p:
            await s.delete(p)
            await s.commit()
    await cb.answer("حذف شد")
    await cb_products(cb)


# --------------------------------------------------------------------------- #
#  Categories / Discounts / Gifts (lists + add hints)
# --------------------------------------------------------------------------- #
@router.callback_query(F.data == "g:cats")
async def cb_cats(cb: CallbackQuery):
    async with async_session() as s:
        items = (await s.execute(select(Category))).scalars().all()
    rows = [[_btn(f"🗂 #{c.id} {c.name}", f"g:catdel:{c.id}")] for c in items]
    rows.append([_btn("➕ افزودن دسته", "g:help:addcat")])
    rows.append([_btn("🔙 بازگشت", "g:home")])
    await cb.message.edit_text(
        "🗂 <b>دسته‌بندی‌ها</b>\n(روی هر دسته بزنید تا حذف شود)" if items else "🗂 دسته‌ای نیست.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("g:catdel:"))
async def cb_cat_del(cb: CallbackQuery):
    cid = int(cb.data.split(":")[2])
    async with async_session() as s:
        c = (await s.execute(select(Category).where(Category.id == cid))).scalar_one_or_none()
        if c:
            await s.delete(c)
            await s.commit()
    await cb.answer("حذف شد")
    await cb_cats(cb)


@router.callback_query(F.data == "g:discs")
async def cb_discs(cb: CallbackQuery):
    async with async_session() as s:
        items = (await s.execute(select(Discount))).scalars().all()
    rows = [[_btn(f"🎁 {d.code} ({d.percent}%)", f"g:discdel:{d.id}")] for d in items]
    rows.append([_btn("➕ افزودن کد", "g:help:adddisc")])
    rows.append([_btn("🔙 بازگشت", "g:home")])
    await cb.message.edit_text(
        "🎁 <b>کدهای تخفیف</b>\n(روی هر کد بزنید تا حذف شود)" if items else "🎁 کدی نیست.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("g:discdel:"))
async def cb_disc_del(cb: CallbackQuery):
    did = int(cb.data.split(":")[2])
    async with async_session() as s:
        d = (await s.execute(select(Discount).where(Discount.id == did))).scalar_one_or_none()
        if d:
            await s.delete(d)
            await s.commit()
    await cb.answer("حذف شد")
    await cb_discs(cb)


@router.callback_query(F.data == "g:gifts")
async def cb_gifts(cb: CallbackQuery):
    async with async_session() as s:
        items = (await s.execute(select(GiftCode).limit(30))).scalars().all()
    rows = [[_btn(f"🎟 {g.code} ({g.amount:,}ت {g.used}/{g.max_uses or '∞'})", f"g:giftdel:{g.id}")]
            for g in items]
    rows.append([_btn("➕ افزودن / انبوه", "g:help:addgift")])
    rows.append([_btn("🔙 بازگشت", "g:home")])
    await cb.message.edit_text(
        "🎟 <b>کدهای هدیه/شارژ</b>\n(روی هر کد بزنید تا حذف شود)" if items else "🎟 کدی نیست.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("g:giftdel:"))
async def cb_gift_del(cb: CallbackQuery):
    gid = int(cb.data.split(":")[2])
    async with async_session() as s:
        g = (await s.execute(select(GiftCode).where(GiftCode.id == gid))).scalar_one_or_none()
        if g:
            await s.delete(g)
            await s.commit()
    await cb.answer("حذف شد")
    await cb_gifts(cb)


# --------------------------------------------------------------------------- #
#  Receipts & Agent requests (reuse existing approve/reject callbacks)
# --------------------------------------------------------------------------- #
@router.callback_query(F.data == "g:receipts")
async def cb_receipts(cb: CallbackQuery):
    from app.bot import keyboards as kb
    async with async_session() as s:
        items = (await s.execute(
            select(Receipt).where(Receipt.status == "pending").order_by(Receipt.id)
        )).scalars().all()
    if not items:
        await cb.message.edit_text("💳 رسید در انتظاری نیست.", reply_markup=back_kb())
        await cb.answer()
        return
    await cb.message.edit_text(f"💳 {len(items)} رسید در انتظار — در پیام‌های جدا ارسال شد:",
                              reply_markup=back_kb())
    for r in items:
        try:
            await cb.message.answer_photo(
                r.photo_file_id,
                caption=f"💳 رسید #{r.id}\nکاربر: {r.user_id}\nمبلغ: {r.amount:,} ت",
                reply_markup=kb.receipt_admin_inline(r.id),
            )
        except Exception:  # noqa: BLE001
            await cb.message.answer(f"💳 رسید #{r.id} | {r.user_id} | {r.amount:,} ت",
                                    reply_markup=kb.receipt_admin_inline(r.id))
    await cb.answer()


@router.callback_query(F.data == "g:agents")
async def cb_agents(cb: CallbackQuery):
    async with async_session() as s:
        items = (await s.execute(
            select(AgentRequest).where(AgentRequest.status == "pending").order_by(AgentRequest.id)
        )).scalars().all()
    if not items:
        await cb.message.edit_text("🤝 درخواست نمایندگی در انتظاری نیست.", reply_markup=back_kb())
        await cb.answer()
        return
    rows = []
    for r in items:
        rows.append([_btn(f"✅ تایید #{r.id}", f"g:agok:{r.id}"),
                     _btn(f"❌ رد #{r.id}", f"g:agno:{r.id}")])
    rows.append([_btn("🔙 بازگشت", "g:home")])
    text = "🤝 <b>درخواست‌های نمایندگی</b>\n\n"
    for r in items:
        text += f"#{r.id} | کاربر {r.user_id}\n{r.note}\n\n"
    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


@router.callback_query(F.data.startswith("g:agok:"))
async def cb_agent_ok(cb: CallbackQuery):
    rid = int(cb.data.split(":")[2])
    percent = int(await get_setting("agent_default_discount", "10") or 10)
    async with async_session() as s:
        req = (await s.execute(select(AgentRequest).where(AgentRequest.id == rid))).scalar_one_or_none()
        if not req or req.status != "pending":
            await cb.answer("رسیدگی‌شده.", show_alert=True)
            return
        req.status = "approved"
        u = (await s.execute(select(User).where(User.id == req.user_id))).scalar_one_or_none()
        if u:
            u.is_agent = True
            u.agent_discount = percent
        await s.commit()
        target = req.user_id
    await cb.answer("تایید شد ✅")
    try:
        await cb.bot.send_message(target, f"🎉 نماینده شدید! تخفیف شما: {percent}٪")
    except Exception:  # noqa: BLE001
        pass
    await cb_agents(cb)


@router.callback_query(F.data.startswith("g:agno:"))
async def cb_agent_no(cb: CallbackQuery):
    rid = int(cb.data.split(":")[2])
    async with async_session() as s:
        req = (await s.execute(select(AgentRequest).where(AgentRequest.id == rid))).scalar_one_or_none()
        if not req or req.status != "pending":
            await cb.answer("رسیدگی‌شده.", show_alert=True)
            return
        req.status = "rejected"
        await s.commit()
        target = req.user_id
    await cb.answer("رد شد")
    try:
        await cb.bot.send_message(target, "❌ درخواست نمایندگی شما تایید نشد.")
    except Exception:  # noqa: BLE001
        pass
    await cb_agents(cb)


# --------------------------------------------------------------------------- #
#  Users (hint -> command)
# --------------------------------------------------------------------------- #
@router.callback_query(F.data == "g:users")
async def cb_users(cb: CallbackQuery):
    await cb.message.edit_text(
        "👤 <b>مدیریت کاربر</b>\n\n"
        "این کارها با دستور انجام می‌شوند (کپی کنید):\n"
        "• اطلاعات/شارژ: <code>/addbalance آیدی مبلغ</code>\n"
        "• مسدود: <code>/block آیدی</code>\n"
        "• آزاد: <code>/unblock آیدی</code>\n"
        "• پاسخ تیکت: <code>/reply آیدی_تیکت متن</code>",
        reply_markup=back_kb(),
    )
    await cb.answer()


@router.callback_query(F.data == "g:broadcast")
async def cb_broadcast(cb: CallbackQuery):
    await cb.message.edit_text(
        "📨 <b>پیام همگانی</b>\n\n"
        "از منوی «📨 پیام همگانی» در پنل کیبوردی (/panel) استفاده کنید،\n"
        "یا متن را بفرستید — این بخش به‌زودی کاملاً دکمه‌ای می‌شود.",
        reply_markup=back_kb(),
    )
    await cb.answer()


# --------------------------------------------------------------------------- #
#  Settings (paged toggles + edit hint)
# --------------------------------------------------------------------------- #
TOGGLE_KEYS = [
    "bot_status", "test_enabled", "wheel_enabled", "custom_enabled",
    "discount_enabled", "giftcode_enabled", "agent_enabled", "join_enabled",
    "zarinpal_enabled", "aqayepardakht_enabled", "nowpayments_enabled",
    "cron_enabled", "nightly_report", "auto_remove_expired", "auto_backup",
]
TOGGLE_LABELS = {
    "bot_status": "وضعیت ربات", "test_enabled": "اکانت تست", "wheel_enabled": "گردونه",
    "custom_enabled": "سرویس دلخواه", "discount_enabled": "کد تخفیف",
    "giftcode_enabled": "کد هدیه", "agent_enabled": "نمایندگی", "join_enabled": "عضویت اجباری",
    "zarinpal_enabled": "زرین‌پال", "aqayepardakht_enabled": "آقای‌پرداخت",
    "nowpayments_enabled": "NowPayments", "cron_enabled": "اتوماسیون",
    "nightly_report": "گزارش شبانه", "auto_remove_expired": "حذف منقضی‌ها",
    "auto_backup": "بکاپ خودکار",
}


def _on(key, val) -> bool:
    if key == "bot_status":
        return val == "on"
    return val == "1"


async def _render_settings(cb: CallbackQuery):
    rows = []
    for key in TOGGLE_KEYS:
        val = await get_setting(key, "")
        mark = "🟢" if _on(key, val) else "🔴"
        rows.append([_btn(f"{mark} {TOGGLE_LABELS[key]}", f"g:tog:{key}")])
    rows.append([_btn("✏️ ویرایش متنی (شماره کارت و ...)", "g:settxt")])
    rows.append([_btn("🔙 بازگشت", "g:home")])
    await cb.message.edit_text(
        "⚙️ <b>تنظیمات</b>\nروی هر مورد بزنید تا روشن/خاموش شود:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.startswith("g:settings:"))
async def cb_settings(cb: CallbackQuery):
    await _render_settings(cb)
    await cb.answer()


@router.callback_query(F.data.startswith("g:tog:"))
async def cb_toggle(cb: CallbackQuery):
    key = cb.data.split(":", 2)[2]
    val = await get_setting(key, "")
    if key == "bot_status":
        new = "off" if val == "on" else "on"
    else:
        new = "0" if val == "1" else "1"
    await set_setting(key, new)
    await cb.answer("تغییر کرد ✅")
    await _render_settings(cb)


@router.callback_query(F.data == "g:settxt")
async def cb_settxt(cb: CallbackQuery):
    await cb.message.edit_text(
        "✏️ <b>تنظیمات متنی</b> (با دستور تغییر دهید — کپی کنید):\n\n"
        "<code>/set card_number 6037-9999-8888-7777</code>\n"
        "<code>/set card_holder نام صاحب کارت</code>\n"
        "<code>/set support_id @support</code>\n"
        "<code>/set report_chat_id -1001234567890</code>\n"
        "<code>/set zarinpal_merchant XXXX</code>\n"
        "<code>/set referral_gift 5000</code>\n\n"
        "همه کلیدها با <code>/set</code> قابل تغییرند.",
        reply_markup=back_kb("g:settings:0"),
    )
    await cb.answer()


# --------------------------------------------------------------------------- #
#  Backup & Reset
# --------------------------------------------------------------------------- #
@router.callback_query(F.data == "g:backup")
async def cb_backup(cb: CallbackQuery):
    from app.cron import send_backup
    await cb.answer("در حال تهیه بکاپ...")
    ok = await send_backup(cb.bot)
    await cb.message.answer("🗄 بکاپ ارسال شد." if ok else "بکاپ فقط برای SQLite در دسترس است.")


@router.callback_query(F.data == "g:reset")
async def cb_reset(cb: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [_btn("⚠️ بله، همه‌چیز پاک شود", "g:reset_yes")],
        [_btn("🔙 انصراف", "g:home")],
    ])
    await cb.message.edit_text(
        "🧹 <b>ریست دیتابیس</b>\n\n"
        "⚠️ این کار <b>همه‌ی کاربران، سرویس‌ها، محصولات، پنل‌ها و تراکنش‌ها</b> را پاک می‌کند!\n"
        "تنظیمات پیش‌فرض دوباره ساخته می‌شوند. مطمئنید؟",
        reply_markup=kb,
    )
    await cb.answer()


@router.callback_query(F.data == "g:reset_yes")
async def cb_reset_yes(cb: CallbackQuery):
    from app.database import Base, engine
    from app.models import init_default_settings
    await cb.answer("در حال ریست...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await init_default_settings()
    await cb.message.edit_text(
        "✅ دیتابیس کاملاً ریست شد. همه‌چیز از نو.\n"
        "حالا دوباره پنل و محصول بسازید.", reply_markup=back_kb(),
    )


# --------------------------------------------------------------------------- #
#  Add-form hints (text commands)
# --------------------------------------------------------------------------- #
HELP_TEXTS = {
    "addpanel": ("➕ <b>افزودن پنل</b> — این دستور را بفرستید:\n\n"
                 "<code>/addpanel xui|نام|http://ip:54321|user|pass|1|sub.site.com:2096</code>\n"
                 "یا برای مرزبان:\n"
                 "<code>/addpanel marzban|نام|https://panel.com|user|pass</code>\n"
                 "یا برای پاسارگاد:\n"
                 "<code>/addpanel pasargad|نام|https://pasargad.com|user|pass</code>"),
    "addproduct": ("➕ <b>افزودن محصول</b>:\n\n"
                   "<code>/addproduct یک‌ماهه ۵۰گیگ|50|30|85000</code>\n"
                   "ساختار: نام|حجم(گیگ،۰=نامحدود)|روز|قیمت|panel_id|cat_id"),
    "addcat": "➕ <b>افزودن دسته</b>:\n\n<code>/addcat نام دسته</code>",
    "adddisc": ("➕ <b>کد تخفیف</b>:\n\n<code>/adddisc OFF20|20|100</code>\n"
                "ساختار: کد|درصد|تعداد_مجاز|first(اختیاری)"),
    "addgift": ("➕ <b>کد هدیه/شارژ</b>:\n\n<code>/addgift WELCOME|5000|0</code>\n"
                "ساخت انبوه کارت شارژ:\n<code>/gengift 10|50000</code>"),
}


@router.callback_query(F.data.startswith("g:help:"))
async def cb_help(cb: CallbackQuery):
    key = cb.data.split(":", 2)[2]
    back = {"addpanel": "g:panels", "addproduct": "g:products", "addcat": "g:cats",
            "adddisc": "g:discs", "addgift": "g:gifts"}.get(key, "g:home")
    await cb.message.edit_text(HELP_TEXTS.get(key, "..."), reply_markup=back_kb(back))
    await cb.answer()
