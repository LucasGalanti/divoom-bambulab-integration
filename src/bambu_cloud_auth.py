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
import time
from pathlib import Path

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

    # Bambu may return "token" or "accessToken" depending on the flow
    token: str = data.get("accessToken") or data.get("token")
    if resp.status_code != 200 or not token:
        raise RuntimeError(
            f"Bambu Cloud login failed (HTTP {resp.status_code}): {resp.text[:400]}"
        )

    expires_in = int(data.get("expiresIn", 7_776_000))
    username = _get_username(token)
    save_token_cache(token, username, expires_in)
    logger.info("Bambu Cloud authenticated (%s)", _mask(username))
    return token, username


def _get_username(token: str) -> str:
    """
    Extract the MQTT username (u_<digits>) from the auth token.

    Tries JWT decode first (token starts with eyJ). Falls back to calling the
    Bambu preference API for opaque tokens (start with AAB or similar).
    """
    # JWT path
    if token.startswith("eyJ"):
        try:
            segment = token.split(".")[1]
            segment += "=" * ((4 - len(segment) % 4) % 4)
            payload = json.loads(base64.b64decode(segment))
            username = payload.get("username") or payload.get("sub")
            if username:
                return username
        except Exception:
            pass  # fall through to API call

    # Opaque token path — ask the preference API for the uid
    try:
        resp = requests.get(
            "https://api.bambulab.com/v1/design-user-service/my/preference",
            headers={**_LOGIN_HEADERS, "Authorization": f"Bearer {token}"},
            timeout=10,
        )
        uid = resp.json().get("uid")
        if uid:
            return f"u_{uid}"
    except Exception as exc:
        raise RuntimeError(f"Could not retrieve MQTT username from Bambu API: {exc}") from exc

    raise RuntimeError("Could not determine MQTT username from token or API response")


def _mask(s: str) -> str:
    return s[:7] + "xxxxx" if len(s) > 7 else s


# ---------------------------------------------------------------------------
# Token cache — avoids verification code prompts on every restart
# Stored in <project_root>/.bambu_token.json  (excluded from git)
# ---------------------------------------------------------------------------

_CACHE_FILE = Path(__file__).parent.parent / ".bambu_token.json"
# Refresh 24 h before actual expiry so we never hit an expired token mid-run
_EXPIRY_MARGIN_S = 86_400


def load_cached_token() -> tuple[str, str] | None:
    """
    Return (auth_token, mqtt_username) from the on-disk cache if it is still
    valid, otherwise return None.
    """
    if not _CACHE_FILE.exists():
        return None
    try:
        data = json.loads(_CACHE_FILE.read_text())
        expires_at = data.get("expires_at", 0)
        if time.time() < expires_at - _EXPIRY_MARGIN_S:
            logger.info("Using cached Bambu Cloud token (%s)", _mask(data["username"]))
            return data["token"], data["username"]
        logger.info("Cached token has expired — re-authenticating")
    except Exception as exc:
        logger.debug("Could not read token cache: %s", exc)
    return None


def save_token_cache(token: str, username: str, expires_in_s: int = 7_776_000) -> None:
    """
    Persist the token to disk.  expires_in_s defaults to 90 days
    (Bambu's standard expiry returned in the login response).
    """
    try:
        data = {
            "token": token,
            "username": username,
            "expires_at": time.time() + expires_in_s,
        }
        _CACHE_FILE.write_text(json.dumps(data))
        logger.debug("Token cache saved to %s", _CACHE_FILE)
    except Exception as exc:
        logger.warning("Could not save token cache: %s", exc)


def clear_token_cache() -> None:
    """Delete the cached token (e.g. after an authentication failure)."""
    if _CACHE_FILE.exists():
        _CACHE_FILE.unlink()
        logger.debug("Token cache cleared")
