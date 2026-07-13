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
    CONF_SOURCE_TOTAL_ENERGY,
    CONF_SOURCE_VOLTAGE_L1,
    CONF_SOURCE_VOLTAGE_L2,
    CONF_SOURCE_VOLTAGE_L3,
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
    data = coordinator.data if coordinator else {}

    return async_redact_data(
        {
            "entry": {
                "title": config_entry.title,
                "data": dict(config_entry.data),
                "options": dict(config_entry.options),
            },
            "last_data": data,
        },
        TO_REDACT,
    )
