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
        self.assertEqual(data["raw_dp"]["telemetry"], CHARGING_PAYLOAD)


class PrimeTelemetryFallbackTests(unittest.TestCase):
    def test_update_works_without_raw_dp_mapping(self) -> None:
        """Entries frozen without source_raw_dp heal via the status entity."""
        instance = _make_coordinator()
        data = dict(instance.config_entry.data)
        del data[const.CONF_SOURCE_RAW_DP]
        instance.config_entry.data = data

        result = asyncio.run(instance._async_update_data())
        self.assertEqual(result["power_kw"], 1.4)
        self.assertEqual(result["session_energy_kwh"], 0.1)
        self.assertEqual(result["temperature_c"], 36.0)
        self.assertEqual(result["voltage_l1"], 218.0)
        self.assertEqual(result["cp_voltage_v"], 6.0)
        self.assertEqual(result["session_duration_min"], 22.3)
        self.assertEqual(result["raw_dp"]["telemetry"], CHARGING_PAYLOAD)

    def test_raw_view_labels_and_decodes_the_prime_datapoints(self) -> None:
        data = asyncio.run(_make_coordinator()._async_update_data())
        raw = data["raw_dp"]
        metadata = data["dp_metadata"]
        # Codes, not bare DP numbers, and every code carries its DP id.
        self.assertLessEqual(
            {"work_state", "state_code", "telemetry", "session_data",
             "device_information"},
            set(raw),
        )
        self.assertEqual(metadata["telemetry"]["dp_id"], 102)
        self.assertEqual(metadata["work_state"]["dp_id"], 109)
        self.assertEqual(metadata["state_code"]["dp_id"], 101)
        # The packed payload is rendered instead of repeated verbatim.
        meaning = metadata["telemetry"]["meaning"]
        self.assertIn("L1 218.0 V / 6.6 A / 1.40 kW", meaning)
        self.assertIn("36.0 C", meaning)
        self.assertIn("CP 6.0 V", meaning)
        self.assertIn("22 min", meaning)
        self.assertIn("(V9.1.0)F1.4.1", metadata["device_information"]["meaning"])

    def test_packed_payload_is_listed_as_separate_rows(self) -> None:
        """DP102 readings appear individually, like discrete datapoints."""
        data = asyncio.run(_make_coordinator()._async_update_data())
        raw = data["raw_dp"]
        metadata = data["dp_metadata"]

        # Raw values keep the payload's own encoding...
        self.assertEqual(raw["l1_voltage_v"], 2180)
        self.assertEqual(raw["l1_current_a"], 66)
        self.assertEqual(raw["power_total_kw"], 14)
        self.assertEqual(raw["session_duration_s"], 1340)
        # ...and every row carries its DP, unit and scaled reading.
        self.assertEqual(metadata["l1_voltage_v"]["dp_id"], 102)
        self.assertEqual(metadata["l1_voltage_v"]["meaning"], "218 V")
        self.assertEqual(metadata["l1_current_a"]["meaning"], "6.6 A")
        self.assertEqual(metadata["temp_current_c"]["meaning"], "36 C")
        self.assertEqual(metadata["cp_voltage_v"]["meaning"], "6 V")
        # Phases the charger reports as zeroed stay listed, like a real DP.
        self.assertEqual(raw["l2_voltage_v"], 0)

    def test_sleep_state_is_normalized(self) -> None:
        self.assertEqual(models.normalize_status("sleep"), "Uspiony")
        self.assertEqual(models.normalize_status("SLEEP"), "Uspiony")


