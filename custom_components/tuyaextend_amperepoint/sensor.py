from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory

from .const import CONF_SOURCE_RAW_DP, DOMAIN
from .coordinator import AmperePointCoordinator
from .entity import AmperePointEntity


@dataclass(frozen=True, kw_only=True)
class AmperePointSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]


SENSORS: tuple[AmperePointSensorDescription, ...] = (
    AmperePointSensorDescription(
        key="status",
        translation_key="status",
        icon="mdi:ev-station",
        value_fn=lambda data: data.get("status"),
    ),
    AmperePointSensorDescription(
        key="power",
        translation_key="power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("power_kw"),
    ),
    AmperePointSensorDescription(
        key="session_energy",
        translation_key="session_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: data.get("session_energy_kwh"),
    ),
    AmperePointSensorDescription(
        key="total_energy",
        translation_key="total_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: data.get("total_energy_kwh"),
    ),
    AmperePointSensorDescription(
        key="last_session_energy",
        translation_key="last_session_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda data: data.get("last_session_energy_kwh"),
    ),
    AmperePointSensorDescription(
        key="temperature",
        translation_key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("temperature_c"),
    ),
    AmperePointSensorDescription(
        key="session_cost",
        translation_key="session_cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda data: data.get("session_cost"),
    ),
    AmperePointSensorDescription(
        key="tariff",
        translation_key="tariff",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=lambda data: data.get("tariff"),
    ),
    AmperePointSensorDescription(
        key="phase_count",
        translation_key="phase_count",
        icon="mdi:sine-wave",
        value_fn=lambda data: data.get("phase_count"),
    ),
    AmperePointSensorDescription(
        key="error",
        translation_key="error",
        icon="mdi:alert-circle-outline",
        value_fn=lambda data: data.get("error"),
    ),
    AmperePointSensorDescription(
        key="system_version",
        translation_key="system_version",
        icon="mdi:chip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("system_version"),
    ),
    AmperePointSensorDescription(
        key="raw_dp",
        translation_key="raw_dp",
        icon="mdi:database-search",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("raw_dp_count"),
    ),
    AmperePointSensorDescription(
        key="voltage_l1",
        translation_key="voltage_l1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("voltage_l1"),
    ),
    AmperePointSensorDescription(
        key="voltage_l2",
        translation_key="voltage_l2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("voltage_l2"),
    ),
    AmperePointSensorDescription(
        key="voltage_l3",
        translation_key="voltage_l3",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("voltage_l3"),
    ),
    AmperePointSensorDescription(
        key="current_l1",
        translation_key="current_l1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("current_l1"),
    ),
    AmperePointSensorDescription(
        key="current_l2",
        translation_key="current_l2",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("current_l2"),
    ),
    AmperePointSensorDescription(
        key="current_l3",
        translation_key="current_l3",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("current_l3"),
    ),
    AmperePointSensorDescription(
        key="power_l1",
        translation_key="power_l1",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.get("power_l1"),
    ),
    AmperePointSensorDescription(
        key="power_l2",
        translation_key="power_l2",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.get("power_l2"),
    ),
    AmperePointSensorDescription(
        key="power_l3",
        translation_key="power_l3",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.get("power_l3"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AmperePointCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AmperePointSensor(coordinator, description) for description in SENSORS
    )


class AmperePointSensor(AmperePointEntity, SensorEntity):
    entity_description: AmperePointSensorDescription

    def __init__(
        self,
        coordinator: AmperePointCoordinator,
        description: AmperePointSensorDescription,
    ) -> None:
        super().__init__(coordinator, description)
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.entity_description.key == "session_cost":
            return self.coordinator.data.get("currency")
        if self.entity_description.key == "tariff":
            return f"{self.coordinator.data.get('currency', '')}/kWh".strip()
        return super().native_unit_of_measurement

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key != "raw_dp":
            return None

        raw_dp = self.coordinator.data.get("raw_dp", {})
        metadata = self.coordinator.data.get("dp_metadata", {})
        attributes: dict[str, Any] = {
            "source_type": self.coordinator.data.get("source_type"),
            "source_online": self.coordinator.data.get("source_online"),
            "raw_dp": raw_dp,
            "dp_metadata": metadata,
        }
        attributes.update({f"raw_{code}": value for code, value in raw_dp.items()})

        source = self.coordinator.native_source
        if source is not None:
            attributes.update(
                {
                    "forward_energy_total_kwh": source.scaled("forward_energy_total"),
                    "power_total_kw": source.scaled("power_total"),
                    "charge_current_a": source.scaled("charge_cur_set"),
                    "energy_charge_kwh": source.scaled("energy_charge"),
                    "temp_current_c": source.scaled("temp_current"),
                    "charge_energy_once_kwh": source.scaled("charge_energy_once"),
                }
            )
        else:
            source_entity = self.coordinator._config(CONF_SOURCE_RAW_DP)
            source_state = (
                self.hass.states.get(source_entity) if source_entity else None
            )
            if source_state is not None:
                attributes.update(
                    {
                        key: value
                        for key, value in source_state.attributes.items()
                        if key not in {"friendly_name", "icon"}
                    }
                )
        return attributes
