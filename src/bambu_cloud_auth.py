"""
bambu_cloud_auth.py — Bambu Cloud login helper.

Exchanges Bambu account credentials for a JWT auth token and MQTT username.
Used when BAMBU_CONNECTION_MODE=cloud so the printer keeps full Bambu Handy
and Bambu Cloud functionality without needing LAN mode.

Note: Bambu's login API sits behind Cloudflare. Plain `requests` works in most
      cases; if you get repeated 403 errors install the optional `cloudscraper`
      package:  pip install cloudscraper
"""

import base64
import json
import logging

import requests

logger = logging.getLogger(__name__)

CLOUD_LOGIN_URL = "https://api.bambulab.com/v1/user-service/user/login"
CLOUD_MQTT_HOST = "us.mqtt.bambulab.com"
CLOUD_MQTT_PORT = 8883

_LOGIN_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "bambu_network_agent/01.09.05.01",
}


class VerificationRequiredError(Exception):
    """Raised when Bambu Cloud requires an email/SMS verification code."""
    def __init__(self, login_type: str):
        super().__init__(
            f"Bambu Cloud requires a verification code (type: {login_type}). "
            "Check your email or SMS for the code and enter it when prompted."
        )
        self.login_type = login_type


def cloud_login(email: str, password: str, verification_code: str = "") -> tuple[str, str]:
    """
    Authenticate with Bambu Cloud.

    Args:
        email:             Bambu account email address.
        password:          Bambu account password.
        verification_code: Optional email/SMS code if a first attempt raised
                           VerificationRequiredError.

    Returns:
        (auth_token, mqtt_username)  e.g. ("eyJ...", "u_1234567890")

    Raises:
        VerificationRequiredError: Bambu requires a verification code.
        RuntimeError:              Any other authentication failure.
    """
    payload: dict = {"account": email, "password": password, "apiError": ""}
    if verification_code:
        payload["code"] = verification_code

    try:
        resp = requests.post(CLOUD_LOGIN_URL, json=payload, headers=_LOGIN_HEADERS, timeout=15)
    except requests.RequestException as exc:
        raise RuntimeError(f"Network error connecting to Bambu Cloud: {exc}") from exc

    try:
        data = resp.json()
    except ValueError:
        data = {}

    # Bambu returns 200 even when a verification step is required
    login_type = data.get("loginType", "")
    if login_type in ("verifyCode", "tfa"):
        raise VerificationRequiredError(login_type)

    if resp.status_code != 200 or "token" not in data:
        raise RuntimeError(
            f"Bambu Cloud login failed (HTTP {resp.status_code}): {resp.text[:400]}"
        )

    token: str = data["token"]
    username = _username_from_jwt(token)
    logger.info("Bambu Cloud authenticated (%s)", _mask(username))
    return token, username


def _username_from_jwt(token: str) -> str:
    """Decode JWT payload (no signature verification) and return the 'username' field."""
    try:
        segment = token.split(".")[1]
        segment += "=" * ((4 - len(segment) % 4) % 4)
        payload = json.loads(base64.b64decode(segment))
        username = payload.get("username") or payload.get("sub")
        if not username:
            raise ValueError(f"No 'username' or 'sub' in JWT payload (keys: {list(payload.keys())})")
        return username
    except Exception as exc:
        raise RuntimeError(f"Could not extract MQTT username from JWT: {exc}") from exc


def _mask(s: str) -> str:
    return s[:7] + "xxxxx" if len(s) > 7 else s