class MappedDatapointViewTests(unittest.TestCase):
    """Chargers with one entity per datapoint still get a raw-DP view."""

    def _coordinator(self):
        instance = object.__new__(coordinator.AmperePointCoordinator)
        instance.config_entry = types.SimpleNamespace(
            data={
                const.CONF_MODEL: "q_series",
                const.CONF_SOURCE_STATUS: "sensor.q11_status",
                const.CONF_SOURCE_CURRENT_LIMIT: "number.q11_current",
                const.CONF_SOURCE_POWER: "sensor.q11_power",
                const.CONF_SOURCE_CONNECTED: "sensor.q11_connection",
                const.CONF_SOURCE_TEMPERATURE: "sensor.q11_temperature",
            },
            options={},
        )
        instance.hass = types.SimpleNamespace(
            states=_States(
                {
                    "sensor.q11_status": _state("charger_free"),
                    "number.q11_current": _state("8", unit_of_measurement="A"),
                    "sensor.q11_power": _state("0", unit_of_measurement="kW"),
                    "sensor.q11_connection": _state("controlpi_12v"),
                    "sensor.q11_temperature": _state("25", unit_of_measurement="C"),
                }
            )
        )
        instance.native_source = None
        return instance

    def test_snapshot_carries_codes_dp_ids_and_write_access(self) -> None:
        values, metadata = self._coordinator()._mapped_source_snapshot()
        self.assertEqual(values["work_state"], "charger_free")
        self.assertEqual(values["charge_cur_set"], "8")
        self.assertEqual(values["connection_state"], "controlpi_12v")
        self.assertEqual(metadata["work_state"]["dp_id"], 3)
        self.assertEqual(metadata["charge_cur_set"]["dp_id"], 4)
        self.assertEqual(metadata["temp_current"]["dp_id"], 24)
        # A number entity can be written back, a sensor cannot.
        self.assertTrue(metadata["charge_cur_set"]["writable"])
        self.assertFalse(metadata["work_state"]["writable"])

    def test_local_readings_win_over_the_cloud_copy(self) -> None:
        """Cloud keeps every datapoint; LAN carries the live ones."""
        instance = self._coordinator()

        class _Native:
            def values(self):
                return {
                    "work_state": "charger_charging",
                    "charge_cur_set": 16,
                    "forward_energy_total": 4210,
                    "system_version": "V1",
                }

            def definitions(self):
                return {
                    "work_state": {"dp_id": 3},
                    "charge_cur_set": {"dp_id": 4, "scale": 0},
                    "forward_energy_total": {"dp_id": 1, "scale": 2},
                    "system_version": {"dp_id": 23},
                }

        instance.native_source = _Native()
        values, metadata = instance._datapoint_view(False)

        # Datapoints only the cloud knows are kept...
        self.assertEqual(values["forward_energy_total"], 4210)
        self.assertEqual(values["system_version"], "V1")
        self.assertEqual(metadata["forward_energy_total"]["scale"], 2)
        # ...while the LAN reading replaces the cloud copy, without the
        # cloud's scale, because an entity state is already scaled.
        self.assertEqual(values["charge_cur_set"], "8")
        self.assertNotIn("scale", metadata["charge_cur_set"])
        self.assertEqual(values["work_state"], "charger_free")

    def test_packed_source_keeps_its_own_numbering(self) -> None:
        """A Prime's DP150 must not be relabelled as the Q Series DP4."""
        instance = self._coordinator()
        instance._mapped_raw_values = lambda: {"telemetry": "{}"}
        instance._mapped_raw_metadata = lambda: {"telemetry": {"dp_id": 102}}
        values, metadata = instance._datapoint_view(True)
        self.assertEqual(set(values), {"telemetry"})
        self.assertEqual(metadata["telemetry"]["dp_id"], 102)

    def test_empty_cloud_snapshot_is_replaced(self) -> None:
        self.assertFalse(coordinator._has_reported_values({}))
        self.assertFalse(
            coordinator._has_reported_values({"work_state": None, "fault": ""})
        )
        self.assertTrue(coordinator._has_reported_values({"work_state": "charging"}))


class PrimeDiscoveryGateTests(unittest.TestCase):
    def test_wallbox_and_prime_names_pass_the_gate(self) -> None:
        for text in (
            "Wallbox Prime 22kW",
            "wallbox_stock_1",
            "gbmxngploofmhbjc",
            "Ladowarka garaz Wallbox",
        ):
            self.assertTrue(discovery._looks_like_amperepoint(text), text)

    def test_unrelated_devices_stay_filtered(self) -> None:
        self.assertFalse(discovery._looks_like_amperepoint("Living room lamp"))


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
