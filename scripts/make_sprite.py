#!/usr/bin/env python3
"""
make_sprite.py — Programmatic pixel art sprite generator for Divoom Pixoo 64

Usage:
  python scripts/make_sprite.py --type printer --size 20 --out assets/sprites/printer.png
  python scripts/make_sprite.py --type done --size 20 --out assets/sprites/done.png
  python scripts/make_sprite.py --type idle --size 32 --out assets/sprites/idle.png
  python scripts/make_sprite.py --type failed --size 20 --out assets/sprites/failed.png
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


SPRITES = {
    "printer": _sprite_printer,
    "done":    _sprite_done,
    "idle":    _sprite_idle,
    "failed":  _sprite_failed,
}

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate pixel-art sprites for Pixoo 64")
    parser.add_argument("--type", choices=list(SPRITES.keys()), help="Sprite type to generate")
    parser.add_argument("--size", type=int, default=20, help="Output size in pixels (default: 20)")
    parser.add_argument("--out", type=str, default=None, help="Output PNG path (default: assets/sprites/<type>.png)")
    parser.add_argument("--list", action="store_true", help="List available sprite types and exit")
    args = parser.parse_args()

    if args.list:
        print("Available sprite types:")
        for name in SPRITES:
            print(f"  {name}")
        sys.exit(0)

    if not args.type:
        parser.error("--type is required unless using --list")

    out_path = args.out or f"assets/sprites/{args.type}.png"
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    img = SPRITES[args.type](args.size)
    img.save(out_path, format="PNG", optimize=True)
    print(f"Saved {args.size}x{args.size} '{args.type}' sprite → {out_path}")


if __name__ == "__main__":
    main()
