"""
pixoo_renderer.py — HTTP client for the Divoom Pixoo 64 local API.

Handles:
- Sending frames via Draw/SendHttpGif
- PicID counter management (auto-reset before device limit)
- Throttling (min interval between pushes)
- Brightness control
"""

import base64
import json
import logging
import time
from threading import Lock
from typing import Optional

import requests
from PIL import Image

logger = logging.getLogger(__name__)

PIXOO_SIZE = 64
PIC_ID_RESET_THRESHOLD = 250  # reset before hitting the ~300 device limit


class PixooRenderer:
    """
    Sends PIL Images to a Divoom Pixoo 64 over local HTTP.

    Usage:
        renderer = PixooRenderer(ip="192.168.1.X", min_interval_s=3)
        renderer.push(my_image)
        renderer.set_brightness(80)
    """

    def __init__(self, ip: str, min_interval_s: float = 3.0):
        self.ip = ip
        self.min_interval_s = min_interval_s
        self._pic_id = 1
        self._last_push_ts = 0.0
        self._lock = Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def push(self, img: Image.Image, force: bool = False) -> bool:
        """
        Push a single frame to the display.
        Respects min_interval_s throttle unless force=True.
        Returns True if the frame was actually sent.
        """
        with self._lock:
            now = time.time()
            if not force and (now - self._last_push_ts) < self.min_interval_s:
                logger.debug("Push throttled (%.1fs < %.1fs)", now - self._last_push_ts, self.min_interval_s)
                return False

            self._auto_reset_if_needed()
            sent = self._send_frame(img, frame_idx=0, total_frames=1, speed_ms=1000)
            if sent:
                self._last_push_ts = now
                self._pic_id += 1
            return sent

    def push_animation(self, frames: list, fps: int = 10, force: bool = False) -> bool:
        """
        Push a multi-frame animation (list of PIL Images).
        Max 59 frames (device limit).
        """
        if not frames:
            return False

        with self._lock:
            now = time.time()
            if not force and (now - self._last_push_ts) < self.min_interval_s:
                return False

            frames = frames[:59]
            speed_ms = max(1, int(1000 / fps))
            self._reset_counter()

            for i, frame in enumerate(frames):
                ok = self._send_frame(frame, frame_idx=i, total_frames=len(frames), speed_ms=speed_ms)
                if not ok:
                    return False

            self._last_push_ts = now
            self._pic_id += 1
            return True

    def set_brightness(self, level: int) -> bool:
        """Set display brightness 0–100."""
        return self._post({"Command": "Channel/SetBrightness", "Brightness": max(0, min(100, level))})

    def ping(self) -> bool:
        """Returns True if the device responds."""
        result = self._post_get({"Command": "Channel/GetIndex"})
        return result is not None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _send_frame(
        self,
        img: Image.Image,
        frame_idx: int,
        total_frames: int,
        speed_ms: int,
    ) -> bool:
        rgb = img.convert("RGB")
        if rgb.size != (PIXOO_SIZE, PIXOO_SIZE):
            rgb = rgb.resize((PIXOO_SIZE, PIXOO_SIZE), Image.NEAREST)

        data = base64.b64encode(rgb.tobytes()).decode("utf-8")
        return self._post({
            "Command": "Draw/SendHttpGif",
            "PicNum": total_frames,
            "PicWidth": PIXOO_SIZE,
            "PicOffset": frame_idx,
            "PicID": self._pic_id,
            "PicSpeed": speed_ms,
            "PicData": data,
        })

    def _reset_counter(self):
        self._post({"Command": "Draw/ResetHttpGifId"})
        self._pic_id = 1
        logger.debug("PicID counter reset")

    def _auto_reset_if_needed(self):
        if self._pic_id >= PIC_ID_RESET_THRESHOLD:
            logger.info("PicID approaching device limit (%d) — resetting", self._pic_id)
            self._reset_counter()

    def _post(self, payload: dict) -> bool:
        result = self._post_get(payload)
        return result is not None

    def _post_get(self, payload: dict) -> Optional[dict]:
        try:
            resp = requests.post(
                f"http://{self.ip}/post",
                data=json.dumps(payload),
                timeout=5,
            )
            result = resp.json()
            if result.get("error_code", 0) != 0:
                logger.warning("Pixoo API error: %s", result)
                return None
            return result
        except requests.exceptions.ConnectionError:
            logger.error("Cannot reach Pixoo at %s — check IP and WiFi", self.ip)
            return None
        except requests.exceptions.Timeout:
            logger.warning("Pixoo request timed out")
            return None
        except Exception as e:
            logger.error("Unexpected error sending to Pixoo: %s", e)
            return None
