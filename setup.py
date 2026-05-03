#!/usr/bin/env python3
"""
setup.py -- Interactive setup wizard for BambuLab -> Pixoo 64 Integration

Run with:
    python setup.py

Guides you through each required configuration value step by step,
explains where to find each piece of information, verifies connectivity,
and writes the final .env file.
"""

import os
import re
import socket
import sys
import time
import urllib.request
import urllib.error
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Terminal color helpers (no external deps)
# ---------------------------------------------------------------------------

def _supports_color() -> bool:
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            # Also set UTF-8 output for Windows
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        return True
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

_COLOR = _supports_color()

_HR  = "=" * 60   # horizontal rule (ASCII-safe)
_CHK = "[OK]"
_ERR = "[!!]"
_WRN = "[??]"
_ARR = ">>"

def _c(code: str, text: str) -> str:
    if not _COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"

def bold(t):    return _c("1", t)
def green(t):   return _c("32", t)
def yellow(t):  return _c("33", t)
def cyan(t):    return _c("36", t)
def red(t):     return _c("31", t)
def dim(t):     return _c("2", t)

def header(title: str):
    print()
    print(bold(cyan(_HR)))
    print(bold(cyan(f"  {title}")))
    print(bold(cyan(_HR)))

def step(n: int, total: int, label: str):
    print()
    print(bold(f"  [{n}/{total}] {label}"))

def info(text: str):
    for line in text.strip().splitlines():
        print(dim(f"        {line}"))

def tip(text: str):
    prefix = yellow(f"  {_ARR} ")
    for i, line in enumerate(text.strip().splitlines()):
        print(prefix + line if i == 0 else "     " + line)

def ok(text: str):
    print(green(f"  {_CHK}  {text}"))

def err(text: str):
    print(red(f"  {_ERR}  {text}"))

def warn(text: str):
    print(yellow(f"  {_WRN}  {text}"))

# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

