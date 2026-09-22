"""Power/counter agreement, idle-resume regression and source freshness."""
from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import load_integration_module
import test_energy as energy_tests

make_coordinator, state = energy_tests.make_coordinator, energy_tests.state

energy = load_integration_module("energy")
observer_module = load_integration_module("power_observer")
const = load_integration_module("const")
source_module = load_integration_module("source")


class PowerValidationTests(unittest.TestCase):
    def setUp(self):
        self.meter = energy.ChargingEnergy()

    def update(self, value, now, power=3.7, stamp=None, source="q:dp1", power_source="q:power"):
        return self.meter.update(energy.EnergySample(source, "device_counter", value), now, 25,
                                 energy.PowerSample(power_source, power, now if stamp is None else stamp))

    def hour(self, multiplier=1, start=1, base=0):
        self.update(base, start)
        for elapsed in range(15, 3601, 15):
            self.update(base + multiplier * 3.7 * elapsed / 3600, start + elapsed)

    def test_ten_percent_is_accepted(self):
        self.hour(1.10)
        self.assertAlmostEqual(self.meter.total, 4.07)
        self.assertEqual(self.meter.corrections, 0)
        self.assertAlmostEqual(self.meter.power_total, 3.7)

    def test_quantization_and_report_delay_margin(self):
        self.update(0, 1, 11)
        # Counter leads one sample by 0.1 kWh, then stays unchanged while
        # the power estimate catches up. Neither report may be "corrected".
        self.update(0.1, 16, 11)
        self.update(0.1, 31, 11)
        self.update(0.1, 46, 11)
        self.assertEqual(self.meter.corrections, 0)

    def test_small_absolute_difference_at_zero_does_not_correct(self):
        self.update(0, 1, 0)
        self.update(0.1, 16, 0)
        self.assertEqual(self.meter.corrections, 0)

    def test_above_ten_percent_plus_absolute_margin_is_corrected(self):
        self.update(0, 1)
        for t in range(16, 3602, 15):
            self.update(0, t)
        self.update(4.24, 3616)  # within 10% plus rounding/report-lag margins
        self.assertEqual(self.meter.corrections, 0)
        self.update(5, 3631)
        self.assertEqual(self.meter.corrections, 1)
        # Already published energy is never decreased.
        self.assertAlmostEqual(self.meter.total, 4.24 + 3.7 * 15 / 3600)

    def test_five_hour_idle_then_double_count_is_excluded(self):
        self.hour()
        self.update(3.7, 3616, 0)
        for t in range(3631, 21617, 15):
            self.update(3.7, t, 0)
        before = self.meter.total
        self.update(7.4, 21631, 3.7)
        self.assertLess(self.meter.total - before, 0.02)
        self.assertEqual(self.meter.quality, "power_corrected")
        self.assertEqual(self.meter.corrections, 1)
        self.assertGreater(self.meter.excluded_energy, 3.6)
        corrected = self.meter.total
        self.update(7.4, 21646, 3.7)
        self.assertEqual(self.meter.total, corrected)
        self.update(7.42, 21661, 3.7)
        self.assertAlmostEqual(self.meter.total, corrected + 0.02)
        self.assertEqual(self.meter.corrections, 1)

    def test_normal_resume_and_delayed_energy_report(self):
        self.update(0, 1)
        for t in range(16, 3602, 15):
            self.update(0, t)
        # All energy arrives late in one report; compare the entire interval.
        self.update(3.7, 3616, 0)
        for t in range(3631, 21617, 15):
            self.update(3.7, t, 0)
        self.update(3.7, 21631, 3.7)
        self.update(3.72, 21646, 3.7)
        self.assertEqual(self.meter.corrections, 0)
        self.assertAlmostEqual(self.meter.total, 3.72)

    def test_stale_zero_cannot_authorize_correction(self):
        self.update(0, 1, 0)
        for t in range(16, 7202, 15):
            self.update(0, t, 0, stamp=1)
        self.update(5, 7216, 0, stamp=1)
        self.assertEqual(self.meter.total, 5)
        self.assertEqual(self.meter.corrections, 0)
        self.assertTrue(self.meter.power_incomplete)

    def test_outage_cannot_be_filled_or_used_to_correct(self):
        self.update(0, 1)
        self.update(0, 16)
        self.update(0, 31, None)
        self.update(5, 7201)
        self.assertEqual(self.meter.total, 5)
        self.assertLess(self.meter.power_total, 0.02)
        self.assertEqual(self.meter.corrections, 0)

    def test_restart_preserves_correction_and_does_not_recount(self):
        self.update(0, 1, 0)
        self.update(5, 16, 0)
        self.assertEqual(self.meter.corrections, 1)
        saved = json.loads(json.dumps(self.meter.dump()))
        self.meter = energy.ChargingEnergy(saved)
        self.update(5, 3601, 0)
        self.assertEqual(self.meter.total, 0)
        self.assertEqual(self.meter.corrections, 1)
        self.assertEqual(self.meter.excluded_energy, 5)
        self.assertTrue(self.meter.power_incomplete)

    def test_restart_unknown_interval_preserves_counter_delta(self):
        self.update(0, 1, 0)
        self.meter = energy.ChargingEnergy(self.meter.dump())
        self.update(5, 7201, 0)
        self.assertEqual(self.meter.total, 5)
        self.assertEqual(self.meter.corrections, 0)

    def test_source_changes_do_not_compare_unrelated_meters(self):
        self.update(0, 1, 0)
        self.update(10, 7201, 0, source="other")
        self.assertEqual(self.meter.total, 0)
        self.update(10.1, 7216, 0, source="other", power_source="other-power")
        self.assertAlmostEqual(self.meter.total, 0.1)
        self.assertEqual(self.meter.corrections, 0)

    def test_counter_reset_and_return_from_transient_bad_value(self):
        self.update(0, 1, 0)
        self.update(5, 16, 0)
        self.update(0, 31, 3.7)
        self.update(0.02, 46, 3.7)
        self.assertAlmostEqual(self.meter.total, 0.02)
        self.assertEqual(self.meter.corrections, 1)

    def test_missing_counter_still_accumulates_parallel_power(self):
        self.update(0, 1)
        self.update(None, 16)
        self.update(None, 31)
        self.assertAlmostEqual(self.meter.power_total, 3.7 * 30 / 3600)
        self.assertEqual(self.meter.validation, "missing_counter")

    def test_counter_arriving_before_start_power_report_is_not_corrected(self):
        self.update(0, 1, 0)
        self.update(0.3, 46, 0)
        self.update(0.3, 61, 24)
        self.assertEqual(self.meter.corrections, 0)

    def test_lower_counter_is_not_automatically_topped_up(self):
        self.hour(0.5)
        self.assertAlmostEqual(self.meter.total, 1.85)
        self.assertEqual(self.meter.corrections, 0)

    def test_invalid_saved_power_total_does_not_reset_diagnostic_meter(self):
        saved = self.meter.dump()
        saved["power_total"] = -1
        self.meter = energy.ChargingEnergy(saved)
        self.assertIsNone(self.update(0, 1))
        self.assertEqual(self.meter.quality, "storage_error")


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.observer = observer_module.PowerReportObserver("q")

    def report(self, items, now=100, **data):
        with patch.object(observer_module.time, "time", return_value=now):
            self.observer._on_message({"protocol": 4, "data": {"devId": "q", "status": items, **data}})

    def test_only_matching_power_reports_refresh_timestamp(self):
        self.report([{"code": "power_total", "value": 0}])
        self.assertEqual(self.observer.reported_at(0), 100)
        self.report([{"code": "temp_current", "value": 20}], 200)
        self.assertEqual(self.observer.reported_at(0), 100)
        self.report([{"code": "power_total", "value": 0}], 210, devId="other")
        self.assertEqual(self.observer.reported_at(0), 100)
        self.report([{"code": "power_total", "value": 0}], 220)
        self.assertEqual(self.observer.reported_at(0), 220)
        self.assertIsNone(self.observer.reported_at(10))

    def test_report_timestamp_replay_and_invalid_value(self):
        self.report([{"code": "power_total", "value": 0, "t": 90}])
        self.report([{"code": "power_total", "value": 0, "t": 80}], 200)
        self.assertEqual(self.observer.reported_at(0), 90)
        self.report([{"code": "power_total", "value": None}])
        self.assertIsNone(self.observer.reported_at(0))

    def test_milliseconds_and_future_timestamps(self):
        self.report([{"code": "power_total", "value": 0, "t": 1800000000000}], 1800000001)
        self.assertEqual(self.observer.reported_at(0), 1800000000)
        self.report([{"code": "power_total", "value": 0, "t": 1800000050000}], 1800000001)
        self.assertIsNone(self.observer.reported_at(0))

    def test_reconnect_and_unload_remove_listener_and_stale_report(self):
        def mq():
            listeners = set()
            return types.SimpleNamespace(add_message_listener=listeners.add,
                                         remove_message_listener=listeners.discard, listeners=listeners)
        a, b = mq(), mq()
        self.observer.attach(a)
        self.report([{"code": "power_total", "value": 0}])
        self.observer.attach(b)
        self.assertFalse(a.listeners)
        self.assertEqual(len(b.listeners), 1)
        self.assertIsNone(self.observer.reported_at(0))
        self.observer.close()
        self.observer.close()
        self.assertFalse(b.listeners)


