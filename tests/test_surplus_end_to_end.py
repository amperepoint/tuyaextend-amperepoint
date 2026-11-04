"""A full coordinator refresh with PV sources wired up.

These exercise the path a user actually gets: configured entities ->
normalization -> engine decision -> the values the dashboard reads.
"""

from __future__ import annotations

import asyncio
import sys
import types
import unittest
import unittest.mock
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import load_integration_module  # noqa: E402

const = load_integration_module("const")
coordinator = load_integration_module("coordinator")
models = load_integration_module("models")
surplus = load_integration_module("surplus")

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)


class _States:
    def __init__(self, states):
        self._states = states

    def get(self, entity_id):
        return self._states.get(entity_id)

    def set(self, entity_id, value, unit=None, updated=NOW):
        self._states[entity_id] = types.SimpleNamespace(
            state=value,
            attributes={"unit_of_measurement": unit} if unit else {},
            last_updated=updated,
        )

    def touch(self, moment):
        for state in self._states.values():
            state.last_updated = moment


class _Store:
    async def async_save(self, *_args, **_kwargs) -> None:
        pass


def _make(config_extra=None, states=None):
    instance = object.__new__(coordinator.AmperePointCoordinator)
    config = {
        const.CONF_MODEL: "q22_ota",
        const.CONF_SOURCE_STATUS: "sensor.charger_status",
        const.CONF_SOURCE_POWER: "sensor.charger_power",
        const.CONF_PV_MODE: surplus.MODE_PV_ONLY,
        const.CONF_SOURCE_GRID_POWER: "sensor.grid",
        const.CONF_SESSION_ENERGY_MODE: const.SESSION_ENERGY_MODE_POWER_INTEGRATION,
    }
    config.update(config_extra or {})
    store = _States(
        {
            "sensor.charger_status": types.SimpleNamespace(
                state="charging", attributes={}, last_updated=NOW
            ),
            "sensor.charger_power": types.SimpleNamespace(
                state="0", attributes={"unit_of_measurement": "kW"}, last_updated=NOW
            ),
        }
    )
    for entity_id, (value, unit) in (states or {}).items():
        store.set(entity_id, value, unit)

    instance.config_entry = types.SimpleNamespace(data=config, options={})
    instance.hass = types.SimpleNamespace(states=store)
    instance.model = models.get_model(config[const.CONF_MODEL])
    instance.native_source = None
    instance._store = _Store()
    instance._refresh_lock = asyncio.Lock()
    instance._unloading = False
    instance._session_energy_kwh = 0.0
    instance._total_energy_baseline_kwh = None
    instance._last_total_energy_kwh = None
    instance._last_update = None
    instance._was_charging = False
    instance._was_connected = False
    instance._complete_candidate_since = None
    instance._seen_datapoints = {}
    instance.surplus_engine = coordinator.SurplusEngine()
    instance.surplus_decision = None
    instance._session_pv_energy_kwh = 0.0
    instance._daily_pv_energy_kwh = 0.0
    instance._daily_pv_day = None
    instance.data = {}
    return instance, store


