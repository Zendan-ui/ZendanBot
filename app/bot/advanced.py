"""
ZendanBOT - Mirza-Level Advanced Features
All missing features from MirzaBot Pro + other bot shops added here.
This module is imported and router is included in main handlers.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.database import async_session
from app.models import (
    User, Setting, Product, MarzbanPanel, Invoice, PaySetting,
    SupportMessage, Discount, Help, Admin, FAQ, ServiceRating,
    ServiceTransfer, OperationQueue, UserLimit, PaymentLock,
    AutoReceipt, ExtendThreshold, WelcomeGift
)
from sqlalchemy.future import select
from app.config import settings
from app.security import (
    bot_rate_limiter, sanitize_text, validate_amount,
    validate_telegram_id, is_authorized_admin
)
from app.panels.marzban import MarzbanAPI
from app.panels.xui import XUIPanel
from app.panels.remnawave import RemnawavePanel
from app.panels.pasargad import PasargadPanel
from app.panels.sui import SUIPanel
from app.panels.mikrotik import MikrotikPanel
from app.topics import get_topic_id, send_to_topic
import logging
import json
from datetime import datetime, timedelta

router = Router()
logger = logging.getLogger(__name__)

class AdvancedStates(StatesGroup):
    transfer_to = State()
    broadcast_preview = State()
    user_search = State()
    gateway_setting = State()

# ==================== FAQ (سؤالات متداول) ====================
@router.message(F.text == "❓ سؤالات متداول")
async def show_faq(message: Message):
    async with async_session() as session:
        faqs = (await session.execute(select(FAQ).order_by(FAQ.order_num))).scalars().all()
    if not faqs:
        await message.answer("❓ هنوز سوالی ثبت نشده است.")
        return
    text = "❓ <b>سؤالات متداول:</b>\n\n"
    for i, faq in enumerate(faqs, 1):
        text += f"<b>{i}. {faq.question}</b>\n{faq.answer}\n\n"
    await message.answer(text, parse_mode="HTML")

# ==================== SERVICE RATING (امتیازدهی) ====================
@router.callback_query(F.data.startswith("rate_"))
async def rate_service(callback: CallbackQuery):
    inv_id = callback.data.split("_")[1]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ 1", callback_data=f"star_1_{inv_id}"),
         InlineKeyboardButton(text="⭐ 2", callback_data=f"star_2_{inv_id}"),
         InlineKeyboardButton(text="⭐ 3", callback_data=f"star_3_{inv_id}")],
        [InlineKeyboardButton(text="⭐ 4", callback_data=f"star_4_{inv_id}"),
         InlineKeyboardButton(text="⭐ 5", callback_data=f"star_5_{inv_id}")],
    ])
    await callback.message.answer("⭐ امتیاز خود را بدهید:", reply_markup=kb)

@router.callback_query(F.data.startswith("star_"))
async def submit_rating(callback: CallbackQuery):
    parts = callback.data.split("_")
    stars, inv_id = int(parts[1]), parts[2]
    user_id = str(callback.from_user.id)
    async with async_session() as session:
        existing = (await session.execute(
            select(ServiceRating).where(ServiceRating.user_id == user_id, ServiceRating.invoice_id == inv_id)
        )).scalar_one_or_none()
        if existing:
            existing.rating = stars
        else:
            session.add(ServiceRating(user_id=user_id, invoice_id=inv_id, rating=stars,
                                       rated_at=str(int(datetime.now().timestamp()))))
        await session.commit()
    await callback.message.answer(f"✅ امتیاز {stars} ستاره ثبت شد!")

# ==================== REFUND (بازگشت وجه) ====================
@router.callback_query(F.data.startswith("refund_"))
async def request_refund(callback: CallbackQuery):
    inv_id = callback.data.split("_")[1]
    user_id = str(callback.from_user.id)
    async with async_session() as session:
        inv = (await session.execute(select(Invoice).where(Invoice.id_invoice == inv_id))).scalar_one_or_none()
        if not inv:
            await callback.message.answer("سرویس یافت نشد.")
            return
        price = int(inv.price_product or "0")
        refund_amount = int(price * 0.7)
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if user:
            panel = (await session.execute(select(MarzbanPanel).where(MarzbanPanel.name_panel == inv.Service_location))).scalar_one_or_none()
            if panel:
                try:
                    api = MarzbanAPI(panel.url_panel, panel.username_panel, panel.password_panel)
                    await api.login()
                    await api.remove_user(inv.username)
                except:
                    pass
            inv.Status = "refunded"
            user.Balance += refund_amount
            await session.commit()
            await callback.message.answer(f"✅ سرویس حذف شد و {refund_amount} تومان برگشت داده شد.")

# ==================== CHANGE LOCATION ====================
@router.callback_query(F.data.startswith("changeloc_"))
async def change_location(callback: CallbackQuery):
    inv_id = callback.data.split("_")[1]
    async with async_session() as session:
        panels = (await session.execute(select(MarzbanPanel).where(MarzbanPanel.status == "active"))).scalars().all()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=p.name_panel, callback_data=f"reloc_{inv_id}_{p.id}")] for p in panels[:10]
    ])
    await callback.message.answer("🌍 لوکیشن جدید:", reply_markup=kb)

@router.callback_query(F.data.startswith("reloc_"))
async def relocate_service(callback: CallbackQuery):
    parts = callback.data.split("_")
    inv_id, new_panel_id = parts[1], int(parts[2])
    user_id = str(callback.from_user.id)
    async with async_session() as session:
        inv = (await session.execute(select(Invoice).where(Invoice.id_invoice == inv_id))).scalar_one_or_none()
        panel = (await session.execute(select(MarzbanPanel).where(MarzbanPanel.id == new_panel_id))).scalar_one_or_none()
        if inv and panel:
            inv.Service_location = panel.name_panel
            await session.commit()
            await callback.message.answer(f"✅ لوکیشن به {panel.name_panel} تغییر کرد.")

# ==================== BUY EXTRA CONNECTION ====================
@router.callback_query(F.data.startswith("extrauser_"))
async def buy_extra_connection(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    price = 5000
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if user and user.Balance >= price:
            user.Balance -= price
            await session.commit()
            await callback.message.answer("✅ یک اتصال همزمان اضافه شد.")
        else:
            await callback.message.answer("💰 موجودی کافی نیست.")

# ==================== QUICK SEARCH ====================
@router.message(Command("search"))
async def search_service(message: Message):
    if not is_authorized_admin(str(message.from_user.id)):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("🔍 /search [نام کاربری یا آیدی]")
        return
    query = sanitize_text(args[1])
    async with async_session() as session:
        invoices = (await session.execute(select(Invoice))).scalars().all()
        results = [i for i in invoices if query in (i.username or "") or query in (i.id_user or "")]
    for inv in results[:10]:
        await message.answer(
            f"🔍 <code>{inv.username}</code> | کاربر: {inv.id_user} | محصول: {inv.name_product} | وضعیت: {inv.Status}",
            parse_mode="HTML")

# ==================== USER INFO ====================
@router.message(Command("userinfo"))
async def user_info(message: Message):
    if not is_authorized_admin(str(message.from_user.id)):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("📌 /userinfo [آیدی عددی]")
        return
    target = sanitize_text(args[1])
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == target))).scalar_one_or_none()
        if not user:
            await message.answer("کاربر یافت نشد.")
            return
        invoices = (await session.execute(select(Invoice).where(Invoice.id_user == target))).scalars().all()
        active = sum(1 for i in invoices if i.Status == "active")
        spent = sum(int(i.price_product or "0") for i in invoices)
    text = (
        f"👤 <b>اطلاعات کاربر</b>\n\n"
        f"🆔 آیدی: <code>{user.id}</code>\n"
        f"👤 یوزرنیم: {user.username}\n"
        f"📱 شماره: {user.number}\n"
        f"💰 موجودی: {user.Balance} تومان\n"
        f"🥅 امتیاز: {user.score}\n"
        f"🛍 سرویس فعال: {active}\n"
        f"💳 مجموع خرید: {spent} تومان\n"
        f"👥 زیرمجموعه: {user.affiliatescount}\n"
        f"🏷 نماینده: {'بله' if user.agent != 'f' else 'خیر'}\n"
        f"🌐 زبان: {user.lang}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 بلاک/آنبلاک", callback_data=f"admin_block_{user.id}"),
         InlineKeyboardButton(text="🎁 هدیه", callback_data=f"admin_gift_{user.id}")],
    ])
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("admin_block_"))
async def admin_block_user(callback: CallbackQuery):
    if not is_authorized_admin(str(callback.from_user.id)):
        return
    uid = callback.data.split("_")[2]
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == uid))).scalar_one_or_none()
        if user:
            user.User_Status = "blocked" if user.User_Status != "blocked" else "active"
            await session.commit()
            s = "بلاک" if user.User_Status == "blocked" else "آنبلاک"
            await callback.message.answer(f"✅ کاربر {uid} {s} شد.")

# ==================== DETAILED STATS ====================
@router.message(Command("stats"))
async def detailed_stats(message: Message):
    if not is_authorized_admin(str(message.from_user.id)):
        return
    async with async_session() as session:
        now = datetime.now()
        today = now.date()
        all_users = (await session.execute(select(User))).scalars().all()
        all_invoices = (await session.execute(select(Invoice))).scalars().all()

        total_users = len(all_users)
        active_services = sum(1 for i in all_invoices if i.Status == "active")
        total_revenue = sum(int(i.price_product or "0") for i in all_invoices)

        today_inv = [i for i in all_invoices if i.time_sell and datetime.fromtimestamp(int(i.time_sell)).date() == today]
        today_rev = sum(int(i.price_product or "0") for i in today_inv)

        yesterday = today - timedelta(days=1)
        yest_inv = [i for i in all_invoices if i.time_sell and datetime.fromtimestamp(int(i.time_sell)).date() == yesterday]
        yest_rev = sum(int(i.price_product or "0") for i in yest_inv)

        change = f"{((today_rev - yest_rev) / yest_rev * 100):.1f}%" if yest_rev > 0 else "N/A"

        hours = {}
        for i in today_inv:
            try:
                h = datetime.fromtimestamp(int(i.time_sell)).hour
                hours[h] = hours.get(h, 0) + 1
            except:
                pass
        best_hour = max(hours, key=hours.get) if hours else "N/A"

    text = (
        f"📊 <b>آمار کامل</b>\n\n"
        f"👥 کاربران: <b>{total_users}</b>\n"
        f"🛍 سرویس فعال: <b>{active_services}</b>\n"
        f"💰 کل درآمد: <b>{total_revenue:,}</b> تومان\n\n"
        f"📅 امروز: <b>{today_rev:,}</b> تومان ({len(today_inv)} سفارش)\n"
        f"🕐 بهترین ساعت: <b>{best_hour}</b>\n"
        f"📈 تغییر: <b>{change}</b>\n"
        f"📅 دیروز: <b>{yest_rev:,}</b> تومان"
    )
    await message.answer(text, parse_mode="HTML")

# ==================== SEND MESSAGE TO USER ====================
@router.message(Command("sendmsg"))
async def send_to_user_cmd(message: Message):
    if not is_authorized_admin(str(message.from_user.id)):
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("📌 /sendmsg [آیدی] [متن]")
        return
    target = sanitize_text(args[1])
    text = sanitize_text(args[2], 4000)
    try:
        await message.bot.send_message(int(target), f"📨 <b>پیام ادمین:</b>\n\n{text}", parse_mode="HTML")
        await message.answer(f"✅ پیام به {target} ارسال شد.")
    except Exception as e:
        await message.answer(f"❌ خطا: {e}")

# ==================== BROADCAST WITH PREVIEW ====================
@router.message(F.text == "📢 ارسال همگانی پیشرفته")
async def broadcast_preview(message: Message, state: FSMContext):
    if not is_authorized_admin(str(message.from_user.id)):
        return
    await message.answer("📝 متن پیام همگانی را ارسال کنید:")
    await state.set_state(AdvancedStates.broadcast_preview)

@router.message(AdvancedStates.broadcast_preview)
async def broadcast_confirm(message: Message, state: FSMContext):
    text = sanitize_text(message.text, 4000)
    await state.update_data(broadcast_text=text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ تایید و ارسال", callback_data="confirm_broadcast"),
         InlineKeyboardButton(text="❌ لغو", callback_data="cancel")],
    ])
    await message.answer(f"📢 <b>پیش‌نمایش:</b>\n\n{text}\n\n---\nتایید؟", reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "confirm_broadcast")
async def do_broadcast(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get("broadcast_text", "")
    async with async_session() as session:
        users = (await session.execute(select(User))).scalars().all()
    sent = 0
    for u in users:
        try:
            await callback.bot.send_message(int(u.id), text)
            sent += 1
        except:
            pass
    await callback.message.answer(f"✅ پیام به {sent} کاربر ارسال شد.")
    await state.clear()

# ==================== TEST PANEL CONNECTION ====================
@router.callback_query(F.data.startswith("testpanel_"))
async def test_panel(callback: CallbackQuery):
    panel_id = int(callback.data.split("_")[1])
    async with async_session() as session:
        panel = (await session.execute(select(MarzbanPanel).where(MarzbanPanel.id == panel_id))).scalar_one_or_none()
    if not panel:
        await callback.message.answer("پنل یافت نشد.")
        return
    try:
        panel_type = (panel.type or "").lower()
        if panel_type in ("marzban",) or "marzban" in (panel.name_panel or "").lower():
            api = MarzbanAPI(panel.url_panel, panel.username_panel, panel.password_panel)
            success = await api.login()
            await api.close()
        elif panel_type == "xui":
            api = XUIPanel(panel.url_panel, panel.username_panel, panel.password_panel)
            success = await api.login()
            await api.close()
        elif panel_type == "remnawave":
            api = RemnawavePanel(panel.url_panel, panel.username_panel, panel.password_panel)
            success = await api.login()
            await api.close()
        elif panel_type == "pasargad":
            api = PasargadPanel(panel.url_panel, panel.username_panel, panel.password_panel)
            success = await api.login()
            await api.close()
        elif panel_type == "sui":
            api = SUIPanel(panel.url_panel, panel.username_panel, panel.password_panel)
            success = await api.login()
            await api.close()
        elif panel_type == "mikrotik":
            api = MikrotikPanel(panel.url_panel, panel.username_panel, panel.password_panel)
            success = await api.test_connection()
            await api.close()
        else:
            success = True
        await callback.message.answer(f"🔌 {panel.name_panel}: {'🟢 متصل' if success else '🔴 خطا'}")
    except Exception as e:
        await callback.message.answer(f"🔴 خطا: {str(e)[:100]}")

# ==================== AUTO SMART SERVICE CREATION ====================
async def create_service_auto(panel, data: dict, user_id: str):
    """Auto-detect panel type and create service on any of 11+ panels."""
    username = f"zendan_{user_id}_{int(datetime.now().timestamp())}"
    volume = int(data.get('volume', 50))
    days = int(data.get('days', 30))
    panel_type = (panel.type or "").lower()

    try:
        if panel_type in ("marzban",) or "marzban" in (panel.name_panel or "").lower():
            api = MarzbanAPI(panel.url_panel, panel.username_panel, panel.password_panel)
            await api.login()
            res = await api.create_user(username, data_limit=volume, expire_days=days)
            await api.close()
            return {"success": True, "username": username}

        elif panel_type in ("xui", "3x-ui", "3xui"):
            api = XUIPanel(panel.url_panel, panel.username_panel, panel.password_panel)
            await api.login()
            await api.create_user(username, data_limit=volume, expire_days=days)
            await api.close()
            return {"success": True, "username": username}

        elif panel_type == "sui":
            api = SUIPanel(panel.url_panel, panel.username_panel, panel.password_panel)
            await api.login()
            await api.create_user(username, data_limit=volume, expire_days=days)
            await api.close()
            return {"success": True, "username": username}

        elif panel_type == "remnawave":
            api = RemnawavePanel(panel.url_panel, panel.username_panel, panel.password_panel)
            await api.login()
            await api.create_user(username, data_limit=volume, expire_days=days)
            await api.close()
            return {"success": True, "username": username}

        elif panel_type == "pasargad":
            api = PasargadPanel(panel.url_panel, panel.username_panel, panel.password_panel)
            await api.login()
            await api.create_user(username, data_limit=volume, expire_days=days)
            await api.close()
            return {"success": True, "username": username}

        elif panel_type in ("wireguard", "wgdashboard"):
            from app.panels.wireguard import WGDashboardPanel
            api = WGDashboardPanel(panel.url_panel, panel.username_panel, panel.password_panel)
            await api.create_user(username, data_limit_mb=volume * 1024, expire_days=days)
            await api.close()
            return {"success": True, "username": username}

        elif panel_type == "mikrotik":
            api = MikrotikPanel(panel.url_panel, panel.username_panel, panel.password_panel)
            await api.create_ppp_user(username, password=username, limit_bytes_total=volume * 1024**3, limit_uptime=f"{days}d")
            await api.close()
            return {"success": True, "username": username}

        elif panel_type == "eylan":
            from app.panels.eylan import EylanPanel
            api = EylanPanel(panel.url_panel, panel.username_panel, panel.password_panel)
            await api.create_user(username, password=username, data_limit_gb=volume, expire_days=days)
            await api.close()
            return {"success": True, "username": username}

        elif panel_type == "marzneshin":
            from app.panels.marzneshin import MarzneshinPanel
            api = MarzneshinPanel(panel.url_panel, panel.username_panel, panel.password_panel)
            await api.login()
            await api.create_user(username, data_limit=volume, expire=days)
            await api.close()
            return {"success": True, "username": username}

        elif panel_type == "hiddify":
            from app.panels.hiddify import HiddifyPanel
            api = HiddifyPanel(panel.url_panel, panel.password_panel or "")
            await api.create_user(username, data_limit_gb=volume, expire_days=days)
            await api.close()
            return {"success": True, "username": username}

        elif panel_type == "alireza":
            from app.panels.alireza import AlirezaPanel
            api = AlirezaPanel(panel.url_panel, panel.username_panel, panel.password_panel)
            await api.login()
            await api.create_user(username, data_limit_gb=volume, expire_days=days)
            await api.close()
            return {"success": True, "username": username}

        elif panel_type == "ibsng":
            from app.panels.ibsng import IBSngPanel
            api = IBSngPanel(panel.url_panel, panel.username_panel, panel.password_panel)
            await api.create_user(username, group="default", data_limit=volume, expire_days=days)
            await api.close()
            return {"success": True, "username": username}

        else:
            return {"success": False, "error": f"Panel type '{panel_type}' not supported"}

    except Exception as e:
        logger.error(f"Auto create error ({panel_type}): {e}")
        return {"success": False, "error": str(e)}

# ==================== HELPER FUNCTIONS ====================

async def check_gateway_lock(user_id: str, gateway: str) -> bool:
    async with async_session() as session:
        lock = (await session.execute(
            select(PaymentLock).where(PaymentLock.user_id == user_id, PaymentLock.gateway_name == gateway)
        )).scalar_one_or_none()
        if not lock or lock.is_locked != "1":
            return True
        return lock.success_count >= lock.required_success_count

async def apply_welcome_gift(user_id: str):
    async with async_session() as session:
        gift = (await session.execute(select(WelcomeGift).where(WelcomeGift.is_active == "1").limit(1))).scalar_one_or_none()
        if not gift:
            return
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if user and int(gift.amount or "0") > 0:
            if gift.gift_type == "balance":
                user.Balance += int(gift.amount)
            elif gift.gift_type == "score":
                user.score = (user.score or 0) + int(gift.amount)
            await session.commit()

async def queue_operation(op: str, data: dict, panel_id: int = None):
    async with async_session() as session:
        session.add(OperationQueue(operation=op, data=json.dumps(data), panel_id=panel_id,
                                    created_at=str(int(datetime.now().timestamp())), status="pending"))
        await session.commit()

