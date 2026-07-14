from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_SOURCE_CHARGE_SWITCH, DOMAIN
from .coordinator import AmperePointCoordinator
from .entity import AmperePointEntity, AmperePointEntityDescription


CHARGING_DESCRIPTION = AmperePointEntityDescription(
    key="charging",
    translation_key="charging",
    icon="mdi:ev-station",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AmperePointCoordinator = hass.data[DOMAIN][entry.entry_id]
    if (
        entry.options.get(CONF_SOURCE_CHARGE_SWITCH)
        or entry.data.get(CONF_SOURCE_CHARGE_SWITCH)
        or coordinator.can_write_dp("switch")
    ):
        async_add_entities([AmperePointChargingSwitch(coordinator)])


class AmperePointChargingSwitch(AmperePointEntity, SwitchEntity):
    def __init__(self, coordinator: AmperePointCoordinator) -> None:
        super().__init__(coordinator, CHARGING_DESCRIPTION)

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.get("switch_enabled")

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_charging(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_charging(False)
        await self.coordinator.async_request_refresh()
