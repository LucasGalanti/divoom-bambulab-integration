#!/usr/bin/env python3
"""
make_sprite.py — Programmatic pixel art sprite generator for Divoom Pixoo 64

Small icons (20x20) — used as elements inside larger 64x64 layouts:
  python scripts/make_sprite.py --type printer  --size 20
  python scripts/make_sprite.py --type done     --size 20
  python scripts/make_sprite.py --type idle     --size 20
  python scripts/make_sprite.py --type failed   --size 20

Full screens (64x64) — status trigger splash screens:
  python scripts/make_sprite.py --type screen-started      --size 64
  python scripts/make_sprite.py --type screen-done         --size 64
  python scripts/make_sprite.py --type screen-paused       --size 64
  python scripts/make_sprite.py --type screen-failed       --size 64
  python scripts/make_sprite.py --type screen-filament-out --size 64
  python scripts/make_sprite.py --type screen-heating      --size 64

Generate all assets at once:
  python scripts/make_sprite.py --all

List all types:
  python scripts/make_sprite.py --list
"""

import argparse
import sys
from pathlib import Path
from PIL import Image, ImageDraw

# ---------------------------------------------------------------------------
# Sprite definitions — each is a function(size) -> Image.Image (RGBA)
# ---------------------------------------------------------------------------

def _sprite_printer(size: int) -> Image.Image:
    """3D printer icon — nozzle + bed + filament."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 20  # scale factor relative to 20x20 design grid

    def r(x1, y1, x2, y2, fill):
        d.rectangle([int(x1 * s), int(y1 * s), int(x2 * s), int(y2 * s)], fill=fill)

    # Frame / body
    r(1, 5, 18, 15, (200, 200, 200, 255))
    # Top rail
    r(1, 4, 18, 5, (80, 80, 80, 255))
    # Gantry arm
    r(8, 3, 11, 5, (120, 120, 120, 255))
    # Print head
    r(8, 5, 12, 9, (60, 60, 60, 255))
    # Nozzle tip (hot orange)
    r(9, 9, 11, 12, (255, 140, 0, 255))
    # Print bed
    r(2, 14, 17, 16, (70, 70, 200, 255))
    # Printed object (small rectangle on bed)
    r(6, 11, 13, 14, (180, 240, 180, 255))

    return img


def _sprite_done(size: int) -> Image.Image:
    """Checkmark — print finished successfully."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 20
    w = max(1, int(1.5 * s))

    # Circle background
    d.ellipse([0, 0, size - 1, size - 1], fill=(4, 204, 2, 255))
    # Checkmark — left descending stroke
    d.line([int(3*s), int(11*s), int(7*s), int(15*s)], fill=(255, 255, 255, 255), width=w)
    # Checkmark — right ascending stroke
    d.line([int(6*s), int(15*s), int(17*s), int(4*s)], fill=(255, 255, 255, 255), width=w)

    return img


def _sprite_idle(size: int) -> Image.Image:
    """Clock / pause symbol — printer idle."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 20

    # Clock circle
    d.ellipse([0, 0, size - 1, size - 1], fill=(80, 80, 80, 255))
    d.ellipse([int(2 * s), int(2 * s), int(17 * s), int(17 * s)], fill=(30, 30, 30, 255))

    # Clock hands
    cx, cy = size // 2, size // 2
    # Hour hand (pointing up-left)
    d.line([cx, cy, cx - int(3 * s), cy - int(4 * s)], fill=(255, 255, 255, 255), width=max(1, int(s)))
    # Minute hand (pointing right)
    d.line([cx, cy, cx + int(5 * s), cy], fill=(255, 255, 255, 255), width=max(1, int(s)))
    # Center dot
    d.ellipse([cx - 1, cy - 1, cx + 1, cy + 1], fill=(255, 200, 0, 255))

    return img


def _sprite_failed(size: int) -> Image.Image:
    """X mark — print failed."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 20

    # Red circle background
    d.ellipse([0, 0, size - 1, size - 1], fill=(200, 20, 20, 255))

    # X strokes
    w = max(2, int(2 * s))
    d.line([int(4 * s), int(4 * s), int(16 * s), int(16 * s)], fill=(255, 255, 255, 255), width=w)
    d.line([int(16 * s), int(4 * s), int(4 * s), int(16 * s)], fill=(255, 255, 255, 255), width=w)

    return img


