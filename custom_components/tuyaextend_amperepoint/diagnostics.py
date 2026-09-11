from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_SOURCE_CHARGE_SWITCH,
    CONF_SOURCE_CONNECTED,
    CONF_SOURCE_CURRENT_L1,
    CONF_SOURCE_CURRENT_L2,
    CONF_SOURCE_CURRENT_L3,
    CONF_SOURCE_CURRENT_LIMIT,
    CONF_SOURCE_ERROR,
    CONF_SOURCE_POWER,
    CONF_SOURCE_SESSION_ENERGY,
    CONF_SOURCE_STATUS,
    CONF_SOURCE_TARGET_ENERGY,
    CONF_SOURCE_TOTAL_ENERGY,
    CONF_SOURCE_VOLTAGE_L1,
    CONF_SOURCE_VOLTAGE_L2,
    CONF_SOURCE_VOLTAGE_L3,
    CONF_SOURCE_WORK_MODE,
    CONF_TARIFF_ENTITY,
    DOMAIN,
)

TO_REDACT = {
    CONF_SOURCE_STATUS,
    CONF_SOURCE_CONNECTED,
    CONF_SOURCE_POWER,
    CONF_SOURCE_SESSION_ENERGY,
    CONF_SOURCE_TOTAL_ENERGY,
    CONF_SOURCE_CURRENT_LIMIT,
    CONF_SOURCE_CHARGE_SWITCH,
    CONF_SOURCE_WORK_MODE,
    CONF_SOURCE_TARGET_ENERGY,
    CONF_SOURCE_ERROR,
    CONF_TARIFF_ENTITY,
    CONF_SOURCE_VOLTAGE_L1,
    CONF_SOURCE_VOLTAGE_L2,
    CONF_SOURCE_VOLTAGE_L3,
    CONF_SOURCE_CURRENT_L1,
    CONF_SOURCE_CURRENT_L2,
    CONF_SOURCE_CURRENT_L3,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> dict[str, Any]:
    coordinator = hass.data.get(DOMAIN, {}).get(config_entry.entry_id)
    data = (coordinator.data if coordinator else {}) or {}
    if config_entry.data.get("source_integration") == "amperepoint_local":
        # Never export local credentials, identifiers or raw protocol payloads.
        from .const import VERSION
        return {
            "version": VERSION,
            "source_type": data.get("source_type"),
            "source_online": data.get("source_online"),
            "read_only": True,
            "local_family": config_entry.data.get("local_family"),
            "dp_count": data.get("raw_dp_count"),
            "last_update_success": getattr(coordinator, "last_update_success", None),
        }
    native_source = coordinator.native_source if coordinator else None

    return async_redact_data(
        {
            "entry": {
                "title": config_entry.title,
                "data": dict(config_entry.data),
                "options": dict(config_entry.options),
            },
            "last_data": data,
            "native_tuya": (
                {
                    "available": native_source.available,
                    "category": getattr(native_source.device, "category", None),
                    "product_id": getattr(native_source.device, "product_id", None),
                    "status": native_source.values(),
                    "definitions": native_source.definitions(),
                }
                if native_source
                else None
            ),
        },
        TO_REDACT,
    )
