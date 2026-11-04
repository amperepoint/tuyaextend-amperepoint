from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import load_integration_module  # noqa: E402

surplus = load_integration_module("surplus")

START = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)


def _settings(**overrides):
    defaults = {
        "mode": surplus.MODE_PV_ONLY,
        "phases": 1,
        "min_current_a": 6.0,
        "max_current_a": 16.0,
        "reserve_w": 0.0,
        "max_import_w": 0.0,
        "smoothing_samples": 1,
        "start_delay": timedelta(0),
        "stop_delay": timedelta(0),
        "min_run_time": timedelta(0),
        "current_step_a": 100.0,  # allow immediate jumps unless a test cares
    }
    defaults.update(overrides)
    return surplus.SurplusSettings(**defaults)


def _engine(**overrides):
    return surplus.SurplusEngine(settings=_settings(**overrides))


def _measure(**kwargs):
    return surplus.SurplusMeasurements(**kwargs)


class SurplusAccountingTests(unittest.TestCase):
    def test_export_is_available_surplus(self) -> None:
        engine = _engine()
        # Exporting 3 kW with nothing charging yet.
        available = engine.available_surplus_w(_measure(grid_w=-3000.0))
        self.assertEqual(available, 3000.0)

    def test_charger_draw_counts_as_available(self) -> None:
        """Otherwise raising the current looks like a deficit and oscillates."""
        engine = _engine()
        available = engine.available_surplus_w(_measure(grid_w=0.0, charger_w=1400.0))
        self.assertEqual(available, 1400.0)

    def test_house_reserve_is_subtracted(self) -> None:
        engine = _engine(reserve_w=500.0)
        self.assertEqual(engine.available_surplus_w(_measure(grid_w=-3000.0)), 2500.0)

    def test_pv_minus_house_when_no_grid_meter(self) -> None:
        engine = _engine()
        available = engine.available_surplus_w(_measure(pv_w=5000.0, house_w=1500.0))
        self.assertEqual(available, 3500.0)

    def test_battery_charging_has_priority(self) -> None:
        engine = _engine(battery_min_soc=80.0)
        available = engine.available_surplus_w(
            _measure(grid_w=-3000.0, battery_w=2000.0, battery_soc=50.0)
        )
        self.assertEqual(available, 1000.0)

    def test_full_battery_does_not_reserve_power(self) -> None:
        engine = _engine(battery_min_soc=80.0)
        available = engine.available_surplus_w(
            _measure(grid_w=-3000.0, battery_w=2000.0, battery_soc=95.0)
        )
        self.assertEqual(available, 3000.0)

    def test_surplus_never_exceeds_production(self) -> None:
        """A meter that does not see the charger must not create surplus.

        Found by driving the engine from the SUN2000 simulator: the charger's
        own draw counts as available, so when the grid meter does not include
        it the accounting feeds back on itself and ramps to maximum at night.
        """
        engine = _engine()
        available = engine.available_surplus_w(
            _measure(pv_w=0.0, grid_w=800.0, charger_w=16000.0)
        )
        self.assertEqual(available, 0.0)

    def test_production_cap_still_allows_a_real_surplus(self) -> None:
        engine = _engine()
        available = engine.available_surplus_w(
            _measure(pv_w=8500.0, grid_w=-3000.0, charger_w=4000.0)
        )
        self.assertEqual(available, 7000.0)

    def test_night_time_never_charges_in_pv_only_mode(self) -> None:
        engine = _engine(smoothing_samples=1)
        decision = engine.evaluate(
            START, _measure(pv_w=0.0, grid_w=800.0, charger_w=11000.0)
        )
        self.assertFalse(decision.charging)

    def test_discharging_battery_is_not_added_twice(self) -> None:
        engine = _engine()
        available = engine.available_surplus_w(
            _measure(grid_w=-1000.0, battery_w=-500.0, battery_soc=60.0)
        )
        self.assertEqual(available, 1000.0)


class PvOnlyModeTests(unittest.TestCase):
    def test_waits_until_surplus_reaches_minimum_current(self) -> None:
        engine = _engine()
        decision = engine.evaluate(START, _measure(grid_w=-1000.0))
        self.assertFalse(decision.charging)
        self.assertEqual(decision.state, surplus.STATE_WAITING)

    def test_starts_and_scales_current_with_surplus(self) -> None:
        engine = _engine()
        decision = engine.evaluate(START, _measure(grid_w=-2300.0))
        self.assertTrue(decision.charging)
        self.assertEqual(decision.current_a, 10.0)
        self.assertEqual(decision.state, surplus.STATE_CHARGING_PV)

    def test_current_is_capped_by_hardware_maximum(self) -> None:
        engine = _engine(max_current_a=16.0)
        decision = engine.evaluate(START, _measure(grid_w=-20000.0))
        self.assertEqual(decision.current_a, 16.0)

    def test_three_phase_needs_three_times_the_power(self) -> None:
        single = _engine(phases=1).evaluate(START, _measure(grid_w=-2300.0))
        three = _engine(phases=3).evaluate(START, _measure(grid_w=-2300.0))
        self.assertEqual(single.current_a, 10.0)
        # 2300 W over three phases is below the 6 A minimum (4140 W).
        self.assertFalse(three.charging)

    def test_three_phase_starts_with_enough_surplus(self) -> None:
        decision = _engine(phases=3).evaluate(START, _measure(grid_w=-6900.0))
        self.assertTrue(decision.charging)
        self.assertEqual(decision.current_a, 10.0)

    def test_pv_only_never_uses_the_import_allowance(self) -> None:
        engine = _engine(mode=surplus.MODE_PV_ONLY, max_import_w=5000.0)
        decision = engine.evaluate(START, _measure(grid_w=-500.0))
        self.assertFalse(decision.charging)