# ---------------------------------------------------------------------------
# Full-screen 64×64 status trigger splash screens
# ---------------------------------------------------------------------------

def _draw_banner(d: ImageDraw.ImageDraw, text: str, canvas_w: int, y: int, color: tuple):
    """Draw simple 3x5 pixel-block text centered horizontally."""
    _GLYPHS = {
        "A": [7,5,7,5,5], "B": [6,5,6,5,6], "C": [7,4,4,4,7],
        "D": [6,5,5,5,6], "E": [7,4,6,4,7], "F": [7,4,6,4,4],
        "G": [7,4,5,5,7], "H": [5,5,7,5,5], "I": [7,2,2,2,7],
        "J": [1,1,1,5,7], "K": [5,5,6,5,5], "L": [4,4,4,4,7],
        "M": [5,7,7,5,5], "N": [5,7,5,5,5], "O": [7,5,5,5,7],
        "P": [7,5,7,4,4], "Q": [7,5,5,7,1], "R": [7,5,7,5,5],
        "S": [7,4,7,1,7], "T": [7,2,2,2,2], "U": [5,5,5,5,7],
        "V": [5,5,5,7,2], "W": [5,5,7,7,5], "X": [5,5,2,5,5],
        "Y": [5,5,7,2,2], "Z": [7,1,2,4,7],
        "0": [7,5,5,5,7], "1": [2,6,2,2,7], "2": [7,1,7,4,7],
        "3": [7,1,7,1,7], "4": [5,5,7,1,1], "5": [7,4,7,1,7],
        "6": [7,4,7,5,7], "7": [7,1,1,1,1], "8": [7,5,7,5,7],
        "9": [7,5,7,1,7], ".": [0,0,0,0,2], "!": [2,2,2,0,2],
        " ": [0,0,0,0,0], ":": [0,2,0,2,0], "-": [0,0,7,0,0],
        "/": [1,1,2,4,4], "?": [7,1,7,0,2],
    }
    GW, SCALE = 3, 2  # glyph width, pixel scale (2 = readable on LED)
    chars = [c.upper() for c in text]
    total_w = len(chars) * (GW + 1) * SCALE - SCALE
    x = max(1, (canvas_w - total_w) // 2)
    for ch in chars:
        rows = _GLYPHS.get(ch, _GLYPHS[" "])
        for ri, row_bits in enumerate(rows):
            for bi in range(GW):
                if row_bits & (1 << (GW - 1 - bi)):
                    px = x + bi * SCALE
                    py = y + ri * SCALE
                    d.rectangle([px, py, px + SCALE - 1, py + SCALE - 1], fill=color)
        x += (GW + 1) * SCALE


def _screen_started(size: int) -> Image.Image:
    """Print started — green burst, printer silhouette."""
    img = Image.new("RGB", (size, size), (5, 30, 5))
    d = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2

    for r, c in [(28, (0, 60, 0)), (22, (0, 100, 0)), (16, (0, 160, 20))]:
        d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=c, width=2)

    d.ellipse([cx-10, cy-10, cx+10, cy+10], fill=(0, 218, 52))
    # Printer silhouette
    d.rectangle([cx-7, cy-2, cx+7, cy+5], fill=(255,255,255))
    d.rectangle([cx-7, cy-5, cx+7, cy-3], fill=(180,255,180))
    d.rectangle([cx-2, cy-8, cx+2, cy-5], fill=(180,255,180))
    d.rectangle([cx-1, cy+5, cx+1, cy+9], fill=(255,200,80))

    d.rectangle([0, 0, size-1, 11], fill=(0,50,10))
    _draw_banner(d, "STARTED", size, 2, (0,255,80))
    d.rectangle([0, size-13, size-1, size-1], fill=(0,50,10))
    _draw_banner(d, "PRINTING", size, size-12, (255,255,255))
    return img


