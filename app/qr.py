"""Professional QR code generator for subscription links.

Produces a clean branded card: rounded QR modules, gradient-ish frame,
a title + caption strip, returned as PNG bytes ready to send with aiogram's
BufferedInputFile. Falls back to a plain QR if styled rendering fails.
"""
from __future__ import annotations

import io
import logging

import qrcode
from qrcode.constants import ERROR_CORRECT_H
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.colormasks import SolidFillColorMask
from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


def _plain_png(data: str) -> bytes:
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_H, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


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


def make_config_qr(
    data: str,
    title: str = "ZendanBot",
    subtitle: str = "Scan to connect",
    fg=(28, 28, 60),
    accent=(90, 70, 220),
) -> bytes:
    """Return PNG bytes of a professional, branded QR card."""
    try:
        qr = qrcode.QRCode(error_correction=ERROR_CORRECT_H, box_size=10, border=1)
        qr.add_data(data)
        qr.make(fit=True)
        qr_img = qr.make_image(
            image_factory=StyledPilImage,
            module_drawer=RoundedModuleDrawer(radius_ratio=1),
            color_mask=SolidFillColorMask(front_color=fg, back_color=(255, 255, 255)),
        ).convert("RGB")

        qr_w, qr_h = qr_img.size
        pad = 40
        header = 90
        footer = 64
        card_w = qr_w + pad * 2
        card_h = qr_h + pad * 2 + header + footer

        card = Image.new("RGB", (card_w, card_h), (245, 246, 252))
        draw = ImageDraw.Draw(card)

        # header band
        draw.rectangle([0, 0, card_w, header], fill=accent)
        tfont = _font(40)
        tw = draw.textlength(title, font=tfont)
        draw.text(((card_w - tw) / 2, (header - 40) / 2), title, font=tfont, fill=(255, 255, 255))

        # white rounded plate behind QR
        plate = [pad - 12, header + pad - 12, pad + qr_w + 12, header + pad + qr_h + 12]
        draw.rounded_rectangle(plate, radius=24, fill=(255, 255, 255),
                               outline=accent, width=3)
        card.paste(qr_img, (pad, header + pad))

        # footer caption
        sfont = _font(26)
        sw = draw.textlength(subtitle, font=sfont)
        draw.text(((card_w - sw) / 2, header + pad + qr_h + pad - 6),
                  subtitle, font=sfont, fill=(90, 90, 110))

        buf = io.BytesIO()
        card.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as exc:  # noqa: BLE001
        logger.warning("styled QR failed, using plain: %s", exc)
        return _plain_png(data)