class CloudAndHysteresisTests(unittest.TestCase):
    def test_short_cloud_does_not_stop_charging(self) -> None:
        engine = _engine(
            smoothing_samples=3, stop_delay=timedelta(minutes=3), min_run_time=timedelta(0)
        )
        now = START
        for _ in range(3):
            engine.evaluate(now, _measure(grid_w=-3000.0))
            now += timedelta(minutes=1)
        # A single dark minute: smoothing keeps the average above the minimum.
        decision = engine.evaluate(now, _measure(grid_w=0.0))
        self.assertTrue(decision.charging)

    def test_sustained_loss_of_surplus_stops_charging(self) -> None:
        engine = _engine(
            smoothing_samples=2, stop_delay=timedelta(minutes=3), min_run_time=timedelta(0)
        )
        now = START
        engine.evaluate(now, _measure(grid_w=-3000.0))
        for _ in range(6):
            now += timedelta(minutes=1)
            decision = engine.evaluate(now, _measure(grid_w=200.0))
        self.assertFalse(decision.charging)
        self.assertEqual(decision.state, surplus.STATE_WAITING)

    def test_start_delay_debounces_a_brief_sunny_spell(self) -> None:
        engine = _engine(start_delay=timedelta(minutes=2))
        first = engine.evaluate(START, _measure(grid_w=-3000.0))
        self.assertFalse(first.charging)
        later = engine.evaluate(START + timedelta(minutes=3), _measure(grid_w=-3000.0))
        self.assertTrue(later.charging)

    def test_minimum_run_time_survives_a_house_load_spike(self) -> None:
        engine = _engine(min_run_time=timedelta(minutes=5), smoothing_samples=1)
        engine.evaluate(START, _measure(grid_w=-3000.0))
        # Oven switches on one minute later and eats the whole surplus.
        decision = engine.evaluate(START + timedelta(minutes=1), _measure(grid_w=2000.0))
        self.assertTrue(decision.charging)
        # Once the minimum run time has passed the charger releases.
        decision = engine.evaluate(START + timedelta(minutes=6), _measure(grid_w=2000.0))
        self.assertFalse(decision.charging)

    def test_current_ramps_instead_of_jumping(self) -> None:
        engine = _engine(current_step_a=1.0)
        engine.evaluate(START, _measure(grid_w=-1610.0))  # 7 A
        decision = engine.evaluate(START, _measure(grid_w=-3680.0))  # wants 16 A
        self.assertEqual(decision.current_a, 8.0)


class ModeTests(unittest.TestCase):
    def test_pv_grid_tops_up_from_the_import_allowance(self) -> None:
        engine = _engine(mode=surplus.MODE_PV_GRID, max_import_w=2300.0)
        decision = engine.evaluate(START, _measure(grid_w=-1150.0))
        self.assertTrue(decision.charging)
        self.assertEqual(decision.current_a, 15.0)
        self.assertEqual(decision.state, surplus.STATE_CHARGING_MIXED)

    def test_target_mode_charges_without_any_surplus(self) -> None:
        engine = _engine(mode=surplus.MODE_TARGET)
        decision = engine.evaluate(START, _measure(grid_w=3000.0), target_active=True)
        self.assertTrue(decision.charging)
        self.assertEqual(decision.current_a, 6.0)
        self.assertEqual(decision.state, surplus.STATE_TARGET_NEEDS_GRID)

    def test_target_mode_without_deadline_behaves_like_surplus(self) -> None:
        engine = _engine(mode=surplus.MODE_TARGET)
        decision = engine.evaluate(START, _measure(grid_w=3000.0), target_active=False)
        self.assertFalse(decision.charging)

    def test_off_mode_never_charges(self) -> None:
        engine = _engine(mode=surplus.MODE_OFF)
        decision = engine.evaluate(START, _measure(grid_w=-10000.0))
        self.assertFalse(decision.charging)
        self.assertEqual(decision.state, surplus.STATE_DISABLED)


class SafetyTests(unittest.TestCase):
    def test_missing_measurements_stop_the_mode(self) -> None:
        engine = _engine()
        decision = engine.evaluate(START, _measure())
        self.assertFalse(decision.charging)
        self.assertEqual(decision.state, surplus.STATE_NO_DATA)

    def test_stale_measurements_stop_charging(self) -> None:
        engine = _engine(max_data_age=timedelta(minutes=5))
        engine.evaluate(START, _measure(grid_w=-3000.0, updated_at=START))
        decision = engine.evaluate(
            START + timedelta(minutes=10),
            _measure(grid_w=-3000.0, updated_at=START),
        )
        self.assertFalse(decision.charging)
        self.assertEqual(decision.state, surplus.STATE_NO_DATA)

    def test_history_is_dropped_when_data_goes_missing(self) -> None:
        """After a gap, control restarts from fresh samples, not stale ones."""
        engine = _engine(smoothing_samples=5)
        for _ in range(5):
            engine.evaluate(START, _measure(grid_w=-5000.0))
        engine.evaluate(START, _measure())
        decision = engine.evaluate(START, _measure(grid_w=-1000.0))
        self.assertFalse(decision.charging)

    def test_import_never_exceeds_the_configured_allowance(self) -> None:
        engine = _engine(mode=surplus.MODE_PV_GRID, max_import_w=1000.0, phases=1)
        decision = engine.evaluate(START, _measure(grid_w=0.0, charger_w=0.0))
        used_w = (decision.current_a or 0) * 230.0
        self.assertLessEqual(used_w, 1000.0 + 1e-6)


if __name__ == "__main__":
    unittest.main()
