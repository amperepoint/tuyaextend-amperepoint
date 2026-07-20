from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_validation as cv, selector

from .const import (
    CONF_COMPLETE_IDLE_MINUTES,
    CONF_COMPLETE_POWER_THRESHOLD,
    CONF_CURRENCY,
    CONF_MODEL,
    CONF_SOURCE_CHARGE_SWITCH,
    CONF_SOURCE_CONNECTED,
    CONF_SOURCE_CURRENT_L1,
    CONF_SOURCE_CURRENT_L2,
    CONF_SOURCE_CURRENT_L3,
    CONF_SOURCE_CURRENT_LIMIT,
    CONF_SOURCE_DEVICE_ID,
    CONF_SOURCE_ERROR,
    CONF_SOURCE_LAST_SESSION_ENERGY,
    CONF_SOURCE_NAME,
    CONF_SOURCE_PHASE_A,
    CONF_SOURCE_PHASE_B,
    CONF_SOURCE_PHASE_C,
    CONF_SOURCE_POWER,
    CONF_SOURCE_POWER_L1,
    CONF_SOURCE_POWER_L2,
    CONF_SOURCE_POWER_L3,
    CONF_SOURCE_RAW_DP,
    CONF_SOURCE_SESSION_ENERGY,
    CONF_SOURCE_TEMPERATURE,
    CONF_SOURCE_TARGET_ENERGY,
    CONF_SOURCE_TOTAL_ENERGY,
    CONF_SOURCE_STATUS,
    CONF_SOURCE_VOLTAGE_L1,
    CONF_SOURCE_VOLTAGE_L2,
    CONF_SOURCE_VOLTAGE_L3,
    CONF_SOURCE_WORK_MODE,
    CONF_TARIFF_ENTITY,
    CONF_TARIFF_VALUE,
    DEFAULT_COMPLETE_IDLE_MINUTES,
    DEFAULT_COMPLETE_POWER_THRESHOLD_KW,
    DEFAULT_CURRENCY,
    DEFAULT_TARIFF_VALUE,
    DOMAIN,
    NAME,
    SESSION_ENERGY_MODE_AUTO,
    SESSION_ENERGY_MODES,
    CONF_SESSION_ENERGY_MODE,
)
from .discovery import SourceCandidate, discover_sources
from .models import DEFAULT_MODEL, MODELS


def _model_options() -> dict[str, str]:
    return {key: model.name for key, model in MODELS.items()}


def _entity_selector(domains: list[str] | None = None) -> selector.EntitySelector:
    config = selector.EntitySelectorConfig(domain=domains) if domains else None
    return selector.EntitySelector(config)


def _optional_entity(
    key: str,
    domains: list[str] | None = None,
    current: Mapping[str, Any] | None = None,
) -> tuple[vol.Optional, selector.EntitySelector]:
    current_value = current.get(key) if current else None
    marker = (
        vol.Optional(key, default=current_value) if current_value else vol.Optional(key)
    )
    return marker, _entity_selector(domains)


def _settings_fields(current: Mapping[str, Any] | None = None) -> dict[Any, Any]:
    current = current or {}
    return {
        vol.Required(
            CONF_TARIFF_VALUE,
            default=current.get(CONF_TARIFF_VALUE, DEFAULT_TARIFF_VALUE),
        ): cv.positive_float,
        vol.Required(
            CONF_CURRENCY,
            default=current.get(CONF_CURRENCY, DEFAULT_CURRENCY),
        ): cv.string,
        vol.Required(
            CONF_COMPLETE_POWER_THRESHOLD,
            default=current.get(
                CONF_COMPLETE_POWER_THRESHOLD, DEFAULT_COMPLETE_POWER_THRESHOLD_KW
            ),
        ): cv.positive_float,
        vol.Required(
            CONF_COMPLETE_IDLE_MINUTES,
            default=current.get(
                CONF_COMPLETE_IDLE_MINUTES, DEFAULT_COMPLETE_IDLE_MINUTES
            ),
        ): cv.positive_int,
    }


def _settings_schema(current: Mapping[str, Any] | None = None) -> vol.Schema:
    return vol.Schema(_settings_fields(current))


