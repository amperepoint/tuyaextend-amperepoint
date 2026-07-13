from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AmperePointCoordinator
from .entity import AmperePointEntity


@dataclass(frozen=True, kw_only=True)
class AmperePointBinarySensorDescription(BinarySensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], bool]


BINARY_SENSORS: tuple[AmperePointBinarySensorDescription, ...] = (
    AmperePointBinarySensorDescription(
        key="vehicle_connected",
        translation_key="vehicle_connected",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=lambda data: bool(data.get("vehicle_connected")),
    ),
    AmperePointBinarySensorDescription(
        key="charging_complete",
        translation_key="charging_complete",
        icon="mdi:battery-check",
        value_fn=lambda data: bool(data.get("charging_complete")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AmperePointCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AmperePointBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
    )


class AmperePointBinarySensor(AmperePointEntity, BinarySensorEntity):
    entity_description: AmperePointBinarySensorDescription

    @property
    def is_on(self) -> bool:
        return self.entity_description.value_fn(self.coordinator.data)
