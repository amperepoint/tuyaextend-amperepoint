from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_SOURCE_CURRENT_LIMIT, CONF_SOURCE_TARGET_ENERGY, DOMAIN
from .coordinator import AmperePointCoordinator
from .entity import AmperePointEntity, AmperePointEntityDescription


CURRENT_LIMIT_DESCRIPTION = AmperePointEntityDescription(
    key="current_limit",
    translation_key="current_limit",
    icon="mdi:current-ac",
)

TARGET_ENERGY_DESCRIPTION = AmperePointEntityDescription(
    key="target_energy",
    translation_key="target_energy",
    icon="mdi:battery-arrow-up",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AmperePointCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[NumberEntity] = []
    current_source = entry.options.get(CONF_SOURCE_CURRENT_LIMIT) or entry.data.get(
        CONF_SOURCE_CURRENT_LIMIT
    )
    if (
        current_source and current_source.split(".", 1)[0] in {"number", "input_number"}
    ) or coordinator.can_write_dp("charge_cur_set"):
        entities.append(AmperePointCurrentLimitNumber(coordinator))
    target_source = entry.options.get(CONF_SOURCE_TARGET_ENERGY) or entry.data.get(
        CONF_SOURCE_TARGET_ENERGY
    )
    if (
        target_source and target_source.split(".", 1)[0] in {"number", "input_number"}
    ) or coordinator.can_write_dp("energy_charge"):
        entities.append(AmperePointTargetEnergyNumber(coordinator))
    async_add_entities(entities)


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
        if value := _mapped_number_attribute(
            self.coordinator, CONF_SOURCE_CURRENT_LIMIT, "min"
        ):
            return value
        if value := self.coordinator.dp_definition("charge_cur_set").get("min"):
            return float(value)
        return float(self.coordinator.model_limits.min_current_a)

    @property
    def native_max_value(self) -> float:
        if value := _mapped_number_attribute(
            self.coordinator, CONF_SOURCE_CURRENT_LIMIT, "max"
        ):
            return value
        if value := self.coordinator.dp_definition("charge_cur_set").get("max"):
            return float(value)
        return float(self.coordinator.model_limits.max_current_a)

    @property
    def native_step(self) -> float:
        if value := _mapped_number_attribute(
            self.coordinator, CONF_SOURCE_CURRENT_LIMIT, "step"
        ):
            return value
        if value := self.coordinator.dp_definition("charge_cur_set").get("step"):
            return float(value)
        return float(self.coordinator.model_limits.current_step_a)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_current_limit(value)
        await self.coordinator.async_request_refresh()


class AmperePointTargetEnergyNumber(AmperePointEntity, NumberEntity):
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, coordinator: AmperePointCoordinator) -> None:
        super().__init__(coordinator, TARGET_ENERGY_DESCRIPTION)

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("target_energy_kwh")

    @property
    def native_min_value(self) -> float:
        if value := _mapped_number_attribute(
            self.coordinator, CONF_SOURCE_TARGET_ENERGY, "min"
        ):
            return value
        return float(self.coordinator.dp_definition("energy_charge").get("min") or 0)

    @property
    def native_max_value(self) -> float:
        if value := _mapped_number_attribute(
            self.coordinator, CONF_SOURCE_TARGET_ENERGY, "max"
        ):
            return value
        return float(self.coordinator.dp_definition("energy_charge").get("max") or 200)

    @property
    def native_step(self) -> float:
        if value := _mapped_number_attribute(
            self.coordinator, CONF_SOURCE_TARGET_ENERGY, "step"
        ):
            return value
        return float(self.coordinator.dp_definition("energy_charge").get("step") or 1)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_target_energy(value)
        await self.coordinator.async_request_refresh()


def _mapped_number_attribute(
    coordinator: AmperePointCoordinator, config_key: str, attribute: str
) -> float | None:
    entity_id = coordinator._config(config_key)
    state = coordinator.hass.states.get(entity_id) if entity_id else None
    value = state.attributes.get(attribute) if state else None
    return float(value) if value is not None else None
