from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_validation as cv, selector

from .const import (
    CONF_AUTO_DISCOVERED,
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
    CONF_SOURCE_TOTAL_ENERGY,
    CONF_SOURCE_STATUS,
    CONF_SOURCE_VOLTAGE_L1,
    CONF_SOURCE_VOLTAGE_L2,
    CONF_SOURCE_VOLTAGE_L3,
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
    marker = vol.Optional(key, default=current_value) if current_value else vol.Optional(key)
    return marker, _entity_selector(domains)


def _schema(current: Mapping[str, Any] | None = None) -> vol.Schema:
    current = current or {}
    schema: dict[Any, Any] = {
        vol.Required(CONF_MODEL, default=current.get(CONF_MODEL, DEFAULT_MODEL)): vol.In(
            _model_options()
        ),
        vol.Optional(CONF_NAME, default=current.get(CONF_NAME, NAME)): cv.string,
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
            default=current.get(CONF_COMPLETE_IDLE_MINUTES, DEFAULT_COMPLETE_IDLE_MINUTES),
        ): cv.positive_int,
        vol.Required(
            CONF_SESSION_ENERGY_MODE,
            default=current.get(CONF_SESSION_ENERGY_MODE, SESSION_ENERGY_MODE_AUTO),
        ): vol.In(SESSION_ENERGY_MODES),
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


def _auto_schema(candidates: list[SourceCandidate]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_SOURCE_DEVICE_ID): vol.In(
                {candidate.device_id: candidate.option_label for candidate in candidates}
            ),
            vol.Optional(CONF_NAME): cv.string,
            vol.Required(CONF_TARIFF_VALUE, default=DEFAULT_TARIFF_VALUE): cv.positive_float,
            vol.Required(CONF_CURRENCY, default=DEFAULT_CURRENCY): cv.string,
            vol.Required(
                CONF_COMPLETE_POWER_THRESHOLD,
                default=DEFAULT_COMPLETE_POWER_THRESHOLD_KW,
            ): cv.positive_float,
            vol.Required(
                CONF_COMPLETE_IDLE_MINUTES,
                default=DEFAULT_COMPLETE_IDLE_MINUTES,
            ): cv.positive_int,
        }
    )


class AmperePointConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    _candidates: list[SourceCandidate]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        candidates = discover_sources(self.hass)

        if user_input is not None:
            if CONF_SOURCE_DEVICE_ID in user_input:
                candidate = next(
                    (
                        item
                        for item in candidates
                        if item.device_id == user_input[CONF_SOURCE_DEVICE_ID]
                    ),
                    None,
                )
                if candidate is None:
                    errors["base"] = "device_not_found"
                else:
                    data = {
                        **candidate.as_config_data(),
                        CONF_NAME: user_input.get(CONF_NAME) or candidate.title,
                        CONF_TARIFF_VALUE: user_input[CONF_TARIFF_VALUE],
                        CONF_CURRENCY: user_input[CONF_CURRENCY],
                        CONF_COMPLETE_POWER_THRESHOLD: user_input[
                            CONF_COMPLETE_POWER_THRESHOLD
                        ],
                        CONF_COMPLETE_IDLE_MINUTES: user_input[CONF_COMPLETE_IDLE_MINUTES],
                    }
                    await self.async_set_unique_id(
                        f"{DOMAIN}_{candidate.device_id}"
                    )
                    self._abort_if_unique_id_configured()
                    title = data[CONF_NAME]
                    return self.async_create_entry(title=title, data=data)

            if errors:
                return self.async_show_form(
                    step_id="user",
                    data_schema=_auto_schema(candidates),
                    errors=errors,
                )

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
            step_id="user",
            data_schema=_auto_schema(candidates) if candidates else _schema(),
            errors=errors,
            description_placeholders={
                "count": str(len(candidates)),
                "mode": "auto" if candidates else "manual",
            },
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