def _screen_done(size: int) -> Image.Image:
    """Print done — blue, big checkmark, sparkles."""
    img = Image.new("RGB", (size, size), (0, 20, 70))
    d = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2

    for sx, sy in [(8,8),(56,8),(8,56),(56,56),(32,6),(6,32),(58,32)]:
        d.rectangle([sx-1,sy-4,sx+1,sy+4], fill=(80,150,255))
        d.rectangle([sx-4,sy-1,sx+4,sy+1], fill=(80,150,255))

    d.ellipse([cx-20, cy-20, cx+20, cy+20], outline=(0,80,200), width=2)
    w = 5
    d.line([12, 34, 26, 50], fill=(4,220,100), width=w)
    d.line([24, 50, 52, 14], fill=(4,220,100), width=w)

    d.rectangle([0, 0, size-1, 11], fill=(0,30,100))
    _draw_banner(d, "PRINT", size, 2, (80,180,255))
    d.rectangle([0, size-13, size-1, size-1], fill=(0,30,100))
    _draw_banner(d, "COMPLETE", size, size-12, (4,220,100))
    return img


def _screen_paused(size: int) -> Image.Image:
    """Print paused — amber, pause icon."""
    img = Image.new("RGB", (size, size), (35, 20, 0))
    d = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2

    d.ellipse([cx-22, cy-22, cx+22, cy+22], outline=(200,120,0), width=3)
    d.ellipse([cx-18, cy-18, cx+18, cy+18], fill=(70,40,0))
    d.rectangle([cx-9, cy-12, cx-3, cy+12], fill=(255,165,0))
    d.rectangle([cx+3, cy-12, cx+9, cy+12], fill=(255,165,0))

    d.rectangle([0, 0, size-1, 11], fill=(55,30,0))
    _draw_banner(d, "PRINT", size, 2, (255,165,0))
    d.rectangle([0, size-13, size-1, size-1], fill=(55,30,0))
    _draw_banner(d, "PAUSED", size, size-12, (255,210,60))
    return img


def _screen_failed(size: int) -> Image.Image:
    """Print failed — dark red, warning triangle with exclamation."""
    img = Image.new("RGB", (size, size), (30, 0, 0))
    d = ImageDraw.Draw(img)
    cx = size // 2

    d.polygon([(cx, 10), (cx+24, 50), (cx-24, 50)], outline=(220,0,0), fill=(80,0,0))
    d.rectangle([cx-2, 20, cx+2, 37], fill=(255,60,60))
    d.rectangle([cx-2, 40, cx+2, 45], fill=(255,60,60))

    d.rectangle([0, 0, size-1, 11], fill=(60,0,0))
    _draw_banner(d, "PRINT", size, 2, (255,80,80))
    d.rectangle([0, size-13, size-1, size-1], fill=(60,0,0))
    _draw_banner(d, "FAILED", size, size-12, (255,40,40))
    return img


def _screen_filament_out(size: int) -> Image.Image:
    """Filament runout — magenta alert, spool with broken filament."""
    img = Image.new("RGB", (size, size), (25, 0, 25))
    d = ImageDraw.Draw(img)
    cx, cy = size // 2, 30

    d.ellipse([cx-14, cy-14, cx+14, cy+14], outline=(200,0,200), width=3)
    d.ellipse([cx-6,  cy-6,  cx+6,  cy+6],  fill=(100,0,100))

    d.line([cx+14, cy, cx+26, cy-8], fill=(200,100,255), width=2)
    w2 = 2
    d.line([cx+22, cy-10, cx+30, cy-2], fill=(255,50,50), width=w2)
    d.line([cx+30, cy-10, cx+22, cy-2], fill=(255,50,50), width=w2)

    for x in range(0, size, 8):
        d.rectangle([x, 0, x+4, 2], fill=(200,0,200))
        d.rectangle([x, size-3, x+4, size-1], fill=(200,0,200))
    for y in range(0, size, 8):
        d.rectangle([0, y, 2, y+4], fill=(200,0,200))
        d.rectangle([size-3, y, size-1, y+4], fill=(200,0,200))

    d.rectangle([0, 0, size-1, 11], fill=(45,0,45))
    _draw_banner(d, "FILAMENT", size, 2, (255,100,255))
    d.rectangle([0, size-13, size-1, size-1], fill=(45,0,45))
    _draw_banner(d, "RUNOUT!", size, size-12, (255,50,255))
    return img


