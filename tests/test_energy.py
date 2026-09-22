"""Regression tests for the HA Energy consumption stream (issue #36, part 1)."""
from __future__ import annotations
import asyncio
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
from datetime import datetime, UTC

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import load_integration_module, _Store

energy = load_integration_module("energy")
const = load_integration_module("const")
coordinator_module = load_integration_module("coordinator")
source_module = load_integration_module("source")
local_module = load_integration_module("local_source")


class MeterTests(unittest.TestCase):
    def setUp(self):
        self.meter = energy.ChargingEnergy()

    def counter(self, value, timestamp, source="q:dp1", resolution=0.01):
        return self.meter.update(energy.EnergySample(source, "device_counter", value, resolution), timestamp, 25)

    def power(self, value, timestamp):
        return self.meter.update(energy.EnergySample("p", "power_estimate", value), timestamp, 25)

    def test_initial_value_is_not_historical_consumption(self):
        self.assertEqual(self.counter(500, 100), 0)
        self.assertAlmostEqual(self.counter(501, 3700), 1)

    def test_q_session_style_dp1_reset_is_not_lifetime(self):
        self.counter(0, 100)
        self.assertEqual(self.counter(10, 3700), 10)
        self.assertEqual(self.counter(0, 3800), 10)
        self.assertEqual(self.counter(4, 7400), 14)

    def test_prime_counter_quantization_and_duplicate_polls(self):
        self.counter(0, 100, resolution=0.1)
        for timestamp in range(115, 400, 15):
            self.assertEqual(self.counter(0, timestamp, resolution=0.1), 0)
        self.assertAlmostEqual(self.counter(0.1, 401, resolution=0.1), 0.1)

    def test_duplicate_reading_does_not_add_energy(self):
        self.counter(0, 100)
        self.counter(2, 3700)
        self.assertEqual(self.counter(2, 7300), 2)

    def test_small_downward_correction_keeps_high_water_mark(self):
        self.counter(10, 100)
        self.assertEqual(self.counter(9.99, 200), 0)
        self.assertEqual(self.counter(10, 300), 0)
        self.assertAlmostEqual(self.counter(10.01, 400), 0.01)

    def test_nonzero_reset_is_not_added(self):
        self.counter(10, 100)
        self.assertEqual(self.counter(2, 3700), 0)
        self.assertTrue(self.meter.incomplete)
        self.assertEqual(self.counter(3, 7300), 1)

    def test_missing_counter_does_not_emit_zero_and_recovers_delta(self):
        self.counter(100, 100)
        self.assertIsNone(self.counter(None, 3700))
        self.assertEqual(self.counter(103, 7300), 3)
        self.assertEqual(self.meter.quality, "gap_recovered")

    def test_counter_restart_uses_persisted_baseline(self):
        self.counter(50, 100)
        self.counter(53, 3700)
        self.meter = energy.ChargingEnergy(json.loads(json.dumps(self.meter.dump())))
        self.assertEqual(self.counter(55, 7300), 5)

    def test_restart_with_same_sample_does_not_duplicate(self):
        self.counter(0, 100)
        self.counter(1, 3700)
        self.meter = energy.ChargingEnergy(self.meter.dump())
        self.assertEqual(self.counter(1, 7300), 1)

    def test_source_switch_rebases_without_counting_overlap(self):
        self.counter(0, 100)
        self.counter(3, 3700)
        self.assertEqual(self.counter(800, 4000, source="lan:other"), 3)
        self.assertEqual(self.counter(801, 7600, source="lan:other"), 4)

    def test_spike_is_rejected(self):
        self.counter(1, 100)
        self.assertIsNone(self.counter(1000, 115))
        self.assertAlmostEqual(self.counter(1.1, 200), 0.1)

    def test_stale_pre_reset_reading_cannot_add_whole_previous_session(self):
        self.counter(0, 100)
        self.counter(10, 3700)
        self.counter(0, 3800)
        self.assertIsNone(self.counter(10, 3815))
        self.assertAlmostEqual(self.counter(0.1, 3900), 10.1)

    def test_out_of_order_timestamp_is_ignored(self):
        self.counter(0, 100)
        self.counter(2, 3700)
        self.assertEqual(self.counter(0, 200), 2)
        self.assertEqual(self.counter(3, 7300), 3)

    def test_duplicate_poll_timestamp_still_blocks_older_reset(self):
        self.counter(10, 100)
        self.counter(10, 400)
        self.assertEqual(self.counter(0, 300), 0)
        self.assertEqual(self.meter.baseline, 10)
        self.assertEqual(self.counter(11, 3700), 1)

    def test_invalid_numbers_never_enter_statistics(self):
        for value in (True, -1, float("nan"), float("inf"), "unavailable", "unknown"):
            with self.subTest(value=value):
                self.assertIsNone(self.counter(value, 100))
                self.assertEqual(self.meter.total, 0)

    def test_power_left_sum_and_zero_tester(self):
        self.power(0, 100)
        self.assertEqual(self.power(0, 130), 0)
        self.power(12, 160)
        self.assertAlmostEqual(self.power(0, 190), 0.1)
        self.assertAlmostEqual(self.power(0, 220), 0.1)

    def test_power_does_not_integrate_long_gaps(self):
        self.power(12, 100)
        self.assertEqual(self.power(12, 3600), 0)
        self.assertEqual(self.meter.quality, "gap_not_integrated")

    def test_power_explicit_outage_breaks_integration_even_if_short(self):
        self.power(12, 100)
        self.meter.missing()
        self.assertEqual(self.power(12, 115), 0)
        self.assertAlmostEqual(self.power(12, 145), 0.1)

    def test_power_restart_never_reconstructs_unobserved_interval(self):
        self.power(12, 100)
        self.meter = energy.ChargingEnergy(self.meter.dump())
        self.assertEqual(self.power(12, 130), 0)
        self.assertAlmostEqual(self.power(12, 160), 0.1)

    def test_invalid_initial_power_cannot_poison_next_interval(self):
        self.assertIsNone(self.power(99999, 100))
        self.assertEqual(self.power(1, 130), 0)

    def test_unsupported_storage_version_does_not_import_garbage(self):
        saved = {"format": 999, "total": 500}
        self.meter = energy.ChargingEnergy(saved)
        self.assertIsNone(self.counter(100, 100))
        self.assertEqual(self.meter.quality, "storage_error")
        self.assertEqual(self.meter.dump(), saved)

    def test_corrupt_storage_is_safe(self):
        for saved in ([], {"format": 1, "total": float("nan")}):
            self.meter = energy.ChargingEnergy(saved)
            self.assertIsNone(self.counter(100, 100))
            self.assertEqual(self.meter.quality, "storage_error")

    def test_old_session_storage_without_energy_starts_a_new_meter(self):
        self.meter = energy.ChargingEnergy(None)
        self.assertEqual(self.counter(100, 100), 0)


