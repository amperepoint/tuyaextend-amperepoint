from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AmperePointCoordinator
from .entity import AmperePointEntity, AmperePointEntityDescription


SCHEDULE_START_DESCRIPTION = AmperePointEntityDescription(
    key="schedule_time",
    translation_key="schedule_start_time",
    value_key="schedule_start_time",
    icon="mdi:clock-start",
)

SCHEDULE_END_DESCRIPTION = AmperePointEntityDescription(
    key="schedule_end_time",
    translation_key="schedule_end_time",
    value_key="schedule_end_time",
    icon="mdi:clock-end",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AmperePointCoordinator = hass.data[DOMAIN][entry.entry_id]
    if not coordinator.can_write_dp("local_timer"):
        return
    if (
        coordinator.data.get("schedule_start_time") is None
        or coordinator.data.get("schedule_end_time") is None
    ):
        return
    async_add_entities(
        [
            AmperePointScheduleBoundary(
                coordinator, SCHEDULE_START_DESCRIPTION, "start"
            ),
            AmperePointScheduleBoundary(coordinator, SCHEDULE_END_DESCRIPTION, "end"),
        ]
    )


class AmperePointScheduleBoundary(AmperePointEntity, TimeEntity):
    def __init__(
        self,
        coordinator: AmperePointCoordinator,
        description: AmperePointEntityDescription,
        boundary: str,
    ) -> None:
        super().__init__(coordinator, description)
        self._boundary = boundary

    @property
    def native_value(self) -> time | None:
        return self._data_value

    async def async_set_value(self, value: time) -> None:
        await self.coordinator.async_set_schedule_boundary(self._boundary, value)
        await self.coordinator.async_request_refresh()