class EndToEndTests(unittest.TestCase):
    def setUp(self) -> None:
        # The coordinator stamps its own "now"; drive it from the test so the
        # engine's start delay and elapsed-time maths are deterministic.
        self.clock = NOW
        patcher = unittest.mock.patch.object(
            coordinator.dt_util, "utcnow", lambda: self.clock
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _refresh(self, instance, advance=timedelta(0), store=None):
        self.clock += advance
        if store is not None:
            # A live sensor keeps reporting; without this the engine would
            # correctly call the measurements stale.
            store.touch(self.clock)
        return asyncio.run(instance._async_update_data())

    def _settled(self, instance, store=None):
        """Run past the start delay so a decision can turn into charging."""
        self._refresh(instance, store=store)
        return self._refresh(instance, timedelta(minutes=3), store=store)

    def test_export_produces_a_charging_decision(self) -> None:
        # The Q22 OTA is three phase, so 10 A needs 3 x 230 V x 10 A.
        instance, store = _make(states={"sensor.grid": ("-6900", "W")})
        data = self._settled(instance, store)
        self.assertEqual(data["surplus_mode"], surplus.MODE_PV_ONLY)
        self.assertEqual(data["surplus_state"], surplus.STATE_CHARGING_PV)
        self.assertTrue(data["surplus_charging"])
        self.assertEqual(data["surplus_current_a"], 10.0)
        self.assertEqual(data["surplus_available_w"], 6900)
        self.assertEqual(data["grid_power_w"], -6900.0)

    def test_export_below_the_three_phase_minimum_waits(self) -> None:
        """3450 W is 5 A per phase - under the charger's 6 A floor."""
        instance, store = _make(states={"sensor.grid": ("-3450", "W")})
        data = self._settled(instance, store)
        self.assertFalse(data["surplus_charging"])
        self.assertEqual(data["surplus_state"], surplus.STATE_WAITING)

    def test_import_keeps_the_charger_waiting(self) -> None:
        instance, _ = _make(states={"sensor.grid": ("1200", "W")})
        data = self._refresh(instance)
        self.assertFalse(data["surplus_charging"])
        self.assertEqual(data["surplus_state"], surplus.STATE_WAITING)

    def test_missing_grid_entity_reports_no_data(self) -> None:
        instance, _ = _make(config_extra={const.CONF_SOURCE_GRID_POWER: None})
        data = self._refresh(instance)
        self.assertEqual(data["surplus_state"], surplus.STATE_NO_DATA)
        self.assertFalse(data["surplus_charging"])

    def test_pv_mode_off_leaves_the_engine_disabled(self) -> None:
        instance, _ = _make(
            config_extra={const.CONF_PV_MODE: surplus.MODE_OFF},
            states={"sensor.grid": ("-5000", "W")},
        )
        data = self._refresh(instance)
        self.assertEqual(data["surplus_state"], surplus.STATE_DISABLED)
        self.assertFalse(data["surplus_charging"])

    def test_solar_energy_accumulates_only_while_charging_from_sun(self) -> None:
        instance, store = _make(states={"sensor.grid": ("-6900", "W")})
        self._settled(instance, store)

        # Ten minutes of 6.9 kW covered entirely by surplus.
        store.set("sensor.charger_power", "6.9", "kW")
        data = self._refresh(instance, timedelta(minutes=10), store=store)
        self.assertGreater(data["session_pv_energy_kwh"], 0.5)
        self.assertGreater(data["daily_pv_energy_kwh"], 0.5)
        self.assertIsNotNone(data["session_pv_share_pct"])

    def test_no_solar_energy_is_credited_while_importing(self) -> None:
        # Importing more than the charger draws: nothing is solar.
        instance, store = _make(states={"sensor.grid": ("8000", "W")})
        store.set("sensor.charger_power", "6.9", "kW")
        self._refresh(instance, store=store)
        data = self._refresh(instance, timedelta(minutes=10), store=store)
        self.assertEqual(data["session_pv_energy_kwh"], 0.0)
        self.assertEqual(data["surplus_state"], surplus.STATE_WAITING)

    def test_only_the_solar_part_of_a_mixed_session_is_credited(self) -> None:
        """Importing 2 kW while drawing 6.9 kW means 4.9 kW came from the sun."""
        instance, store = _make(states={"sensor.grid": ("-6900", "W")})
        self._settled(instance, store)

        store.set("sensor.grid", "2000", "W")
        store.set("sensor.charger_power", "6.9", "kW")
        data = self._refresh(instance, timedelta(minutes=10), store=store)
        # 4.9 kW for ten minutes, not the full 6.9 kW.
        self.assertAlmostEqual(data["session_pv_energy_kwh"], 4.9 / 6, places=2)
        self.assertLess(data["session_pv_energy_kwh"], 6.9 / 6)

    def test_daily_counter_resets_on_a_new_day(self) -> None:
        instance, _ = _make(states={"sensor.grid": ("-3450", "W")})
        instance._daily_pv_energy_kwh = 12.5
        instance._daily_pv_day = "2026-07-24"
        data = self._refresh(instance)
        self.assertEqual(data["daily_pv_energy_kwh"], 0.0)


if __name__ == "__main__":
    unittest.main()
