from __future__ import annotations

import base64
import binascii
import json
import logging
from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.components.tuya.const import TUYA_HA_SIGNAL_UPDATE_ENTITY
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.helpers.dispatcher import async_dispatcher_connect
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
    CONF_SOURCE_INTEGRATION,
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
    CONF_SOURCE_TARGET_ENERGY,
    CONF_SOURCE_TOTAL_ENERGY,
    CONF_SOURCE_VOLTAGE_L1,
    CONF_SOURCE_VOLTAGE_L2,
    CONF_SOURCE_VOLTAGE_L3,
    CONF_SOURCE_WORK_MODE,
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
from .source import NativeTuyaSource

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
PRIME_TELEMETRY_ATTRIBUTE = "telemetry"

# Mapped source entities for the raw view of chargers that expose one entity
# per datapoint instead of a raw-DP entity: (config key, code, DP id, unit).
# The phase readings share DP6/7/8, the way the charger packs them.
MAPPED_DP_CODES: tuple[tuple[str, str, int, str | None], ...] = (
    (CONF_SOURCE_TOTAL_ENERGY, "forward_energy_total", 1, "kWh"),
    (CONF_SOURCE_STATUS, "work_state", 3, None),
    (CONF_SOURCE_CURRENT_LIMIT, "charge_cur_set", 4, "A"),
    (CONF_SOURCE_VOLTAGE_L1, "l1_voltage", 6, "V"),
    (CONF_SOURCE_CURRENT_L1, "l1_current", 6, "A"),
    (CONF_SOURCE_POWER_L1, "l1_power", 6, "kW"),
    (CONF_SOURCE_VOLTAGE_L2, "l2_voltage", 7, "V"),
    (CONF_SOURCE_CURRENT_L2, "l2_current", 7, "A"),
    (CONF_SOURCE_POWER_L2, "l2_power", 7, "kW"),
    (CONF_SOURCE_VOLTAGE_L3, "l3_voltage", 8, "V"),
    (CONF_SOURCE_CURRENT_L3, "l3_current", 8, "A"),
    (CONF_SOURCE_POWER_L3, "l3_power", 8, "kW"),
    (CONF_SOURCE_POWER, "power_total", 9, "kW"),
    (CONF_SOURCE_ERROR, "fault", 10, None),
    (CONF_SOURCE_CONNECTED, "connection_state", 13, None),
    (CONF_SOURCE_WORK_MODE, "work_mode", 14, None),
    (CONF_SOURCE_TARGET_ENERGY, "energy_charge", 17, "kWh"),
    (CONF_SOURCE_CHARGE_SWITCH, "switch", 18, None),
    (CONF_SOURCE_TEMPERATURE, "temp_current", 24, "C"),
    (CONF_SOURCE_LAST_SESSION_ENERGY, "charge_energy_once", 25, "kWh"),
)


