"""Lightweight bar-chart image (no matplotlib) using Pillow only.

Used for the admin "sales last 7 days" chart.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.future import select
from PIL import Image, ImageDraw, ImageFont

from app.database import async_session
from app.models import Service

logger = logging.getLogger(__name__)


def _font(size: int):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


async def sales_last_7_days() -> list[tuple[str, int, int]]:
    """Return [(label, count, revenue), ...] for the last 7 days (old->new)."""
    out = []
    today = datetime.utcnow().date()
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        start = datetime(day.year, day.month, day.day)
        end = start + timedelta(days=1)
        async with async_session() as s:
            cnt = (await s.execute(
                select(func.count()).select_from(Service)
                .where(Service.created_at >= start, Service.created_at < end)
            )).scalar()
            rev = (await s.execute(
                select(func.coalesce(func.sum(Service.price), 0))
                .where(Service.created_at >= start, Service.created_at < end)
            )).scalar()
        out.append((day.strftime("%m/%d"), int(cnt or 0), int(rev or 0)))
    return out


def render_bar_chart(data: list[tuple[str, int, int]],
                     title: str = "فروش ۷ روز اخیر") -> bytes:
    W, H = 760, 420
    pad = 50
    base_y = H - 70
    top_y = 70
    img = Image.new("RGB", (W, H), (248, 249, 253))
    d = ImageDraw.Draw(img)
    accent = (90, 70, 220)

    d.rectangle([0, 0, W, 50], fill=accent)
    tf = _font(26)
    d.text((pad, 12), "Sales — last 7 days", font=tf, fill=(255, 255, 255))

    max_rev = max((r for _, _, r in data), default=0) or 1
    n = len(data)
    gap = 24
    bw = (W - pad * 2 - gap * (n - 1)) / n
    lf = _font(18)
    sf = _font(15)

    # axis
    d.line([pad, base_y, W - pad, base_y], fill=(200, 200, 210), width=2)

    for i, (label, cnt, rev) in enumerate(data):
        x0 = pad + i * (bw + gap)
        h = int((rev / max_rev) * (base_y - top_y))
        y0 = base_y - h
        d.rounded_rectangle([x0, y0, x0 + bw, base_y], radius=8, fill=accent)
        # value on top
        val = f"{rev // 1000}k" if rev >= 1000 else str(rev)
        vw = d.textlength(val, font=sf)
        d.text((x0 + (bw - vw) / 2, y0 - 20), val, font=sf, fill=(60, 60, 80))
        # count badge
        cnttxt = f"×{cnt}"
        cw = d.textlength(cnttxt, font=sf)
        if h > 24:
            d.text((x0 + (bw - cw) / 2, base_y - 22), cnttxt, font=sf, fill=(255, 255, 255))
        # label
        lw = d.textlength(label, font=lf)
        d.text((x0 + (bw - lw) / 2, base_y + 10), label, font=lf, fill=(70, 70, 90))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def sales_chart_png() -> bytes:
    return render_bar_chart(await sales_last_7_days())
