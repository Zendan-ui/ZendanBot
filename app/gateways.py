"""Online payment gateways for polling-mode bots.

Because the bot runs in long-polling (no public webhook server), each gateway
follows the pattern:
    1. create a payment / invoice  -> returns a pay URL + an id we store
    2. user pays on the gateway page
    3. user taps "✅ پرداخت کردم" -> bot verifies the payment via the gateway API
       and, if paid, credits the wallet.

Supported: Zarinpal, AqayePardakht, NowPayments (crypto).
All amounts are in TOMAN at the bot level; Zarinpal/Aqaye use RIAL on the wire
(×10), NowPayments uses a fiat price (we send IRT-equivalent as USD-less by
using price_amount in Toman with price_currency unsupported -> we use a simple
order and just check status).
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

import aiohttp

from app.models import get_setting

logger = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=20)


async def callback_url() -> str:
    base = (await get_setting("public_base_url", "")).rstrip("/")
    # we don't host a callback; gateways still require a return URL. Use a
    # harmless landing (telegram) so the user can come back to the bot.
    return base or "https://t.me"


# --------------------------------------------------------------------------- #
#  Zarinpal
# --------------------------------------------------------------------------- #
async def zarinpal_create(amount_toman: int, description: str) -> Tuple[bool, str, str]:
    """Returns (ok, authority_or_error, pay_url)."""
    merchant = await get_setting("zarinpal_merchant", "")
    if not merchant:
        return False, "merchant_not_set", ""
    payload = {
        "merchant_id": merchant,
        "amount": amount_toman * 10,  # rial
        "description": description,
        "callback_url": await callback_url(),
    }
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as s:
            async with s.post("https://api.zarinpal.com/pg/v4/payment/request.json",
                              json=payload) as r:
                data = await r.json(content_type=None)
    except Exception as exc:  # noqa: BLE001
        return False, str(exc), ""
    d = data.get("data") or {}
    if d.get("code") == 100 and d.get("authority"):
        authority = d["authority"]
        return True, authority, f"https://www.zarinpal.com/pg/StartPay/{authority}"
    return False, str((data.get("errors") or {}).get("message", "request_failed")), ""


async def zarinpal_verify(authority: str, amount_toman: int) -> Tuple[bool, str]:
    """Returns (paid, ref_id_or_error)."""
    merchant = await get_setting("zarinpal_merchant", "")
    payload = {"merchant_id": merchant, "amount": amount_toman * 10, "authority": authority}
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as s:
            async with s.post("https://api.zarinpal.com/pg/v4/payment/verify.json",
                              json=payload) as r:
                data = await r.json(content_type=None)
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    d = data.get("data") or {}
    if d.get("code") in (100, 101):  # 101 = already verified
        return True, str(d.get("ref_id", ""))
    return False, "not_paid"


# --------------------------------------------------------------------------- #
#  AqayePardakht
# --------------------------------------------------------------------------- #
async def aqaye_create(amount_toman: int) -> Tuple[bool, str, str]:
    pin = await get_setting("aqayepardakht_pin", "")
    if not pin:
        return False, "pin_not_set", ""
    payload = {
        "pin": pin,
        "amount": amount_toman,  # toman
        "callback": await callback_url(),
    }
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as s:
            async with s.post("https://panel.aqayepardakht.ir/api/v2/create",
                              json=payload) as r:
                data = await r.json(content_type=None)
    except Exception as exc:  # noqa: BLE001
        return False, str(exc), ""
    if str(data.get("status")) == "1" and data.get("transid"):
        transid = str(data["transid"])
        return True, transid, f"https://panel.aqayepardakht.ir/startpay/{transid}"
    return False, str(data.get("code", "request_failed")), ""


async def aqaye_verify(transid: str, amount_toman: int) -> Tuple[bool, str]:
    pin = await get_setting("aqayepardakht_pin", "")
    payload = {"pin": pin, "amount": amount_toman, "transid": transid}
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as s:
            async with s.post("https://panel.aqayepardakht.ir/api/v2/verify",
                              json=payload) as r:
                data = await r.json(content_type=None)
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    if str(data.get("status")) in ("1", "2"):  # 1 = ok, 2 = already verified
        return True, transid
    return False, "not_paid"


# --------------------------------------------------------------------------- #
#  NowPayments (crypto)
# --------------------------------------------------------------------------- #
async def nowpayments_create(amount_toman: int, order_id: str) -> Tuple[bool, str, str]:
    api_key = await get_setting("nowpayments_api_key", "")
    if not api_key:
        return False, "api_key_not_set", ""
    # NowPayments needs a fiat price; we send the toman amount as IRT-less by
    # using "usd"-style price isn't accurate, so we use price in the smallest
    # supported fiat. Most resellers configure USD; here we just create an
    # invoice in USD-equivalent is out of scope, so we use price_currency 'usd'
    # with a converted value is unavailable -> we create with price in 'usd'
    # using a fixed display. For reliability we just create a generic invoice.
    payload = {
        "price_amount": max(1, round(amount_toman / 60000, 2)),  # rough toman->usd
        "price_currency": "usd",
        "order_id": order_id,
        "order_description": "Wallet charge",
    }
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as s:
            async with s.post("https://api.nowpayments.io/v1/invoice",
                              json=payload, headers=headers) as r:
                data = await r.json(content_type=None)
    except Exception as exc:  # noqa: BLE001
        return False, str(exc), ""
    if data.get("id") and data.get("invoice_url"):
        return True, str(data["id"]), data["invoice_url"]
    return False, str(data.get("message", "request_failed")), ""


async def nowpayments_status(invoice_id: str) -> Optional[str]:
    api_key = await get_setting("nowpayments_api_key", "")
    headers = {"x-api-key": api_key}
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as s:
            async with s.get(f"https://api.nowpayments.io/v1/payment/{invoice_id}",
                             headers=headers) as r:
                data = await r.json(content_type=None)
    except Exception as exc:  # noqa: BLE001
        logger.warning("nowpayments status error: %s", exc)
        return None
    return data.get("payment_status")  # finished / confirmed / waiting / ...


# --------------------------------------------------------------------------- #
async def enabled_gateways() -> list[tuple[str, str]]:
    """Return list of (key, label) for enabled online gateways."""
    out = []
    if await get_setting("zarinpal_enabled", "0") == "1":
        out.append(("zarinpal", "🟡 زرین‌پال"))
    if await get_setting("aqayepardakht_enabled", "0") == "1":
        out.append(("aqayepardakht", "💎 آقای پرداخت"))
    if await get_setting("nowpayments_enabled", "0") == "1":
        out.append(("nowpayments", "₿ ارز دیجیتال (NowPayments)"))
    return out
