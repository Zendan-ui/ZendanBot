"""User-facing handlers. Inline-driven flows; reply main menu always escapes
any state, so the user can never get stuck ("buttons stop working")."""
from __future__ import annotations

import logging
import random

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.future import select

from app.bot import keyboards as kb
from app.bot.states import UserSG
from app.config import settings
from app.database import async_session
from app.models import (
    AgentRequest, Category, Discount, GiftCode, GiftCodeUsed, Panel, Product,
    Receipt, Service, Ticket, User, get_setting,
)
from app.security import bot_rate_limiter, sanitize_text
from app.services import (
    change_service_link, fetch_usage, provision_service,
    provision_test_service, renew_service, toggle_service,
)

router = Router()
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#  helpers
# --------------------------------------------------------------------------- #
async def custom_enabled() -> bool:
    return await get_setting("custom_enabled", "0") == "1"


async def menu_markup():
    return kb.main_menu(custom_enabled=await custom_enabled())


async def get_or_create_user(message: Message, referrer_id: int | None = None) -> User:
    uid = message.from_user.id
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == uid))).scalar_one_or_none()
        if user is None:
            user = User(
                id=uid,
                username=message.from_user.username or "",
                first_name=message.from_user.first_name or "",
                referrer_id=referrer_id if referrer_id and referrer_id != uid else None,
            )
            session.add(user)
            await session.commit()
            if user.referrer_id:
                ref = (await session.execute(
                    select(User).where(User.id == user.referrer_id)
                )).scalar_one_or_none()
                if ref:
                    gift = int(await get_setting("referral_gift", "0") or 0)
                    ref.balance += gift
                    ref.referrals_count += 1
                    await session.commit()
                    try:
                        await message.bot.send_message(
                            ref.id,
                            f"🎁 یک زیرمجموعه جدید اضافه شد! مبلغ {gift:,} تومان به کیف پول شما اضافه شد.",
                        )
                    except Exception:  # noqa: BLE001
                        pass
        return user


async def report(bot, text: str, kind: str = "buy") -> None:
    from app.reports import send_report
    await send_report(bot, kind, text)


def is_admin(user_id) -> bool:
    return str(user_id) == str(settings.ADMIN_ID)


async def send_config(message, caption: str, sub_url: str, remark: str = ""):
    """Send a config with a professional QR if possible, else just text."""
    if sub_url:
        try:
            from aiogram.types import BufferedInputFile
            from app.qr import make_config_qr
            png = make_config_qr(sub_url, title="ZendanBot", subtitle=remark or "Scan to connect")
            await message.answer_photo(
                BufferedInputFile(png, filename="config.png"),
                reply_markup=await menu_markup(),
                caption=caption,
            )
            return
        except Exception:  # noqa: BLE001
            pass
    await message.answer(caption, reply_markup=await menu_markup())


# --------------------------------------------------------------------------- #
#  Forced channel join
# --------------------------------------------------------------------------- #
async def _join_channels() -> list[str]:
    if await get_setting("join_enabled", "0") != "1":
        return []
    raw = await get_setting("join_channels", "")
    return [c.strip() for c in raw.split(",") if c.strip()]


async def not_joined_channels(bot, user_id: int) -> list[str]:
    """Return the list of channels the user has NOT joined yet."""
    missing = []
    for ch in await _join_channels():
        try:
            member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status in ("left", "kicked"):
                missing.append(ch)
        except Exception:  # noqa: BLE001
            # if we can't verify (bot not admin / wrong id) skip enforcement
            continue
    return missing


async def enforce_join(message: Message) -> bool:
    """Return True if the user is allowed to proceed; otherwise prompt to join."""
    missing = await not_joined_channels(message.bot, message.from_user.id)
    if missing:
        await message.answer(
            "📢 برای استفاده از ربات ابتدا در کانال‌های زیر عضو شوید و سپس «بررسی عضویت» را بزنید:",
            reply_markup=kb.join_inline(missing),
        )
        return False
    return True


@router.callback_query(F.data == "check_join")
async def cb_check_join(cb: CallbackQuery):
    missing = await not_joined_channels(cb.bot, cb.from_user.id)
    if missing:
        await cb.answer("هنوز در همه کانال‌ها عضو نشده‌اید.", show_alert=True)
        return
    await cb.message.delete()
    await cb.message.answer("✅ عضویت تایید شد. خوش آمدید!", reply_markup=await menu_markup())
    await cb.answer()


# --------------------------------------------------------------------------- #
#  /start
# --------------------------------------------------------------------------- #
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    if not bot_rate_limiter.is_allowed(str(message.from_user.id)):
        return
    if await get_setting("bot_status", "on") != "on" and not is_admin(message.from_user.id):
        await message.answer("🛠 ربات در حال حاضر در دست تعمیر است. لطفاً بعداً مراجعه کنید.")
        return

    referrer_id = None
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) > 1 and parts[1].strip().isdigit():
        referrer_id = int(parts[1].strip())

    await get_or_create_user(message, referrer_id)
    if not await enforce_join(message):
        return
    welcome = await get_setting("welcome_text", "")
    await message.answer(welcome, reply_markup=await menu_markup())


@router.message(Command("panel"))
async def cmd_panel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("👨‍💼 پنل مدیریت", reply_markup=kb.admin_menu())


