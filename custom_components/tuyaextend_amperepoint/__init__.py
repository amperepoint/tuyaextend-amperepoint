from __future__ import annotations

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS
from .coordinator import AmperePointCoordinator
from .dashboard import async_create_dashboard
from .discovery import discover_sources
from .frontend import async_register_frontend
from .planner import AmperePointPlanner
from .planner_model import PlannerConfigError


SERVICE_SET_PLANNER = "set_planner"
SERVICE_SET_PLANNER_OVERRIDE = "set_planner_override"
_SERVICES_REGISTERED = f"{DOMAIN}_planner_services_registered"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    await async_register_frontend(hass)
    _async_register_planner_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await async_register_frontend(hass)

    coordinator = AmperePointCoordinator(hass, entry)
    await coordinator.async_load_state()
    await coordinator.async_config_entry_first_refresh()

    planner = AmperePointPlanner(hass, entry, coordinator)
    await planner.async_load()
    coordinator.planner = planner

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await planner.async_start()

    await async_create_dashboard(hass, entry)
    _async_adopt_discovered_chargers(hass)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


def _async_adopt_discovered_chargers(hass: HomeAssistant) -> None:
    """Start discovery flows for Tuya chargers that have no entry yet.

    New devices join the integration (and the panel's device selector)
    automatically; duplicates are rejected by the flow's unique_id.
    """
    for candidate in discover_sources(hass):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_INTEGRATION_DISCOVERY},
                data=candidate.as_config_data(),
            )
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator: AmperePointCoordinator = hass.data[DOMAIN][entry.entry_id]
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await coordinator.planner.async_stop()
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _async_register_planner_services(hass: HomeAssistant) -> None:
    if hass.data.get(_SERVICES_REGISTERED):
        return

    async def set_planner(call: ServiceCall) -> None:
        planner = _planner_for_call(hass, call)
        try:
            await planner.async_set_config(
                bool(call.data.get("enabled", False)),
                call.data.get("windows", []),
            )
        except PlannerConfigError as err:
            raise HomeAssistantError(str(err)) from err

    async def set_planner_override(call: ServiceCall) -> None:
        planner = _planner_for_call(hass, call)
        try:
            await planner.async_set_override(
                str(call.data.get("mode", "clear")),
                duration_minutes=call.data.get("duration_minutes"),
                energy_kwh=call.data.get("energy_kwh"),
                current_a=call.data.get("current_a"),
            )
        except (PlannerConfigError, TypeError, ValueError) as err:
            raise HomeAssistantError(str(err)) from err

    hass.services.async_register(DOMAIN, SERVICE_SET_PLANNER, set_planner)
    hass.services.async_register(
        DOMAIN, SERVICE_SET_PLANNER_OVERRIDE, set_planner_override
    )
    hass.data[_SERVICES_REGISTERED] = True


def _planner_for_call(hass: HomeAssistant, call: ServiceCall) -> AmperePointPlanner:
    entry_id = str(call.data.get("config_entry_id", ""))
    coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
    planner = getattr(coordinator, "planner", None)
    if planner is None:
        raise HomeAssistantError("AmperePoint planner entry was not found")
    return planner