class PowerSourceTests(unittest.TestCase):
    def test_native_cloud_requires_matching_per_dp_report(self):
        obj = make_coordinator()
        definition = types.SimpleNamespace(type="Integer", values=json.dumps({"scale": 1}))
        device = types.SimpleNamespace(id="q", online=True, status={"power_total": 37},
                                       status_range={"power_total": definition}, function={})
        obj.native_source = source_module.NativeTuyaSource(None, None, device)
        obj._power_observer = observer_module.PowerReportObserver("q")
        self.assertIsNone(obj._energy_power_sample(None, 100).reported_at)
        with patch.object(observer_module.time, "time", return_value=100):
            obj._power_observer._on_message({"protocol": 4, "data": {
                "devId": "q", "status": [{"code": "power_total", "value": 37}]}})
        sample = obj._energy_power_sample(None, 115)
        self.assertEqual((sample.value, sample.reported_at), (3.7, 100))
        device.online = False
        self.assertIsNone(obj._energy_power_sample(None, 115))

    def test_mapped_power_uses_last_reported_and_converts_units(self):
        s = state(3700, unit_of_measurement="W")
        s.last_reported = datetime.fromtimestamp(100, UTC)
        obj = make_coordinator({const.CONF_SOURCE_POWER: "sensor.p"}, {"sensor.p": s})
        sample = obj._energy_power_sample(None, 115)
        self.assertEqual((sample.value, sample.reported_at), (3.7, 100))
        self.assertEqual(obj._energy_power_sample(None, 130).reported_at, 100)

    def test_aggregate_q_attributes_cannot_certify_power_freshness(self):
        s = state("charging", power_total_kw=3.7)
        s.last_reported = datetime.fromtimestamp(100, UTC)
        obj = make_coordinator({const.CONF_SOURCE_RAW_DP: "sensor.raw"}, {"sensor.raw": s})
        self.assertIsNone(obj._energy_power_sample(None, 100).reported_at)


class PowerPipelineTests(unittest.TestCase):
    make = energy_tests.CoordinatorPipelineTests.make
    update = energy_tests.CoordinatorPipelineTests.update

    def test_corrected_value_and_evidence_are_checkpointed_before_publish(self):
        config = {const.CONF_SOURCE_TOTAL_ENERGY: "sensor.e", const.CONF_SOURCE_POWER: "sensor.p"}
        p = state(0, unit_of_measurement="kW")
        p.last_reported = datetime.fromtimestamp(100, UTC)
        states = {"sensor.e": state(0, unit_of_measurement="kWh"), "sensor.p": p}
        obj = self.make(config, states)
        self.update(obj, 100)
        states["sensor.e"] = state(5, unit_of_measurement="kWh")
        p.last_reported = datetime.fromtimestamp(115, UTC)
        data = self.update(obj, 115)
        self.assertEqual(data["charging_energy_kwh"], 0)
        self.assertEqual(data["energy_corrections"], 1)
        self.assertEqual(data["excluded_energy_kwh"], 5)
        self.assertEqual(obj._store._data["charging_energy"]["baseline"], 5)
        self.assertEqual(obj._store._data["charging_energy"]["corrections"], 1)


if __name__ == "__main__":
    unittest.main()
