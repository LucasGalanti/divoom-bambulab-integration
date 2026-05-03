#!/usr/bin/env python3
"""
encode_icon.py — Convert a PNG/JPEG to base64 string for embedding in YAML or Python configs.

Usage:
  python scripts/encode_icon.py --file assets/sprites/printer.png
  python scripts/encode_icon.py --file assets/sprites/printer.png --size 20 --out assets/generated/printer_b64.txt
  python scripts/encode_icon.py --file assets/sprites/done.png --size 20 --clip
"""

import argparse
import base64
import sys
from io import BytesIO
from pathlib import Path
from PIL import Image


def encode_icon(file_path: str, size: int | None = None) -> str:
    """Load an image, optionally resize, and return base64-encoded PNG string."""
    img = Image.open(file_path)

    if size is not None:
        img = img.resize((size, size), Image.NEAREST)

    # Always save as PNG to preserve transparency
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def main():
    parser = argparse.ArgumentParser(description="Encode a PNG to base64 for Pixoo YAML embedding")
    parser.add_argument("--file", required=True, help="Input PNG or JPEG file path")
    parser.add_argument("--size", type=int, default=None, help="Resize to NxN pixels before encoding (uses NEAREST resampling)")
    parser.add_argument("--out", type=str, default=None, help="Save base64 string to this text file (optional)")
    parser.add_argument("--clip", action="store_true", help="Also print a ready-to-paste YAML snippet")
    args = parser.parse_args()

    if not Path(args.file).exists():
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    b64 = encode_icon(args.file, args.size)
    print(b64)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(b64, encoding="utf-8")
        print(f"\nSaved to: {args.out}")

    if args.clip:
        snippet = f"""
# YAML snippet — paste into your pixoo-homeassistant page config:
variables:
  icon: "{b64}"
components:
  - type: image
    position: [22, 35]
    image_data: "{{{{ icon }}}}"
    resample_mode: box
    height: {args.size or 20}
"""
        print(snippet)


if __name__ == "__main__":
    main()
