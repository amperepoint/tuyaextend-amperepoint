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

from .const import DOMAIN, VERSION

_LOGGER = logging.getLogger(__name__)

_DASHBOARD_LOCK = "dashboard_lock"

DASHBOARD_URL_PATH = "amperepoint-panel"
DASHBOARD_STORAGE_ID = "amperepoint_panel"
DASHBOARD_TITLE = "AmperePoint"
DASHBOARD_ICON = "mdi:ev-station"
SETTINGS_PATH = f"/config/integrations/integration/{DOMAIN}"

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
    "session_duration": "sessionDuration",
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
    """Return the exact entity mapping generated for a legacy entry panel."""
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


def _dashboard_config() -> dict[str, Any]:
    # The card resolves entities from the entity registry and offers a device
    # selector, so one shared panel serves every configured charger.
    return {
        "title": DASHBOARD_TITLE,
        "views": [
            {
                "title": DASHBOARD_TITLE,
                "path": "charger",
                "icon": DASHBOARD_ICON,
                "panel": True,
                "cards": [
                    {
                        "type": "custom:amperepoint-q22-card",
                        "dashboardVersion": VERSION,
                        "settingsPath": SETTINGS_PATH,
                    }
                ],
            }
        ],
    }


def _is_generated_legacy_dashboard(
    config: Any, entry: ConfigEntry, expected_entities: dict[str, str]
) -> bool:
    """Return whether a legacy dashboard still has the generated shape.

    Older releases promised to preserve user dashboard edits.  We can safely
    remove the per-entry panel only while its stored configuration still
    matches the integration-owned single-card layout.
    """
    if not isinstance(config, dict):
        return False
    if set(config) != {"title", "views"}:
        return False
    if config.get("title") != f"AmperePoint – {entry.title}":
        return False

    views = config.get("views")
    if not isinstance(views, list) or len(views) != 1:
        return False
    view = views[0]
    if not isinstance(view, dict):
        return False
    if set(view) != {"title", "path", "icon", "panel", "cards"}:
        return False
    if (
        view.get("title") != entry.title
        or view.get("path") != "charger"
        or view.get("icon") != DASHBOARD_ICON
        or view.get("panel") is not True
    ):
        return False

    cards = view.get("cards")
    if not isinstance(cards, list) or len(cards) != 1:
        return False
    card = cards[0]
    if not isinstance(card, dict):
        return False
    if card.get("type") != "custom:amperepoint-q22-card":
        return False
    if not set(card).issubset(
        {
            "type",
            "entities",
            "configEntryId",
            "dashboardVersion",
            "settingsPath",
        }
    ):
        return False
    if card.get("entities", {}) != expected_entities:
        return False
    if card.get("configEntryId", entry.entry_id) != entry.entry_id:
        return False
    if card.get("settingsPath", SETTINGS_PATH) != SETTINGS_PATH:
        return False
    return True


async def _async_remove_legacy_dashboard(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Remove an unchanged per-entry dashboard generated by earlier versions."""
    url_path = f"amperepoint-{entry.entry_id[:8]}"
    dashboards = hass.data[LOVELACE_DATA].dashboards
    legacy = dashboards.get(url_path)
    if not isinstance(legacy, LovelaceStorage):
        return False

    try:
        config = await legacy.async_load(False)
    except ConfigNotFound:
        config = None
    if config is not None and not _is_generated_legacy_dashboard(
        config, entry, _card_entities(hass, entry)
    ):
        _LOGGER.warning(
            "Preserving customized legacy AmperePoint dashboard at /%s", url_path
        )
        return False

    try:
        await legacy.async_delete()
    except Exception:  # pragma: no cover - defensive
        _LOGGER.warning(
            "Could not delete legacy AmperePoint dashboard storage %s", url_path
        )
        return False
    try:
        frontend.async_remove_panel(hass, url_path)
    except (KeyError, ValueError):  # pragma: no cover - defensive
        pass
    dashboards.pop(url_path, None)
    _LOGGER.info("Removed legacy AmperePoint dashboard at /%s", url_path)
    return True


async def async_create_dashboard(hass: HomeAssistant, entry: ConfigEntry) -> str:
    """Ensure the single shared AmperePoint panel exists."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    lock = domain_data.setdefault(_DASHBOARD_LOCK, asyncio.Lock())

    async with lock:
        await _async_remove_legacy_dashboard(hass, entry)

        existing = hass.data[LOVELACE_DATA].dashboards.get(DASHBOARD_URL_PATH)
        if existing is not None:
            return DASHBOARD_URL_PATH

        item = {
            "id": DASHBOARD_STORAGE_ID,
            CONF_ICON: DASHBOARD_ICON,
            CONF_TITLE: DASHBOARD_TITLE,
            "url_path": DASHBOARD_URL_PATH,
        }
        storage = LovelaceStorage(hass, item)
        hass.data[LOVELACE_DATA].dashboards[DASHBOARD_URL_PATH] = storage
        frontend.async_register_built_in_panel(
            hass,
            "lovelace",
            frontend_url_path=DASHBOARD_URL_PATH,
            require_admin=False,
            show_in_sidebar=True,
            sidebar_title=DASHBOARD_TITLE,
            sidebar_icon=DASHBOARD_ICON,
            config={"mode": MODE_STORAGE},
        )
        try:
            await storage.async_load(False)
        except ConfigNotFound:
            await storage.async_save(_dashboard_config())
            _LOGGER.info("Created AmperePoint dashboard at /%s", DASHBOARD_URL_PATH)
        return DASHBOARD_URL_PATH
