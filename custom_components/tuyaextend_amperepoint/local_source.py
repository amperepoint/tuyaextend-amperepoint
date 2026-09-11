"""Integration-owned, read-only Tuya LAN transport for validated PRIME layouts.

No imports from Tuya Local or the cloud integration; TinyTuya handles the wire
protocol. Keys are used only for the local handshake and never in diagnostics.
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import time
from typing import Any

from homeassistant.exceptions import HomeAssistantError

LOCAL_SOURCE = "amperepoint_local"
LOCAL_FIELDS = ("local_device_id", "local_key", "local_host", "local_protocol")
SAFE_DPS = {"101", "102", "106", "107", "109", "117", "150", "151", "152", "153", "154", "155", "157"}


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
    # Unknown/card-related datapoints are deliberately not exposed to HA.
    return {str(k): v for k, v in dps.items() if str(k) in SAFE_DPS}, family


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
        if code == "work_state":
            return self.dps.get("109")
        if code == "system_version":
            return as_mapping(self.dps.get("106")).get("fv")
        return None

    def scaled(self, code):
        return self.raw(code)

    def has(self, code):
        return self.raw(code) is not None

    def writable(self, code):
        return False

    def definition(self, code):
        return {"writable": False}

    def values(self):
        return {f"dp_{dp}": value for dp, value in self.dps.items()}

    def definitions(self):
        return {f"dp_{dp}": {"dp_id": int(dp), "writable": False} for dp in self.dps}

    def bitmap_labels(self, code):
        return []

    async def async_send(self, code, value):
        raise HomeAssistantError("AmperePoint Local: this tested profile is read-only")
