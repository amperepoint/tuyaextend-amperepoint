"""Integration-owned Tuya LAN transport for validated PRIME layouts.

No imports from Tuya Local or the cloud integration; TinyTuya handles the wire
protocol. Keys are used only for the local handshake and never in diagnostics.
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import time
import math
from typing import Any

from homeassistant.exceptions import HomeAssistantError

LOCAL_SOURCE = "amperepoint_local"
LOCAL_FIELDS = ("local_device_id", "local_key", "local_host", "local_protocol")
CONTROL_PROFILE = "prime_split_v1"
PRIVATE_DPS = {"112", "113"}  # Card/authentication data, not telemetry.


def public_dps(dps: dict) -> dict:
    """Keep every reported DP visible, but never publish card/auth payloads."""
    return {str(k): ("[redacted: card/auth data]" if str(k) in PRIVATE_DPS else v)
            for k, v in dps.items()}


class LocalConnectionError(Exception):
    """Safe error code, without device response or credentials."""


def as_mapping(value: Any) -> dict:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return {}
    return value if isinstance(value, dict) else {}


def validate_snapshot(response: Any) -> tuple[dict, str]:
    if not isinstance(response, dict) or response.get("Error") or response.get("Err"):
        raise LocalConnectionError("local_cannot_connect")
    dps = response.get("dps")
    if not isinstance(dps, dict):
        raise LocalConnectionError("local_cannot_connect")
    payload = as_mapping(dps.get("102"))
    if not all(k in payload for k in ("p", "e", "t")) or not isinstance(dps.get("109"), str):
        raise LocalConnectionError("local_unsupported")
    if isinstance(payload.get("L"), list):
        family = "prime_split"
    elif isinstance(payload.get("L1"), list):
        family = "prime_packed"
    else:
        raise LocalConnectionError("local_unsupported")
    return public_dps(dps), family


def control_supported(config: dict, dps: dict, family: str) -> bool:
    """Enable only the device entry explicitly approved after physical tests."""
    return (config.get("local_control_profile") == CONTROL_PROFILE
            and family == "prime_split"
            and as_mapping(dps.get("106")).get("fv") == "(V7.0.0)F2.0.0"
            and type(dps.get("140")) is bool
            and type(dps.get("150")) is int
            and type(dps.get("152")) is int
            and 6 <= dps["152"] <= 80)


def current_max(dps: dict) -> int:
    # The tested device is capped at 16 A. Never write its installation limit.
    limit = dps.get("152")
    return min(16, limit) if type(limit) is int and limit >= 6 else 6


def write_local(config: dict, code: str, value: Any) -> dict:
    """A fresh preflight and independent readback, never optimistic success."""
    before = read_local(config)
    if not control_supported(config, before["dps"], before["family"]):
        raise LocalConnectionError("local_control_not_verified")
    if code == "switch" and type(value) is bool:
        mode = as_mapping(before["dps"].get("151")).get("m")
        if value and not (type(mode) is int and mode == 0):
            raise LocalConnectionError("local_immediate_mode_required")
        dp, expected = 140, value
    elif code == "charge_cur_set" and type(value) in (int, float):
        if not math.isfinite(value) or value != int(value) or not 6 <= value <= current_max(before["dps"]):
            raise LocalConnectionError("local_current_out_of_range")
        dp, expected = 150, int(value)
    else:
        raise LocalConnectionError("local_control_not_verified")
    import tinytuya
    device = tinytuya.Device(config["local_device_id"], before["host"], config["local_key"],
                            version=float(config.get("local_protocol", "3.5")),
                            connection_timeout=4, connection_retry_limit=1,
                            connection_retry_delay=0, persist=False)
    try:
        response = device.set_value(dp, expected)
        if isinstance(response, dict) and (response.get("Error") or response.get("Err")):
            raise LocalConnectionError("local_command_rejected")
    except LocalConnectionError:
        raise
    except Exception:
        raise LocalConnectionError("local_command_failed") from None
    finally:
        device.close()
    # Acknowledgement alone is insufficient. Fresh state must match exactly.
    for attempt in range(3):
        time.sleep(0.5 if attempt == 0 else 1)
        after = read_local({**config, "local_host": before["host"]})
        if after["dps"].get(str(dp)) == expected:
            if dp != 140 or after["dps"].get("101") in (
                (200, 300) if expected else (201, 204)
            ):
                return after
    raise LocalConnectionError("local_command_unconfirmed")


def validate_credentials(config: dict) -> None:
    if not str(config.get("local_device_id", "")).strip() or len(str(config.get("local_key", ""))) != 16:
        raise LocalConnectionError("local_invalid_credentials")
    host = str(config.get("local_host", "")).strip()
    if host:
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            raise LocalConnectionError("local_invalid_host") from None
        if address.version != 4 or not address.is_private or address.is_loopback or address.is_multicast or address.is_unspecified or address.is_link_local:
            raise LocalConnectionError("local_invalid_host")
    if str(config.get("local_protocol", "3.5")) not in {"3.3", "3.4", "3.5"}:
        raise LocalConnectionError("local_invalid_credentials")


def discover_host(device_id: str) -> str:
    from tinytuya import scanner

    try:
        found = scanner.devices(verbose=False, scantime=5, color=False, poll=False,
                                forcescan=False, byID=True, wantids=[device_id])
    except Exception:
        raise LocalConnectionError("local_not_found") from None
    item = found.get(device_id, {})
    return str(item.get("ip") or "")


def read_local(config: dict, rediscover: bool = False) -> dict:
    """Run only in an executor; one bounded connection, closed even on failure."""
    import tinytuya

    validate_credentials(config)
    host = str(config.get("local_host") or "").strip()
    if rediscover or not host:
        discovered = discover_host(config["local_device_id"])
        if discovered:
            host = discovered
        elif not host:
            raise LocalConnectionError("local_not_found")
    validate_credentials({**config, "local_host": host})
    device = tinytuya.Device(config["local_device_id"], host, config["local_key"],
                            version=float(config.get("local_protocol", "3.5")),
                            connection_timeout=4, connection_retry_limit=1,
                            connection_retry_delay=0, persist=False)
    try:
        dps, family = validate_snapshot(device.status())
    except LocalConnectionError:
        raise
    except Exception:
        # Never put protocol responses, credentials or a device repr in logs.
        raise LocalConnectionError("local_cannot_connect") from None
    finally:
        device.close()
    return {"host": host, "dps": dps, "family": family}


class NativeLocalSource:
    source_type = LOCAL_SOURCE

    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.config = {**entry.data, **entry.options}
        self.dps: dict = {}
        self.family = ""
        self.available = False
        self.command_status = "idle"
        self.command_error = None
        self._lock = asyncio.Lock()
        self._next_discovery = time.monotonic() + 60

    async def async_refresh(self):
        async with self._lock:
            try:
                result = await self.hass.async_add_executor_job(read_local, self.config)
            except LocalConnectionError as err:
                self.available = False
                if str(err) != "local_cannot_connect" or time.monotonic() < self._next_discovery:
                    raise
                self._next_discovery = time.monotonic() + 300
                result = await self.hass.async_add_executor_job(read_local, self.config, True)
            self.dps = result["dps"]
            self.family = result["family"]
            self.available = True
            self.config["local_host"] = result["host"]
            # Persist recovered DHCP address without reloading the entire entry.
            # HA options reconfiguration explicitly reloads after successful probe.
            if self.entry.data.get("local_host") != result["host"]:
                self.hass.config_entries.async_update_entry(
                    self.entry, data={**self.entry.data, "local_host": result["host"]}
                )

    def attributes(self):
        return {name: self.dps[dp] for dp, name in {
            "101": "state_code", "102": "telemetry", "106": "device_information",
            "117": "electrical_measurements",
        }.items() if dp in self.dps}

    def raw(self, code):
        if code == "switch":
            return self.dps.get("140")
        if code == "charge_cur_set":
            return self.dps.get("150")
        if code == "work_state":
            return self.dps.get("109")
        if code == "work_mode":
            mode = as_mapping(self.dps.get("151")).get("m")
            return "charge_now" if type(mode) is int and mode == 0 else None
        if code == "system_version":
            return as_mapping(self.dps.get("106")).get("fv")
        return None

    def scaled(self, code):
        return self.raw(code)

    def has(self, code):
        return self.raw(code) is not None

    def writable(self, code):
        return self.controls_verified and code in {"switch", "charge_cur_set"}

    @property
    def controls_verified(self):
        return control_supported(self.config, self.dps, self.family)

    def definition(self, code):
        if code == "charge_cur_set":
            return {"dp_id": 150, "min": 6, "max": current_max(self.dps),
                    "step": 1, "scale": 0, "unit": "A", "writable": self.writable(code)}
        return {"writable": self.writable(code)}

    def values(self):
        return {f"dp_{dp}": value for dp, value in self.dps.items()}

    def definitions(self):
        return {f"dp_{dp}": {"dp_id": int(dp), "writable": False} for dp in self.dps}

    def bitmap_labels(self, code):
        return []

    async def async_send(self, code, value):
        if not self.writable(code):
            raise HomeAssistantError("AmperePoint Local: this control is read-only / not verified")
        async with self._lock:
            self.command_status, self.command_error = "pending", None
            try:
                result = await self.hass.async_add_executor_job(write_local, self.config, code, value)
            except LocalConnectionError as err:
                self.command_status, self.command_error = "failed", str(err)
                raise HomeAssistantError(f"AmperePoint Local: {err}") from None
            self.dps, self.family = result["dps"], result["family"]
            self.available = True
            self.command_status = "confirmed"
