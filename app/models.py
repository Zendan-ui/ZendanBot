"""
ZendanBot database models (clean, working core).

This is a trimmed, fully-working schema that backs the rebuilt bot.
Only the tables actually used by the bot are defined here so the whole
project stays understandable and every button maps to real data.
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.future import select
from sqlalchemy.sql import func

from app.database import Base, async_session


# --------------------------------------------------------------------------- #
#  Users
# --------------------------------------------------------------------------- #
class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)            # telegram user id
    username = Column(String(255), default="")
    first_name = Column(String(255), default="")
    balance = Column(Integer, default=0)                 # toman
    is_blocked = Column(Boolean, default=False)
    test_used = Column(Integer, default=0)               # how many test accounts taken
    referrer_id = Column(BigInteger, nullable=True)
    referrals_count = Column(Integer, default=0)
    lang = Column(String(5), default="fa")
    # agent / reseller
    is_agent = Column(Boolean, default=False)
    agent_discount = Column(Integer, default=0)          # % off all purchases for this agent
    created_at = Column(DateTime, default=func.now())


# --------------------------------------------------------------------------- #
#  Panels (servers) — currently the bot drives 3X-UI / XUI panels
# --------------------------------------------------------------------------- #
class Panel(Base):
    __tablename__ = "panels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)           # shown to the user as location
    type = Column(String(50), default="xui")             # xui / marzban / ...
    url = Column(String(1000), nullable=False)           # e.g. http://1.2.3.4:54321
    username = Column(String(255), nullable=False)
    password = Column(String(255), nullable=False)
    inbound_id = Column(Integer, default=1)              # which inbound to add clients to
    sub_domain = Column(String(500), default="")         # domain:port for sub link (optional)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())


# --------------------------------------------------------------------------- #
#  Products (plans)
# --------------------------------------------------------------------------- #
class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    category_id = Column(Integer, nullable=True)         # optional grouping
    volume_gb = Column(Integer, default=0)               # 0 = unlimited
    days = Column(Integer, default=30)
    price = Column(Integer, default=0)                   # toman
    panel_id = Column(Integer, nullable=True)            # optional fixed panel
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())


# --------------------------------------------------------------------------- #
#  Services (a delivered config / invoice)
# --------------------------------------------------------------------------- #
class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    panel_id = Column(Integer, nullable=True)
    product_name = Column(String(255), default="")
    remark = Column(String(255), default="")             # username/email on the panel
    sub_url = Column(String(1000), default="")
    config_uuid = Column(String(255), default="")
    volume_gb = Column(Integer, default=0)
    days = Column(Integer, default=30)
    price = Column(Integer, default=0)
    status = Column(String(50), default="active")        # active / disabled / expired
    expire_at = Column(DateTime, nullable=True)          # computed expiry for reminders
    renew_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())


# --------------------------------------------------------------------------- #
#  Discount codes (apply at purchase) & gift codes (add balance)
# --------------------------------------------------------------------------- #
class Discount(Base):
    __tablename__ = "discounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(100), nullable=False, unique=True)
    percent = Column(Integer, default=0)                 # 0-100
    max_uses = Column(Integer, default=0)                # 0 = unlimited
    used = Column(Integer, default=0)
    first_purchase_only = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())


class GiftCode(Base):
    __tablename__ = "gift_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(100), nullable=False, unique=True)
    amount = Column(Integer, default=0)                  # toman added to wallet
    max_uses = Column(Integer, default=1)               # 0 = unlimited
    used = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())


class GiftCodeUsed(Base):
    __tablename__ = "gift_codes_used"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code_id = Column(Integer, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=func.now())


# --------------------------------------------------------------------------- #
#  Card-to-card payment receipts (admin approval flow)
# --------------------------------------------------------------------------- #
class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    amount = Column(Integer, default=0)
    photo_file_id = Column(String(1000), default="")
    status = Column(String(50), default="pending")       # pending / approved / rejected
    admin_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=func.now())
    handled_at = Column(DateTime, nullable=True)


# --------------------------------------------------------------------------- #
#  Support tickets
# --------------------------------------------------------------------------- #
class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    text = Column(Text, default="")
    answer = Column(Text, default="")
    status = Column(String(50), default="open")          # open / answered / closed
    created_at = Column(DateTime, default=func.now())


# --------------------------------------------------------------------------- #
#  Agent (reseller) requests
# --------------------------------------------------------------------------- #
class AgentRequest(Base):
    __tablename__ = "agent_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    note = Column(Text, default="")
    status = Column(String(50), default="pending")       # pending / approved / rejected
    created_at = Column(DateTime, default=func.now())


# --------------------------------------------------------------------------- #
#  Online payment transactions (Zarinpal / AqayePardakht / NowPayments)
# --------------------------------------------------------------------------- #
class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    gateway = Column(String(50), default="")             # zarinpal / aqayepardakht / nowpayments
    amount = Column(Integer, default=0)                  # toman
    authority = Column(String(255), default="")          # gateway-side id / authority / order id
    ref_id = Column(String(255), default="")             # final reference after verify
    status = Column(String(50), default="pending")       # pending / paid / failed
    created_at = Column(DateTime, default=func.now())
    paid_at = Column(DateTime, nullable=True)


# --------------------------------------------------------------------------- #
#  Key/value settings (card number, support id, prices, toggles, texts...)
# --------------------------------------------------------------------------- #
class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(255), primary_key=True)
    value = Column(Text, default="")


# --------------------------------------------------------------------------- #
#  Default settings bootstrap
# --------------------------------------------------------------------------- #
DEFAULT_SETTINGS = {
    "bot_status": "on",                 # on / off (maintenance)
    "card_number": "0000-0000-0000-0000",
    "card_holder": "نام صاحب کارت",
    "support_id": "",                   # @username for support
    "channel_id": "",                   # @channel for forced join (empty = off)
    "report_chat_id": "",               # group/channel id to receive reports
    "test_enabled": "1",
    "test_volume_gb": "1",
    "test_days": "1",
    "test_limit_per_user": "1",
    "referral_gift": "5000",
    "wheel_enabled": "1",
    "min_charge": "10000",
    "max_charge": "5000000",
    # forced channel join (comma separated @channels, empty = off)
    "join_channels": "",
    "join_enabled": "0",
    # custom service (user picks own volume/days)
    "custom_enabled": "0",
    "custom_price_per_gb": "1000",      # toman per GB
    "custom_price_per_day": "1000",     # toman per day
    "custom_min_gb": "1",
    "custom_max_gb": "200",
    "custom_min_days": "1",
    "custom_max_days": "180",
    "custom_panel_id": "0",             # 0 = let user pick location
    # discount / gift
    "discount_enabled": "1",
    "giftcode_enabled": "1",
    # agent / reseller
    "agent_enabled": "0",
    "agent_request_price": "0",          # cost (toman) to request agent (0 = free)
    "agent_default_discount": "10",      # default % discount granted on approval
    # online payment gateways
    "zarinpal_enabled": "0",
    "zarinpal_merchant": "",             # Zarinpal merchant id
    "aqayepardakht_enabled": "0",
    "aqayepardakht_pin": "",             # AqayePardakht pin
    "nowpayments_enabled": "0",
    "nowpayments_api_key": "",
    # public base url for callbacks (only needed for card-redirect gateways)
    "public_base_url": "",
    # cron / automation
    "cron_enabled": "1",
    "expire_reminder_days": "3",         # warn this many days before expiry
    "nightly_report": "1",               # send nightly summary to report chat
    "auto_remove_expired": "0",          # delete config from panel when expired
    "auto_backup": "0",                  # send daily db backup to admin
    "welcome_text": (
        "🎉 به ربات فروش کانفیگ خوش آمدید!\n\n"
        "از منوی پایین می‌توانید سرویس بخرید، اکانت تست بگیرید، "
        "کیف پول خود را شارژ کنید و سرویس‌هایتان را مدیریت کنید."
    ),
    "rules_text": "قوانین ربات هنوز تنظیم نشده است.",
    "help_text": "برای دریافت آموزش اتصال با پشتیبانی در ارتباط باشید.",
    # report topic thread ids (optional; empty = group general thread)
    "topic_buy": "",
    "topic_payment": "",
    "topic_test": "",
    "topic_support": "",
    "topic_agent": "",
    "topic_error": "",
    "topic_cron": "",
    "topic_night": "",
}


async def get_setting(key: str, default: str = "") -> str:
    async with async_session() as session:
        row = (await session.execute(select(Setting).where(Setting.key == key))).scalar_one_or_none()
        if row is None:
            return DEFAULT_SETTINGS.get(key, default)
        return row.value


async def set_setting(key: str, value: str) -> None:
    async with async_session() as session:
        row = (await session.execute(select(Setting).where(Setting.key == key))).scalar_one_or_none()
        if row is None:
            session.add(Setting(key=key, value=str(value)))
        else:
            row.value = str(value)
        await session.commit()


async def init_default_settings() -> None:
    async with async_session() as session:
        existing = {
            r.key for r in (await session.execute(select(Setting))).scalars().all()
        }
        for key, value in DEFAULT_SETTINGS.items():
            if key not in existing:
                session.add(Setting(key=key, value=value))
        await session.commit()
