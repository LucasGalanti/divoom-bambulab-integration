"""
bambu_mqtt.py — Local MQTT client for BambuLab X1C printer.

Connects to the printer's built-in MQTT broker (LAN mode, no cloud needed).
Subscribes to the device report topic and parses print status updates.

Authentication:
  - username: "bblp"
  - password: LAN access code (shown on printer display under Settings → Network)
  - TLS: self-signed certificate from the printer (verify disabled)
"""

import json
import logging
import ssl
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


@dataclass
class PrintState:
    """Current state of the printer as reported via MQTT."""
    gcode_state: str = "IDLE"          # IDLE | RUNNING | FINISH | FAILED | PAUSE
    layer_num: int = 0
    total_layer_num: int = 0
    mc_percent: int = 0                # 0–100
    mc_remaining_time: int = 0         # minutes
    subtask_name: str = ""
    nozzle_temper: float = 0.0
    bed_temper: float = 0.0
    wifi_signal: int = 0
    filament_runout: bool = False   # HMS error: filament out
    hms_errors: list = field(default_factory=list)  # raw HMS error codes

    @property
    def is_printing(self) -> bool:
        return self.gcode_state.upper() in ("RUNNING", "PREPARE")

    @property
    def is_paused(self) -> bool:
        return self.gcode_state.upper() == "PAUSE"

    @property
    def is_finished(self) -> bool:
        return self.gcode_state.upper() == "FINISH"

    @property
    def is_failed(self) -> bool:
        return self.gcode_state.upper() == "FAILED"

    @property
    def is_heating(self) -> bool:
        return self.gcode_state.upper() == "PREPARE"

    @property
    def is_idle(self) -> bool:
        return not self.is_printing and not self.is_finished and not self.is_failed and not self.is_paused


class BambuMQTTClient:
    """
    MQTT client for BambuLab X1C local LAN mode.

    Usage:
        client = BambuMQTTClient(
            ip="192.168.1.50",
            serial="BBLP00CXXXXXXX",
            access_code="12345678",
            on_state_change=my_callback
        )
        client.start()
        # ... later ...
        client.stop()
    """

    MQTT_USER = "bblp"
    MQTT_PORT_TLS = 8883
    RECONNECT_DELAY_S = 5

    def __init__(
        self,
        ip: str,
        serial: str,
        access_code: str,
        on_state_change: Optional[Callable[[PrintState], None]] = None,
        tls: bool = True,
    ):
        self.ip = ip
        self.serial = serial
        self.access_code = access_code
        self.on_state_change = on_state_change
        self.tls = tls
        self._state = PrintState()
        self._client: Optional[mqtt.Client] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @property
    def report_topic(self) -> str:
        return f"device/{self.serial}/report"

    @property
    def state(self) -> PrintState:
        return self._state

    def start(self):
        """Start MQTT connection in a background thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="bambu-mqtt")
        self._thread.start()
        logger.info("BambuMQTTClient started (ip=%s, serial=%s)", self.ip, self.serial)

    def stop(self):
        """Stop the MQTT client gracefully."""
        self._stop_event.set()
        if self._client:
            self._client.disconnect()
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("BambuMQTTClient stopped")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_client(self) -> mqtt.Client:
        client = mqtt.Client(client_id=f"pixoo-bambu-{self.serial[:8]}")
        client.username_pw_set(self.MQTT_USER, self.access_code)

        if self.tls:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE  # printer uses self-signed cert
            client.tls_set_context(ctx)

        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        return client

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                self._client = self._build_client()
                port = self.MQTT_PORT_TLS if self.tls else 1883
                self._client.connect(self.ip, port, keepalive=60)
                self._client.loop_forever()
            except Exception as e:
                logger.warning("MQTT connection error: %s — retrying in %ds", e, self.RECONNECT_DELAY_S)
                if not self._stop_event.is_set():
                    time.sleep(self.RECONNECT_DELAY_S)

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("Connected to printer MQTT broker at %s", self.ip)
            client.subscribe(self.report_topic)
            logger.info("Subscribed to %s", self.report_topic)
        else:
            logger.error("MQTT connect failed, rc=%d", rc)

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            logger.warning("Unexpected MQTT disconnect (rc=%d) — will reconnect", rc)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            self._parse_report(payload)
        except Exception as e:
            logger.debug("Failed to parse MQTT message: %s", e)

    def _parse_report(self, payload: dict):
        """Parse printer report JSON and update state."""
        # The X1C nests print data under "print" key
        data = payload.get("print", payload)

        changed = False

        def _get(key, default=None):
            return data.get(key, default)

        new_state = _get("gcode_state", self._state.gcode_state)
        if new_state != self._state.gcode_state:
            changed = True
            self._state.gcode_state = new_state

        for attr, key, default in [
            ("layer_num",         "layer_num",         self._state.layer_num),
            ("total_layer_num",   "total_layer_num",   self._state.total_layer_num),
            ("mc_percent",        "mc_percent",        self._state.mc_percent),
            ("mc_remaining_time", "mc_remaining_time", self._state.mc_remaining_time),
            ("subtask_name",      "subtask_name",      self._state.subtask_name),
            ("nozzle_temper",     "nozzle_temper",     self._state.nozzle_temper),
            ("bed_temper",        "bed_temper",        self._state.bed_temper),
            ("wifi_signal",       "wifi_signal",       self._state.wifi_signal),
        ]:
            val = _get(key, None)
            if val is not None and val != getattr(self._state, attr):
                setattr(self._state, attr, val)
                changed = True

        if changed and self.on_state_change:
            self.on_state_change(self._state)

        # HMS errors (separate key in payload, not inside "print")
        hms_list = payload.get("hms", [])
        if hms_list:
            self._state.hms_errors = hms_list
            # Filament runout: attr_id starts with "0700" (spool sensor error family)
            runout = any(
                str(e.get("attr_id", "")).startswith("0700") or "700" in str(e.get("attr_id", ""))
                for e in hms_list
            )
            if runout != self._state.filament_runout:
                self._state.filament_runout = runout
                if self.on_state_change:
                    self.on_state_change(self._state)


class BambuCloudMQTTClient(BambuMQTTClient):
    """
    Cloud MQTT variant — connects to Bambu's cloud broker instead of the
    printer's local LAN broker.

    The printer does NOT need LAN mode enabled; Bambu Handy and Bambu Cloud
    continue to work normally. Latency is ~500 ms vs ~100 ms for LAN mode.

    Usage:
        from bambu_cloud_auth import cloud_login
        token, username = cloud_login(email, password)
        client = BambuCloudMQTTClient(
            serial="00M09D4A2100978",
            auth_token=token,
            mqtt_username=username,
            on_state_change=my_callback,
        )
        client.start()
    """

    CLOUD_HOST = "us.mqtt.bambulab.com"

    def __init__(
        self,
        serial: str,
        auth_token: str,
        mqtt_username: str,
        on_state_change: Optional[Callable[[PrintState], None]] = None,
    ):
        # Pass the cloud host as ip; access_code carries the JWT token as MQTT password
        super().__init__(
            ip=self.CLOUD_HOST,
            serial=serial,
            access_code=auth_token,
            on_state_change=on_state_change,
            tls=True,
        )
        self._mqtt_username = mqtt_username  # "u_<digits>"

    def _build_client(self) -> mqtt.Client:
        client = mqtt.Client(client_id=f"pixoo-bambu-{self.serial[:8]}")
        # Cloud auth: username = u_<user_id>, password = JWT token
        client.username_pw_set(self._mqtt_username, self.access_code)

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        client.tls_set_context(ctx)

        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        return client
