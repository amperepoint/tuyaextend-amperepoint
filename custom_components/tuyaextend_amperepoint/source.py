from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import CONF_SOURCE_DEVICE_ID


KNOWN_DP_IDS: dict[str, int] = {
    "forward_energy_total": 1,
    "work_state": 3,
    "charge_cur_set": 4,
    "phase_a": 6,
    "phase_b": 7,
    "phase_c": 8,
    "power_total": 9,
    "fault": 10,
    "connection_state": 13,
    "work_mode": 14,
    "energy_charge": 17,
    "switch": 18,
    "local_timer": 19,
    "system_version": 23,
    "temp_current": 24,
    "charge_energy_once": 25,
    "mode_set": 33,
}


@dataclass(slots=True)
class NativeTuyaSource:
    """Read and control charger DPS from the official Tuya runtime."""

    hass: HomeAssistant
    manager: Any
    device: Any

    @classmethod
    def resolve(
        cls, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> NativeTuyaSource | None:
        source_device_id = config_entry.options.get(
            CONF_SOURCE_DEVICE_ID,
            config_entry.data.get(CONF_SOURCE_DEVICE_ID),
        )
        if not source_device_id:
            return None

        device_entry = dr.async_get(hass).async_get(source_device_id)
        if device_entry is None:
            return None

        tuya_device_id = next(
            (
                identifier[1]
                for identifier in device_entry.identifiers
                if identifier[0] == "tuya"
            ),
            None,
        )
        if tuya_device_id is None:
            return None

        for entry_id in device_entry.config_entries:
            source_entry = hass.config_entries.async_get_entry(entry_id)
            if source_entry is None or source_entry.domain != "tuya":
                continue
            listener = getattr(source_entry, "runtime_data", None)
            manager = getattr(listener, "manager", None)
            device_map = getattr(manager, "device_map", {})
            if device := device_map.get(tuya_device_id):
                return cls(hass=hass, manager=manager, device=device)

        return None

    @property
    def available(self) -> bool:
        return bool(getattr(self.device, "online", False))

    def has(self, code: str) -> bool:
        return code in getattr(self.device, "status", {}) or code in getattr(
            self.device, "function", {}
        )

    def writable(self, code: str) -> bool:
        return code in getattr(self.device, "function", {})

    def raw(self, code: str) -> Any:
        return getattr(self.device, "status", {}).get(code)

    def definition(self, code: str) -> dict[str, Any]:
        function = getattr(self.device, "function", {}).get(code)
        status_range = getattr(self.device, "status_range", {}).get(code)
        definition = function or status_range
        values: dict[str, Any] = {}
        if definition is not None:
            try:
                values = json.loads(getattr(definition, "values", "{}"))
            except (TypeError, ValueError):
                values = {}

        return {
            "dp_id": KNOWN_DP_IDS.get(code),
            "type": getattr(definition, "type", None),
            "unit": values.get("unit"),
            "scale": values.get("scale", 0),
            "min": values.get("min"),
            "max": values.get("max"),
            "step": values.get("step"),
            "range": values.get("range"),
            "labels": values.get("label"),
            "writable": function is not None,
        }

    def scaled(self, code: str) -> Any:
        value = self.raw(code)
        if (
            value is None
            or isinstance(value, bool)
            or not isinstance(value, int | float)
        ):
            return value
        scale = self.definition(code).get("scale") or 0
        return value / (10**scale)

    def values(self) -> dict[str, Any]:
        return dict(getattr(self.device, "status", {}))

    def definitions(self) -> dict[str, dict[str, Any]]:
        codes = set(self.values())
        codes.update(getattr(self.device, "function", {}))
        codes.update(getattr(self.device, "status_range", {}))
        return {code: self.definition(code) for code in sorted(codes)}

    def bitmap_labels(self, code: str) -> list[str]:
        value = self.raw(code)
        labels = self.definition(code).get("labels") or []
        if not isinstance(value, int) or value == 0:
            return []
        return [label for bit, label in enumerate(labels) if value & (1 << bit)]

    async def async_send(self, code: str, value: Any) -> None:
        if not self.writable(code):
            raise HomeAssistantError(f"Tuya DP code is not writable: {code}")
        definition = self.definition(code)
        scale = definition.get("scale") or 0
        encoded = value
        if isinstance(value, int | float) and not isinstance(value, bool) and scale:
            encoded = round(value * (10**scale))
        await self.hass.async_add_executor_job(
            self.manager.send_commands,
            self.device.id,
            [{"code": code, "value": encoded}],
        )
