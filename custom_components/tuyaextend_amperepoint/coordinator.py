from __future__ import annotations

import base64
import binascii
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_COMPLETE_IDLE_MINUTES,
    CONF_COMPLETE_POWER_THRESHOLD,
    CONF_CURRENCY,
    CONF_MODEL,
    CONF_SESSION_ENERGY_MODE,
    CONF_SOURCE_CHARGE_SWITCH,
    CONF_SOURCE_CONNECTED,
    CONF_SOURCE_CURRENT_L1,
    CONF_SOURCE_CURRENT_L2,
    CONF_SOURCE_CURRENT_L3,
    CONF_SOURCE_CURRENT_LIMIT,
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
    CONF_SOURCE_STATUS,
    CONF_SOURCE_TEMPERATURE,
    CONF_SOURCE_TOTAL_ENERGY,
    CONF_SOURCE_VOLTAGE_L1,
    CONF_SOURCE_VOLTAGE_L2,
    CONF_SOURCE_VOLTAGE_L3,
    CONF_TARIFF_ENTITY,
    CONF_TARIFF_VALUE,
    DEFAULT_COMPLETE_IDLE_MINUTES,
    DEFAULT_COMPLETE_POWER_THRESHOLD_KW,
    DEFAULT_CURRENCY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TARIFF_VALUE,
    DOMAIN,
    SESSION_ENERGY_MODE_AUTO,
    SESSION_ENERGY_MODE_POWER_INTEGRATION,
    SESSION_ENERGY_MODE_SESSION_ENTITY,
    SESSION_ENERGY_MODE_TOTAL_DELTA,
)
from .models import (
    CHARGING_STATUSES,
    COMPLETE_STATUSES,
    AmperePointModel,
    get_model,
    normalize_connected,
    normalize_error,
    normalize_status,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1


class AmperePointCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.config_entry = config_entry
        self.model = get_model(self._config(CONF_MODEL))
        self._store = Store[dict[str, Any]](
            hass, STORAGE_VERSION, f"{DOMAIN}.{config_entry.entry_id}.session"
        )
        self._session_energy_kwh = 0.0
        self._total_energy_baseline_kwh: float | None = None
        self._last_total_energy_kwh: float | None = None
        self._last_update: datetime | None = None
        self._was_charging = False
        self._was_connected = False
        self._complete_candidate_since: datetime | None = None

    def _config(self, key: str, default: Any = None) -> Any:
        return self.config_entry.options.get(
            key, self.config_entry.data.get(key, default)
        )

    def set_model(self, model_key: str) -> None:
        self.model = get_model(model_key)

    async def async_load_state(self) -> None:
        data = await self._store.async_load()
        if not isinstance(data, dict):
            return

        self._session_energy_kwh = _as_float(data.get("session_energy_kwh")) or 0.0
        self._total_energy_baseline_kwh = _as_float(
            data.get("total_energy_baseline_kwh")
        )
        self._last_total_energy_kwh = _as_float(data.get("last_total_energy_kwh"))
        self._was_charging = bool(data.get("was_charging", False))
        self._was_connected = bool(data.get("was_connected", False))

    async def _async_update_data(self) -> dict[str, Any]:
        now = dt_util.utcnow()

        status = normalize_status(
            self._state_value(CONF_SOURCE_STATUS)
            or self._raw_attr("raw_work_state")
        )
        power_kw = (
            self._numeric_entity(CONF_SOURCE_POWER, "power_kw")
            or self._numeric_raw_attr("power_total_kw")
            or 0.0
        )
        source_session_energy = self._numeric_entity(
            CONF_SOURCE_SESSION_ENERGY, "energy_kwh"
        )
        source_total_energy = self._numeric_entity(
            CONF_SOURCE_TOTAL_ENERGY, "energy_kwh"
        )
        if source_total_energy is None:
            source_total_energy = self._numeric_raw_attr("forward_energy_total_kwh")
        last_session_energy = self._numeric_entity(
            CONF_SOURCE_LAST_SESSION_ENERGY, "energy_kwh"
        )
        if last_session_energy is None:
            last_session_energy = self._numeric_raw_attr("charge_energy_once_kwh")
        temperature_c = self._numeric_entity(CONF_SOURCE_TEMPERATURE, "plain")
        if temperature_c is None:
            temperature_c = self._numeric_raw_attr("temp_current_c")
        threshold_kw = float(
            self._config(CONF_COMPLETE_POWER_THRESHOLD, DEFAULT_COMPLETE_POWER_THRESHOLD_KW)
        )

        is_charging = status in CHARGING_STATUSES or power_kw > threshold_kw
        is_complete_from_status = status in COMPLETE_STATUSES
        connected = normalize_connected(
            self._state_value(CONF_SOURCE_CONNECTED)
            or self._raw_attr("raw_connection_state"),
            fallback=is_charging or power_kw > 0,
        )

        session_energy_kwh = self._calculate_session_energy(
            now=now,
            power_kw=power_kw,
            is_charging=is_charging,
            connected=connected,
            source_session_energy=source_session_energy,
            source_total_energy=source_total_energy,
        )

        tariff_value = self._current_tariff()
        currency = self._config(CONF_CURRENCY, DEFAULT_CURRENCY)
        session_cost = session_energy_kwh * tariff_value

        phases = [
            self._phase_values(
                CONF_SOURCE_VOLTAGE_L1,
                CONF_SOURCE_CURRENT_L1,
                CONF_SOURCE_POWER_L1,
                CONF_SOURCE_PHASE_A,
                "phase_a",
            ),
            self._phase_values(
                CONF_SOURCE_VOLTAGE_L2,
                CONF_SOURCE_CURRENT_L2,
                CONF_SOURCE_POWER_L2,
                CONF_SOURCE_PHASE_B,
                "phase_b",
            ),
            self._phase_values(
                CONF_SOURCE_VOLTAGE_L3,
                CONF_SOURCE_CURRENT_L3,
                CONF_SOURCE_POWER_L3,
                CONF_SOURCE_PHASE_C,
                "phase_c",
            ),
        ]
        phase_voltages = [phase.get("voltage") for phase in phases]
        phase_currents = [phase.get("current") for phase in phases]
        phase_powers = [phase.get("power") for phase in phases]

        phase_count = self._detect_phase_count(phase_currents, power_kw)
        charging_complete = self._detect_charging_complete(
            now=now,
            connected=connected,
            is_charging=is_charging,
            power_kw=power_kw,
            threshold_kw=threshold_kw,
            complete_from_status=is_complete_from_status,
        )

        current_limit = self._numeric_entity(CONF_SOURCE_CURRENT_LIMIT, "current_a")
        if current_limit is None:
            current_limit = float(self.model.max_current_a)

        self._last_update = now
        self._was_charging = is_charging
        self._was_connected = connected
        self._schedule_state_save()

        return {
            "model": self.model.name,
            "status": status,
            "vehicle_connected": connected,
            "charging": is_charging,
            "charging_complete": charging_complete,
            "power_kw": round(power_kw, 3),
            "session_energy_kwh": round(session_energy_kwh, 3),
            "total_energy_kwh": (
                round(source_total_energy, 3) if source_total_energy is not None else None
            ),
            "last_session_energy_kwh": (
                round(last_session_energy, 3)
                if last_session_energy is not None
                else None
            ),
            "session_cost": round(session_cost, 2),
            "tariff": round(tariff_value, 4),
            "currency": currency,
            "phase_count": phase_count,
            "error": normalize_error(
                self._state_value(CONF_SOURCE_ERROR) or self._raw_attr("raw_fault")
            ),
            "current_limit_a": round(current_limit, 1),
            "temperature_c": (
                round(temperature_c, 1) if temperature_c is not None else None
            ),
            "voltage_l1": phase_voltages[0],
            "voltage_l2": phase_voltages[1],
            "voltage_l3": phase_voltages[2],
            "current_l1": phase_currents[0],
            "current_l2": phase_currents[1],
            "current_l3": phase_currents[2],
            "power_l1": phase_powers[0],
            "power_l2": phase_powers[1],
            "power_l3": phase_powers[2],
        }

    def _state_value(self, key: str) -> Any:
        entity_id = self._config(key)
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        return state.state if state else None

    def _numeric_entity(self, key: str, kind: str) -> float | None:
        entity_id = self._config(key)
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None:
            return None

        value = _as_float(state.state)
        if value is None:
            return None

        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        return _convert_unit(value, unit, kind)

    def _numeric_raw_attr(self, attr_name: str) -> float | None:
        return _as_float(self._raw_attr(attr_name))

    def _raw_attr(self, attr_name: str) -> Any:
        entity_id = self._config(CONF_SOURCE_RAW_DP)
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None:
            return None
        return state.attributes.get(attr_name)

    def _phase_values(
        self,
        voltage_key: str,
        current_key: str,
        power_key: str,
        raw_key: str,
        raw_attr_prefix: str,
    ) -> dict[str, float | None]:
        voltage = self._numeric_entity(voltage_key, "voltage_v")
        current = self._numeric_entity(current_key, "current_a")
        power = self._numeric_entity(power_key, "power_kw")

        decoded = self._decode_phase_source(raw_key, raw_attr_prefix)
        if decoded is not None:
            voltage = voltage if voltage is not None else decoded["voltage"]
            current = current if current is not None else decoded["current"]
            power = power if power is not None else decoded["power"]

        return {
            "voltage": voltage,
            "current": current,
            "power": power,
        }

    def _decode_phase_source(
        self, raw_key: str, raw_attr_prefix: str
    ) -> dict[str, float] | None:
        raw_value = self._state_value(raw_key)
        if raw_value is None:
            raw_value = self._raw_attr(f"raw_{raw_attr_prefix}")
        return _decode_phase_payload(raw_value)

    def _current_tariff(self) -> float:
        entity_value = self._numeric_entity(CONF_TARIFF_ENTITY, "plain")
        if entity_value is not None:
            return entity_value
        return float(self._config(CONF_TARIFF_VALUE, DEFAULT_TARIFF_VALUE))

    def _store_state(self) -> dict[str, Any]:
        return {
            "session_energy_kwh": self._session_energy_kwh,
            "total_energy_baseline_kwh": self._total_energy_baseline_kwh,
            "last_total_energy_kwh": self._last_total_energy_kwh,
            "was_charging": self._was_charging,
            "was_connected": self._was_connected,
        }

    def _schedule_state_save(self) -> None:
        self._store.async_delay_save(self._store_state, 2)

    def _calculate_session_energy(
        self,
        *,
        now: datetime,
        power_kw: float,
        is_charging: bool,
        connected: bool,
        source_session_energy: float | None,
        source_total_energy: float | None,
    ) -> float:
        mode = self._config(CONF_SESSION_ENERGY_MODE, SESSION_ENERGY_MODE_AUTO)

        if mode == SESSION_ENERGY_MODE_SESSION_ENTITY and source_session_energy is not None:
            self._session_energy_kwh = max(source_session_energy, 0.0)
            self._update_total_energy_tracking(source_total_energy, connected)
            return self._session_energy_kwh

        if mode == SESSION_ENERGY_MODE_TOTAL_DELTA and source_total_energy is not None:
            return self._calculate_total_delta_session(source_total_energy, connected)

        if mode == SESSION_ENERGY_MODE_AUTO:
            if source_total_energy is not None:
                return self._calculate_total_delta_session(source_total_energy, connected)
            if source_session_energy is not None:
                self._session_energy_kwh = max(source_session_energy, 0.0)
                return self._session_energy_kwh

        self._update_total_energy_tracking(source_total_energy, connected)
        if mode == SESSION_ENERGY_MODE_POWER_INTEGRATION:
            return self._calculate_power_integrated_session(
                now, power_kw, is_charging, connected
            )

        return self._calculate_power_integrated_session(
            now, power_kw, is_charging, connected
        )

    def _calculate_total_delta_session(
        self,
        source_total_energy: float,
        connected: bool,
    ) -> float:
        if (
            self._total_energy_baseline_kwh is None
            or (connected and not self._was_connected)
            or source_total_energy < self._total_energy_baseline_kwh
        ):
            self._total_energy_baseline_kwh = source_total_energy

        self._last_total_energy_kwh = source_total_energy
        self._session_energy_kwh = max(
            source_total_energy - self._total_energy_baseline_kwh, 0.0
        )
        return self._session_energy_kwh

    def _update_total_energy_tracking(
        self,
        source_total_energy: float | None,
        connected: bool,
    ) -> None:
        if source_total_energy is None:
            return
        self._last_total_energy_kwh = source_total_energy
        if self._total_energy_baseline_kwh is None or (
            connected and not self._was_connected
        ):
            self._total_energy_baseline_kwh = source_total_energy

    def _calculate_power_integrated_session(
        self,
        now: datetime,
        power_kw: float,
        is_charging: bool,
        connected: bool,
    ) -> float:
        if connected and not self._was_connected:
            self._session_energy_kwh = 0.0

        if is_charging and self._last_update is not None:
            elapsed = now - self._last_update
            if timedelta(0) <= elapsed <= timedelta(minutes=10):
                self._session_energy_kwh += power_kw * (
                    elapsed.total_seconds() / 3600
                )

        return self._session_energy_kwh

    def _detect_phase_count(
        self, currents: list[float | None], power_kw: float
    ) -> int:
        measured = [current for current in currents if current is not None]
        if measured:
            active = sum(1 for current in measured if abs(current) > 0.5)
            return max(active, 1 if power_kw > 0 else 0)

        if power_kw <= 0:
            return 0

        estimated_phase_power_kw = (
            self.model.nominal_voltage_v * self.model.max_current_a
        ) / 1000
        estimated = round(power_kw / estimated_phase_power_kw)
        return max(1, min(self.model.phases, estimated or 1))

    def _detect_charging_complete(
        self,
        *,
        now: datetime,
        connected: bool,
        is_charging: bool,
        power_kw: float,
        threshold_kw: float,
        complete_from_status: bool,
    ) -> bool:
        if complete_from_status:
            self._complete_candidate_since = now
            return True

        if not connected or is_charging or power_kw > threshold_kw:
            self._complete_candidate_since = None
            return False

        if self._was_charging and self._complete_candidate_since is None:
            self._complete_candidate_since = now

        if self._complete_candidate_since is None:
            return False

        idle_minutes = int(
            self._config(CONF_COMPLETE_IDLE_MINUTES, DEFAULT_COMPLETE_IDLE_MINUTES)
        )
        return now - self._complete_candidate_since >= timedelta(minutes=idle_minutes)

    async def async_set_current_limit(self, value: float) -> None:
        entity_id = self._config(CONF_SOURCE_CURRENT_LIMIT)
        if not entity_id:
            raise HomeAssistantError("No source current limit entity configured")

        domain = entity_id.split(".", 1)[0]
        if domain in {"number", "input_number"}:
            await self.hass.services.async_call(
                domain,
                "set_value",
                {"entity_id": entity_id, "value": value},
                blocking=True,
            )
            return

        raise HomeAssistantError(
            f"Unsupported current limit source domain: {domain}"
        )

    async def async_set_charging(self, enabled: bool) -> None:
        entity_id = self._config(CONF_SOURCE_CHARGE_SWITCH)
        if not entity_id:
            raise HomeAssistantError("No source charging switch configured")

        domain = entity_id.split(".", 1)[0]
        service = "turn_on" if enabled else "turn_off"
        if domain in {"switch", "input_boolean"}:
            await self.hass.services.async_call(
                domain,
                service,
                {"entity_id": entity_id},
                blocking=True,
            )
            return

        raise HomeAssistantError(f"Unsupported charging switch source domain: {domain}")

    @property
    def model_limits(self) -> AmperePointModel:
        return self.model


def _as_float(value: Any) -> float | None:
    if value in {None, "unknown", "unavailable"}:
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _convert_unit(value: float, unit: str | None, kind: str) -> float:
    if kind == "power_kw":
        if unit in {UnitOfPower.WATT, "W"}:
            return value / 1000
        return value

    if kind == "energy_kwh":
        if unit in {UnitOfEnergy.WATT_HOUR, "Wh"}:
            return value / 1000
        return value

    if kind == "current_a":
        if unit in {UnitOfElectricCurrent.MILLIAMPERE, "mA"}:
            return value / 1000
        return value

    if kind == "voltage_v":
        if unit in {UnitOfElectricPotential.MILLIVOLT, "mV"}:
            return value / 1000
        return value

    if unit == PERCENTAGE:
        return value

    return value


def _decode_phase_payload(value: Any) -> dict[str, float] | None:
    if value in {None, "unknown", "unavailable", ""}:
        return None

    try:
        payload = base64.b64decode(str(value), validate=True)
    except (binascii.Error, ValueError):
        return None

    if len(payload) != 7:
        return None

    voltage_raw = int.from_bytes(payload[0:2], "big")
    current_raw = int.from_bytes(payload[2:5], "big")
    power_raw = int.from_bytes(payload[5:7], "big")
    return {
        "voltage": voltage_raw / 10.0,
        "current": current_raw / 1000.0,
        "power": power_raw / 1000.0,
    }
