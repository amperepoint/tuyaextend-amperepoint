from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_MODEL, DOMAIN
from .coordinator import AmperePointCoordinator
from .entity import AmperePointEntity, AmperePointEntityDescription
from .models import MODELS


MODEL_DESCRIPTION = AmperePointEntityDescription(
    key="model",
    translation_key="model",
    icon="mdi:ev-plug-type2",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AmperePointCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AmperePointModelSelect(coordinator)])


class AmperePointModelSelect(AmperePointEntity, SelectEntity):
    def __init__(self, coordinator: AmperePointCoordinator) -> None:
        super().__init__(coordinator, MODEL_DESCRIPTION)

    @property
    def options(self) -> list[str]:
        return [model.name for model in MODELS.values()]

    @property
    def current_option(self) -> str | None:
        return self.coordinator.model.name

    async def async_select_option(self, option: str) -> None:
        model_key = next(
            (key for key, model in MODELS.items() if model.name == option),
            None,
        )
        if model_key is None:
            return

        entry = self.coordinator.config_entry
        data = {**entry.data, CONF_MODEL: model_key}
        self.hass.config_entries.async_update_entry(entry, data=data)
        self.coordinator.set_model(model_key)
        await self.coordinator.async_request_refresh()
