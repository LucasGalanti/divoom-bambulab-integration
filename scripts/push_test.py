#!/usr/bin/env python3
"""
push_test.py — Test connectivity and push content to the Divoom Pixoo 64.

Usage:
  python scripts/push_test.py --ip 192.168.1.X --mode ping
  python scripts/push_test.py --ip 192.168.1.X --mode progress --value 73
  python scripts/push_test.py --ip 192.168.1.X --mode image --file assets/sprites/printer.png
  python scripts/push_test.py --ip 192.168.1.X --mode gif --file animation.gif --fps 10
  python scripts/push_test.py --ip 192.168.1.X --mode brightness --value 80
  python scripts/push_test.py --ip 192.168.1.X --mode idle
  python scripts/push_test.py --ip 192.168.1.X --mode done
"""

import argparse
import base64
import json
import sys
import time
from pathlib import Path
from PIL import Image, ImageDraw

PIXOO_SIZE = 64


# ---------------------------------------------------------------------------
# Low-level HTTP helpers
# ---------------------------------------------------------------------------

def _post(ip: str, payload: dict) -> dict:
    import requests
    try:
        resp = requests.post(
            f"http://{ip}/post",
            data=json.dumps(payload),
            timeout=5
        )
        return resp.json()
    except Exception as e:
        print(f"  [error] {e}", file=sys.stderr)
        return {}


def reset_counter(ip: str):
    _post(ip, {"Command": "Draw/ResetHttpGifId"})


def set_brightness(ip: str, level: int):
    return _post(ip, {"Command": "Channel/SetBrightness", "Brightness": max(0, min(100, level))})


def send_frame(ip: str, img: Image.Image, frame_idx=0, total_frames=1, speed_ms=1000, pic_id=1):
    rgb = img.convert("RGB").resize((PIXOO_SIZE, PIXOO_SIZE), Image.NEAREST)
    data = base64.b64encode(rgb.tobytes()).decode("utf-8")
    return _post(ip, {
        "Command": "Draw/SendHttpGif",
        "PicNum": total_frames,
        "PicWidth": PIXOO_SIZE,
        "PicOffset": frame_idx,
        "PicID": pic_id,
        "PicSpeed": speed_ms,
        "PicData": data,
    })


# ---------------------------------------------------------------------------
# Test modes
# ---------------------------------------------------------------------------

def mode_ping(ip: str):
    print(f"Pinging Pixoo at {ip}...")
    result = _post(ip, {"Command": "Channel/GetIndex"})
    if result:
        print(f"  OK — response: {result}")
    else:
        print("  FAILED — no response")
        sys.exit(1)


def mode_brightness(ip: str, value: int):
    print(f"Setting brightness to {value}...")
    r = set_brightness(ip, value)
    print(f"  Response: {r}")


def mode_progress(ip: str, value: int):
    """Render a progress bar screen at given percent."""
    print(f"Pushing progress screen at {value}%...")
    img = _make_progress_image(value, layer=47, all_layers=230, footer="14:52")
    reset_counter(ip)
    r = send_frame(ip, img)
    print(f"  Response: {r}")


def mode_idle(ip: str):
    """Push idle screen (dark background, clock)."""
    print("Pushing idle screen...")
    img = _make_idle_image()
    reset_counter(ip)
    r = send_frame(ip, img)
    print(f"  Response: {r}")


def mode_done(ip: str):
    """Push print done screen."""
    print("Pushing done screen...")
    img = _make_done_image()
    reset_counter(ip)
    r = send_frame(ip, img)
    print(f"  Response: {r}")


def mode_image(ip: str, file_path: str):
    print(f"Pushing image: {file_path}...")
    if not Path(file_path).exists():
        print(f"  File not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    img = Image.open(file_path)
    reset_counter(ip)
    r = send_frame(ip, img)
    print(f"  Response: {r}")


def mode_gif(ip: str, file_path: str, fps: int):
    print(f"Pushing GIF: {file_path} at {fps}fps...")
    if not Path(file_path).exists():
        print(f"  File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    gif = Image.open(file_path)
    n = getattr(gif, "n_frames", 1)
    frames = []
    for i in range(min(n, 59)):
        gif.seek(i)
        frames.append(gif.copy())

    speed_ms = int(1000 / max(fps, 1))
    reset_counter(ip)
    for i, frame in enumerate(frames):
        r = send_frame(ip, frame, frame_idx=i, total_frames=len(frames), speed_ms=speed_ms)
        print(f"  Frame {i+1}/{len(frames)} → {r}")

    print("Done.")


# ---------------------------------------------------------------------------
# Screen composers
# ---------------------------------------------------------------------------

def _make_progress_image(percent: int, layer: int = 0, all_layers: int = 0, footer: str = "??:??") -> Image.Image:
    img = Image.new("RGB", (PIXOO_SIZE, PIXOO_SIZE), (0, 218, 52))
    d = ImageDraw.Draw(img)

    # Header bar
    d.rectangle([0, 0, 63, 6], fill=(51, 51, 51))
    # Footer bar
    d.rectangle([0, 57, 63, 63], fill=(51, 51, 51))
    # Progress track
    d.rectangle([2, 25, 61, 33], fill=(40, 40, 40))
    # Progress fill (dynamic)
    fill_w = int(58 / 100 * max(0, min(100, percent)))
    if fill_w > 0:
        d.rectangle([3, 26, 3 + fill_w, 32], fill=(255, 0, 68))

    return img


def _make_idle_image() -> Image.Image:
    img = Image.new("RGB", (PIXOO_SIZE, PIXOO_SIZE), (20, 20, 20))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 63, 6], fill=(51, 51, 51))
    d.rectangle([0, 57, 63, 63], fill=(51, 51, 51))
    return img


def _make_done_image() -> Image.Image:
    img = Image.new("RGB", (PIXOO_SIZE, PIXOO_SIZE), (0, 80, 200))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 63, 6], fill=(51, 51, 51))
    d.rectangle([0, 57, 63, 63], fill=(51, 51, 51))
    # Big checkmark
    w = 3
    d.line([14, 34, 26, 46], fill=(4, 204, 2), width=w)
    d.line([26, 46, 50, 20], fill=(4, 204, 2), width=w)
    return img


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Test push content to Divoom Pixoo 64")
    parser.add_argument("--ip", required=True, help="Pixoo IP address")
    parser.add_argument("--mode", required=True,
                        choices=["ping", "brightness", "progress", "idle", "done", "image", "gif"],
                        help="Test mode")
    parser.add_argument("--value", type=int, default=50, help="Integer value (percent or brightness)")
    parser.add_argument("--file", type=str, default=None, help="Image or GIF file path")
    parser.add_argument("--fps", type=int, default=10, help="FPS for GIF mode")
    args = parser.parse_args()

    dispatch = {
        "ping":       lambda: mode_ping(args.ip),
        "brightness": lambda: mode_brightness(args.ip, args.value),
        "progress":   lambda: mode_progress(args.ip, args.value),
        "idle":       lambda: mode_idle(args.ip),
        "done":       lambda: mode_done(args.ip),
        "image":      lambda: mode_image(args.ip, args.file or ""),
        "gif":        lambda: mode_gif(args.ip, args.file or "", args.fps),
    }

    dispatch[args.mode]()


if __name__ == "__main__":
    main()