def make_coordinator(data=None, states=None):
    instance = object.__new__(coordinator_module.AmperePointCoordinator)
    instance._charging_energy = energy.ChargingEnergy()
    instance.native_source = None
    instance.config_entry = types.SimpleNamespace(data=data or {}, options={})
    instance.hass = types.SimpleNamespace(states=types.SimpleNamespace(get=lambda key: (states or {}).get(key)))
    return instance


def state(value, **attrs):
    return types.SimpleNamespace(state=str(value), attributes=attrs)


class SourceSelectionTests(unittest.TestCase):
    def test_mapped_mwh_are_converted_and_wrong_units_rejected(self):
        for unit, expected in (("MWh", 1500), ("W", None), ("kWh/day", None)):
            obj = make_coordinator({const.CONF_SOURCE_TOTAL_ENERGY: "sensor.energy"},
                                  {"sensor.energy": state(1.5, unit_of_measurement=unit)})
            self.assertEqual(obj._energy_sample(None).value, expected)

    def test_mapped_wh_are_converted_to_kwh(self):
        obj = make_coordinator({const.CONF_SOURCE_TOTAL_ENERGY: "sensor.energy"},
                               {"sensor.energy": state(1500, unit_of_measurement="Wh")})
        self.assertEqual(obj._energy_sample(None).value, 1.5)

    def test_total_and_session_are_not_added_together(self):
        obj = make_coordinator({const.CONF_SOURCE_TOTAL_ENERGY: "sensor.total", const.CONF_SOURCE_SESSION_ENERGY: "sensor.session"},
                               {"sensor.total": state(100), "sensor.session": state(10)})
        sample = obj._energy_sample(None)
        self.assertEqual(sample.value, 100)
        self.assertEqual(sample.source, "entity:sensor.total")

    def test_unavailable_counter_never_falls_back_to_power(self):
        obj = make_coordinator({const.CONF_SOURCE_TOTAL_ENERGY: "sensor.total", const.CONF_SOURCE_POWER: "sensor.power"},
                               {"sensor.total": state("unavailable"), "sensor.power": state(11)})
        self.assertEqual(obj._energy_sample(None).method, "device_counter")
        self.assertIsNone(obj._energy_sample(None).value)

    def test_last_session_dp25_is_never_live_consumption(self):
        obj = make_coordinator({const.CONF_SOURCE_LAST_SESSION_ENERGY: "sensor.previous"},
                               {"sensor.previous": state(99)})
        self.assertIsNone(obj._energy_sample(None).value)

    def test_prime_mapped_payload(self):
        obj = make_coordinator({const.CONF_SOURCE_STATUS: "sensor.prime"}, {"sensor.prime": state("charging")})
        sample = obj._energy_sample({"session_energy_kwh": 0.2})
        self.assertEqual((sample.method, sample.value, sample.resolution), ("session_counter", 0.2, 0.1))

    def test_prime_unavailable_attributes_cannot_be_recounted(self):
        obj = make_coordinator({const.CONF_SOURCE_STATUS: "sensor.prime"}, {"sensor.prime": state("unavailable")})
        self.assertIsNone(obj._energy_sample({"session_energy_kwh": 1}).value)

    def test_prime_stale_raw_mapping_uses_the_actual_status_provider(self):
        obj = make_coordinator({const.CONF_SOURCE_RAW_DP: "sensor.deleted", const.CONF_SOURCE_STATUS: "sensor.prime"},
                               {"sensor.prime": state("charging", telemetry={"e": 1})})
        sample = obj._energy_sample({"session_energy_kwh": 0.1})
        self.assertEqual(sample.source, "entity:sensor.prime:dp102.e")
        self.assertEqual(sample.value, 0.1)

    def test_native_q_metadata_scale(self):
        obj = make_coordinator()
        definition = types.SimpleNamespace(type="Integer", values=json.dumps({"scale": 2}))
        device = types.SimpleNamespace(id="test", online=True, status={"forward_energy_total": 125},
                                       status_range={"forward_energy_total": definition}, function={})
        obj.native_source = source_module.NativeTuyaSource(None, None, device)
        sample = obj._energy_sample(None)
        self.assertEqual((sample.value, sample.resolution), (1.25, 0.01))
        device.online = False
        self.assertIsNone(obj._energy_sample(None).value)

    def test_native_prime_lan(self):
        obj = make_coordinator()
        obj.native_source = local_module.NativeLocalSource(None, types.SimpleNamespace(data={"local_device_id": "test"}, options={}))
        obj.native_source.available = True
        sample = obj._energy_sample({"session_energy_kwh": 0.1})
        self.assertEqual(sample.method, "session_counter")
        self.assertEqual(sample.value, 0.1)

    def test_power_only_fallback_is_explicitly_estimated_and_converts_w(self):
        obj = make_coordinator({const.CONF_SOURCE_POWER: "sensor.power"}, {"sensor.power": state(11000, unit_of_measurement="W")})
        sample = obj._energy_sample(None)
        self.assertEqual((sample.method, sample.value), ("power_estimate", 11))


