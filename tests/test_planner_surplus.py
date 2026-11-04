"""Who owns the charging decision when PV surplus and the weekly plan meet."""

from __future__ import annotations

import asyncio
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import load_integration_module  # noqa: E402

planner_module = load_integration_module("planner")
planner_model = load_integration_module("planner_model")
surplus = load_integration_module("surplus")

# 2026-07-23 is a Thursday (weekday 3).
NOW = datetime(2026, 7, 23, 11, 0, tzinfo=timezone.utc)


def _decision(state, charging=False, current_a=None, available_w=0.0):
    return surplus.SurplusDecision(charging, current_a, state, available_w)


class _Coordinator:
    def __init__(self, decision=None):
        self.data = {"source_online": True}
        self.surplus_decision = decision
        self.model_limits = types.SimpleNamespace(min_current_a=6.0, max_current_a=32.0)


def _planner(decision=None, *, enabled=False, windows=(), managed=False):
    instance = planner_module.AmperePointPlanner.__new__(
        planner_module.AmperePointPlanner
    )
    instance.coordinator = _Coordinator(decision)
    instance.config = {"enabled": enabled, "windows": list(windows)}
    instance.override = None
    instance.managed_charging = managed
    return instance


def _window(start, end, current=16.0):
    return {
        "id": "w1",
        "days": [0, 1, 2, 3, 4, 5, 6],
        "start": start,
        "end": end,
        "current_a": current,
        "priority": 0,
    }


def _desired(planner, now=NOW):
    return asyncio.run(planner._async_desired(now))


class SurplusOwnershipTests(unittest.TestCase):
    def test_surplus_drives_charging_when_no_weekly_plan(self) -> None:
        planner = _planner(
            _decision(surplus.STATE_CHARGING_PV, charging=True, current_a=10.0)
        )
        desired = _desired(planner)
        self.assertTrue(desired["charging"])
        self.assertEqual(desired["current_a"], 10.0)
        self.assertEqual(desired["state"], surplus.STATE_CHARGING_PV)

    def test_manual_override_beats_surplus(self) -> None:
        planner = _planner(
            _decision(surplus.STATE_WAITING, charging=False)
        )
        planner.override = {"mode": "charge", "current_a": 16, "until": None}
        desired = _desired(planner)
        self.assertTrue(desired["charging"])
        self.assertEqual(desired["state"], "override_charging")

    def test_pause_override_beats_surplus(self) -> None:
        planner = _planner(
            _decision(surplus.STATE_CHARGING_PV, charging=True, current_a=12.0)
        )
        planner.override = {"mode": "pause", "until": None}
        desired = _desired(planner)
        self.assertFalse(desired["charging"])
        self.assertEqual(desired["state"], "override_paused"),

    def test_disabled_surplus_leaves_the_weekly_plan_in_charge(self) -> None:
        planner = _planner(
            _decision(surplus.STATE_DISABLED),
            enabled=True,
            windows=[_window("10:00", "14:00", 16.0)],
        )
        desired = _desired(planner)
        self.assertTrue(desired["charging"])
        self.assertEqual(desired["state"], "scheduled_charging")
        self.assertEqual(desired["current_a"], 16.0)

    def test_weekly_window_caps_the_surplus_current(self) -> None:
        planner = _planner(
            _decision(surplus.STATE_CHARGING_PV, charging=True, current_a=32.0),
            enabled=True,
            windows=[_window("10:00", "14:00", 10.0)],
        )
        desired = _desired(planner)
        self.assertTrue(desired["charging"])
        self.assertEqual(desired["current_a"], 10.0)

    def test_surplus_waits_outside_the_permitted_window(self) -> None:
        planner = _planner(
            _decision(surplus.STATE_CHARGING_PV, charging=True, current_a=16.0),
            enabled=True,
            windows=[_window("22:00", "23:00")],
            managed=True,
        )
        desired = _desired(planner)
        self.assertFalse(desired["charging"])
        self.assertEqual(desired["state"], "waiting")

    def test_no_data_stops_a_session_the_planner_started(self) -> None:
        planner = _planner(_decision(surplus.STATE_NO_DATA), managed=True)
        desired = _desired(planner)
        self.assertFalse(desired["charging"])
        self.assertEqual(desired["state"], "surplus_no_data")

    def test_no_data_does_not_touch_a_charger_we_do_not_manage(self) -> None:
        planner = _planner(_decision(surplus.STATE_NO_DATA), managed=False)
        self.assertIsNone(_desired(planner))

    def test_waiting_for_surplus_is_reported_verbatim(self) -> None:
        planner = _planner(_decision(surplus.STATE_WAITING))
        desired = _desired(planner)
        self.assertFalse(desired["charging"])
        self.assertEqual(desired["state"], surplus.STATE_WAITING)

    def test_target_mode_state_reaches_the_planner(self) -> None:
        planner = _planner(
            _decision(surplus.STATE_TARGET_NEEDS_GRID, charging=True, current_a=6.0)
        )
        desired = _desired(planner)
        self.assertTrue(desired["charging"])
        self.assertEqual(desired["state"], surplus.STATE_TARGET_NEEDS_GRID)


if __name__ == "__main__":
    unittest.main()
