#!/usr/bin/env python3
"""
main.py — BambuLab X1C → Divoom Pixoo 64 Integration

Entry point. Reads config from .env, connects to the printer via local MQTT,
and updates the Pixoo display in real time based on print status.

Setup:
  1. Copy .env.example to .env and fill in your values
  2. pip install -r requirements.txt
  3. python src/main.py

Running as a background service:
  Windows: pythonw src/main.py
  Linux:   systemd service (see README for unit file)
"""

import logging
import os
import signal
import sys
import time
from pathlib import Path

# Allow running from either project root or src/
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv()

from bambu_mqtt import BambuMQTTClient, PrintState
from display_layouts import (
    make_progress_screen,
    make_idle_screen,
    make_done_screen,
    make_failed_screen,
    load_sprite,
)
from pixoo_renderer import PixooRenderer

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _require_env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        logger.error("Missing required environment variable: %s (check your .env file)", key)
        sys.exit(1)
    return val


PIXOO_IP         = _require_env("PIXOO_IP")
BAMBU_IP         = _require_env("BAMBU_PRINTER_IP")
BAMBU_SERIAL     = _require_env("BAMBU_SERIAL")
BAMBU_CODE       = _require_env("BAMBU_ACCESS_CODE")
PIXOO_BRIGHTNESS = int(os.getenv("PIXOO_BRIGHTNESS", "80"))
UPDATE_INTERVAL  = float(os.getenv("PIXOO_UPDATE_INTERVAL", "3"))

SPRITE_DIR = Path(__file__).parent.parent / "assets" / "sprites"

# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------

_renderer: PixooRenderer = None
_printer_icon = None
_last_pushed_state: str = ""
_running = True

# ---------------------------------------------------------------------------
# Display logic
# ---------------------------------------------------------------------------

def _push_for_state(state: PrintState, force: bool = False):
    global _last_pushed_state

    if state.is_printing:
        img = make_progress_screen(
            percent=state.mc_percent,
            layer=state.layer_num,
            total_layers=state.total_layer_num,
            remaining_minutes=state.mc_remaining_time,
            icon=_printer_icon,
        )
        pushed = _renderer.push(img, force=force)
        if pushed:
            logger.info(
                "Display updated → PRINTING  %d%%  L:%d/%d  ~%dmin",
                state.mc_percent,
                state.layer_num,
                state.total_layer_num,
                state.mc_remaining_time,
            )

    elif state.is_finished:
        if force or _last_pushed_state != "done":
            img = make_done_screen(job_name=state.subtask_name)
            _renderer.push(img, force=True)
            logger.info("Display updated → DONE (%s)", state.subtask_name)
            _last_pushed_state = "done"

    elif state.is_failed:
        if force or _last_pushed_state != "failed":
            img = make_failed_screen()
            _renderer.push(img, force=True)
            logger.info("Display updated → FAILED")
            _last_pushed_state = "failed"

    else:
        if force or _last_pushed_state != "idle":
            img = make_idle_screen()
            _renderer.push(img, force=True)
            logger.info("Display updated → IDLE")
            _last_pushed_state = "idle"


def on_state_change(state: PrintState):
    """Callback fired by BambuMQTTClient on every state change."""
    logger.debug("State change: %s  %d%%  L:%d/%d",
                 state.gcode_state, state.mc_percent,
                 state.layer_num, state.total_layer_num)
    _push_for_state(state)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global _renderer, _printer_icon, _running

    logger.info("=== BambuLab → Pixoo 64 Integration starting ===")
    logger.info("Pixoo IP:   %s", PIXOO_IP)
    logger.info("Printer IP: %s (serial: %s)", BAMBU_IP, BAMBU_SERIAL)

    # Load printer sprite
    sprite_path = SPRITE_DIR / "printer.png"
    _printer_icon = load_sprite(str(sprite_path), size=20)
    if _printer_icon:
        logger.info("Loaded printer sprite from %s", sprite_path)
    else:
        logger.warning("Printer sprite not found at %s — run: python scripts/make_sprite.py --type printer", sprite_path)

    # Init renderer
    _renderer = PixooRenderer(ip=PIXOO_IP, min_interval_s=UPDATE_INTERVAL)

    # Ping Pixoo
    if _renderer.ping():
        logger.info("Pixoo 64 reachable at %s ✓", PIXOO_IP)
        _renderer.set_brightness(PIXOO_BRIGHTNESS)
    else:
        logger.error("Cannot reach Pixoo at %s — check IP and WiFi connection", PIXOO_IP)
        sys.exit(1)

    # Push initial idle screen
    _push_for_state(PrintState(), force=True)

    # Start MQTT client
    client = BambuMQTTClient(
        ip=BAMBU_IP,
        serial=BAMBU_SERIAL,
        access_code=BAMBU_CODE,
        on_state_change=on_state_change,
        tls=True,
    )
    client.start()
    logger.info("Listening for printer events... (Ctrl+C to stop)")

    # Graceful shutdown
    def _shutdown(signum, frame):
        global _running
        logger.info("Shutting down...")
        _running = False
        client.stop()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Keep-alive loop: refresh the clock on the idle screen every minute
    try:
        while _running:
            time.sleep(30)
            if _running:
                _push_for_state(client.state, force=False)
    except KeyboardInterrupt:
        pass
    finally:
        client.stop()
        logger.info("Stopped.")


if __name__ == "__main__":
    main()