def _screen_heating(size: int) -> Image.Image:
    """Heating — orange heat waves, thermometer."""
    img = Image.new("RGB", (size, size), (18, 5, 0))
    d = ImageDraw.Draw(img)
    cx = size // 2

    for y in range(size-1, 12, -1):
        intensity = int(200 * (size - y) / size)
        d.line([4, y, size-5, y], fill=(min(255, intensity+60), max(0, intensity//4), 0), width=1)

    tx, ty = cx, 14
    d.rectangle([tx-3, ty,   tx+3, ty+26], fill=(60,60,60))
    d.rectangle([tx-2, ty+1, tx+2, ty+25], fill=(18,5,0))
    d.ellipse(  [tx-6, ty+24, tx+6, ty+36], fill=(255,80,0))
    d.rectangle([tx-1, ty+8,  tx+1, ty+25], fill=(255,80,0))
    for ty2 in [ty+8, ty+14, ty+20]:
        d.line([tx+3, ty2, tx+7, ty2], fill=(140,140,140), width=1)

    d.rectangle([0, 0, size-1, 11], fill=(40,10,0))
    _draw_banner(d, "HEATING", size, 2, (255,160,0))
    d.rectangle([0, size-13, size-1, size-1], fill=(40,10,0))
    _draw_banner(d, "WAIT...", size, size-12, (255,110,0))
    return img


_SCREEN_DEFAULTS = {
    "screen-started":      (64, _screen_started),
    "screen-done":         (64, _screen_done),
    "screen-paused":       (64, _screen_paused),
    "screen-failed":       (64, _screen_failed),
    "screen-filament-out": (64, _screen_filament_out),
    "screen-heating":      (64, _screen_heating),
}

SPRITES = {
    "printer": _sprite_printer,
    "done":    _sprite_done,
    "idle":    _sprite_idle,
    "failed":  _sprite_failed,
    **{k: fn for k, (_, fn) in _SCREEN_DEFAULTS.items()},
}

_ALL_TYPES = {
    "printer": 20,
    "done":    20,
    "idle":    20,
    "failed":  20,
    **{k: sz for k, (sz, _) in _SCREEN_DEFAULTS.items()},
}

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate pixel-art sprites for Pixoo 64")
    parser.add_argument("--type", choices=list(SPRITES.keys()), help="Sprite type to generate")
    parser.add_argument("--size", type=int, default=None, help="Output size in pixels (overrides default)")
    parser.add_argument("--out", type=str, default=None, help="Output PNG path (default: assets/sprites/<type>.png)")
    parser.add_argument("--list", action="store_true", help="List available sprite types and exit")
    parser.add_argument("--all", action="store_true", help="Generate all sprites with their default sizes")
    args = parser.parse_args()

    if args.list:
        print("Available sprite types:")
        print("\n  Icons (embed inside 64x64 layouts):")
        for name in ["printer", "done", "idle", "failed"]:
            print(f"    {name:22s} default size: 20x20")
        print("\n  Full screens (64x64 status triggers):")
        for name in _SCREEN_DEFAULTS:
            print(f"    {name:22s} default size: 64x64")
        sys.exit(0)

    if args.all:
        Path("assets/sprites").mkdir(parents=True, exist_ok=True)
        for name, default_size in _ALL_TYPES.items():
            img = SPRITES[name](default_size)
            out = f"assets/sprites/{name}.png"
            img.save(out, format="PNG", optimize=True)
            print(f"  {out}  ({default_size}x{default_size})")
        print(f"\nGenerated {len(_ALL_TYPES)} sprites.")
        sys.exit(0)

    if not args.type:
        parser.error("--type is required unless using --list or --all")

    size = args.size or _ALL_TYPES.get(args.type, 64)
    out_path = args.out or f"assets/sprites/{args.type}.png"
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    img = SPRITES[args.type](size)
    img.save(out_path, format="PNG", optimize=True)
    print(f"Saved {size}x{size} '{args.type}' sprite → {out_path}")


if __name__ == "__main__":
    main()