class CoordinatorPipelineTests(unittest.TestCase):
    def make(self, config, states):
        entry = types.SimpleNamespace(data=config, options={}, entry_id="test-entry", title="Test")
        hass = types.SimpleNamespace(states=types.SimpleNamespace(get=states.get))
        with patch.object(source_module.NativeTuyaSource, "resolve", return_value=None):
            obj = coordinator_module.AmperePointCoordinator(hass, entry)
        obj._store = _Store()
        return obj

    def update(self, obj, timestamp):
        with patch.object(coordinator_module.dt_util, "utcnow", return_value=datetime.fromtimestamp(timestamp, UTC)):
            obj.data = asyncio.run(obj._async_update_data())
        return obj.data

    def test_q_pipeline_restart_and_reset_preserve_consumption(self):
        states = {"sensor.source": state(50, unit_of_measurement="kWh")}
        config = {const.CONF_SOURCE_TOTAL_ENERGY: "sensor.source"}
        obj = self.make(config, states)
        self.assertEqual(self.update(obj, 100)["charging_energy_kwh"], 0)
        states["sensor.source"] = state(52, unit_of_measurement="kWh")
        self.assertEqual(self.update(obj, 3700)["charging_energy_kwh"], 2)
        saved = json.loads(json.dumps(obj._store._data))
        obj = self.make(config, states)
        obj._store._data = saved
        asyncio.run(obj.async_load_state())
        states["sensor.source"] = state(53, unit_of_measurement="kWh")
        self.assertEqual(self.update(obj, 7300)["charging_energy_kwh"], 3)
        states["sensor.source"] = state(0, unit_of_measurement="kWh")
        self.assertEqual(self.update(obj, 7400)["charging_energy_kwh"], 3)
        states["sensor.source"] = state(2, unit_of_measurement="kWh")
        self.assertEqual(self.update(obj, 11000)["charging_energy_kwh"], 5)

    def test_prime_split_and_packed_payloads_use_e_not_cp_or_session_state(self):
        for payload in ({"L": [2300, 0, 0], "e": 100, "p": 0},
                        {"L1": [2300, 0, 0], "L2": [0, 0, 0], "L3": [0, 0, 0], "e": 100, "p": 0, "cp": 60}):
            states = {"sensor.prime": state("STATE_C", telemetry=payload)}
            obj = self.make({const.CONF_MODEL: "prime", const.CONF_SOURCE_STATUS: "sensor.prime"}, states)
            self.assertEqual(self.update(obj, 100)["charging_energy_kwh"], 0)
            self.assertEqual(self.update(obj, 115)["charging_energy_kwh"], 0)
            payload["e"] = 110
            self.assertEqual(self.update(obj, 3700)["charging_energy_kwh"], 1)
            states["sensor.prime"] = state("unavailable", telemetry=payload)
            self.assertIsNone(self.update(obj, 4000)["charging_energy_kwh"])

    def test_old_session_state_does_not_import_session_energy_as_consumption(self):
        obj = self.make({}, {})
        obj._store._data = {"session_energy_kwh": 33, "was_charging": True}
        asyncio.run(obj.async_load_state())
        self.assertEqual(obj._charging_energy.total, 0)
        self.assertEqual(obj._session_energy_kwh, 33)

    def test_each_charger_has_an_independent_meter(self):
        states = {"sensor.a": state(10), "sensor.b": state(20)}
        a = self.make({const.CONF_SOURCE_TOTAL_ENERGY: "sensor.a"}, states)
        b = self.make({const.CONF_SOURCE_TOTAL_ENERGY: "sensor.b"}, states)
        self.update(a, 100)
        self.update(b, 100)
        states["sensor.a"] = state(11)
        self.assertEqual(self.update(a, 3700)["charging_energy_kwh"], 1)
        self.assertEqual(self.update(b, 3700)["charging_energy_kwh"], 0)


