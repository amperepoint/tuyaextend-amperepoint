"""Where PV surplus meets the rest of the integration.

The surplus engine was written before LAN entries, the canonical energy meter
and the planner's current-following existed. These pin the points where it
touches them: which entries may use it, what the planner sends, when a
reading counts as fresh and what the dashboard can read.
"""

from __future__ import annotations

import asyncio
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import load_integration_module  # noqa: E402

const = load_integration_module("const")
coordinator = load_integration_module("coordinator")
planner_module = load_integration_module("planner")
sensor = load_integration_module("sensor")
select = load_integration_module("select")
surplus = load_integration_module("surplus")

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
PV_ENTITY_KEYS = {"pv_mode", "pv_surplus", "session_pv_energy", "session_pv_share", "daily_pv_energy"}


class _LanSource(coordinator.NativeLocalSource):
    """A LAN source as far as isinstance is concerned, without a connection."""

    def __init__(self) -> None:
        pass

    def writable(self, code):
        return False


def _coordinator(native_source=None, options=None):
    instance = object.__new__(coordinator.AmperePointCoordinator)
    instance.config_entry = types.SimpleNamespace(
        entry_id="entry",
        title="Charger",
        data={const.CONF_MODEL: "q22_ota", const.CONF_PV_MODE: surplus.MODE_PV_ONLY},
        options=options or {},
    )
    instance.model = coordinator.get_model("q22_ota")
    instance.native_source = native_source
    instance.data = {}
    instance.planner = None
    return instance


def _entity_keys(coord):
    hass = types.SimpleNamespace(data={const.DOMAIN: {"entry": coord}})
    added = []
    asyncio.run(sensor.async_setup_entry(hass, coord.config_entry, added.extend))
    asyncio.run(select.async_setup_entry(hass, coord.config_entry, added.extend))
    return {entity.entity_description.key for entity in added}


class LanEntryTests(unittest.TestCase):
    """A LAN entry has no options step for PV sources, so no surplus at all."""

    def test_a_configured_mode_stays_off_on_a_lan_entry(self) -> None:
        cloud, lan = _coordinator(), _coordinator(_LanSource())
        self.assertTrue(cloud.supports_surplus)
        self.assertEqual(cloud.surplus_settings().mode, surplus.MODE_PV_ONLY)
        self.assertFalse(lan.supports_surplus)
        self.assertEqual(lan.surplus_settings().mode, surplus.MODE_OFF)

    def test_pv_entities_exist_only_where_pv_can_be_configured(self) -> None:
        self.assertLessEqual(PV_ENTITY_KEYS, _entity_keys(_coordinator()))
        self.assertFalse(PV_ENTITY_KEYS & _entity_keys(_coordinator(_LanSource())))


class PlannerCurrentTests(unittest.TestCase):
    """The engine ramps in fractions; chargers take whole amperes."""

    @staticmethod
    def _desired(current_a, windows=()):
        instance = planner_module.AmperePointPlanner.__new__(planner_module.AmperePointPlanner)
        instance.coordinator = types.SimpleNamespace(
            data={"source_online": True},
            surplus_decision=surplus.SurplusDecision(True, current_a, surplus.STATE_CHARGING_PV, 0.0),
            model_limits=types.SimpleNamespace(min_current_a=6.0, max_current_a=32.0),
        )
        instance.config = {"enabled": bool(windows), "windows": list(windows)}
        instance.override = None
        instance.managed_charging = False
        return asyncio.run(instance._async_desired(NOW))

    def test_a_fractional_request_is_rounded_down(self) -> None:
        # Rounding up would draw more than the surplus; a fraction would never
        # match the whole-ampere readback and be sent again on every refresh.
        for engine, sent in ((7.8, 7.0), (6.4, 6.0), (13.0, 13.0)):
            with self.subTest(engine=engine):
                self.assertEqual(self._desired(engine)["current_a"], sent)

    def test_rounding_never_goes_below_the_minimum(self) -> None:
        self.assertEqual(self._desired(5.5)["current_a"], 6.0)


class FreshnessTests(unittest.TestCase):
    def test_a_repeated_reading_is_still_fresh(self) -> None:
        # A clipped inverter or zero export repeats one value: last_updated
        # stops while last_reported keeps moving.
        coord = _coordinator(options={const.CONF_SOURCE_GRID_POWER: "sensor.grid"})
        state = types.SimpleNamespace(
            state="-3000",
            attributes={"unit_of_measurement": "W"},
            last_updated=NOW - timedelta(minutes=20),
            last_reported=NOW - timedelta(seconds=10),
        )
        coord.hass = types.SimpleNamespace(states=types.SimpleNamespace(get=lambda _entity_id: state))
        self.assertEqual(
            coord._entity_updated_at(const.CONF_SOURCE_GRID_POWER), NOW - timedelta(seconds=10)
        )

    def test_without_last_reported_the_change_time_is_used(self) -> None:
        coord = _coordinator(options={const.CONF_SOURCE_GRID_POWER: "sensor.grid"})
        state = types.SimpleNamespace(state="-3000", attributes={}, last_updated=NOW)
        coord.hass = types.SimpleNamespace(states=types.SimpleNamespace(get=lambda _entity_id: state))
        self.assertEqual(coord._entity_updated_at(const.CONF_SOURCE_GRID_POWER), NOW)


class DashboardSourceTests(unittest.TestCase):
    def test_the_surplus_sensor_carries_the_decision_and_the_flows(self) -> None:
        description = next(item for item in sensor.SENSORS if item.key == "pv_surplus")
        coord = types.SimpleNamespace(
            config_entry=types.SimpleNamespace(entry_id="entry"),
            last_update_success=True,
            data={
                "surplus_available_w": 2300,
                "surplus_state": surplus.STATE_CHARGING_PV,
                "surplus_mode": surplus.MODE_PV_ONLY,
                "pv_power_w": 5400.0,
            },
        )
        entity = sensor.AmperePointSensor(coord, description)
        self.assertEqual(entity.native_value, 2300)
        self.assertEqual(entity.extra_state_attributes["surplus_state"], surplus.STATE_CHARGING_PV)
        self.assertEqual(entity.extra_state_attributes["pv_power_w"], 5400.0)


if __name__ == "__main__":
    unittest.main()