# --------------------------------------------------------------------------- #
#  Main reply buttons — always work, always clear state
# --------------------------------------------------------------------------- #
@router.message(F.text == kb.BTN_HOME)
async def go_home(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 منوی اصلی", reply_markup=await menu_markup())


@router.message(F.text == kb.BTN_BUY)
async def menu_buy(message: Message, state: FSMContext):
    await state.clear()
    if not await enforce_join(message):
        return
    async with async_session() as session:
        cats = (await session.execute(
            select(Category).where(Category.is_active == True)  # noqa: E712
        )).scalars().all()
    if cats:
        await message.answer("🗂 یک دسته را انتخاب کنید:", reply_markup=kb.categories_inline(cats))
        return
    async with async_session() as session:
        products = (await session.execute(
            select(Product).where(Product.is_active == True)  # noqa: E712
        )).scalars().all()
    if not products:
        await message.answer("فعلاً محصولی برای فروش موجود نیست.")
        return
    await message.answer("🛍 یکی از پلن‌ها را انتخاب کنید:",
                         reply_markup=kb.products_inline(products))


@router.callback_query(F.data.startswith("cat:"))
async def cb_category(cb: CallbackQuery):
    cid = int(cb.data.split(":")[1])
    async with async_session() as session:
        products = (await session.execute(
            select(Product).where(Product.is_active == True, Product.category_id == cid)  # noqa: E712
        )).scalars().all()
    if not products:
        await cb.answer("محصولی در این دسته نیست.", show_alert=True)
        return
    await cb.message.edit_text("🛍 یکی از پلن‌ها را انتخاب کنید:",
                               reply_markup=kb.products_inline(products, back="back_cats"))
    await cb.answer()


@router.callback_query(F.data == "back_cats")
async def cb_back_cats(cb: CallbackQuery):
    async with async_session() as session:
        cats = (await session.execute(
            select(Category).where(Category.is_active == True)  # noqa: E712
        )).scalars().all()
    await cb.message.edit_text("🗂 یک دسته را انتخاب کنید:", reply_markup=kb.categories_inline(cats))
    await cb.answer()


@router.message(F.text == kb.BTN_SERVICES)
async def menu_services(message: Message, state: FSMContext):
    await state.clear()
    await _show_services(message)


async def _show_services(message: Message):
    async with async_session() as session:
        services = (await session.execute(
            select(Service).where(Service.user_id == message.from_user.id)
            .order_by(Service.id.desc())
        )).scalars().all()
    if not services:
        await message.answer("شما هنوز سرویسی ندارید. از «🛍 خرید سرویس» اقدام کنید.")
        return
    await message.answer("📦 سرویس‌های شما:", reply_markup=kb.services_inline(services))


@router.message(F.text == kb.BTN_TEST)
async def menu_test(message: Message, state: FSMContext):
    await state.clear()
    if not await enforce_join(message):
        return
    if await get_setting("test_enabled", "1") != "1":
        await message.answer("دریافت اکانت تست در حال حاضر غیرفعال است.")
        return
    uid = message.from_user.id
    limit = int(await get_setting("test_limit_per_user", "1") or 1)
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == uid))).scalar_one_or_none()
        if user and user.test_used >= limit:
            await message.answer("شما قبلاً سهمیه اکانت تست خود را دریافت کرده‌اید.")
            return
        panel = (await session.execute(
            select(Panel).where(Panel.is_active == True)  # noqa: E712
        )).scalars().first()
    if not panel:
        await message.answer("هیچ سروری برای ساخت اکانت تست پیکربندی نشده است.")
        return
    vol = int(await get_setting("test_volume_gb", "1") or 1)
    days = int(await get_setting("test_days", "1") or 1)
    await message.answer("⏳ در حال ساخت اکانت تست...")
    ok, msg, service = await provision_test_service(uid, panel, vol, days)
    if not ok:
        await message.answer(msg)
        return
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == uid))).scalar_one_or_none()
        if user:
            user.test_used += 1
            await session.commit()
    await send_config(
        message,
        f"🎁 <b>اکانت تست شما آماده شد</b>\n\n"
        f"حجم: {vol} گیگ | مدت: {days} روز\n"
        f"🔗 لینک اتصال:\n<code>{service.sub_url}</code>",
        service.sub_url, service.remark,
    )
    await report(message.bot, f"🎁 اکانت تست جدید توسط کاربر {uid}", "test")


@router.message(F.text == kb.BTN_WALLET)
async def menu_wallet(message: Message, state: FSMContext):
    await state.clear()
    async with async_session() as session:
        user = (await session.execute(
            select(User).where(User.id == message.from_user.id)
        )).scalar_one_or_none()
    bal = user.balance if user else 0
    await message.answer(
        f"💰 <b>کیف پول شما</b>\n\nموجودی: <b>{bal:,}</b> تومان",
        reply_markup=kb.wallet_inline(),
    )


@router.message(F.text == kb.BTN_REFERRAL)
async def menu_referral(message: Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    count = user.referrals_count if user else 0
    gift = await get_setting("referral_gift", "0")
    username = settings.BOT_USERNAME.lstrip("@")
    await message.answer(
        f"👥 <b>زیرمجموعه‌گیری</b>\n\n"
        f"تعداد زیرمجموعه‌ها: <b>{count}</b>\n"
        f"هدیه هر زیرمجموعه: <b>{int(gift):,}</b> تومان\n\n"
        f"🔗 لینک دعوت شما:\n<code>https://t.me/{username}?start={uid}</code>"
        + ("\n\n🤝 برای درخواست نمایندگی دستور /agent را بزنید."
           if await get_setting("agent_enabled", "0") == "1" else ""),
    )


@router.message(Command("agent"))
async def menu_agent(message: Message, state: FSMContext):
    await state.clear()
    if await get_setting("agent_enabled", "0") != "1":
        await message.answer("بخش نمایندگی در حال حاضر فعال نیست.")
        return
    uid = message.from_user.id
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == uid))).scalar_one_or_none()
        if user and user.is_agent:
            await message.answer(
                f"🤝 شما هم‌اکنون نماینده هستید.\nتخفیف شما روی همه خریدها: {user.agent_discount}٪"
            )
            return
        pending = (await session.execute(
            select(AgentRequest).where(AgentRequest.user_id == uid, AgentRequest.status == "pending")
        )).scalar_one_or_none()
    if pending:
        await message.answer("⏳ درخواست نمایندگی شما در حال بررسی است.")
        return
    price = int(await get_setting("agent_request_price", "0") or 0)
    note = f"\n\nهزینه درخواست: {price:,} تومان (از کیف پول کسر می‌شود)" if price else ""
    await message.answer(
        "🤝 <b>درخواست نمایندگی</b>\n\nچند جمله درباره خودتان و میزان فروشتان بنویسید:" + note,
        reply_markup=kb.cancel_inline(),
    )
    await state.set_state(UserSG.agent_note)