class SensorContractTests(unittest.TestCase):
    def test_only_canonical_energy_has_a_statistics_state_class(self):
        sensor = load_integration_module("sensor")
        descriptions = {desc.key: desc for desc in sensor.SENSORS}
        canonical = descriptions["charging_energy"]
        self.assertEqual(canonical.native_unit_of_measurement, "kWh")
        self.assertEqual(canonical.device_class, "energy")
        self.assertEqual(canonical.state_class, "total_increasing")
        for key in ("session_energy", "last_session_energy", "total_energy", "session_cost"):
            self.assertIsNone(descriptions[key].state_class)
        self.assertEqual(descriptions["power"].state_class, "measurement")

    def test_identity_availability_and_bounded_attributes(self):
        sensor = load_integration_module("sensor")
        desc = next(item for item in sensor.SENSORS if item.key == "charging_energy")
        coord = types.SimpleNamespace(config_entry=types.SimpleNamespace(entry_id="first"),
                                      data={"charging_energy_kwh": 0}, last_update_success=True)
        entity = sensor.AmperePointSensor(coord, desc)
        self.assertEqual(entity._attr_unique_id, "first_charging_energy")
        self.assertTrue(entity.available)
        self.assertEqual(entity.extra_state_attributes["power_tolerance_percent"], 10)
        coord.data["charging_energy_kwh"] = None
        self.assertFalse(entity.available)
        coord.data["charging_energy_kwh"] = 1
        coord.last_update_success = False
        self.assertFalse(entity.available)

    def test_dashboard_backend_maps_the_same_entity(self):
        dashboard = load_integration_module("dashboard")
        self.assertEqual(dashboard._CARD_ENTITY_KEYS["charging_energy"], "chargingEnergy")


if __name__ == "__main__":
    unittest.main()
