"""Provisioning layer: turns a (user, product, panel) into a real config on the
panel and a Service row in the database. Works with multiple panel types
(xui, marzban) via a small driver factory, so handlers stay panel-agnostic.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.future import select

from app.database import async_session
from app.models import Panel, Product, Service, User
from app.panels.marzban import MarzbanPanel
from app.panels.pasargad import PasargadPanel
from app.panels.xui import XUIPanel

logger = logging.getLogger(__name__)

SUPPORTED_TYPES = ("xui", "marzban", "pasargad")


def get_driver(panel: Panel):
    """Return an async-context-manager panel driver for this panel, or None."""
    common = dict(inbound_id=panel.inbound_id, sub_domain=panel.sub_domain)
    if panel.type == "xui":
        return XUIPanel(panel.url, panel.username, panel.password, **common)
    if panel.type == "marzban":
        return MarzbanPanel(panel.url, panel.username, panel.password, **common)
    if panel.type == "pasargad":
        return PasargadPanel(panel.url, panel.username, panel.password, **common)
    return None


def _make_remark(user_id: int) -> str:
    return f"u{user_id}-{int(time.time())}"


async def _panel_of(service: Service) -> Optional[Panel]:
    async with async_session() as session:
        return (await session.execute(
            select(Panel).where(Panel.id == service.panel_id)
        )).scalar_one_or_none()


async def provision_service(
    user_id: int, product: Product, panel: Panel,
) -> Tuple[bool, str, Optional[Service]]:
    remark = _make_remark(user_id)
    driver = get_driver(panel)
    if driver is None:
        return False, f"نوع پنل پشتیبانی نمی‌شود: {panel.type}", None
    try:
        async with driver as api:
            res = await api.create_client(
                email=remark, volume_gb=product.volume_gb, days=product.days
            )
    except Exception as exc:  # noqa: BLE001
        logger.error("provision error: %s", exc)
        return False, "خطا در ارتباط با پنل. لطفاً بعداً تلاش کنید.", None
    if not res.get("success"):
        return False, f"خطا در ساخت کانفیگ روی پنل: {res.get('error')}", None

    expire_at = datetime.utcnow() + timedelta(days=product.days) if product.days else None
    async with async_session() as session:
        service = Service(
            user_id=user_id,
            panel_id=panel.id,
            product_name=product.name,
            remark=remark,
            sub_url=res.get("sub_url", ""),
            config_uuid=res.get("uuid", ""),
            volume_gb=product.volume_gb,
            days=product.days,
            price=product.price,
            status="active",
            expire_at=expire_at,
        )
        session.add(service)
        await session.commit()
        await session.refresh(service)
    return True, "✅ سرویس با موفقیت ساخته شد.", service


async def renew_service(service: Service, add_volume_gb: int, add_days: int) -> Tuple[bool, str]:
    panel = await _panel_of(service)
    driver = get_driver(panel) if panel else None
    if driver is None:
        return False, "نوع پنل برای تمدید پشتیبانی نمی‌شود."
    try:
        async with driver as api:
            res = await api.renew_client(service.remark, service.config_uuid,
                                         add_volume_gb, add_days)
    except Exception as exc:  # noqa: BLE001
        logger.error("renew error: %s", exc)
        return False, "خطا در ارتباط با پنل."
    if not res.get("success"):
        return False, f"خطا در تمدید: {res.get('error')}"
    async with async_session() as session:
        s = (await session.execute(select(Service).where(Service.id == service.id))).scalar_one()
        base = s.expire_at if s.expire_at and s.expire_at > datetime.utcnow() else datetime.utcnow()
        s.expire_at = base + timedelta(days=add_days) if add_days else s.expire_at
        s.status = "active"
        s.renew_count = (s.renew_count or 0) + 1
        await session.commit()
    return True, "✅ سرویس با موفقیت تمدید شد."


async def change_service_link(service: Service) -> Tuple[bool, str]:
    panel = await _panel_of(service)
    driver = get_driver(panel) if panel else None
    if driver is None:
        return False, ""
    try:
        async with driver as api:
            res = await api.change_link(service.remark, service.config_uuid)
    except Exception as exc:  # noqa: BLE001
        logger.error("change_link error: %s", exc)
        return False, ""
    if not res.get("success"):
        return False, ""
    new_url = res.get("sub_url", "")
    async with async_session() as session:
        s = (await session.execute(select(Service).where(Service.id == service.id))).scalar_one()
        s.sub_url = new_url
        await session.commit()
    return True, new_url


async def provision_test_service(
    user_id: int, panel: Panel, volume_gb: int, days: int
) -> Tuple[bool, str, Optional[Service]]:
    fake_product = Product(
        name="اکانت تست", volume_gb=volume_gb, days=days, price=0, panel_id=panel.id
    )
    return await provision_service(user_id, fake_product, panel)


async def toggle_service(service: Service, enable: bool) -> bool:
    panel = await _panel_of(service)
    driver = get_driver(panel) if panel else None
    if driver is None:
        return False
    async with driver as api:
        return await api.set_client_enabled(service.remark, service.config_uuid, enable)


async def fetch_usage(service: Service) -> Optional[dict]:
    panel = await _panel_of(service)
    driver = get_driver(panel) if panel else None
    if driver is None:
        return None
    async with driver as api:
        res = await api.get_client_traffic(service.remark)
    return res.get("data") if res.get("success") else None
