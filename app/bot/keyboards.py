"""All keyboards for the bot. User flows use inline keyboards so the user is
never trapped in an FSM state by a reply keyboard."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# --------------------------------------------------------------------------- #
#  Persistent main reply menu (always visible, never traps)
# --------------------------------------------------------------------------- #
BTN_BUY = "🛍 خرید سرویس"
BTN_CUSTOM = "🧩 سرویس دلخواه"
BTN_SERVICES = "📦 سرویس‌های من"
BTN_TEST = "🎁 اکانت تست"
BTN_WALLET = "💰 کیف پول"
BTN_GIFT = "🎟 کد هدیه"
BTN_REFERRAL = "👥 زیرمجموعه‌گیری"
BTN_WHEEL = "🎲 گردونه شانس"
BTN_SUPPORT = "☎️ پشتیبانی"
BTN_HELP = "📚 آموزش"
BTN_RULES = "📜 قوانین"
BTN_LANG = "🌐 زبان / Language"
BTN_HOME = "🏠 منوی اصلی"

MAIN_BUTTONS = {
    BTN_BUY, BTN_CUSTOM, BTN_SERVICES, BTN_TEST, BTN_WALLET, BTN_GIFT,
    BTN_REFERRAL, BTN_WHEEL, BTN_SUPPORT, BTN_HELP, BTN_RULES, BTN_LANG, BTN_HOME,
}


def lang_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇮🇷 فارسی", callback_data="setlang:fa"),
         InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang:en")],
    ])


def main_menu(custom_enabled: bool = False) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=BTN_BUY), KeyboardButton(text=BTN_SERVICES)]]
    if custom_enabled:
        rows.append([KeyboardButton(text=BTN_CUSTOM), KeyboardButton(text=BTN_TEST)])
        rows.append([KeyboardButton(text=BTN_WALLET), KeyboardButton(text=BTN_GIFT)])
    else:
        rows.append([KeyboardButton(text=BTN_TEST), KeyboardButton(text=BTN_WALLET)])
        rows.append([KeyboardButton(text=BTN_GIFT), KeyboardButton(text=BTN_WHEEL)])
    rows.append([KeyboardButton(text=BTN_REFERRAL), KeyboardButton(text=BTN_WHEEL)]
                if custom_enabled else [KeyboardButton(text=BTN_REFERRAL)])
    rows.append([KeyboardButton(text=BTN_SUPPORT), KeyboardButton(text=BTN_HELP)])
    rows.append([KeyboardButton(text=BTN_RULES), KeyboardButton(text=BTN_LANG)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 آمار"), KeyboardButton(text="🖥 مدیریت پنل‌ها")],
            [KeyboardButton(text="🛍 مدیریت محصولات"), KeyboardButton(text="🗂 دسته‌بندی‌ها")],
            [KeyboardButton(text="🎁 کدهای تخفیف"), KeyboardButton(text="🎟 کدهای هدیه")],
            [KeyboardButton(text="💳 رسیدهای در انتظار"), KeyboardButton(text="🤝 درخواست‌های نمایندگی")],
            [KeyboardButton(text="👤 مدیریت کاربر"), KeyboardButton(text="📨 پیام همگانی")],
            [KeyboardButton(text="🪟 پنل شیشه‌ای"), KeyboardButton(text="⚙️ تنظیمات")],
            [KeyboardButton(text="🏠 منوی اصلی")],
        ],
        resize_keyboard=True,
    )


# --------------------------------------------------------------------------- #
#  Forced join
# --------------------------------------------------------------------------- #
def join_inline(channels: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for ch in channels:
        uname = ch.lstrip("@")
        rows.append([InlineKeyboardButton(text=f"📢 عضویت در {ch}",
                                          url=f"https://t.me/{uname}")])
    rows.append([InlineKeyboardButton(text="✅ بررسی عضویت", callback_data="check_join")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# --------------------------------------------------------------------------- #
#  Buy flow inline keyboards
# --------------------------------------------------------------------------- #
def categories_inline(categories) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"🗂 {c.name}", callback_data=f"cat:{c.id}")]
            for c in categories]
    rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def products_inline(products, back: str = "home") -> InlineKeyboardMarkup:
    rows = []
    for p in products:
        vol = "نامحدود" if not p.volume_gb else f"{p.volume_gb}گیگ"
        rows.append([InlineKeyboardButton(
            text=f"{p.name} | {vol} | {p.days}روز | {p.price:,} ت",
            callback_data=f"buy:{p.id}",
        )])
    rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data=back)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def panels_inline(panels, action: str) -> InlineKeyboardMarkup:
    """action carries enough context, e.g. 'loc:<product_id>' or 'cloc'."""
    rows = [[InlineKeyboardButton(text=f"🌐 {p.name}", callback_data=f"{action}:{p.id}")]
            for p in panels]
    rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_products")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_buy_inline(product_id: int, panel_id: int, has_discount: bool) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="✅ پرداخت از کیف پول و دریافت",
                                  callback_data=f"pay:{product_id}:{panel_id}")]]
    if has_discount:
        rows.append([InlineKeyboardButton(text="🎁 ثبت کد تخفیف",
                                          callback_data=f"disc:{product_id}:{panel_id}")])
    rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_products")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_custom_inline(panel_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ پرداخت و دریافت", callback_data=f"cpay:{panel_id}")],
        [InlineKeyboardButton(text="🔙 انصراف", callback_data="cancel")],
    ])


# --------------------------------------------------------------------------- #
#  My services
# --------------------------------------------------------------------------- #
def services_inline(services) -> InlineKeyboardMarkup:
    rows = []
    for s in services:
        status = "🟢" if s.status == "active" else "🔴"
        rows.append([InlineKeyboardButton(
            text=f"{status} {s.product_name} ({s.remark})",
            callback_data=f"svc:{s.id}",
        )])
    rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def service_actions_inline(service) -> InlineKeyboardMarkup:
    toggle_text = "🔴 خاموش کردن" if service.status == "active" else "🟢 روشن کردن"
    toggle_action = "off" if service.status == "active" else "on"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 دریافت لینک/کانفیگ", callback_data=f"svc_link:{service.id}")],
        [InlineKeyboardButton(text="📊 مشاهده مصرف", callback_data=f"svc_usage:{service.id}")],
        [InlineKeyboardButton(text="♻️ تمدید سرویس", callback_data=f"svc_renew:{service.id}")],
        [InlineKeyboardButton(text="⚙️ تغییر لینک", callback_data=f"svc_changelink:{service.id}")],
        [InlineKeyboardButton(text="🎁 انتقال به کاربر دیگر", callback_data=f"svc_transfer:{service.id}")],
        [InlineKeyboardButton(text=toggle_text, callback_data=f"svc_{toggle_action}:{service.id}")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="my_services")],
    ])


def renew_products_inline(service_id: int, products) -> InlineKeyboardMarkup:
    rows = []
    for p in products:
        vol = "نامحدود" if not p.volume_gb else f"{p.volume_gb}گیگ"
        rows.append([InlineKeyboardButton(
            text=f"{p.name} | {vol} | {p.days}روز | {p.price:,} ت",
            callback_data=f"dorenew:{service_id}:{p.id}",
        )])
    rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"svc:{service_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# --------------------------------------------------------------------------- #
#  Wallet
# --------------------------------------------------------------------------- #
def wallet_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 شارژ کیف پول", callback_data="charge")],
        [InlineKeyboardButton(text="🎟 ثبت کد هدیه", callback_data="giftcode")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="home")],
    ])


def pay_methods_inline(amount: int, gateways: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="💳 کارت به کارت", callback_data=f"pm:card:{amount}")]]
    for key, label in gateways:
        rows.append([InlineKeyboardButton(text=label, callback_data=f"pm:{key}:{amount}")])
    rows.append([InlineKeyboardButton(text="✖️ انصراف", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def gateway_pay_inline(pay_url: str, payment_id: int, gateway: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 پرداخت", url=pay_url)],
        [InlineKeyboardButton(text="✅ پرداخت کردم / بررسی",
                              callback_data=f"vpay:{gateway}:{payment_id}")],
        [InlineKeyboardButton(text="✖️ انصراف", callback_data="cancel")],
    ])


def receipt_admin_inline(receipt_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ تایید", callback_data=f"rcpt_ok:{receipt_id}"),
         InlineKeyboardButton(text="❌ رد", callback_data=f"rcpt_no:{receipt_id}")],
    ])


def cancel_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✖️ انصراف", callback_data="cancel")],
    ])
