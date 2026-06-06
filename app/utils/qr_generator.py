"""
ZendanBOT - Professional QR Code Generator
Generates beautiful, branded QR codes with gradient backgrounds, logos, and styled cards.
"""

import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer, CircleModuleDrawer, GappedSquareModuleDrawer
from qrcode.image.styles.colormasks import RadialGradiantColorMask, SolidFillColorMask, SquareGradiantColorMask
from PIL import Image, ImageDraw, ImageFont
import io
import os
from typing import Optional, Tuple


def generate_professional_qr(
    data: str,
    filename: str = "qr_output.png",
    size: int = 1024,
    qr_box_size: int = 12,
    qr_border: int = 4,
    style: str = "rounded",  # rounded, circle, square
    fg_color: Tuple[int, int, int] = (255, 255, 255),
    bg_color: Tuple[int, int, int] = (25, 25, 50),
    accent_color: Optional[Tuple[int, int, int]] = (100, 80, 220),
    card_bg_color: Tuple[int, int, int] = (18, 18, 38),
    card_border_color: Tuple[int, int, int] = (100, 80, 220),
    card_title: str = "",
    card_subtitle: str = "",
    card_footer: str = "",
    show_logo: bool = False,
    logo_path: str = "",
) -> bytes:
    """
    Generate a professional, branded QR code with styled card background.
    
    Returns PNG bytes ready to send via Telegram.
    """

    # ---- Step 1: Create QR Code ----
    qr = qrcode.QRCode(
        version=None,  # Auto-detect
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # High for logo overlay
        box_size=qr_box_size,
        border=qr_border,
    )
    qr.add_data(data)
    qr.make(fit=True)

    # Choose drawer style
    if style == "rounded":
        drawer = RoundedModuleDrawer(radius_ratio=0.5)
    elif style == "circle":
        drawer = CircleModuleDrawer(radius_ratio=0.8)
    else:
        drawer = GappedSquareModuleDrawer()

    # Create gradient mask
    if accent_color:
        color_mask = RadialGradiantColorMask(
            back_color=bg_color,
            center_color=fg_color,
            edge_color=accent_color,
        )
    else:
        color_mask = SolidFillColorMask(back_color=bg_color, front_color=fg_color)

    qr_img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=drawer,
        color_mask=color_mask,
    )

    qr_img = qr_img.convert("RGBA")

    # ---- Step 2: Resize QR ----
    qr_size = int(size * 0.55)
    qr_img = qr_img.resize((qr_size, qr_size), Image.LANCZOS)

    # ---- Step 3: Create Card Background ----
    card = Image.new("RGBA", (size, size), card_bg_color)
    draw = ImageDraw.Draw(card)

    # Gradient border
    border_width = 3
    for i in range(border_width):
        opacity = 255 - (i * 60)
        color = (*card_border_color, opacity)
        draw.rounded_rectangle(
            [i, i, size - i - 1, size - i - 1],
            radius=20 + i,
            outline=color,
            width=2,
        )

    # Inner glow effect
    for i in range(8):
        alpha = max(0, 30 - i * 4)
        glow_color = (*card_border_color, alpha)
        draw.rounded_rectangle(
            [10 + i, 10 + i, size - 10 - i, size - 10 - i],
            radius=18,
            outline=glow_color,
            width=1,
        )

    # Background gradient overlay (subtle)
    for y in range(size):
        progress = y / size
        r = int(card_bg_color[0] + (card_border_color[0] - card_bg_color[0]) * progress * 0.15)
        g = int(card_bg_color[1] + (card_border_color[1] - card_bg_color[1]) * progress * 0.15)
        b = int(card_bg_color[2] + (card_border_color[2] - card_bg_color[2]) * progress * 0.15)
        draw.line([(0, y), (size, y)], fill=(r, g, b))

    # ---- Step 4: Draw Text Elements ----
    try:
        # Try to load a good font
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
            "arial.ttf",
        ]
        font_path = None
        for fp in font_paths:
            if os.path.exists(fp):
                font_path = fp
                break

        if font_path:
            font_title = ImageFont.truetype(font_path, 28)
            font_subtitle = ImageFont.truetype(font_path, 22)
            font_footer = ImageFont.truetype(font_path, 18)
            font_small = ImageFont.truetype(font_path, 16)
        else:
            font_title = ImageFont.load_default()
            font_subtitle = ImageFont.load_default()
            font_footer = ImageFont.load_default()
            font_small = ImageFont.load_default()
    except Exception:
        font_title = font_subtitle = font_footer = font_small = ImageFont.load_default()

    current_y = 30

    # Title
    if card_title:
        draw.text(
            (size // 2, current_y),
            card_title,
            fill=(255, 255, 255),
            font=font_title,
            anchor="mt",
        )
        current_y += 45

    # Subtitle
    if card_subtitle:
        # Wrap text
        max_width = size - 80
        lines = _wrap_text(card_subtitle, font_subtitle, max_width, draw)
        for line in lines:
            draw.text(
                (size // 2, current_y),
                line,
                fill=(180, 180, 220),
                font=font_subtitle,
                anchor="mt",
            )
            current_y += 30
        current_y += 10

    # Separator line
    line_y = current_y + 5
    draw.line([(60, line_y), (size - 60, line_y)], fill=(*card_border_color, 100), width=1)
    current_y = line_y + 20

    # ---- Step 5: Paste QR Code ----
    qr_x = (size - qr_size) // 2
    qr_y = current_y

    # QR shadow
    shadow_offset = 5
    shadow = Image.new("RGBA", (qr_size + 20, qr_size + 20), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle([10, 10, qr_size + 10, qr_size + 10], radius=12, fill=(0, 0, 0, 40))
    card.paste(shadow, (qr_x - 10 + shadow_offset, qr_y - 10 + shadow_offset), shadow)

    # QR background (white rounded)
    qr_bg = Image.new("RGBA", (qr_size + 20, qr_size + 20), (0, 0, 0, 0))
    qr_bg_draw = ImageDraw.Draw(qr_bg)
    qr_bg_draw.rounded_rectangle(
        [5, 5, qr_size + 15, qr_size + 15],
        radius=15,
        fill=(255, 255, 255, 245),
    )
    card.paste(qr_bg, (qr_x - 10, qr_y - 10), qr_bg)

    # Paste QR
    card.paste(qr_img, (qr_x, qr_y), qr_img)
    current_y = qr_y + qr_size + 25

    # ---- Step 6: Footer ----
    if card_footer:
        draw.line([(60, current_y), (size - 60, current_y)], fill=(*card_border_color, 80), width=1)
        current_y += 15

        lines = _wrap_text(card_footer, font_footer, size - 80, draw)
        for line in lines:
            draw.text(
                (size // 2, current_y),
                line,
                fill=(140, 140, 180),
                font=font_footer,
                anchor="mt",
            )
            current_y += 25

    # Branding watermark
    draw.text(
        (size // 2, size - 25),
        "ZendanBOT",
        fill=(60, 60, 100),
        font=font_small,
        anchor="mb",
    )

    # ---- Step 7: Export ----
    output = io.BytesIO()
    card = card.convert("RGB")
    card.save(output, format="PNG", quality=95)
    output.seek(0)
    return output.getvalue()


def generate_simple_qr(
    data: str,
    fg_color: Tuple[int, int, int] = (0, 0, 0),
    bg_color: Tuple[int, int, int] = (255, 255, 255),
    box_size: int = 10,
    border: int = 4,
) -> bytes:
    """Quick simple QR code without fancy styling."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color=fg_color, back_color=bg_color)
    output = io.BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output.getvalue()


def _wrap_text(text: str, font, max_width: int, draw) -> list:
    """Wrap text to fit within max_width pixels."""
    if not text:
        return []
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines


print("✅ Professional QR Code Generator loaded.")
