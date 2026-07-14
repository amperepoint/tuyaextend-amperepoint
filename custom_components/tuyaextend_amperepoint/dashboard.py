from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components import frontend
from homeassistant.components.lovelace.dashboard import LovelaceStorage
from homeassistant.components.lovelace.const import (
    ConfigNotFound,
    CONF_TITLE,
    LOVELACE_DATA,
    MODE_STORAGE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ICON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_DASHBOARD_LOCK = "dashboard_lock"

_CARD_ENTITY_KEYS = {
    "charging": "switch",
    "current_limit": "currentLimit",
    "target_energy": "targetEnergy",
    "charging_mode": "chargingMode",
    "schedule_time": "scheduleStartTime",
    "schedule_end_time": "scheduleEndTime",
    "planner": "planner",
    "status": "status",
    "vehicle_connected": "cp",
    "error": "faults",
    "power": "power",
    "session_energy": "sessionEnergy",
    "total_energy": "totalEnergy",
    "last_session_energy": "lastSessionDp25",
    "temperature": "temperature",
    "system_version": "systemVersion",
    "raw_dp": "rawDp",
    "phase_count": "phaseCount",
    "voltage_l1": "l1Voltage",
    "voltage_l2": "l2Voltage",
    "voltage_l3": "l3Voltage",
    "current_l1": "l1Current",
    "current_l2": "l2Current",
    "current_l3": "l3Current",
    "power_l1": "l1Power",
    "power_l2": "l2Power",
    "power_l3": "l3Power",
}


def _card_entities(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, str]:
    registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_"
    entities: dict[str, str] = {}

    for registry_entry in registry.entities.values():
        if registry_entry.config_entry_id != entry.entry_id:
            continue
        unique_id = registry_entry.unique_id
        if not unique_id.startswith(prefix):
            continue
        key = unique_id.removeprefix(prefix)
        if card_key := _CARD_ENTITY_KEYS.get(key):
            entities[card_key] = registry_entry.entity_id

    return entities


def _dashboard_config(entry: ConfigEntry, entities: dict[str, str]) -> dict[str, Any]:
    return {
        "title": f"AmperePoint – {entry.title}",
        "views": [
            {
                "title": entry.title,
                "path": "charger",
                "icon": "mdi:ev-station",
                "panel": True,
                "cards": [
                    {
                        "type": "custom:amperepoint-q22-card",
                        "entities": entities,
                    }
                ],
            }
        ],
    }


async def _async_merge_card_entities(
    storage: LovelaceStorage, entities: dict[str, str]
) -> None:
    """Migrate generated views and add entities without replacing user choices."""
    try:
        config = await storage.async_load(False)
    except ConfigNotFound:
        return

    changed = False
    for view in config.get("views", []):
        cards = view.get("cards", [])
        amperepoint_cards = [
            card for card in cards if card.get("type") == "custom:amperepoint-q22-card"
        ]
        if len(cards) == 1 and amperepoint_cards and view.get("panel") is not True:
            view["panel"] = True
            changed = True

        for card in amperepoint_cards:
            card_entities = card.setdefault("entities", {})
            legacy_schedule = card_entities.pop("scheduleTime", None)
            if legacy_schedule:
                changed = True
                if "scheduleStartTime" not in card_entities:
                    card_entities["scheduleStartTime"] = legacy_schedule
            for key, entity_id in entities.items():
                if key not in card_entities:
                    card_entities[key] = entity_id
                    changed = True

    if changed:
        await storage.async_save(config)


async def async_create_dashboard(hass: HomeAssistant, entry: ConfigEntry) -> str:
    """Create one dedicated, non-destructive dashboard for a config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    lock = domain_data.setdefault(_DASHBOARD_LOCK, asyncio.Lock())
    url_path = f"amperepoint-{entry.entry_id[:8]}"

    async with lock:
        existing = hass.data[LOVELACE_DATA].dashboards.get(url_path)
        if existing is not None:
            if isinstance(existing, LovelaceStorage):
                await _async_merge_card_entities(existing, _card_entities(hass, entry))
            return url_path

        item = {
            "id": f"amperepoint_{entry.entry_id[:8].lower()}",
            CONF_ICON: "mdi:ev-station",
            CONF_TITLE: f"AmperePoint – {entry.title}",
            "url_path": url_path,
        }
        storage = LovelaceStorage(hass, item)
        hass.data[LOVELACE_DATA].dashboards[url_path] = storage
        frontend.async_register_built_in_panel(
            hass,
            "lovelace",
            frontend_url_path=url_path,
            require_admin=False,
            show_in_sidebar=True,
            sidebar_title=item[CONF_TITLE],
            sidebar_icon=item.get(CONF_ICON, "mdi:view-dashboard"),
            config={"mode": MODE_STORAGE},
        )
        try:
            await storage.async_load(False)
        except ConfigNotFound:
            await storage.async_save(
                _dashboard_config(entry, _card_entities(hass, entry))
            )
            _LOGGER.info("Created AmperePoint dashboard at /%s", url_path)
        else:
            await _async_merge_card_entities(storage, _card_entities(hass, entry))
        return url_path
