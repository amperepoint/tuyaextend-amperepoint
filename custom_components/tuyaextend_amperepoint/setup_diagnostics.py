"""Bounded, sanitized snapshots for failed LAN setup, never raw debug logs."""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from typing import Any

from .const import VERSION

REDACTED = "[redacted]"
MAX_DPS = 128
MAX_TEXT = 4096
NUMERIC_DPS = {"101", "140", "150", "152", "154", "155", "157", "188"}
OBJECT_FIELDS = {
    "102": {"p", "e", "t", "d", "c", "s", "p3", "cp", "L", "L1", "L2", "L3"},
    "106": {"fv"},
    "117": {"L", "L1", "L2", "L3", "cp", "gd", "dpn"},
    "151": {"m", "c", "dt", "ss", "se"},
}
ERROR_CODES = {
    "local_cannot_connect", "local_unsupported", "local_invalid_credentials",
    "local_invalid_host", "local_not_found", "device_not_found",
}


def value_type(value: Any) -> str:
    return {dict: "object", list: "array", str: "string", bool: "boolean",
            int: "integer", float: "number", type(None): "null"}.get(type(value), "other")


def _numeric(value: Any, depth: int = 0) -> Any:
    if type(value) is bool or value is None:
        return value
    if type(value) in (int, float) and abs(value) <= 1e12 and math.isfinite(value):
        return value
    if isinstance(value, list) and depth < 2:
        return [_numeric(item, depth + 1) for item in value[:16]]
    return REDACTED


def _parse(value: Any) -> Any:
    if isinstance(value, str) and len(value) <= MAX_TEXT:
        try:
            return json.loads(value)
        except (ValueError, RecursionError):
            pass
    return value


def _safe_text(value: Any, pattern: str, secrets: tuple[str, ...]) -> str:
    if (isinstance(value, str) and len(value) <= 64
            and re.fullmatch(pattern, value)
            and not any(secret in value for secret in secrets)):
        return value
    return REDACTED


def describe_response(response: Any, config: dict) -> dict:
    """Export known telemetry values and unknown DP types, never arbitrary text.

    Unknown values/fields and card DPs 112/113 are deliberately excluded. New
    firmware needs a reviewed schema before more fields can be exported.
    """
    secrets = tuple(str(config[key]) for key in ("local_key", "local_device_id", "local_host")
                    if config.get(key))
    result = {"response_type": value_type(response), "dps": {}, "checks": {}}
    if not isinstance(response, dict):
        return result
    result["protocol_error"] = bool(response.get("Error") or response.get("Err"))
    # Error bodies can contain keys and raw packets. Only a numeric Tuya code is safe.
    error = response.get("Err")
    if type(error) is int and 0 <= error <= 9999:
        result["protocol_error_code"] = error
    elif isinstance(error, str) and re.fullmatch(r"\d{1,4}", error):
        result["protocol_error_code"] = error
    dps = response.get("dps")
    result["dps_type"] = value_type(dps)
    if not isinstance(dps, dict):
        return result
    payload = _parse(dps.get("102"))
    payload = payload if isinstance(payload, dict) else {}
    result["checks"] = {
        "dp102_present": "102" in dps,
        "dp102_object": isinstance(_parse(dps.get("102")), dict),
        "dp102_missing_required_fields": [key for key in ("p", "e", "t") if key not in payload],
        "dp102_L_is_array": isinstance(payload.get("L"), list),
        "dp102_L1_is_array": isinstance(payload.get("L1"), list),
        "dp109_present": "109" in dps,
        "dp109_is_string": isinstance(dps.get("109"), str),
    }
    result["dp_count"] = len(dps)
    result["dps_truncated"] = len(dps) > MAX_DPS
    for key, raw in list(dps.items())[:MAX_DPS]:
        dp = str(key)
        if not re.fullmatch(r"\d{1,4}", dp):
            continue
        item = {"type": value_type(raw), "value": REDACTED}
        parsed = _parse(raw)
        if dp in NUMERIC_DPS:
            item["value"] = _numeric(raw)
        elif dp == "107":
            item["value"] = _numeric(parsed)
        elif dp == "109":
            item["value"] = _safe_text(raw, r"[A-Z][A-Z_0-9 -]{0,47}", secrets)
        elif dp in OBJECT_FIELDS and isinstance(parsed, dict):
            item["encoding"] = "json_string" if isinstance(raw, str) else "object"
            item["value"] = {}
            for field in sorted(OBJECT_FIELDS[dp]):
                if field not in parsed:
                    continue
                value = parsed[field]
                if dp == "106" and field == "fv":
                    safe = _safe_text(value, r"[()vVfF0-9. _-]+", secrets)
                elif dp == "151" and field in {"ss", "se"}:
                    safe = _safe_text(value, r"\d{2}:\d{2}", secrets)
                else:
                    safe = _numeric(value)
                item["value"][field] = {"type": value_type(value), "value": safe}
            item["omitted_fields"] = sum(key not in OBJECT_FIELDS[dp] for key in parsed)
        result["dps"][dp] = item
    return result


def build_report(error: Exception, config: dict, source: str, ha_version: str) -> dict:
    code = str(error)
    private = tuple(str(config[key]) for key in ("local_key", "local_device_id", "local_host") if config.get(key))
    product_id = _safe_text(config.get("local_product_id"), r"[a-zA-Z0-9]{8,32}", private)
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "integration": "tuyaextend_amperepoint",
        "integration_version": VERSION,
        "home_assistant_version": ha_version,
        "operation": source if source in {"local_import", "local_manual", "local_connection"} else "local_setup",
        "error": code if code in ERROR_CODES else "local_cannot_connect",
        "failure_stage": {
            "local_invalid_credentials": "input_validation",
            "local_invalid_host": "input_validation",
            "local_not_found": "lan_discovery",
            "local_unsupported": "dp_or_control_profile_validation",
        }.get(code, "lan_connection_or_response"),
        "product_id": product_id if product_id != REDACTED else None,
        "connection": {
            "protocol": config.get("local_protocol") if config.get("local_protocol") in {"3.3", "3.4", "3.5"} else "unknown",
            "host_provided": bool(config.get("local_host")),
            "device_id_provided": bool(config.get("local_device_id")),
            "local_key_provided": bool(config.get("local_key")),
        },
        "snapshot": getattr(error, "diagnostics", None),
        "device_commands_sent": False,
        "privacy": "No device ID, host, local key, account details, card data or raw error messages. Unknown DP values are omitted.",
    }
