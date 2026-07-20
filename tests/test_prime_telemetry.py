from __future__ import annotations

import asyncio
import json
import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import load_integration_module  # noqa: E402

const = load_integration_module("const")
coordinator = load_integration_module("coordinator")
discovery = load_integration_module("discovery")
models = load_integration_module("models")

CHARGING_PAYLOAD = {
    "L1": [2180, 66, 14],
    "L2": [0, 0, 0],
    "L3": [0, 0, 0],
    "t": 360,
    "p": 14,
    "d": 1340,
    "e": 1,
    "cp": 60,
}


class _States:
    def __init__(self, states: dict[str, object]) -> None:
        self._states = states

    def get(self, entity_id: str):
        return self._states.get(entity_id)


class _Store:
    def async_delay_save(self, *_args, **_kwargs) -> None:
        pass


def _state(value, **attributes):
    return types.SimpleNamespace(state=value, attributes=attributes)


def _make_coordinator() -> object:
    instance = object.__new__(coordinator.AmperePointCoordinator)
    instance.config_entry = types.SimpleNamespace(
        data={
            const.CONF_MODEL: "prime_22kw",
            const.CONF_SOURCE_INTEGRATION: "tuya_local",
            const.CONF_SOURCE_RAW_DP: "sensor.prime_charging_status",
            const.CONF_SOURCE_STATUS: "sensor.prime_charging_status",
            const.CONF_SOURCE_CURRENT_LIMIT: "sensor.prime_current_limit",
            const.CONF_SESSION_ENERGY_MODE: const.SESSION_ENERGY_MODE_AUTO,
        },
        options={},
    )
    instance.hass = types.SimpleNamespace(
        states=_States(
            {
                "sensor.prime_charging_status": _state(
                    "charging",
                    state_code=300,
                    telemetry=CHARGING_PAYLOAD,
                    session_data={"r": [1, 1]},
                    device_information={"fv": "(V9.1.0)F1.4.1"},
                ),
                "sensor.prime_current_limit": _state("17", unit_of_measurement="A"),
            }
        )
    )
    instance.model = models.get_model("prime_22kw")
    instance.native_source = None
    instance._store = _Store()
    instance._session_energy_kwh = 0.0
    instance._total_energy_baseline_kwh = None
    instance._last_total_energy_kwh = None
    instance._last_update = None
    instance._was_charging = False
    instance._was_connected = False
    instance._complete_candidate_since = None
    return instance


class PrimeTelemetryDecodeTests(unittest.TestCase):
    def test_charging_payload_is_scaled(self) -> None:
        decoded = coordinator._decode_prime_telemetry(CHARGING_PAYLOAD)
        self.assertEqual(
            decoded["phases"]["L1"],
            {
                "voltage": 218.0,
                "current": 6.6,
                "power": 1.4,
            },
        )
        self.assertEqual(decoded["power_kw"], 1.4)
        self.assertEqual(decoded["session_energy_kwh"], 0.1)
        self.assertEqual(decoded["temperature_c"], 36.0)
        self.assertEqual(decoded["session_duration_s"], 1340)
        self.assertEqual(decoded["cp_voltage_v"], 6.0)
        self.assertIs(decoded["vehicle_connected"], True)

    def test_json_string_and_idle_cp_are_decoded(self) -> None:
        payload = {**CHARGING_PAYLOAD, "cp": 121, "p": 0, "e": 0}
        decoded = coordinator._decode_prime_telemetry(json.dumps(payload))
        self.assertEqual(decoded["cp_voltage_v"], 12.1)
        self.assertIs(decoded["vehicle_connected"], False)

    def test_invalid_payload_is_rejected(self) -> None:
        self.assertIsNone(coordinator._decode_prime_telemetry("not-json"))
        self.assertIsNone(coordinator._decode_prime_telemetry({"foo": "bar"}))

    def test_full_update_maps_standard_dashboard_values(self) -> None:
        data = asyncio.run(_make_coordinator()._async_update_data())
        self.assertEqual(data["model"], "Ampere Point Wallbox Prime 22kW")
        self.assertEqual(data["status"], "Ladowanie")
        self.assertIs(data["vehicle_connected"], True)
        self.assertEqual(data["power_kw"], 1.4)
        self.assertEqual(data["session_energy_kwh"], 0.1)
        self.assertEqual(data["temperature_c"], 36.0)
        self.assertEqual(data["current_limit_a"], 17.0)
        self.assertEqual(data["voltage_l1"], 218.0)
        self.assertEqual(data["current_l1"], 6.6)
        self.assertEqual(data["power_l1"], 1.4)
        self.assertIsNone(data["voltage_l2"])
        self.assertEqual(data["phase_count"], 1)
        self.assertEqual(data["cp_voltage_v"], 6.0)
        self.assertEqual(data["session_duration_s"], 1340)
        self.assertEqual(data["session_duration_min"], 22.3)
        self.assertEqual(data["raw_dp"]["102"], CHARGING_PAYLOAD)


class PrimeTelemetryDiscoveryTests(unittest.TestCase):
    def test_telemetry_attribute_is_selected_as_raw_dp_source(self) -> None:
        entry = types.SimpleNamespace(
            entity_id="sensor.prime_charging_status",
            name="Charging status",
            original_name="Charging status",
            translation_key=None,
            unique_id="prime_status",
        )
        hass = types.SimpleNamespace(
            states=_States(
                {entry.entity_id: _state("charging", telemetry=CHARGING_PAYLOAD)}
            )
        )
        mapping = discovery.map_source_entities([entry], hass)
        self.assertEqual(mapping[const.CONF_SOURCE_STATUS], entry.entity_id)
        self.assertEqual(mapping[const.CONF_SOURCE_RAW_DP], entry.entity_id)

    def test_candidate_uses_auto_session_energy_for_prime_payload(self) -> None:
        candidate = discovery.SourceCandidate(
            device_id="device-1",
            title="Wallbox Prime 22kW",
            model_key="prime_22kw",
            source_integration="tuya_local",
            mapping={
                const.CONF_SOURCE_RAW_DP: "sensor.prime_charging_status",
            },
        )
        self.assertEqual(
            candidate.as_config_data()[const.CONF_SESSION_ENERGY_MODE],
            const.SESSION_ENERGY_MODE_AUTO,
        )

    def test_prime_model_is_detected_from_name_and_pid(self) -> None:
        self.assertEqual(models.detect_model_key("Wallbox Prime 22kW"), "prime_22kw")
        self.assertEqual(models.detect_model_key("gbmxngploofmhbjc"), "prime_22kw")


if __name__ == "__main__":
    unittest.main()
