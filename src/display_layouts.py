"""
display_layouts.py — Pillow-based screen composers for the Divoom Pixoo 64.

Each function returns a PIL Image (RGB, 64×64) ready to be pushed to the display.
Fonts are drawn as simple rectangles/pixels — the Pixoo's native font rendering
happens on-device; here we compose via Pillow for the Python standalone path.
"""

import math
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw

SIZE = 64

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------

C_BG_PRINTING   = (0, 218, 52)
C_BG_IDLE       = (20, 20, 20)
C_BG_DONE       = (0, 80, 200)
C_BG_FAILED     = (120, 0, 0)
C_HEADER_FOOTER = (51, 51, 51)
C_TEXT          = (255, 255, 255)
C_TEXT_DIM      = (151, 151, 151)
C_BAR_FILL      = (255, 0, 68)
C_BAR_TRACK     = (40, 40, 40)
C_GREEN         = (4, 204, 2)

# ---------------------------------------------------------------------------
# Micro bitmap font (PICO-8 style, 4×5 per character)
# Only digits, colon, slash, percent, space, letters needed for status display
# ---------------------------------------------------------------------------

_FONT4 = {
    "0": "111 101 101 101 111",
    "1": "010 110 010 010 111",
    "2": "111 001 111 100 111",
    "3": "111 001 111 001 111",
    "4": "101 101 111 001 001",
    "5": "111 100 111 001 111",
    "6": "111 100 111 101 111",
    "7": "111 001 001 001 001",
    "8": "111 101 111 101 111",
    "9": "111 101 111 001 111",
    ":": "000 010 000 010 000",
    "/": "001 001 010 100 100",
    "%": "101 001 010 100 101",
    " ": "000 000 000 000 000",
    "L": "100 100 100 100 111",
    "R": "110 101 110 101 101",
    "Y": "101 101 010 010 010",
    "A": "010 101 111 101 101",
    "T": "111 010 010 010 010",
    "E": "111 100 110 100 111",
    "D": "110 101 101 101 110",
    "I": "111 010 010 010 111",
    "N": "101 111 111 101 101",
    "G": "111 100 101 101 111",
    "P": "110 101 110 100 100",
    "F": "111 100 110 100 100",
    "H": "101 101 111 101 101",
    "?": "111 001 011 000 010",
}

_CHAR_W, _CHAR_H = 4, 5


def _draw_char(d: ImageDraw.ImageDraw, char: str, x: int, y: int, color: tuple, scale: int = 1):
    glyph = _FONT4.get(char.upper(), _FONT4[" "])
    rows = glyph.split()
    for row_i, row in enumerate(rows):
        for col_i, bit in enumerate(row):
            if bit == "1":
                px = x + col_i * scale
                py = y + row_i * scale
                d.rectangle([px, py, px + scale - 1, py + scale - 1], fill=color)


def _draw_text(d: ImageDraw.ImageDraw, text: str, x: int, y: int, color: tuple, scale: int = 1):
    cursor = x
    for ch in text:
        _draw_char(d, ch, cursor, y, color, scale)
        cursor += (_CHAR_W + 1) * scale


def _text_width(text: str, scale: int = 1) -> int:
    return len(text) * (_CHAR_W + 1) * scale - scale


# ---------------------------------------------------------------------------
# Screen composers
# ---------------------------------------------------------------------------

