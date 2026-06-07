"""
Offline smoke test for ZendanBot.

Runs the dispatcher against fake Telegram updates with a mocked Bot (no
network, no real token needed beyond format). Verifies that:
 * imports + DB init + router wiring work
 * the main-menu buttons all respond
 * unknown input falls back (buttons are never "dead")
 * an FSM state never traps the user (main menu always escapes)
 * the full buy flow provisions a service and deducts balance (panel mocked)
 * admin-only handlers reject non-admins
 * card receipt approval credits the wallet

Run: python tests/smoke_test.py
"""
import asyncio
import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("BOT_TOKEN", "123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
# FIX 1: از os.environ[] استفاده کن نه setdefault تا CI env را override کند
# ADMIN_ID باید با uid=111 که در test استفاده می‌شود match کند
os.environ["ADMIN_ID"] = "111"
os.environ.setdefault("BOT_USERNAME", "testbot")
os.environ.setdefault("DEBUG", "false")
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./‌_smoke_test.db"

from aiogram import Bot, Dispatcher  # noqa: E402
from aiogram.client.default import DefaultBotProperties  # noqa: E402
from aiogram.enums import ParseMode  # noqa: E402
from aiogram.fsm.storage.memory import MemoryStorage  # noqa: E402
from aiogram.types import CallbackQuery, Chat, Message, Update  # noqa: E402
from aiogram.types import User as TgUser  # noqa: E402
from sqlalchemy import func  # noqa: E402
from sqlalchemy.future import select  # noqa: E402

CALLS: list = []
FAILURES: list = []

def check(name: str, cond: bool):
    print(("✅" if cond else "❌"), name)
    if not cond:
        FAILURES.append(name)

class FakeBot(Bot):
    async def __call__(self, method, request_timeout=None):  # type: ignore[override]
        CALLS.append(method)
        if type(method).__name__ in ("SendMessage", "SendPhoto", "EditMessageText", "EditMessageCaption"):
            return Message(
                message_id=999, date=datetime.now(),
                chat=Chat(id=getattr(method, "chat_id", 1), type="private"),
                from_user=TgUser(id=999, is_bot=True, first_name="bot"),
                text=getattr(method, "text", None) or getattr(method, "caption", ""),
            )
        return True

async def main() -> None:
    if os.path.exists("./‌_smoke_test.db"):
        os.remove("./‌_smoke_test.db")

    from app.bot import keyboards as kb
    from app.bot.admin import router as admin_router
    from app.bot.fallback import router as fallback_router
    from app.bot.glass import router as glass_router
    from app.bot.handlers import router as user_router
    from app.database import async_session, init_db
    from app.models import Panel, Product, Receipt, Service, User, init_default_settings

    await init_db()
    await init_default_settings()
    async with async_session() as s:
        s.add(Product(name="plan1", volume_gb=50, days=30, price=85000))
        s.add(Panel(name="DE", type="xui", url="http://x", username="a", password="b"))
        s.add(User(id=222, username="ali", first_name="Ali", balance=200000))
        await s.commit()

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(glass_router)
    dp.include_router(admin_router)
    dp.include_router(user_router)
    dp.include_router(fallback_router)
    bot = FakeBot(token=os.environ["BOT_TOKEN"],
                  default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    def msg(text, uid=222):
        return Message(message_id=1, date=datetime.now(), chat=Chat(id=uid, type="private"),
                       from_user=TgUser(id=uid, is_bot=False, first_name="Ali", username="ali"),
                       text=text)

    async def feed(text, uid=222):
        CALLS.clear()
        await dp.feed_update(bot, Update(update_id=1, message=msg(text, uid)))
        out = [c for c in CALLS if type(c).__name__ in ("SendMessage", "SendPhoto")]
        return out[-1] if out else None

    def cbq(data, uid=222):
        m = Message(message_id=5, date=datetime.now(), chat=Chat(id=uid, type="private"),
                    from_user=TgUser(id=999, is_bot=True, first_name="bot"), text="prev")
        return CallbackQuery(id="1", from_user=TgUser(id=uid, is_bot=False, first_name="Ali"),
                             chat_instance="ci", data=data, message=m)

    async def feed_cb(data, uid=222):
        CALLS.clear()
        await dp.feed_update(bot, Update(update_id=9, callback_query=cbq(data, uid)))
        return [type(c).__name__ for c in CALLS]

    from app.models import set_setting
    await set_setting("wheel_enabled", "0")  # keep balance deterministic

    # --- main menu ---
    check("/start responds", bool(await feed("/start")))
    for label in (kb.BTN_BUY, kb.BTN_WALLET, kb.BTN_SERVICES, kb.BTN_REFERRAL,
                  kb.BTN_WHEEL, kb.BTN_HELP, kb.BTN_RULES):
        check(f"menu button responds: {label}", bool(await feed(label)))

    # --- fallback (no dead buttons) ---
    check("unknown input falls back", bool(await feed("xyz random")))

    # --- state trap fixed ---
    await feed(kb.BTN_SUPPORT)  # enters support state
    r = await feed(kb.BTN_BUY)  # must still work
    check("main menu escapes FSM state", bool(r))

    # --- full buy flow with mocked panel ---
    with patch("app.services.XUIPanel") as MockPanel:
        inst = AsyncMock()
        inst.create_client = AsyncMock(return_value={"success": True, "uuid": "u1",
                                                      "sub_url": "http://x/sub/abc"})
        MockPanel.return_value.__aenter__.return_value = inst
        await feed_cb("buy:1")
        calls = await feed_cb("pay:1:1")
        check("pay flow sends config", "SendMessage" in calls or "SendPhoto" in calls)
        async with async_session() as s:
            svcs = (await s.execute(select(Service))).scalars().all()
            user = (await s.execute(select(User).where(User.id == 222))).scalar_one()
            check("service created", len(svcs) == 1 and svcs[0].sub_url == "http://x/sub/abc")
            check("balance deducted", user.balance == 200000 - 85000)

    # --- admin gating ---
    check("admin stats works for admin", bool(await feed("📊 آمار", uid=111)))
    check("admin stats blocked for non-admin", not bool(await feed("📊 آمار", uid=222)))

    # --- receipt approval ---
    async with async_session() as s:
        s.add(Receipt(user_id=222, amount=50000, photo_file_id="f", status="pending"))
        await s.commit()
    rid = None
    async with async_session() as s:
        rid = (await s.execute(select(Receipt))).scalars().all()[0].id
    await feed_cb(f"rcpt_ok:{rid}", uid=111)
    async with async_session() as s:
        user = (await s.execute(select(User).where(User.id == 222))).scalar_one()
        check("receipt approval credits wallet", user.balance == (200000 - 85000) + 50000)

    # --- gift code ---
    from app.models import Discount, GiftCode
    async with async_session() as s:
        s.add(GiftCode(code="WELCOME", amount=7000, max_uses=0))
        await s.commit()
    # FIX 2: fresh read از balance قبل از gift
    async with async_session() as s:
        user = (await s.execute(select(User).where(User.id == 222))).scalar_one()
        bal_before = user.balance
    await feed(kb.BTN_GIFT)  # opens gift state
    await feed("WELCOME")  # redeem
    async with async_session() as s:
        user = (await s.execute(select(User).where(User.id == 222))).scalar_one()
        check("gift code credits wallet", user.balance == bal_before + 7000)
    # reuse blocked
    async with async_session() as s:
        user = (await s.execute(select(User).where(User.id == 222))).scalar_one()
        bal2 = user.balance
    await feed(kb.BTN_GIFT)
    await feed("WELCOME")
    async with async_session() as s:
        user = (await s.execute(select(User).where(User.id == 222))).scalar_one()
        check("gift code cannot be reused", user.balance == bal2)

    # --- discount during purchase ---
    async with async_session() as s:
        s.add(Discount(code="OFF50", percent=50, max_uses=0))
        await s.commit()
    async with async_session() as s:
        user = (await s.execute(select(User).where(User.id == 222))).scalar_one()
        bal_b = user.balance
    with patch("app.services.XUIPanel") as MockPanel:
        inst = AsyncMock()
        inst.create_client = AsyncMock(return_value={"success": True, "uuid": "u2",
                                                      "sub_url": "http://x/sub/d"})
        MockPanel.return_value.__aenter__.return_value = inst
        await feed_cb("buy:1")
        await feed_cb("disc:1:1")  # ask for code
        await feed("OFF50")  # apply 50%
        await feed_cb("pay:1:1")  # pay discounted
    async with async_session() as s:
        user = (await s.execute(select(User).where(User.id == 222))).scalar_one()
        # product price 85000, 50% off => 42500
        check("discount applied at purchase", user.balance == bal_b - 42500)

    # --- custom service ---
    from app.models import set_setting as _set
    await _set("custom_enabled", "1")
    await _set("custom_price_per_gb", "1000")
    await _set("custom_price_per_day", "500")
    # FIX 3: fresh read از balance قبل از custom
    async with async_session() as s:
        user = (await s.execute(select(User).where(User.id == 222))).scalar_one()
        bal_c = user.balance
    with patch("app.services.XUIPanel") as MockPanel:
        inst = AsyncMock()
        inst.create_client = AsyncMock(return_value={"success": True, "uuid": "u3",
                                                      "sub_url": "http://x/sub/c"})
        MockPanel.return_value.__aenter__.return_value = inst
        await feed(kb.BTN_CUSTOM)
        await feed("10")   # 10 GB
        await feed("20")   # 20 days -> price = 10*1000 + 20*500 = 20000
        await feed_cb("cloc:1")  # pick location
        await feed_cb("cpay:1")  # pay
    async with async_session() as s:
        user = (await s.execute(select(User).where(User.id == 222))).scalar_one()
        check("custom service charged correctly", user.balance == bal_c - 20000)

    # --- renew ---
    # FIX 4: fresh read از svc و balance قبل از renew
    async with async_session() as s:
        svc = (await s.execute(select(Service).where(Service.user_id == 222))).scalars().first()
        svc_id = svc.id
        user = (await s.execute(select(User).where(User.id == 222))).scalar_one()
        bal_r = user.balance
    with patch("app.services.XUIPanel") as MockPanel:
        inst = AsyncMock()
        inst.renew_client = AsyncMock(return_value={"success": True})
        MockPanel.return_value.__aenter__.return_value = inst
        await feed_cb(f"svc_renew:{svc_id}")
        calls = await feed_cb(f"dorenew:{svc_id}:1")
    async with async_session() as s:
        user = (await s.execute(select(User).where(User.id == 222))).scalar_one()
        svc2 = (await s.execute(select(Service).where(Service.id == svc_id))).scalar_one()
        check("renew charged & counter increased",
              user.balance == bal_r - 85000 and (svc2.renew_count or 0) >= 1)

    # --- forced join blocks non-members ---
    await _set("join_enabled", "1")
    await _set("join_channels", "@somechannel")
    # bot.get_chat_member is not implemented in FakeBot -> treated as "can't verify" -> allowed.
    # So instead verify the prompt path by making get_chat_member say 'left'.
    async def fake_member(*a, **k):
        class M:  # noqa
            status = "left"
        return M()
    bot.get_chat_member = fake_member  # type: ignore
    r = await feed(kb.BTN_BUY)
    check("forced join prompt shown", bool(r) and "عضویت" in (r.text or ""))
    await _set("join_enabled", "0")
    bot.get_chat_member = None  # type: ignore  # restore (FakeBot has none)

    # --- agent: enable, request, admin approve, agent discount on purchase ---
    from app.models import AgentRequest, Payment
    await _set("agent_enabled", "1")
    await _set("agent_request_price", "0")
    await feed("/agent")
    await feed("سلام من فروشنده‌ام")  # submit request note
    async with async_session() as s:
        req = (await s.execute(select(AgentRequest))).scalars().first()
        check("agent request created", req is not None and req.status == "pending")
        req_id = req.id if req else None
    # FIX 5: admin approve از uid=111 (که ADMIN_ID="111" است)
    await feed(f"/agentok {req_id} 25", uid=111)
    async with async_session() as s:
        user = (await s.execute(select(User).where(User.id == 222))).scalar_one()
        check("agent approved with discount", user.is_agent and user.agent_discount == 25)
    # top up so the agent purchase has enough funds
    async with async_session() as s:
        u = (await s.execute(select(User).where(User.id == 222))).scalar_one()
        u.balance = 500000
        await s.commit()
    # purchase now applies agent discount (85000 -> 25% off = 63750)
    async with async_session() as s:
        user = (await s.execute(select(User).where(User.id == 222))).scalar_one()
        bal_a = user.balance
    with patch("app.services.XUIPanel") as MockPanel:
        inst = AsyncMock()
        inst.create_client = AsyncMock(return_value={"success": True, "uuid": "ua",
                                                      "sub_url": "http://x/sub/a"})
        MockPanel.return_value.__aenter__.return_value = inst
        await feed_cb("buy:1")
        await feed_cb("pay:1:1")
    async with async_session() as s:
        user = (await s.execute(select(User).where(User.id == 222))).scalar_one()
        check("agent discount applied on purchase", user.balance == bal_a - 63750)

    # --- online gateway charge (zarinpal) end-to-end, mocked ---
    await _set("zarinpal_enabled", "1")
    await _set("zarinpal_merchant", "x" * 36)
    async with async_session() as s:
        user = (await s.execute(select(User).where(User.id == 222))).scalar_one()
        bal_g = user.balance
    import app.gateways as gw

    async def fake_create(amount, desc):  # noqa
        return True, "AUTH123", "https://pay"
    async def fake_verify(auth, amount):  # noqa
        return True, "REF999"
    gw.zarinpal_create = fake_create  # type: ignore
    gw.zarinpal_verify = fake_verify  # type: ignore
    await feed_cb("charge")  # opens charge -> but charge asks amount via state
    # emulate amount entry then method choice
    from app.bot.states import UserSG
    await dp.feed_update(bot, Update(update_id=1, message=msg("50000")))  # amount -> shows methods
    calls = await feed_cb("pm:zarinpal:50000")
    check("gateway pay link shown", "SendMessage" in calls)
    async with async_session() as s:
        pay = (await s.execute(select(Payment))).scalars().first()
        check("payment record created", pay is not None and pay.status == "pending")
        pay_id = pay.id if pay else None
    await feed_cb(f"vpay:zarinpal:{pay_id}")
    async with async_session() as s:
        user = (await s.execute(select(User).where(User.id == 222))).scalar_one()
        pay = (await s.execute(select(Payment).where(Payment.id == pay_id))).scalar_one()
        check("gateway verify credits wallet", user.balance == bal_g + 50000 and pay.status == "paid")
    await _set("zarinpal_enabled", "0")

    # --- cron jobs run without error ---
    import app.cron as cron
    from datetime import datetime as _dt, timedelta as _td
    # make one service expire soon and one already expired
    async with async_session() as s:
        svcs = (await s.execute(select(Service).where(Service.user_id == 222))).scalars().all()
        if svcs:
            # FIX 6: استفاده از datetime.now(datetime.UTC) به جای utcnow() برای رفع DeprecationWarning
            import datetime as _datetime
            svcs[0].expire_at = _datetime.datetime.now(_datetime.timezone.utc).replace(tzinfo=None) + _td(days=1)
            svcs[0].status = "active"
        if len(svcs) > 1:
            svcs[1].expire_at = _datetime.datetime.now(_datetime.timezone.utc).replace(tzinfo=None) - _td(days=1)
            svcs[1].status = "active"
        await s.commit()
    try:
        await cron.expiry_reminder(bot)
        await cron.mark_and_remove(bot)
        await cron.nightly_report(bot)
        cron_ok = True
    except Exception as exc:  # noqa
        print("cron error:", exc); cron_ok = False
    check("cron jobs run", cron_ok)
    async with async_session() as s:
        expired = (await s.execute(
            select(Service).where(Service.status == "expired")
        )).scalars().all()
        check("expired service marked", len(expired) >= 1)

    # --- language switch (fa/en) ---
    from app.i18n import get_lang
    await feed(kb.BTN_LANG)
    await feed_cb("setlang:en")
    check("language switched to en", (await get_lang(222)) == "en")
    await feed_cb("setlang:fa")
    check("language switched back to fa", (await get_lang(222)) == "fa")

    # --- Marzban panel provisioning (driver factory) ---
    from app.models import Panel as PanelM
    from app.services import provision_service, get_driver
    async with async_session() as s:
        s.add(PanelM(name="MZ", type="marzban", url="http://m", username="a", password="b"))
        await s.commit()
    async with async_session() as s:
        mz = (await s.execute(select(PanelM).where(PanelM.type == "marzban"))).scalar_one()
    check("marzban driver resolves", get_driver(mz) is not None)
    with patch("app.services.MarzbanPanel") as MockM:
        inst = AsyncMock()
        inst.create_client = AsyncMock(return_value={"success": True, "uuid": "mzuser",
                                                      "sub_url": "http://m/sub/x"})
        MockM.return_value.__aenter__.return_value = inst
        prod = Product(name="mzplan", volume_gb=10, days=10, price=0)
        ok, _msg, svc = await provision_service(222, prod, mz)
        check("marzban service provisioned", ok and svc and svc.sub_url == "http://m/sub/x")

    # --- service transfer between users ---
    async with async_session() as s:
        s.add(User(id=333, username="bob", first_name="Bob"))
        await s.commit()
    async with async_session() as s:
        tsvc = (await s.execute(select(Service).where(Service.user_id == 222))).scalars().first()
        tsvc_id = tsvc.id
    await feed_cb(f"svc_transfer:{tsvc_id}")
    await feed("333")  # transfer to user 333
    async with async_session() as s:
        moved = (await s.execute(select(Service).where(Service.id == tsvc_id))).scalar_one()
        check("service transferred to other user", moved.user_id == 333)

    # --- bulk gift card generation (admin) ---
    from app.models import GiftCode
    await feed("/gengift 5|30000", uid=111)
    async with async_session() as s:
        gc_count = (await s.execute(
            select(func.count()).select_from(GiftCode).where(GiftCode.code.like("GC-%"))
        )).scalar()
        check("bulk gift cards generated", gc_count == 5)

    # --- backup (sqlite) runs ---
    import app.cron as cron2
    sent = {"docs": 0}
    async def fake_doc(*a, **k):  # noqa
        sent["docs"] += 1
        return True
    bot.send_document = fake_doc  # type: ignore
    ok_b = await cron2.send_backup(bot)
    check("backup sends db file", ok_b and sent["docs"] == 1)

    # --- glass (inline) admin panel ---
    bot.send_document = None  # type: ignore
    r = await feed("/admin", uid=111)
    check("glass panel opens for admin", bool(r) and "شیشه" in (r.text or ""))
    # non-admin cannot open
    r = await feed("/admin", uid=222)
    check("glass panel blocked for non-admin", not bool(r))
    # navigate to stats then back home (callbacks edit message)
    calls = await feed_cb("g:stats", uid=111)
    check("glass stats navigates", "EditMessageText" in calls)
    calls = await feed_cb("g:settings:0", uid=111)
    check("glass settings navigates", "EditMessageText" in calls)
    # toggle a setting via glass
    from app.models import get_setting as _get
    before = await _get("wheel_enabled", "1")
    await feed_cb("g:tog:wheel_enabled", uid=111)
    after = await _get("wheel_enabled", "1")
    check("glass toggle flips setting", before != after)
    # non-admin cannot use glass callbacks
    calls = await feed_cb("g:stats", uid=222)
    check("glass callback blocked for non-admin", "EditMessageText" not in calls)

    # --- Pasargad panel driver (marzban-compatible) ---
    from app.services import get_driver
    from app.models import Panel as PanelP
    async with async_session() as s:
        s.add(PanelP(name="PG", type="pasargad", url="http://pg", username="a", password="b"))
        await s.commit()
    async with async_session() as s:
        pg = (await s.execute(select(PanelP).where(PanelP.type == "pasargad"))).scalar_one()
    check("pasargad driver resolves", get_driver(pg) is not None)
    with patch("app.services.PasargadPanel") as MockPG:
        inst = AsyncMock()
        inst.create_client = AsyncMock(return_value={"success": True, "uuid": "pguser",
                                                      "sub_url": "http://pg/sub/x"})
        MockPG.return_value.__aenter__.return_value = inst
        from app.services import provision_service as _prov
        prod = Product(name="pgplan", volume_gb=5, days=5, price=0)
        okp, _m, svcp = await _prov(222, prod, pg)
        check("pasargad service provisioned", okp and svcp and svcp.sub_url == "http://pg/sub/x")

    # --- professional QR generation ---
    from app.qr import make_config_qr
    qr_png = make_config_qr("vless://x@h:443#t", title="ZendanBot", subtitle="u-1")
    check("QR png generated", len(qr_png) > 1000 and qr_png[:8] == b"\x89PNG\r\n\x1a\n")

    # --- sales chart generation ---
    from app.chart import sales_chart_png
    chart_png = await sales_chart_png()
    check("sales chart png generated", len(chart_png) > 1000 and chart_png[:8] == b"\x89PNG\r\n\x1a\n")
    # glass chart callback sends a photo
    calls = await feed_cb("g:chart", uid=111)
    check("glass chart sends photo", "SendPhoto" in calls)

    # reset via glass wipes data
    async with async_session() as s:
        s.add(User(id=777, username="temp"))
        await s.commit()
    await feed_cb("g:reset_yes", uid=111)
    async with async_session() as s:
        remaining = (await s.execute(select(func.count()).select_from(User))).scalar()
        check("glass reset wipes database", remaining == 0)

    if os.path.exists("./‌_smoke_test.db"):
        os.remove("./‌_smoke_test.db")

    print()
    if FAILURES:
        print(f"❌ {len(FAILURES)} check(s) failed:", ", ".join(FAILURES))
        sys.exit(1)
    print("🎉 All smoke checks passed.")

if __name__ == "__main__":
    asyncio.run(main())