def _schema(current: Mapping[str, Any] | None = None) -> vol.Schema:
    current = current or {}
    schema: dict[Any, Any] = {
        vol.Required(
            CONF_MODEL, default=current.get(CONF_MODEL, DEFAULT_MODEL)
        ): vol.In(_model_options()),
        vol.Optional(CONF_NAME, default=current.get(CONF_NAME, NAME)): cv.string,
        vol.Required(
            CONF_SESSION_ENERGY_MODE,
            default=current.get(CONF_SESSION_ENERGY_MODE, SESSION_ENERGY_MODE_AUTO),
        ): vol.In(SESSION_ENERGY_MODES),
        **_settings_fields(current),
    }

    optional_entities = (
        (CONF_SOURCE_RAW_DP, ["sensor"]),
        (CONF_SOURCE_STATUS, ["sensor", "select"]),
        (CONF_SOURCE_CONNECTED, ["binary_sensor", "sensor"]),
        (CONF_SOURCE_POWER, ["sensor"]),
        (CONF_SOURCE_SESSION_ENERGY, ["sensor"]),
        (CONF_SOURCE_TOTAL_ENERGY, ["sensor"]),
        (CONF_SOURCE_LAST_SESSION_ENERGY, ["sensor"]),
        (CONF_SOURCE_CURRENT_LIMIT, ["number", "input_number", "sensor"]),
        (CONF_SOURCE_CHARGE_SWITCH, ["switch", "input_boolean"]),
        (CONF_SOURCE_WORK_MODE, ["select", "sensor"]),
        (CONF_SOURCE_TARGET_ENERGY, ["number", "input_number", "sensor"]),
        (CONF_SOURCE_ERROR, ["sensor", "binary_sensor"]),
        (CONF_SOURCE_TEMPERATURE, ["sensor"]),
        (CONF_TARIFF_ENTITY, ["sensor", "input_number"]),
        (CONF_SOURCE_VOLTAGE_L1, ["sensor"]),
        (CONF_SOURCE_VOLTAGE_L2, ["sensor"]),
        (CONF_SOURCE_VOLTAGE_L3, ["sensor"]),
        (CONF_SOURCE_CURRENT_L1, ["sensor"]),
        (CONF_SOURCE_CURRENT_L2, ["sensor"]),
        (CONF_SOURCE_CURRENT_L3, ["sensor"]),
        (CONF_SOURCE_POWER_L1, ["sensor"]),
        (CONF_SOURCE_POWER_L2, ["sensor"]),
        (CONF_SOURCE_POWER_L3, ["sensor"]),
        (CONF_SOURCE_PHASE_A, ["sensor"]),
        (CONF_SOURCE_PHASE_B, ["sensor"]),
        (CONF_SOURCE_PHASE_C, ["sensor"]),
    )

    for key, domains in optional_entities:
        marker, value = _optional_entity(key, domains, current)
        schema[marker] = value

    return vol.Schema(schema)


def _automatic_schema(candidates: list[SourceCandidate]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_SOURCE_DEVICE_ID): vol.In(
                {
                    candidate.device_id: candidate.option_label
                    for candidate in candidates
                }
            ),
            vol.Optional(CONF_NAME): cv.string,
        }
    )


class AmperePointConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    _candidates: list[SourceCandidate]
    _candidate: SourceCandidate
    _entry_name: str

    async def async_step_integration_discovery(
        self, discovery_info: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Adopt a discovered charger automatically with default settings."""
        device_id = str(discovery_info.get(CONF_SOURCE_DEVICE_ID, ""))
        if not device_id:
            return self.async_abort(reason="device_not_found")
        await self.async_set_unique_id(f"{DOMAIN}_{device_id}")
        self._abort_if_unique_id_configured()
        title = str(discovery_info.get(CONF_SOURCE_NAME) or NAME)
        return self.async_create_entry(
            title=title,
            data={**discovery_info, CONF_NAME: title},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        self._candidates = discover_sources(self.hass)
        menu_options = ["automatic", "manual"] if self._candidates else ["manual"]
        return self.async_show_menu(
            step_id="user",
            menu_options=menu_options,
            description_placeholders={
                "count": str(len(self._candidates)),
            },
        )

    async def async_step_automatic(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        self._candidates = discover_sources(self.hass)

        if user_input is not None:
            candidate = next(
                (
                    item
                    for item in self._candidates
                    if item.device_id == user_input[CONF_SOURCE_DEVICE_ID]
                ),
                None,
            )
            if candidate is None:
                errors["base"] = "device_not_found"
            else:
                self._candidate = candidate
                self._entry_name = user_input.get(CONF_NAME) or candidate.title
                return await self.async_step_settings()

        if not self._candidates:
            return await self.async_step_manual()

        return self.async_show_form(
            step_id="automatic",
            data_schema=_automatic_schema(self._candidates),
            errors=errors,
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            await self.async_set_unique_id(f"{DOMAIN}_{self._candidate.device_id}")
            self._abort_if_unique_id_configured()
            data = {
                **self._candidate.as_config_data(),
                **user_input,
                CONF_NAME: self._entry_name,
            }
            return self.async_create_entry(title=self._entry_name, data=data)

        return self.async_show_form(
            step_id="settings",
            data_schema=_settings_schema(),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            source = (
                user_input.get(CONF_SOURCE_STATUS)
                or user_input.get(CONF_SOURCE_POWER)
                or user_input[CONF_MODEL]
            )
            await self.async_set_unique_id(f"{DOMAIN}_{source}")
            self._abort_if_unique_id_configured()

            title = user_input.get(CONF_NAME) or MODELS[user_input[CONF_MODEL]].name
            return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="manual",
            data_schema=_schema(),
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return AmperePointOptionsFlowHandler(config_entry)


class AmperePointOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        current = {**self._config_entry.data, **self._config_entry.options}

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_schema(current),
        )