def make_progress_screen(
    percent: int,
    layer: int,
    total_layers: int,
    remaining_minutes: int,
    icon: Optional[Image.Image] = None,
) -> Image.Image:
    """Main printing progress screen."""
    img = Image.new("RGB", (SIZE, SIZE), C_BG_PRINTING)
    d = ImageDraw.Draw(img)

    # Header bar
    d.rectangle([0, 0, SIZE - 1, 6], fill=C_HEADER_FOOTER)

    # Footer bar
    d.rectangle([0, 57, SIZE - 1, SIZE - 1], fill=C_HEADER_FOOTER)

    # Layer info in header: "L:47/230"
    header_text = f"L:{layer}/{total_layers}"
    _draw_text(d, header_text, 3, 1, C_TEXT)

    # Clock (current time)
    now_str = datetime.now().strftime("%H:%M")
    clock_w = _text_width(now_str)
    _draw_text(d, now_str, (SIZE - clock_w) // 2, 10, C_TEXT_DIM)

    # Icon (printer sprite, centered horizontally)
    if icon:
        icon_rgb = icon.convert("RGB").resize((20, 20), Image.NEAREST)
        img.paste(icon_rgb, (22, 35))

    # Progress bar track
    d.rectangle([2, 25, 61, 33], fill=C_BAR_TRACK)

    # Progress bar fill
    fill_w = int(58 / 100 * max(0, min(100, percent)))
    if fill_w > 0:
        d.rectangle([3, 26, 3 + fill_w - 1, 32], fill=C_BAR_FILL)

    # Percent label on bar
    pct_text = f"{percent}%"
    _draw_text(d, pct_text, 5, 27, C_TEXT)

    # Footer: estimated completion time
    if remaining_minutes > 0:
        done_dt = datetime.now() + timedelta(minutes=remaining_minutes)
        footer_text = f"DONE:{done_dt.strftime('%H:%M')}"
    else:
        footer_text = "FINISHING"
    _draw_text(d, footer_text, 3, 58, C_TEXT)

    return img


def make_idle_screen() -> Image.Image:
    """Idle / standby screen — minimal dark display."""
    img = Image.new("RGB", (SIZE, SIZE), C_BG_IDLE)
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, SIZE - 1, 6], fill=C_HEADER_FOOTER)
    d.rectangle([0, 57, SIZE - 1, SIZE - 1], fill=C_HEADER_FOOTER)

    _draw_text(d, "IDLE", (SIZE - _text_width("IDLE")) // 2, 1, C_TEXT_DIM)

    # Current time, centered
    now_str = datetime.now().strftime("%H:%M")
    _draw_text(d, now_str, (SIZE - _text_width(now_str, scale=2)) // 2, 26, C_TEXT_DIM, scale=2)

    return img


def make_done_screen(job_name: str = "") -> Image.Image:
    """Print finished successfully screen."""
    img = Image.new("RGB", (SIZE, SIZE), C_BG_DONE)
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, SIZE - 1, 6], fill=C_HEADER_FOOTER)
    d.rectangle([0, 57, SIZE - 1, SIZE - 1], fill=C_HEADER_FOOTER)

    _draw_text(d, "DONE", (SIZE - _text_width("DONE")) // 2, 1, C_GREEN)

    # Big checkmark
    w = 3
    d.line([12, 36, 24, 48], fill=C_GREEN, width=w)
    d.line([24, 48, 52, 18], fill=C_GREEN, width=w)

    # Job name in footer (truncated)
    if job_name:
        label = job_name[:10]
        _draw_text(d, label, 3, 58, C_TEXT_DIM)
    else:
        _draw_text(d, "PRINT OK", 3, 58, C_TEXT_DIM)

    return img


def make_failed_screen() -> Image.Image:
    """Print failed screen."""
    img = Image.new("RGB", (SIZE, SIZE), C_BG_FAILED)
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, SIZE - 1, 6], fill=C_HEADER_FOOTER)
    d.rectangle([0, 57, SIZE - 1, SIZE - 1], fill=C_HEADER_FOOTER)

    _draw_text(d, "FAILED", (SIZE - _text_width("FAILED")) // 2, 1, C_TEXT)

    # Big X
    w = 3
    d.line([16, 18, 48, 50], fill=(255, 80, 80), width=w)
    d.line([48, 18, 16, 50], fill=(255, 80, 80), width=w)

    _draw_text(d, "CHECK APP", 3, 58, C_TEXT_DIM)

    return img


def load_sprite(path: str, size: int = 20) -> Optional[Image.Image]:
    """Load a sprite PNG, return None if not found."""
    p = Path(path)
    if not p.exists():
        return None
    return Image.open(p).resize((size, size), Image.NEAREST)