def ask(prompt: str, default: str = "", validator=None, secret: bool = False) -> str:
    disp_default = f" [{dim(default)}]" if default else ""
    while True:
        try:
            if secret:
                import getpass
                val = getpass.getpass(f"\n        {bold('->')} {prompt}{disp_default}: ")
            else:
                val = input(f"\n        {bold('->')} {prompt}{disp_default}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print()
            warn("Setup cancelled.")
            sys.exit(0)

        if not val:
            val = default
        if not val:
            warn("This field is required.")
            continue
        if validator:
            result = validator(val)
            if result is not True:
                warn(result)
                continue
        return val


def ask_int(prompt: str, default: int, min_val: int, max_val: int) -> int:
    def v(s):
        try:
            n = int(s)
        except ValueError:
            return "Please enter a number."
        if n < min_val or n > max_val:
            return f"Must be between {min_val} and {max_val}."
        return True
    return int(ask(prompt, str(default), validator=v))


def ask_yes(prompt: str, default: bool = True) -> bool:
    default_str = "Y/n" if default else "y/N"
    while True:
        try:
            val = input(f"\n        {bold('->')} {prompt} [{default_str}]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        if not val:
            return default
        if val in ("y", "yes"):
            return True
        if val in ("n", "no"):
            return False
        warn("Please type y or n.")

# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

_IP_RE = re.compile(
    r"^((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?)$"
)

def valid_ip(val: str):
    if not _IP_RE.match(val):
        return "Enter a valid IPv4 address, e.g. 192.168.1.42"
    return True

def valid_serial(val: str):
    if len(val) < 8:
        return "Serial number looks too short -- check the printer screen or label."
    return True

def valid_code(val: str):
    if len(val) < 4:
        return "Access code looks too short -- it should be 8 characters on the printer screen."
    return True

# ---------------------------------------------------------------------------
# Connectivity tests
# ---------------------------------------------------------------------------

def _tcp_reachable(ip: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def test_pixoo(ip: str) -> bool:
    """Try the Pixoo /post endpoint."""
    url = f"http://{ip}/post"
    payload = json.dumps({"Command": "Channel/GetIndex"}).encode()
    try:
        req = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=4) as r:
            return r.status == 200
    except Exception:
        return False


def test_bambu(ip: str) -> bool:
    """Check if port 8883 (MQTT TLS) is open on the printer."""
    return _tcp_reachable(ip, 8883, timeout=4)

# ---------------------------------------------------------------------------
# Main wizard
# ---------------------------------------------------------------------------

TOTAL_STEPS = 6

def main():
    header("BambuLab x Pixoo 64 -- Setup Wizard")
    print()
    print("  This wizard will guide you through all required configuration.")
    print("  At the end a " + bold(".env") + " file will be created in this folder.")
    print()
    print(dim("  Press Ctrl+C at any time to cancel without saving."))

    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        print()
        warn(f".env already exists at {env_path}")
        if not ask_yes("Overwrite it?", default=False):
            print()
            print(dim("  Nothing changed. Delete .env manually to re-run setup."))
            sys.exit(0)

    values = {}

    # ------------------------------------------------------------------ STEP 1
    step(1, TOTAL_STEPS, "Divoom Pixoo 64 -- IP Address")
    info("""
Your Pixoo 64 must have a fixed (static) IP on your local network.

How to find it:
  - On the Pixoo itself: Settings -> About -> Device IP
    (swipe left from the main screen, tap the gear icon)
  - OR check your router's DHCP client list (usually at 192.168.1.1
    or 192.168.0.1 in your browser) and look for a device named
    "Pixoo" or "Divoom".

Recommended: set a DHCP reservation in your router so the IP never changes.
""")
    tip("The Pixoo and printer must be on the same 2.4 GHz WiFi as this computer.")
    values["PIXOO_IP"] = ask("Pixoo 64 IP address", "192.168.1.", validator=valid_ip)

    print()
    print(f"  Testing connection to Pixoo at {values['PIXOO_IP']} ?", end="", flush=True)
    if test_pixoo(values["PIXOO_IP"]):
        print()
        ok("Pixoo responded! ?")
    else:
        print()
        warn("Could not reach the Pixoo right now.")
        info("""
Possible causes:
  - Wrong IP -- double-check on the Pixoo screen (Settings -> About)
  - Pixoo is off or in sleep mode -- wake it up and try again
  - Firewall blocking outbound HTTP on port 80
  - Computer is on 5 GHz WiFi while Pixoo is on 2.4 GHz

You can continue setup and fix the IP in .env later.
""")

    # ------------------------------------------------------------------ STEP 2
    step(2, TOTAL_STEPS, "BambuLab X1C -- IP Address")
    info("""
How to find the printer's IP:
  - On the printer touchscreen:
    Settings (gear icon) -> Network -> Connection (or "LAN")
    The IP is shown at the top of the network screen.
  - OR check your router's DHCP client list for a device named
    "X1C", "BambuLab", or similar.

Recommended: set a DHCP reservation so the IP never changes.
""")
    values["BAMBU_PRINTER_IP"] = ask("Printer IP address", "192.168.1.", validator=valid_ip)

    print()
    print(f"  Testing MQTT port 8883 on {values['BAMBU_PRINTER_IP']} ?", end="", flush=True)
    if test_bambu(values["BAMBU_PRINTER_IP"]):
        print()
        ok("Port 8883 open -- printer is reachable! ?")
    else:
        print()
        warn("Could not reach port 8883 on the printer.")
        info("""
Possible causes:
  - Wrong IP -- verify on the printer screen
  - LAN Mode may not be enabled (see next step)
  - Printer is idle/sleeping -- send a small job or wake it up
""")

    # ------------------------------------------------------------------ STEP 3
    step(3, TOTAL_STEPS, "BambuLab X1C -- Serial Number")
    info("""
The serial number identifies your specific printer on MQTT.

Where to find it:
  - Printer touchscreen: Settings -> Device -> Device Info
    It starts with letters like "BBLP00C..." or "01S00C..."
  - On the sticker on the back/bottom of the printer
  - In Bambu Studio: My Printers -> your printer -> Details
""")
    values["BAMBU_SERIAL"] = ask("Printer serial number (e.g. BBLP00CXXXXXXX)",
                                  validator=valid_serial)

    # ------------------------------------------------------------------ STEP 4
    step(4, TOTAL_STEPS, "BambuLab X1C -- LAN Access Code")
    info("""
The LAN access code is an 8-character password used for local MQTT.
It is NOT your Bambu account password.

How to find and enable it:
  1. On the printer touchscreen go to:
     Settings (gear) -> Network -> LAN Mode Liveview
  2. Enable "LAN Mode Liveview" toggle (if not already on)
  3. The 8-character access code will be displayed below the toggle.

[!]  Keep this code private -- anyone with it can control your printer
   over the local network.
""")
    tip("LAN Mode must be ON for this integration to work -- no cloud needed.")
    values["BAMBU_ACCESS_CODE"] = ask("LAN access code (8 characters)",
                                       secret=True, validator=valid_code)

    # ------------------------------------------------------------------ STEP 5
    step(5, TOTAL_STEPS, "Display Preferences")
    info("""
These optional settings control how the Pixoo display behaves.
Press Enter to accept the defaults shown in brackets.
""")
    brightness = ask_int("Display brightness (0?100)", default=80, min_val=0, max_val=100)
    values["PIXOO_BRIGHTNESS"] = str(brightness)

    interval = ask_int("Minimum seconds between display updates (1?30)", default=3,
                        min_val=1, max_val=30)
    values["PIXOO_UPDATE_INTERVAL"] = str(interval)

    # ------------------------------------------------------------------ STEP 6
    step(6, TOTAL_STEPS, "Writing .env file")

    env_content = f"""\
# Generated by setup.py -- do not commit this file

# Divoom Pixoo 64 -- local IP
PIXOO_IP={values['PIXOO_IP']}

# BambuLab X1C -- local IP and credentials
BAMBU_PRINTER_IP={values['BAMBU_PRINTER_IP']}
BAMBU_SERIAL={values['BAMBU_SERIAL']}
BAMBU_ACCESS_CODE={values['BAMBU_ACCESS_CODE']}

# Display preferences
PIXOO_BRIGHTNESS={values['PIXOO_BRIGHTNESS']}
PIXOO_UPDATE_INTERVAL={values['PIXOO_UPDATE_INTERVAL']}
"""

    env_path.write_text(env_content, encoding="utf-8")
    ok(f".env written -> {env_path}")

    # ------------------------------------------------------------------ Summary
    header("Setup complete!")
    print()
    print("  Next steps:")
    print()
    print(f"    1. {bold('Generate sprites')} (first run only):")
    print(f"       {cyan('python scripts/make_sprite.py --all')}")
    print()
    print(f"    2. {bold('Start the integration')}:")
    print(f"       {cyan('python src/main.py')}")
    print()
    print(f"    3. {bold('Run as a background service')} (optional):")
    print(f"       - Linux:   {cyan('bash service/install-linux.sh')}")
    print(f"       - Windows: {cyan('powershell service/install-windows-task.ps1')}")
    print()
    print(dim("  Tip: edit .env any time to change IPs or settings, then restart."))
    print()


if __name__ == "__main__":
    main()