@router.message(UserSG.agent_note)
async def agent_request_submit(message: Message, state: FSMContext):
    uid = message.from_user.id
    note = sanitize_text(message.text or "", 1000)
    price = int(await get_setting("agent_request_price", "0") or 0)
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == uid))).scalar_one_or_none()
        if price and (not user or user.balance < price):
            await message.answer("موجودی کافی برای ثبت درخواست ندارید.")
            await state.clear()
            return
        if price and user:
            user.balance -= price
        req = AgentRequest(user_id=uid, note=note)
        session.add(req)
        await session.commit()
        await session.refresh(req)
    await state.clear()
    await message.answer("✅ درخواست نمایندگی شما ثبت شد و برای ادمین ارسال گردید.",
                         reply_markup=await menu_markup())
    await report(message.bot,
                 f"🤝 درخواست نمایندگی #{req.id}\nکاربر: {uid} (@{message.from_user.username})\n"
                 f"متن: {note}\n\nتایید: /agentok {req.id} [درصد]\nرد: /agentno {req.id}",
                 "agent")
    try:
        await message.bot.send_message(
            settings.ADMIN_ID,
            f"🤝 درخواست نمایندگی #{req.id} از {uid}\n{note}\n\n"
            f"تایید: /agentok {req.id} [درصد]\nرد: /agentno {req.id}",
        )
    except Exception:  # noqa: BLE001
        pass


@router.message(F.text == kb.BTN_WHEEL)
async def menu_wheel(message: Message, state: FSMContext):
    await state.clear()
    if await get_setting("wheel_enabled", "1") != "1":
        await message.answer("گردونه شانس در حال حاضر غیرفعال است.")
        return
    prize = random.choice([0, 0, 1000, 2000, 5000, 10000])
    async with async_session() as session:
        user = (await session.execute(
            select(User).where(User.id == message.from_user.id)
        )).scalar_one_or_none()
        if user and prize:
            user.balance += prize
            await session.commit()
    if prize:
        await message.answer(f"🎉 تبریک! شما {prize:,} تومان برنده شدید و به کیف پولتان اضافه شد.")
    else:
        await message.answer("😔 این بار برنده نشدید. بعداً دوباره امتحان کنید!")


@router.message(F.text == kb.BTN_SUPPORT)
async def menu_support(message: Message, state: FSMContext):
    await state.clear()
    support_id = await get_setting("support_id", "")
    extra = f"\n\nیا مستقیم به {support_id} پیام دهید." if support_id else ""
    await message.answer(
        "☎️ پیام خود را بنویسید تا برای پشتیبانی ارسال شود:" + extra,
        reply_markup=kb.cancel_inline(),
    )
    await state.set_state(UserSG.support_msg)


@router.message(UserSG.support_msg)
async def support_receive(message: Message, state: FSMContext):
    text = sanitize_text(message.text or "", 2000)
    if not text:
        await message.answer("لطفاً متن پیام را ارسال کنید.")
        return
    async with async_session() as session:
        ticket = Ticket(user_id=message.from_user.id, text=text)
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)
    await state.clear()
    await message.answer("✅ پیام شما ثبت شد. به‌زودی پاسخ داده می‌شود.", reply_markup=await menu_markup())
    await report(message.bot,
                 f"📨 تیکت جدید #{ticket.id} از {message.from_user.id}:\n{text}\n\n"
                 f"پاسخ: /reply {ticket.id} <متن>", "support")
    try:
        await message.bot.send_message(
            settings.ADMIN_ID,
            f"📨 تیکت جدید #{ticket.id} از کاربر {message.from_user.id}:\n\n{text}\n\n"
            f"برای پاسخ: /reply {ticket.id} <متن>",
        )
    except Exception:  # noqa: BLE001
        pass


