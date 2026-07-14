from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AmperePointCoordinator
from .entity import AmperePointEntity, AmperePointEntityDescription


SCHEDULE_TIME_DESCRIPTION = AmperePointEntityDescription(
    key="schedule_time",
    translation_key="schedule_time",
    icon="mdi:calendar-clock",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AmperePointCoordinator = hass.data[DOMAIN][entry.entry_id]
    if (
        coordinator.can_write_dp("local_timer")
        and coordinator.data.get("schedule_time") is not None
    ):
        async_add_entities([AmperePointScheduleTime(coordinator)])


class AmperePointScheduleTime(AmperePointEntity, TimeEntity):
    def __init__(self, coordinator: AmperePointCoordinator) -> None:
        super().__init__(coordinator, SCHEDULE_TIME_DESCRIPTION)

    @property
    def native_value(self) -> time | None:
        return self.coordinator.data.get("schedule_time")

    async def async_set_value(self, value: time) -> None:
        await self.coordinator.async_set_schedule_time(value)
        await self.coordinator.async_request_refresh()