def _has_reported_values(raw_dp: Any) -> bool:
    """Whether a datapoint snapshot carries at least one real value."""
    if not isinstance(raw_dp, dict) or not raw_dp:
        return False
    return any(
        value not in (None, "", "unknown", "unavailable") for value in raw_dp.values()
    )


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
        self.native_source = NativeTuyaSource.resolve(hass, config_entry)
        if self.native_source is not None:
            config_entry.async_on_unload(
                async_dispatcher_connect(
                    hass,
                    f"{TUYA_HA_SIGNAL_UPDATE_ENTITY}_{self.native_source.device.id}",
                    self._handle_native_update,
                )
            )
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

    @callback
    def _handle_native_update(self, *_: Any) -> None:
        """Refresh normalized entities immediately after a Tuya push update."""
        self.hass.async_create_task(self.async_request_refresh())

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
        prime_telemetry = _decode_prime_telemetry(self._prime_telemetry_source())

        status = normalize_status(
            self._state_value(CONF_SOURCE_STATUS)
            or self._raw_attr("raw_work_state")
            or self._native_value("work_state")
        )
        source_power_kw = _first_not_none(
            self._numeric_entity(CONF_SOURCE_POWER, "power_kw"),
            self._numeric_raw_attr("power_total_kw"),
            self._native_numeric("power_total"),
            prime_telemetry.get("power_kw") if prime_telemetry else None,
        )
        power_kw = source_power_kw or 0.0
        source_session_energy = _first_not_none(
            self._numeric_entity(CONF_SOURCE_SESSION_ENERGY, "energy_kwh"),
            prime_telemetry.get("session_energy_kwh") if prime_telemetry else None,
        )
        source_total_energy = self._numeric_entity(
            CONF_SOURCE_TOTAL_ENERGY, "energy_kwh"
        )
        if source_total_energy is None:
            source_total_energy = self._numeric_raw_attr("forward_energy_total_kwh")
        if source_total_energy is None:
            source_total_energy = self._native_numeric("forward_energy_total")
        last_session_energy = self._numeric_entity(
            CONF_SOURCE_LAST_SESSION_ENERGY, "energy_kwh"
        )
        if last_session_energy is None:
            last_session_energy = self._numeric_raw_attr("charge_energy_once_kwh")
        if last_session_energy is None:
            last_session_energy = self._native_numeric("charge_energy_once")
        temperature_c = self._numeric_entity(CONF_SOURCE_TEMPERATURE, "plain")
        if temperature_c is None:
            temperature_c = self._numeric_raw_attr("temp_current_c")
        if temperature_c is None:
            temperature_c = self._native_numeric("temp_current")
        if temperature_c is None and prime_telemetry:
            temperature_c = prime_telemetry.get("temperature_c")
        threshold_kw = float(
            self._config(
                CONF_COMPLETE_POWER_THRESHOLD, DEFAULT_COMPLETE_POWER_THRESHOLD_KW
            )
        )

        is_charging = status in CHARGING_STATUSES or power_kw > threshold_kw
        is_complete_from_status = status in COMPLETE_STATUSES
        connected_fallback = is_charging or power_kw > 0
        if prime_telemetry and prime_telemetry.get("vehicle_connected") is not None:
            connected_fallback = bool(prime_telemetry["vehicle_connected"])
        connected = normalize_connected(
            self._state_value(CONF_SOURCE_CONNECTED)
            or self._raw_attr("raw_connection_state")
            or self._native_value("connection_state"),
            fallback=connected_fallback,
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
                _prime_phase(prime_telemetry, "L1"),
            ),
            self._phase_values(
                CONF_SOURCE_VOLTAGE_L2,
                CONF_SOURCE_CURRENT_L2,
                CONF_SOURCE_POWER_L2,
                CONF_SOURCE_PHASE_B,
                "phase_b",
                _prime_phase(prime_telemetry, "L2"),
            ),
            self._phase_values(
                CONF_SOURCE_VOLTAGE_L3,
                CONF_SOURCE_CURRENT_L3,
                CONF_SOURCE_POWER_L3,
                CONF_SOURCE_PHASE_C,
                "phase_c",
                _prime_phase(prime_telemetry, "L3"),
            ),
        ]
        phases = _filter_loaded_phases(phases)
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
            current_limit = self._native_numeric("charge_cur_set")

        fault_value = _first_not_none(
            self._state_value(CONF_SOURCE_ERROR),
            self._raw_attr("raw_fault"),
            self._native_value("fault"),
        )
        fault_labels = (
            self.native_source.bitmap_labels("fault") if self.native_source else []
        )
        switch_enabled = _as_bool(self._state_value(CONF_SOURCE_CHARGE_SWITCH))
        if switch_enabled is None:
            switch_enabled = _as_bool(self._native_value("switch"))
        raw_dp = (
            self.native_source.values()
            if self.native_source
            else self._mapped_raw_values()
        )
        dp_metadata = (
            self.native_source.definitions()
            if self.native_source
            else self._mapped_raw_metadata()
        )
        if not _has_reported_values(raw_dp):
            # A cloud device that lists its codes without ever sending values
            # would leave the raw view empty, even though the mapped local
            # entities carry the same datapoints.
            mapped_dp = self._mapped_source_snapshot()
            if mapped_dp:
                raw_dp, dp_metadata = mapped_dp
        schedule_window = _decode_schedule_window(self._native_value("local_timer"))

        self._last_update = now
        self._was_charging = is_charging
        self._was_connected = connected
        self._schedule_state_save()

        return {
            "model": self.model.name,
            "status": status,
            "vehicle_connected": connected,
            "charging": is_charging,
            "switch_enabled": switch_enabled,
            "charging_complete": charging_complete,
            "power_kw": (
                round(source_power_kw, 3) if source_power_kw is not None else None
            ),
            "session_energy_kwh": round(session_energy_kwh, 3),
            "total_energy_kwh": (
                round(source_total_energy, 3)
                if source_total_energy is not None
                else None
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
            "error": ", ".join(fault_labels)
            if fault_labels
            else normalize_error(fault_value),
            "current_limit_a": (
                round(current_limit, 1) if current_limit is not None else None
            ),
            "temperature_c": (
                round(temperature_c, 1) if temperature_c is not None else None
            ),
            "cp_voltage_v": (
                prime_telemetry.get("cp_voltage_v") if prime_telemetry else None
            ),
            "session_duration_s": (
                prime_telemetry.get("session_duration_s")
                if prime_telemetry
                else None
            ),
            "session_duration_min": (
                round(prime_telemetry["session_duration_s"] / 60, 1)
                if prime_telemetry
                and prime_telemetry.get("session_duration_s") is not None
                else None
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
            "work_mode": self._state_value(CONF_SOURCE_WORK_MODE)
            or self._native_value("work_mode"),
            "target_energy_kwh": _first_not_none(
                self._numeric_entity(CONF_SOURCE_TARGET_ENERGY, "energy_kwh"),
                self._native_numeric("energy_charge"),
            ),
            "schedule_start_time": schedule_window[0] if schedule_window else None,
            "schedule_end_time": schedule_window[1] if schedule_window else None,
            "system_version": self._native_value("system_version"),
            "raw_dp_count": len(raw_dp),
            "raw_dp": raw_dp,
            "dp_metadata": dp_metadata,
            "source_type": (
                "native_tuya"
                if self.native_source
                else self._config(CONF_SOURCE_INTEGRATION, "entity_mapping")
            ),
            "source_online": (
                self.native_source.available if self.native_source else True
            ),
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

    def _native_value(self, code: str) -> Any:
        if self.native_source is None:
            return None
        return self.native_source.raw(code)

    def _native_numeric(self, code: str) -> float | None:
        if self.native_source is None:
            return None
        return _as_float(self.native_source.scaled(code))

    def _raw_attr(self, attr_name: str) -> Any:
        entity_id = self._config(CONF_SOURCE_RAW_DP)
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None:
            return None
        return state.attributes.get(attr_name)

    def _prime_telemetry_source(self) -> Any:
        """Return the raw DP102 payload from any mapped source entity.

        The telemetry attribute lives on the tuya-local charging-status
        sensor. Entries created while that entity was still unavailable (or
        by older releases) have no raw-DP mapping, so the already-mapped
        status entity doubles as a fallback and heals such entries without
        a migration.
        """
        for key in (CONF_SOURCE_RAW_DP, CONF_SOURCE_STATUS):
            entity_id = self._config(key)
            if not entity_id:
                continue
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
            value = state.attributes.get(PRIME_TELEMETRY_ATTRIBUTE)
            if value is not None:
                return value
        return None

    def _mapped_raw_values(self) -> dict[str, Any]:
        entity_id = self._config(CONF_SOURCE_RAW_DP)
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None:
            # Entries without a raw-DP mapping still get the Prime DP list
            # when the status entity carries the telemetry attributes.
            fallback_id = self._config(CONF_SOURCE_STATUS)
            fallback = self.hass.states.get(fallback_id) if fallback_id else None
            if fallback is not None:
                prime_values = _prime_raw_values(fallback.state, fallback.attributes)
                if prime_values:
                    return prime_values
            return {}
        embedded = state.attributes.get("raw_dp")
        if isinstance(embedded, dict):
            return dict(embedded)
        prime_values = _prime_raw_values(state.state, state.attributes)
        if prime_values:
            return prime_values
        excluded_suffixes = ("_voltage_v", "_current_a", "_power_kw")
        return {
            key.removeprefix("raw_"): value
            for key, value in state.attributes.items()
            if key.startswith("raw_") and not key.endswith(excluded_suffixes)
        }

    def _mapped_source_snapshot(self) -> tuple[dict[str, Any], dict[str, Any]] | None:
        """Build a raw-DP view from the mapped source entities.

        Chargers reached over LAN expose one entity per datapoint instead of a
        single raw-DP entity, so the datapoint list is reassembled from the
        entities the config entry maps.
        """
        values: dict[str, Any] = {}
        metadata: dict[str, Any] = {}
        for config_key, code, dp_id, unit in MAPPED_DP_CODES:
            entity_id = self._config(config_key)
            if not entity_id:
                continue
            state = self.hass.states.get(entity_id)
            if state is None or state.state in {None, "unknown", "unavailable"}:
                continue
            values[code] = state.state
            definition: dict[str, Any] = {"dp_id": dp_id}
            entity_unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) or unit
            if entity_unit:
                definition["unit"] = entity_unit
            definition["writable"] = entity_id.split(".", 1)[0] in {
                "number",
                "input_number",
                "select",
                "switch",
                "input_boolean",
            }
            metadata[code] = definition
        if not values:
            return None
        return values, metadata

    def _mapped_raw_metadata(self) -> dict[str, Any]:
        entity_id = self._config(CONF_SOURCE_RAW_DP)
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is None:
            fallback_id = self._config(CONF_SOURCE_STATUS)
            state = self.hass.states.get(fallback_id) if fallback_id else None
        if state is None:
            return {}
        metadata = state.attributes.get("dp_metadata")
        if isinstance(metadata, dict):
            return dict(metadata)
        return _prime_raw_metadata(state.state, state.attributes)

    def _phase_values(
        self,
        voltage_key: str,
        current_key: str,
        power_key: str,
        raw_key: str,
        raw_attr_prefix: str,
        fallback: dict[str, float | None] | None = None,
    ) -> dict[str, float | None]:
        voltage = self._numeric_entity(voltage_key, "voltage_v")
        current = self._numeric_entity(current_key, "current_a")
        power = self._numeric_entity(power_key, "power_kw")

        decoded = self._decode_phase_source(raw_key, raw_attr_prefix)
        if decoded is not None:
            voltage = voltage if voltage is not None else decoded["voltage"]
            current = current if current is not None else decoded["current"]
            power = power if power is not None else decoded["power"]
        if fallback is not None:
            voltage = voltage if voltage is not None else fallback["voltage"]
            current = current if current is not None else fallback["current"]
            power = power if power is not None else fallback["power"]

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
        if raw_value is None:
            raw_value = self._native_value(raw_attr_prefix)
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

        if (
            mode == SESSION_ENERGY_MODE_SESSION_ENTITY
            and source_session_energy is not None
        ):
            self._session_energy_kwh = max(source_session_energy, 0.0)
            self._update_total_energy_tracking(source_total_energy, connected)
            return self._session_energy_kwh

        if mode == SESSION_ENERGY_MODE_TOTAL_DELTA:
            if source_total_energy is not None:
                return self._calculate_total_delta_session(
                    source_total_energy, connected
                )
            if source_session_energy is not None:
                self._session_energy_kwh = max(source_session_energy, 0.0)
                return self._session_energy_kwh

        if mode == SESSION_ENERGY_MODE_AUTO:
            if source_total_energy is not None:
                return self._calculate_total_delta_session(
                    source_total_energy, connected
                )
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
                self._session_energy_kwh += power_kw * (elapsed.total_seconds() / 3600)

        return self._session_energy_kwh

    def _detect_phase_count(self, currents: list[float | None], power_kw: float) -> int:
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
            if self.native_source and self.native_source.writable("charge_cur_set"):
                await self.native_source.async_send("charge_cur_set", value)
                return
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

        raise HomeAssistantError(f"Unsupported current limit source domain: {domain}")

    async def async_set_charging(self, enabled: bool) -> None:
        entity_id = self._config(CONF_SOURCE_CHARGE_SWITCH)
        if not entity_id:
            if self.native_source and self.native_source.writable("switch"):
                await self.native_source.async_send("switch", enabled)
                return
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

    def has_dp(self, code: str) -> bool:
        return bool(self.native_source and self.native_source.has(code))

    def can_write_dp(self, code: str) -> bool:
        return bool(self.native_source and self.native_source.writable(code))

    def dp_definition(self, code: str) -> dict[str, Any]:
        if self.native_source is None:
            return {}
        return self.native_source.definition(code)

    async def async_set_work_mode(self, value: str) -> None:
        entity_id = self._config(CONF_SOURCE_WORK_MODE)
        if entity_id:
            if entity_id.split(".", 1)[0] != "select":
                raise HomeAssistantError("Mapped work mode source is read-only")
            await self.hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": entity_id, "option": value},
                blocking=True,
            )
            return
        if self.native_source is not None:
            await self.native_source.async_send("work_mode", value)
            return
        raise HomeAssistantError("No writable work mode source configured")

    async def async_set_target_energy(self, value: float) -> None:
        entity_id = self._config(CONF_SOURCE_TARGET_ENERGY)
        if entity_id:
            domain = entity_id.split(".", 1)[0]
            if domain not in {"number", "input_number"}:
                raise HomeAssistantError("Mapped target energy source is read-only")
            await self.hass.services.async_call(
                domain,
                "set_value",
                {"entity_id": entity_id, "value": value},
                blocking=True,
            )
            return
        if self.native_source is not None:
            await self.native_source.async_send("energy_charge", value)
            return
        raise HomeAssistantError("No writable target energy source configured")

    async def async_set_schedule_boundary(self, boundary: str, value: time) -> None:
        if self.native_source is None or not self.native_source.writable("local_timer"):
            raise HomeAssistantError("No writable schedule source configured")
        if value.minute or value.second or value.microsecond:
            raise HomeAssistantError("This charger schedule supports whole hours only")
        window = _decode_schedule_window(self._native_value("local_timer"))
        if window is None:
            raise HomeAssistantError("The current charger schedule cannot be decoded")
        start, end = window
        if boundary == "start":
            start = value
        elif boundary == "end":
            end = value
        else:
            raise HomeAssistantError(f"Unsupported schedule boundary: {boundary}")
        payload = base64.b64encode(bytes((start.hour, end.hour))).decode()
        await self.native_source.async_send("local_timer", payload)


def _as_float(value: Any) -> float | None:
    if value in {None, "unknown", "unavailable"}:
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _scaled_number(value: Any, scale: float = 10.0) -> float | None:
    if isinstance(value, bool):
        return None
    numeric = _as_float(value)
    return numeric / scale if numeric is not None else None


def _decode_prime_phase(value: Any) -> dict[str, float | None] | None:
    if not isinstance(value, list | tuple) or len(value) < 3:
        return None
    voltage = _scaled_number(value[0])
    current = _scaled_number(value[1])
    power = _scaled_number(value[2])
    if voltage is None and current is None and power is None:
        return None
    return {"voltage": voltage, "current": current, "power": power}


def _decode_prime_telemetry(value: Any) -> dict[str, Any] | None:
    """Decode the Wallbox Prime 22kW JSON payload exposed by tuya-local."""
    payload = value
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (TypeError, ValueError):
            return None
    if not isinstance(payload, dict):
        return None
    if not any(key in payload for key in ("L1", "L2", "L3", "p", "e", "cp")):
        return None

    phases = {
        phase: _decode_prime_phase(payload.get(phase))
        for phase in ("L1", "L2", "L3")
    }
    cp_voltage_v = _scaled_number(payload.get("cp"))
    vehicle_connected: bool | None = None
    if cp_voltage_v is not None:
        if 2.0 <= cp_voltage_v < 11.0:
            vehicle_connected = True
        elif cp_voltage_v >= 11.0:
            vehicle_connected = False

    duration = _as_float(payload.get("d"))
    return {
        "phases": phases,
        "power_kw": _scaled_number(payload.get("p")),
        "session_energy_kwh": _scaled_number(payload.get("e")),
        "temperature_c": _scaled_number(payload.get("t")),
        "session_duration_s": int(duration) if duration is not None else None,
        "cp_voltage_v": cp_voltage_v,
        "vehicle_connected": vehicle_connected,
    }


def _prime_phase(
    telemetry: dict[str, Any] | None, phase: str
) -> dict[str, float | None] | None:
    if not telemetry:
        return None
    value = telemetry.get("phases", {}).get(phase)
    return value if isinstance(value, dict) else None


# Local Wallbox Prime datapoints, keyed by the code shown in the raw-DP view.
PRIME_DP_CODES: tuple[tuple[str, str, int], ...] = (
    # (attribute on the source entity, code, DP id)
    ("state_code", "state_code", 101),
    (PRIME_TELEMETRY_ATTRIBUTE, "telemetry", 102),
    ("session_data", "session_data", 103),
    ("device_information", "device_information", 106),
)


# DP102 fields, unpacked into one raw row each: (payload key, code, unit,
# scale, index inside a phase array).
PRIME_TELEMETRY_FIELDS: tuple[tuple[str, str, str, float, int | None], ...] = (
    ("L1", "l1_voltage_v", "V", 10, 0),
    ("L1", "l1_current_a", "A", 10, 1),
    ("L1", "l1_power_kw", "kW", 10, 2),
    ("L2", "l2_voltage_v", "V", 10, 0),
    ("L2", "l2_current_a", "A", 10, 1),
    ("L2", "l2_power_kw", "kW", 10, 2),
    ("L3", "l3_voltage_v", "V", 10, 0),
    ("L3", "l3_current_a", "A", 10, 1),
    ("L3", "l3_power_kw", "kW", 10, 2),
    ("p", "power_total_kw", "kW", 10, None),
    ("e", "session_energy_kwh", "kWh", 10, None),
    ("t", "temp_current_c", "C", 10, None),
    ("cp", "cp_voltage_v", "V", 10, None),
    ("d", "session_duration_s", "s", 1, None),
)


def _prime_telemetry_fields(payload: Any) -> dict[str, dict[str, Any]]:
    """Unpack DP102 into one entry per reading.

    The charger delivers all of its live measurements inside a single JSON
    datapoint. Listing that payload as one row hides the individual values,
    so each field is exposed separately, the way a charger with discrete
    datapoints reports them.
    """
    payload = _as_json_mapping(payload)
    if not payload:
        return {}

    fields: dict[str, dict[str, Any]] = {}
    for key, code, unit, scale, index in PRIME_TELEMETRY_FIELDS:
        value = payload.get(key)
        if index is not None:
            if not isinstance(value, list | tuple) or len(value) <= index:
                continue
            value = value[index]
        raw = _as_float(value)
        if raw is None:
            continue
        fields[code] = {
            "raw": value,
            "scaled": raw / scale if scale else raw,
            "unit": unit,
        }
    return fields


def _prime_raw_values(state: Any, attributes: dict[str, Any]) -> dict[str, Any]:
    if _decode_prime_telemetry(attributes.get(PRIME_TELEMETRY_ATTRIBUTE)) is None:
        return {}
    values = {
        code: attributes[attr]
        for attr, code, _dp_id in PRIME_DP_CODES
        if attr in attributes
    }
    values["work_state"] = state
    fields = _prime_telemetry_fields(attributes.get(PRIME_TELEMETRY_ATTRIBUTE))
    values.update({code: field["raw"] for code, field in fields.items()})
    return values


def _prime_raw_metadata(state: Any, attributes: dict[str, Any]) -> dict[str, Any]:
    """Describe the Prime datapoints so the raw view can label and decode them.

    Without this the dashboard shows the JSON payloads verbatim in both the
    raw and the decoded column, with no DP number.
    """
    telemetry = _decode_prime_telemetry(attributes.get(PRIME_TELEMETRY_ATTRIBUTE))
    if telemetry is None:
        return {}

    metadata: dict[str, Any] = {
        code: {"dp_id": dp_id, "writable": False}
        for attr, code, dp_id in PRIME_DP_CODES
        if attr in attributes
    }
    metadata["work_state"] = {"dp_id": 109, "writable": False}

    if "telemetry" in metadata:
        metadata["telemetry"]["meaning"] = _prime_telemetry_summary(telemetry)
    for code, field in _prime_telemetry_fields(
        attributes.get(PRIME_TELEMETRY_ATTRIBUTE)
    ).items():
        metadata[code] = {
            "dp_id": 102,
            "writable": False,
            "unit": field["unit"],
            "meaning": f"{field['scaled']:g} {field['unit']}",
        }
    if "device_information" in metadata:
        info = _as_json_mapping(attributes.get("device_information"))
        parts = [str(info[key]) for key in ("fv", "r") if info.get(key)]
        if parts:
            metadata["device_information"]["meaning"] = " · ".join(parts)
    if "session_data" in metadata:
        session = _as_json_mapping(attributes.get("session_data"))
        if session.get("t"):
            metadata["session_data"]["meaning"] = str(session["t"])
    return metadata


def _prime_telemetry_summary(telemetry: dict[str, Any]) -> str:
    """Render DP102 as a compact, unit-based line."""
    parts: list[str] = []
    for label in ("L1", "L2", "L3"):
        phase = telemetry.get("phases", {}).get(label)
        if not phase or not any(
            value for value in phase.values() if isinstance(value, int | float)
        ):
            continue
        parts.append(
            f"{label} {phase['voltage']:.1f} V / "
            f"{phase['current']:.1f} A / {phase['power']:.2f} kW"
        )
    for value, fmt in (
        (telemetry.get("power_kw"), "{:.2f} kW"),
        (telemetry.get("session_energy_kwh"), "{:.2f} kWh"),
        (telemetry.get("temperature_c"), "{:.1f} C"),
        (telemetry.get("cp_voltage_v"), "CP {:.1f} V"),
    ):
        if value is not None:
            parts.append(fmt.format(value))
    duration = telemetry.get("session_duration_s")
    if duration is not None:
        parts.append(f"{round(duration / 60)} min")
    return " · ".join(parts)


def _as_json_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return {}
    return value if isinstance(value, dict) else {}


def _first_not_none(*values: Any) -> Any:
    return next((value for value in values if value is not None), None)


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"on", "true", "1", "yes"}:
            return True
        if normalized in {"off", "false", "0", "no"}:
            return False
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