@router.message(F.text == kb.BTN_HELP)
async def menu_help(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("📚 " + await get_setting("help_text", ""))


@router.message(F.text == kb.BTN_RULES)
async def menu_rules(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("📜 " + await get_setting("rules_text", ""))


@router.message(F.text == kb.BTN_LANG)
async def menu_lang(message: Message, state: FSMContext):
    await state.clear()
    from app.i18n import t
    from app.i18n import get_lang as _gl
    lang = await _gl(message.from_user.id)
    await message.answer(t("choose_lang", lang), reply_markup=kb.lang_inline())


@router.callback_query(F.data.startswith("setlang:"))
async def cb_set_lang(cb: CallbackQuery):
    from app.i18n import set_lang, t
    lang = cb.data.split(":")[1]
    await set_lang(cb.from_user.id, lang)
    await cb.message.answer(t("lang_set", lang), reply_markup=await menu_markup())
    await cb.answer()


# --------------------------------------------------------------------------- #
#  Gift code
# --------------------------------------------------------------------------- #
@router.message(F.text == kb.BTN_GIFT)
async def menu_gift(message: Message, state: FSMContext):
    await state.clear()
    if await get_setting("giftcode_enabled", "1") != "1":
        await message.answer("بخش کد هدیه غیرفعال است.")
        return
    await message.answer("🎟 کد هدیه خود را ارسال کنید:", reply_markup=kb.cancel_inline())
    await state.set_state(UserSG.gift_code)


@router.callback_query(F.data == "giftcode")
async def cb_giftcode(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("🎟 کد هدیه خود را ارسال کنید:", reply_markup=kb.cancel_inline())
    await state.set_state(UserSG.gift_code)
    await cb.answer()


@router.message(UserSG.gift_code)
async def gift_redeem(message: Message, state: FSMContext):
    code = sanitize_text(message.text or "", 100).strip()
    uid = message.from_user.id
    async with async_session() as session:
        gc = (await session.execute(
            select(GiftCode).where(GiftCode.code == code, GiftCode.is_active == True)  # noqa: E712
        )).scalar_one_or_none()
        if not gc:
            await message.answer("❌ کد نامعتبر است.")
            return
        if gc.max_uses and gc.used >= gc.max_uses:
            await message.answer("❌ ظرفیت استفاده از این کد به پایان رسیده است.")
            return
        already = (await session.execute(
            select(GiftCodeUsed).where(GiftCodeUsed.code_id == gc.id, GiftCodeUsed.user_id == uid)
        )).scalar_one_or_none()
        if already:
            await message.answer("📌 شما قبلاً از این کد استفاده کرده‌اید.")
            return
        user = (await session.execute(select(User).where(User.id == uid))).scalar_one_or_none()
        user.balance += gc.amount
        gc.used += 1
        session.add(GiftCodeUsed(code_id=gc.id, user_id=uid))
        await session.commit()
        new_bal = user.balance
    await state.clear()
    await message.answer(
        f"✅ کد هدیه اعمال شد. {gc.amount:,} تومان به کیف پول شما اضافه شد.\n"
        f"موجودی فعلی: {new_bal:,} تومان",
        reply_markup=await menu_markup(),
    )


# --------------------------------------------------------------------------- #
#  Custom service
# --------------------------------------------------------------------------- #
@router.message(F.text == kb.BTN_CUSTOM)
async def menu_custom(message: Message, state: FSMContext):
    await state.clear()
    if not await custom_enabled():
        await message.answer("سرویس دلخواه غیرفعال است.")
        return
    if not await enforce_join(message):
        return
    mn = await get_setting("custom_min_gb", "1")
    mx = await get_setting("custom_max_gb", "200")
    await message.answer(
        f"🧩 <b>سرویس دلخواه</b>\n\nحجم سرویس را به گیگابایت وارد کنید (بین {mn} و {mx}):",
        reply_markup=kb.cancel_inline(),
    )
    await state.set_state(UserSG.custom_volume)


@router.message(UserSG.custom_volume)
async def custom_volume(message: Message, state: FSMContext):
    raw = sanitize_text(message.text or "")
    if not raw.isdigit():
        await message.answer("لطفاً فقط عدد وارد کنید.")
        return
    vol = int(raw)
    mn = int(await get_setting("custom_min_gb", "1") or 1)
    mx = int(await get_setting("custom_max_gb", "200") or 200)
    if not (mn <= vol <= mx):
        await message.answer(f"حجم باید بین {mn} و {mx} گیگ باشد.")
        return
    await state.update_data(c_vol=vol)
    dmn = await get_setting("custom_min_days", "1")
    dmx = await get_setting("custom_max_days", "180")
    await message.answer(f"⏳ مدت سرویس را به روز وارد کنید (بین {dmn} و {dmx}):",
                         reply_markup=kb.cancel_inline())
    await state.set_state(UserSG.custom_days)


@router.message(UserSG.custom_days)
async def custom_days(message: Message, state: FSMContext):
    raw = sanitize_text(message.text or "")
    if not raw.isdigit():
        await message.answer("لطفاً فقط عدد وارد کنید.")
        return
    days = int(raw)
    dmn = int(await get_setting("custom_min_days", "1") or 1)
    dmx = int(await get_setting("custom_max_days", "180") or 180)
    if not (dmn <= days <= dmx):
        await message.answer(f"مدت باید بین {dmn} و {dmx} روز باشد.")
        return
    data = await state.get_data()
    vol = data.get("c_vol", 0)
    ppg = int(await get_setting("custom_price_per_gb", "1000") or 0)
    ppd = int(await get_setting("custom_price_per_day", "1000") or 0)
    price = vol * ppg + days * ppd
    await state.update_data(c_days=days, c_price=price)

    fixed = int(await get_setting("custom_panel_id", "0") or 0)
    if fixed:
        await _confirm_custom(message, fixed)
        return
    async with async_session() as session:
        panels = (await session.execute(
            select(Panel).where(Panel.is_active == True)  # noqa: E712
        )).scalars().all()
    if not panels:
        await message.answer("هیچ سروری موجود نیست.")
        await state.clear()
        return
    await message.answer(
        f"💰 قیمت محاسبه‌شده: <b>{price:,}</b> تومان\n\n🌐 موقعیت سرور را انتخاب کنید:",
        reply_markup=kb.panels_inline(panels, "cloc"),
    )


@router.callback_query(F.data.startswith("cloc:"))
async def cb_custom_loc(cb: CallbackQuery, state: FSMContext):
    panel_id = int(cb.data.split(":")[1])
    await _confirm_custom(cb.message, panel_id, state_obj=state)
    await cb.answer()


async def _confirm_custom(message: Message, panel_id: int, state_obj: FSMContext | None = None):
    # message here may be a bot message (callback) — fetch state via context isn't
    # available, so we pass values through FSM data already stored.
    await message.answer(
        "برای نهایی‌سازی روی «پرداخت و دریافت» بزنید.",
        reply_markup=kb.confirm_custom_inline(panel_id),
    )


@router.callback_query(F.data.startswith("cpay:"))
async def cb_custom_pay(cb: CallbackQuery, state: FSMContext):
    panel_id = int(cb.data.split(":")[1])
    data = await state.get_data()
    vol = data.get("c_vol")
    days = data.get("c_days")
    price = data.get("c_price")
    if not (vol and days and price is not None):
        await cb.answer("اطلاعات سرویس منقضی شده. دوباره شروع کنید.", show_alert=True)
        await state.clear()
        return
    uid = cb.from_user.id
    async with async_session() as session:
        panel = (await session.execute(select(Panel).where(Panel.id == panel_id))).scalar_one_or_none()
        user = (await session.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    if not panel or not user:
        await cb.answer("اطلاعات نامعتبر.", show_alert=True)
        return
    if user.balance < price:
        await cb.answer(f"موجودی کافی نیست. کمبود: {price - user.balance:,} تومان", show_alert=True)
        return
    await cb.message.edit_text("⏳ در حال ساخت سرویس...")
    product = Product(name=f"دلخواه {vol}گیگ-{days}روز", volume_gb=vol, days=days, price=price)
    ok, msg, service = await provision_service(uid, product, panel)
    if not ok:
        await cb.message.answer(msg, reply_markup=await menu_markup())
        await cb.answer()
        return
    async with async_session() as session:
        u = (await session.execute(select(User).where(User.id == uid))).scalar_one()
        u.balance -= price
        await session.commit()
    await state.clear()
    await send_config(
        cb.message,
        f"✅ <b>سرویس دلخواه ساخته شد</b>\n\n🔗 لینک اتصال:\n<code>{service.sub_url}</code>",
        service.sub_url, service.remark,
    )
    await cb.answer("انجام شد ✅")
    await report(cb.bot, f"🧩 سرویس دلخواه: کاربر {uid} - {price:,} تومان", "buy")


# --------------------------------------------------------------------------- #
#  Buy flow
# --------------------------------------------------------------------------- #
@router.callback_query(F.data == "home")
async def cb_home(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await cb.message.delete()
    except Exception:  # noqa: BLE001
        pass
    await cb.message.answer("🏠 منوی اصلی", reply_markup=await menu_markup())
    await cb.answer()


@router.callback_query(F.data == "back_products")
async def cb_back_products(cb: CallbackQuery):
    async with async_session() as session:
        products = (await session.execute(
            select(Product).where(Product.is_active == True)  # noqa: E712
        )).scalars().all()
    await cb.message.edit_text("🛍 یکی از پلن‌ها را انتخاب کنید:",
                               reply_markup=kb.products_inline(products))
    await cb.answer()


@router.callback_query(F.data.startswith("buy:"))
async def cb_buy(cb: CallbackQuery, state: FSMContext):
    # starting a fresh purchase: drop any stale discount from a previous one
    await state.update_data(d_code=None, d_final=None, d_percent=None, d_product=None)
    product_id = int(cb.data.split(":")[1])
    async with async_session() as session:
        product = (await session.execute(
            select(Product).where(Product.id == product_id)
        )).scalar_one_or_none()
        if not product:
            await cb.answer("محصول یافت نشد.", show_alert=True)
            return
        if product.panel_id:
            await _confirm_buy(cb, product, product.panel_id)
            return
        panels = (await session.execute(
            select(Panel).where(Panel.is_active == True)  # noqa: E712
        )).scalars().all()
    if not panels:
        await cb.answer("هیچ سروری موجود نیست.", show_alert=True)
        return
    await cb.message.edit_text("🌐 موقعیت سرور را انتخاب کنید:",
                               reply_markup=kb.panels_inline(panels, f"loc:{product_id}"))
    await cb.answer()


@router.callback_query(F.data.startswith("loc:"))
async def cb_location(cb: CallbackQuery):
    _, product_id, panel_id = cb.data.split(":")
    async with async_session() as session:
        product = (await session.execute(
            select(Product).where(Product.id == int(product_id))
        )).scalar_one_or_none()
    if not product:
        await cb.answer("محصول یافت نشد.", show_alert=True)
        return
    await _confirm_buy(cb, product, int(panel_id))


async def _confirm_buy(cb: CallbackQuery, product: Product, panel_id: int):
    async with async_session() as session:
        panel = (await session.execute(select(Panel).where(Panel.id == panel_id))).scalar_one_or_none()
        user = (await session.execute(select(User).where(User.id == cb.from_user.id))).scalar_one_or_none()
    bal = user.balance if user else 0
    vol = "نامحدود" if not product.volume_gb else f"{product.volume_gb} گیگ"
    has_disc = await get_setting("discount_enabled", "1") == "1"
    await cb.message.edit_text(
        f"🧾 <b>پیش‌فاکتور</b>\n\n"
        f"پلن: {product.name}\n"
        f"موقعیت: {panel.name if panel else '-'}\n"
        f"حجم: {vol}\n"
        f"مدت: {product.days} روز\n"
        f"قیمت: <b>{product.price:,}</b> تومان\n\n"
        f"موجودی کیف پول شما: <b>{bal:,}</b> تومان",
        reply_markup=kb.confirm_buy_inline(product.id, panel_id, has_disc),
    )
    await cb.answer()


# ---- discount during purchase ----
@router.callback_query(F.data.startswith("disc:"))
async def cb_discount(cb: CallbackQuery, state: FSMContext):
    _, product_id, panel_id = cb.data.split(":")
    await state.update_data(d_product=int(product_id), d_panel=int(panel_id))
    await cb.message.answer("🎁 کد تخفیف خود را ارسال کنید:", reply_markup=kb.cancel_inline())
    await state.set_state(UserSG.discount_code)
    await cb.answer()


@router.message(UserSG.discount_code)
async def discount_apply(message: Message, state: FSMContext):
    code = sanitize_text(message.text or "", 100).strip()
    data = await state.get_data()
    pid, panel_id = data.get("d_product"), data.get("d_panel")
    uid = message.from_user.id
    async with async_session() as session:
        d = (await session.execute(
            select(Discount).where(Discount.code == code, Discount.is_active == True)  # noqa: E712
        )).scalar_one_or_none()
        product = (await session.execute(select(Product).where(Product.id == pid))).scalar_one_or_none()
        if not d or not product:
            await message.answer("❌ کد تخفیف نامعتبر است.")
            return
        if d.max_uses and d.used >= d.max_uses:
            await message.answer("❌ ظرفیت این کد تخفیف به پایان رسیده است.")
            return
        if d.first_purchase_only:
            cnt = (await session.execute(
                select(Service).where(Service.user_id == uid)
            )).scalars().first()
            if cnt:
                await message.answer("❌ این کد فقط برای اولین خرید است.")
                return
    final = int(product.price * (100 - d.percent) / 100)
    await state.update_data(d_code=code, d_percent=d.percent, d_final=final)
    await state.set_state(None)
    await message.answer(
        f"✅ کد تخفیف {d.percent}٪ اعمال شد.\n"
        f"قیمت نهایی: <b>{final:,}</b> تومان\n\nبرای پرداخت روی دکمه زیر بزنید.",
        reply_markup=kb.confirm_buy_inline(pid, panel_id, has_discount=False),
    )


@router.callback_query(F.data.startswith("pay:"))
async def cb_pay(cb: CallbackQuery, state: FSMContext):
    _, product_id, panel_id = cb.data.split(":")
    uid = cb.from_user.id
    data = await state.get_data()
    disc_code = data.get("d_code")
    disc_final = data.get("d_final")
    disc_percent = data.get("d_percent")

    async with async_session() as session:
        product = (await session.execute(select(Product).where(Product.id == int(product_id)))).scalar_one_or_none()
        panel = (await session.execute(select(Panel).where(Panel.id == int(panel_id)))).scalar_one_or_none()
        user = (await session.execute(select(User).where(User.id == uid))).scalar_one_or_none()
        if not product or not panel or not user:
            await cb.answer("اطلاعات نامعتبر است.", show_alert=True)
            return
        price = product.price
        if disc_code and data.get("d_product") == int(product_id) and disc_final is not None:
            price = disc_final
        # agents get their personal discount on top
        if user.is_agent and user.agent_discount:
            price = int(price * (100 - user.agent_discount) / 100)
        if user.balance < price:
            await cb.answer(
                f"موجودی کافی نیست. ابتدا کیف پول را شارژ کنید.\nکمبود: {price - user.balance:,} تومان",
                show_alert=True,
            )
            return

    await cb.message.edit_text("⏳ در حال ساخت سرویس روی سرور...")
    # apply effective price to the service record
    buy_product = Product(name=product.name, volume_gb=product.volume_gb,
                          days=product.days, price=price, panel_id=product.panel_id)
    ok, msg, service = await provision_service(uid, buy_product, panel)
    if not ok:
        await cb.message.answer(msg, reply_markup=await menu_markup())
        await cb.answer()
        return

    async with async_session() as session:
        user = (await session.execute(select(User).where(User.id == uid))).scalar_one()
        user.balance -= price
        if disc_code and disc_final is not None:
            d = (await session.execute(select(Discount).where(Discount.code == disc_code))).scalar_one_or_none()
            if d:
                d.used += 1
        await session.commit()
    await state.clear()
    extra = f"\n(تخفیف {disc_percent}٪ اعمال شد)" if disc_code else ""
    await send_config(
        cb.message,
        f"✅ <b>خرید موفق</b>{extra}\n\n"
        f"پلن: {product.name}\n"
        f"🔗 لینک اتصال:\n<code>{service.sub_url}</code>\n\n"
        f"می‌توانید از «📦 سرویس‌های من» سرویس را مدیریت کنید.",
        service.sub_url, service.remark,
    )
    await cb.answer("انجام شد ✅")
    await report(cb.bot, f"🛍 خرید جدید: کاربر {uid} - {product.name} - {price:,} تومان", "buy")


# --------------------------------------------------------------------------- #
#  My services
# --------------------------------------------------------------------------- #
@router.callback_query(F.data == "my_services")
async def cb_my_services(cb: CallbackQuery):
    async with async_session() as session:
        services = (await session.execute(
            select(Service).where(Service.user_id == cb.from_user.id).order_by(Service.id.desc())
        )).scalars().all()
    if not services:
        await cb.message.edit_text("شما هنوز سرویسی ندارید.")
        await cb.answer()
        return
    await cb.message.edit_text("📦 سرویس‌های شما:", reply_markup=kb.services_inline(services))
    await cb.answer()


async def _get_user_service(service_id: int, user_id: int) -> Service | None:
    async with async_session() as session:
        svc = (await session.execute(select(Service).where(Service.id == service_id))).scalar_one_or_none()
    if svc and svc.user_id == user_id:
        return svc
    return None


@router.callback_query(F.data.startswith("svc:"))
async def cb_service(cb: CallbackQuery):
    svc = await _get_user_service(int(cb.data.split(":")[1]), cb.from_user.id)
    if not svc:
        await cb.answer("سرویس یافت نشد.", show_alert=True)
        return
    vol = "نامحدود" if not svc.volume_gb else f"{svc.volume_gb} گیگ"
    exp = svc.expire_at.strftime("%Y-%m-%d") if svc.expire_at else "-"
    await cb.message.edit_text(
        f"📦 <b>{svc.product_name}</b>\n\n"
        f"نام کاربری: <code>{svc.remark}</code>\n"
        f"حجم: {vol} | مدت: {svc.days} روز\n"
        f"انقضا: {exp}\n"
        f"تمدید شده: {svc.renew_count or 0} بار\n"
        f"وضعیت: {'فعال 🟢' if svc.status == 'active' else 'غیرفعال 🔴'}",
        reply_markup=kb.service_actions_inline(svc),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("svc_link:"))
async def cb_service_link(cb: CallbackQuery):
    svc = await _get_user_service(int(cb.data.split(":")[1]), cb.from_user.id)
    if not svc:
        await cb.answer("سرویس یافت نشد.", show_alert=True)
        return
    await cb.answer("در حال ساخت QR...")
    caption = (
        f"🔗 <b>{svc.product_name}</b>\n\n"
        f"لینک اتصال:\n<code>{svc.sub_url}</code>\n\n"
        f"📱 برای اتصال، QR بالا را در اپ خود اسکن کنید."
    )
    sub = svc.sub_url or ""
    if sub:
        try:
            from aiogram.types import BufferedInputFile
            from app.qr import make_config_qr
            png = make_config_qr(sub, title="ZendanBot", subtitle=svc.remark)
            await cb.message.answer_photo(
                BufferedInputFile(png, filename="config.png"), caption=caption
            )
            return
        except Exception:  # noqa: BLE001
            pass
    await cb.message.answer(caption)


@router.callback_query(F.data.startswith("svc_changelink:"))
async def cb_service_changelink(cb: CallbackQuery):
    svc = await _get_user_service(int(cb.data.split(":")[1]), cb.from_user.id)
    if not svc:
        await cb.answer("سرویس یافت نشد.", show_alert=True)
        return
    await cb.answer("در حال تغییر لینک...")
    ok, new_url = await change_service_link(svc)
    if not ok:
        await cb.message.answer("تغییر لینک ناموفق بود.")
        return
    await cb.message.answer(f"✅ لینک جدید:\n<code>{new_url}</code>")


@router.callback_query(F.data.startswith("svc_transfer:"))
async def cb_service_transfer(cb: CallbackQuery, state: FSMContext):
    sid = int(cb.data.split(":")[1])
    svc = await _get_user_service(sid, cb.from_user.id)
    if not svc:
        await cb.answer("سرویس یافت نشد.", show_alert=True)
        return
    await state.update_data(transfer_sid=sid)
    await cb.message.answer(
        "🎁 آیدی عددی کاربری که می‌خواهید سرویس را به او منتقل کنید بفرستید.\n"
        "(کاربر باید حداقل یک‌بار /start ربات را زده باشد)",
        reply_markup=kb.cancel_inline(),
    )
    await state.set_state(UserSG.transfer_target)
    await cb.answer()


@router.message(UserSG.transfer_target)
async def transfer_submit(message: Message, state: FSMContext):
    raw = sanitize_text(message.text or "")
    if not raw.isdigit():
        await message.answer("آیدی عددی نامعتبر است.")
        return
    target = int(raw)
    data = await state.get_data()
    sid = data.get("transfer_sid")
    uid = message.from_user.id
    if target == uid:
        await message.answer("نمی‌توانید سرویس را به خودتان منتقل کنید.")
        return
    async with async_session() as session:
        svc = (await session.execute(select(Service).where(Service.id == sid))).scalar_one_or_none()
        if not svc or svc.user_id != uid:
            await message.answer("سرویس یافت نشد.")
            await state.clear()
            return
        target_user = (await session.execute(select(User).where(User.id == target))).scalar_one_or_none()
        if not target_user:
            await message.answer("کاربر مقصد یافت نشد. باید ابتدا ربات را /start کند.")
            return
        svc.user_id = target
        await session.commit()
    await state.clear()
    await message.answer("✅ سرویس با موفقیت منتقل شد.", reply_markup=await menu_markup())
    try:
        await message.bot.send_message(
            target, f"🎁 یک سرویس از طرف کاربر {uid} به شما منتقل شد. آن را در «📦 سرویس‌های من» ببینید."
        )
    except Exception:  # noqa: BLE001
        pass
    await report(message.bot, f"🎁 انتقال سرویس #{sid}: از {uid} به {target}", "buy")


@router.callback_query(F.data.startswith("svc_usage:"))
async def cb_service_usage(cb: CallbackQuery):
    svc = await _get_user_service(int(cb.data.split(":")[1]), cb.from_user.id)
    if not svc:
        await cb.answer("سرویس یافت نشد.", show_alert=True)
        return
    await cb.answer("در حال دریافت مصرف...")
    data = await fetch_usage(svc)
    if not data:
        await cb.message.answer("امکان دریافت مصرف فعلاً وجود ندارد.")
        return
    up = data.get("up", 0); down = data.get("down", 0); total = data.get("total", 0)
    used_gb = (up + down) / (1024 ** 3)
    total_txt = f"{total / (1024 ** 3):.1f} گیگ" if total else "نامحدود"
    await cb.message.answer(
        f"📊 مصرف سرویس <b>{svc.product_name}</b>:\n\n"
        f"مصرف‌شده: {used_gb:.2f} گیگ\nکل: {total_txt}"
    )


@router.callback_query(F.data.startswith("svc_renew:"))
async def cb_service_renew(cb: CallbackQuery):
    sid = int(cb.data.split(":")[1])
    svc = await _get_user_service(sid, cb.from_user.id)
    if not svc:
        await cb.answer("سرویس یافت نشد.", show_alert=True)
        return
    async with async_session() as session:
        products = (await session.execute(
            select(Product).where(Product.is_active == True)  # noqa: E712
        )).scalars().all()
    if not products:
        await cb.answer("پلنی برای تمدید موجود نیست.", show_alert=True)
        return
    await cb.message.edit_text("♻️ پلن تمدید را انتخاب کنید:",
                               reply_markup=kb.renew_products_inline(sid, products))
    await cb.answer()


@router.callback_query(F.data.startswith("dorenew:"))
async def cb_do_renew(cb: CallbackQuery):
    _, sid, pid = cb.data.split(":")
    uid = cb.from_user.id
    svc = await _get_user_service(int(sid), uid)
    if not svc:
        await cb.answer("سرویس یافت نشد.", show_alert=True)
        return
    async with async_session() as session:
        product = (await session.execute(select(Product).where(Product.id == int(pid)))).scalar_one_or_none()
        user = (await session.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    if not product:
        await cb.answer("پلن یافت نشد.", show_alert=True)
        return
    if user.balance < product.price:
        await cb.answer(f"موجودی کافی نیست. کمبود: {product.price - user.balance:,} تومان", show_alert=True)
        return
    await cb.message.edit_text("⏳ در حال تمدید سرویس...")
    ok, msg = await renew_service(svc, product.volume_gb, product.days)
    if not ok:
        await cb.message.answer(msg, reply_markup=await menu_markup())
        await cb.answer()
        return
    async with async_session() as session:
        u = (await session.execute(select(User).where(User.id == uid))).scalar_one()
        u.balance -= product.price
        await session.commit()
    await cb.message.answer(
        f"✅ سرویس با موفقیت تمدید شد.\n+{product.volume_gb or 'نامحدود'} گیگ | +{product.days} روز",
        reply_markup=await menu_markup(),
    )
    await cb.answer("تمدید شد ✅")
    await report(cb.bot, f"♻️ تمدید: کاربر {uid} - {product.name} - {product.price:,} تومان", "buy")


@router.callback_query(F.data.startswith("svc_off:") | F.data.startswith("svc_on:"))
async def cb_service_toggle(cb: CallbackQuery):
    action, sid = cb.data.split(":")
    enable = action == "svc_on"
    svc = await _get_user_service(int(sid), cb.from_user.id)
    if not svc:
        await cb.answer("سرویس یافت نشد.", show_alert=True)
        return
    await cb.answer("در حال اعمال...")
    ok = await toggle_service(svc, enable)
    if not ok:
        await cb.message.answer("اعمال تغییر روی پنل ناموفق بود.")
        return
    async with async_session() as session:
        s = (await session.execute(select(Service).where(Service.id == svc.id))).scalar_one()
        s.status = "active" if enable else "disabled"
        await session.commit()
        await session.refresh(s)
    await cb.message.edit_reply_markup(reply_markup=kb.service_actions_inline(s))
    await cb.message.answer("✅ انجام شد." if enable else "✅ سرویس خاموش شد.")


# --------------------------------------------------------------------------- #
#  Wallet charge (card-to-card + receipt)
# --------------------------------------------------------------------------- #
@router.callback_query(F.data == "charge")
async def cb_charge(cb: CallbackQuery, state: FSMContext):
    mn = int(await get_setting("min_charge", "10000") or 10000)
    mx = int(await get_setting("max_charge", "5000000") or 5000000)
    await cb.message.answer(
        f"💳 مبلغ شارژ را به تومان وارد کنید (بین {mn:,} و {mx:,}):",
        reply_markup=kb.cancel_inline(),
    )
    await state.set_state(UserSG.charging)
    await cb.answer()


@router.message(UserSG.charging)
async def charge_amount(message: Message, state: FSMContext):
    raw = sanitize_text(message.text or "").replace(",", "").replace("،", "")
    if not raw.isdigit():
        await message.answer("لطفاً فقط عدد وارد کنید.")
        return
    amount = int(raw)
    mn = int(await get_setting("min_charge", "10000") or 10000)
    mx = int(await get_setting("max_charge", "5000000") or 5000000)
    if not (mn <= amount <= mx):
        await message.answer(f"مبلغ باید بین {mn:,} و {mx:,} تومان باشد.")
        return
    await state.update_data(amount=amount)
    from app.gateways import enabled_gateways
    gws = await enabled_gateways()
    await state.set_state(None)
    await message.answer(
        f"مبلغ شارژ: <b>{amount:,}</b> تومان\n\n💵 روش پرداخت را انتخاب کنید:",
        reply_markup=kb.pay_methods_inline(amount, gws),
    )


async def _start_card_charge(message: Message, amount: int, state: FSMContext):
    await state.update_data(amount=amount)
    card = await get_setting("card_number", "")
    holder = await get_setting("card_holder", "")
    await message.answer(
        f"💳 لطفاً مبلغ <b>{amount:,}</b> تومان را به کارت زیر واریز کنید:\n\n"
        f"شماره کارت:\n<code>{card}</code>\nبه نام: {holder}\n\n"
        f"سپس <b>عکس رسید</b> را همینجا ارسال کنید.",
        reply_markup=kb.cancel_inline(),
    )
    await state.set_state(UserSG.charge_receipt)


@router.callback_query(F.data.startswith("pm:"))
async def cb_pay_method(cb: CallbackQuery, state: FSMContext):
    _, method, amount_s = cb.data.split(":")
    amount = int(amount_s)
    uid = cb.from_user.id
    if method == "card":
        await _start_card_charge(cb.message, amount, state)
        await cb.answer()
        return

    # online gateway
    from app import gateways
    from app.models import Payment
    await cb.message.edit_text("⏳ در حال ساخت لینک پرداخت...")
    ok, ident, pay_url = False, "", ""
    if method == "zarinpal":
        ok, ident, pay_url = await gateways.zarinpal_create(amount, "شارژ کیف پول")
    elif method == "aqayepardakht":
        ok, ident, pay_url = await gateways.aqaye_create(amount)
    elif method == "nowpayments":
        order = f"u{uid}-{amount}"
        ok, ident, pay_url = await gateways.nowpayments_create(amount, order)

    if not ok:
        await cb.message.answer(
            "❌ ساخت لینک پرداخت ناموفق بود. لطفاً روش دیگری را امتحان کنید یا با پشتیبانی تماس بگیرید.",
            reply_markup=await menu_markup(),
        )
        await cb.answer()
        return

    async with async_session() as session:
        pay = Payment(user_id=uid, gateway=method, amount=amount, authority=ident)
        session.add(pay)
        await session.commit()
        await session.refresh(pay)

    await cb.message.answer(
        f"💳 مبلغ <b>{amount:,}</b> تومان\n\n"
        "روی «پرداخت» بزنید، پس از پرداخت دکمه «پرداخت کردم / بررسی» را بزنید.",
        reply_markup=kb.gateway_pay_inline(pay_url, pay.id, method),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("vpay:"))
async def cb_verify_payment(cb: CallbackQuery, state: FSMContext):
    from app import gateways
    from app.models import Payment
    from datetime import datetime as _dt
    _, method, pid = cb.data.split(":")
    async with async_session() as session:
        pay = (await session.execute(select(Payment).where(Payment.id == int(pid)))).scalar_one_or_none()
    if not pay or pay.user_id != cb.from_user.id:
        await cb.answer("پرداخت یافت نشد.", show_alert=True)
        return
    if pay.status == "paid":
        await cb.answer("این پرداخت قبلاً تایید شده است.", show_alert=True)
        return

    await cb.answer("در حال بررسی...")
    paid, ref = False, ""
    if method == "zarinpal":
        paid, ref = await gateways.zarinpal_verify(pay.authority, pay.amount)
    elif method == "aqayepardakht":
        paid, ref = await gateways.aqaye_verify(pay.authority, pay.amount)
    elif method == "nowpayments":
        status = await gateways.nowpayments_status(pay.authority)
        paid = status in ("finished", "confirmed")
        ref = status or ""

    if not paid:
        await cb.message.answer("هنوز پرداخت تایید نشده است. اگر پرداخت کرده‌اید کمی صبر و دوباره بررسی کنید.")
        return

    async with async_session() as session:
        p = (await session.execute(select(Payment).where(Payment.id == pay.id))).scalar_one()
        if p.status == "paid":
            await cb.message.answer("این پرداخت قبلاً اعمال شده است.")
            return
        p.status = "paid"
        p.ref_id = str(ref)
        p.paid_at = _dt.utcnow()
        user = (await session.execute(select(User).where(User.id == pay.user_id))).scalar_one()
        user.balance += pay.amount
        await session.commit()
        new_bal = user.balance
    await cb.message.answer(
        f"✅ پرداخت تایید شد. {pay.amount:,} تومان به کیف پول شما اضافه شد.\n"
        f"موجودی فعلی: {new_bal:,} تومان",
        reply_markup=await menu_markup(),
    )
    await report(cb.bot, f"💵 پرداخت آنلاین: کاربر {pay.user_id} - {pay.amount:,} تومان ({method})",
                 "payment")


@router.message(UserSG.charge_receipt, F.photo)
async def charge_receipt(message: Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount", 0)
    file_id = message.photo[-1].file_id
    async with async_session() as session:
        receipt = Receipt(user_id=message.from_user.id, amount=amount, photo_file_id=file_id)
        session.add(receipt)
        await session.commit()
        await session.refresh(receipt)
    await state.clear()
    await message.answer("✅ رسید شما دریافت شد و در انتظار تایید ادمین است.",
                         reply_markup=await menu_markup())
    try:
        await message.bot.send_photo(
            settings.ADMIN_ID, photo=file_id,
            caption=(f"💳 رسید جدید #{receipt.id}\n"
                     f"کاربر: {message.from_user.id} (@{message.from_user.username})\n"
                     f"مبلغ: {amount:,} تومان"),
            reply_markup=kb.receipt_admin_inline(receipt.id),
        )
    except Exception:  # noqa: BLE001
        pass


@router.message(UserSG.charge_receipt)
async def charge_receipt_wrong(message: Message):
    await message.answer("لطفاً عکس رسید را ارسال کنید (یا انصراف بزنید).")


# --------------------------------------------------------------------------- #
#  cancel
# --------------------------------------------------------------------------- #
@router.callback_query(F.data == "cancel")
async def cb_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.answer("لغو شد.", reply_markup=await menu_markup())
    await cb.answer()
