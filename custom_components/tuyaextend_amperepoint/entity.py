from __future__ import annotations

from dataclasses import dataclass

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AmperePointCoordinator


@dataclass(frozen=True, kw_only=True)
class AmperePointEntityDescription(EntityDescription):
    value_key: str | None = None


class AmperePointEntity(CoordinatorEntity[AmperePointCoordinator]):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AmperePointCoordinator,
        description: AmperePointEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        # The entry title distinguishes chargers of the same model, so the
        # panel's device selector shows a unique name per charger.
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            manufacturer="Ampere Point",
            name=self.coordinator.config_entry.title or self.coordinator.model.name,
            model=self.coordinator.model.name,
        )

    @property
    def _data_value(self):
        if not self.entity_description.value_key:
            return None
        return self.coordinator.data.get(self.entity_description.value_key)