PHASE_MIN_CURRENT_A = 1.0
PHASE_MIN_POWER_KW = 0.23


def _filter_loaded_phases(
    phases: list[dict[str, float | None]],
) -> list[dict[str, float | None]]:
    """Expose only phases that carry real load.

    Phase measurements should appear once charging draws current. Idle
    chargers report zero or residual values, and three-phase chargers can
    report small phantom readings on unloaded phases during minimal
    single-phase charging, which made three phases pop up on a single-phase
    session. Either trustworthy measurement (current or power) establishes
    load on its own, so a genuinely loaded low-current phase is never hidden
    by the state of the other phases.
    """
    filtered: list[dict[str, float | None]] = []
    for phase in phases:
        current = phase.get("current")
        power = phase.get("power")
        current_loaded = current is not None and current >= PHASE_MIN_CURRENT_A
        power_loaded = power is not None and power >= PHASE_MIN_POWER_KW
        filtered.append(
            phase
            if current_loaded or power_loaded
            else {"voltage": None, "current": None, "power": None}
        )
    return filtered


def _decode_phase_payload(value: Any) -> dict[str, float] | None:
    if value in {None, "unknown", "unavailable", ""}:
        return None

    try:
        payload = base64.b64decode(str(value), validate=True)
    except (binascii.Error, ValueError):
        return None

    if len(payload) != 7:
        return None
    if not any(payload):
        return None

    voltage_raw = int.from_bytes(payload[0:2], "big")
    current_raw = int.from_bytes(payload[2:5], "big")
    power_raw = int.from_bytes(payload[5:7], "big")
    return {
        "voltage": voltage_raw / 10.0,
        "current": current_raw / 1000.0,
        "power": power_raw / 1000.0,
    }


def _decode_schedule_window(value: Any) -> tuple[time, time] | None:
    if value in {None, "unknown", "unavailable", ""}:
        return None
    try:
        payload = base64.b64decode(str(value), validate=True)
    except (binascii.Error, ValueError):
        return None
    if len(payload) != 2 or payload[0] > 23 or payload[1] > 23:
        return None
    return time(hour=payload[0]), time(hour=payload[1])
