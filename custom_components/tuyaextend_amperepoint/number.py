from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_SOURCE_CURRENT_LIMIT, DOMAIN
from .coordinator import AmperePointCoordinator
from .entity import AmperePointEntity, AmperePointEntityDescription


CURRENT_LIMIT_DESCRIPTION = AmperePointEntityDescription(
    key="current_limit",
    translation_key="current_limit",
    icon="mdi:current-ac",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AmperePointCoordinator = hass.data[DOMAIN][entry.entry_id]
    if entry.options.get(CONF_SOURCE_CURRENT_LIMIT) or entry.data.get(
        CONF_SOURCE_CURRENT_LIMIT
    ):
        async_add_entities([AmperePointCurrentLimitNumber(coordinator)])


class AmperePointCurrentLimitNumber(AmperePointEntity, NumberEntity):
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE

    def __init__(self, coordinator: AmperePointCoordinator) -> None:
        super().__init__(coordinator, CURRENT_LIMIT_DESCRIPTION)

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("current_limit_a")

    @property
    def native_min_value(self) -> float:
        return float(self.coordinator.model_limits.min_current_a)

    @property
    def native_max_value(self) -> float:
        return float(self.coordinator.model_limits.max_current_a)

    @property
    def native_step(self) -> float:
        return float(self.coordinator.model_limits.current_step_a)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_current_limit(value)
        await self.coordinator.async_request_refresh()
