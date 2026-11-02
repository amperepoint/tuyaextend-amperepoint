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


class _Coordinator:
    def __init__(self) -> None:
        self.data = {
            "source_online": True,
            "work_mode": "charge_now",
            "current_limit_a": 16.0,
            "switch_enabled": True,
        }
        self.model_limits = types.SimpleNamespace(
            min_current_a=6.0,
            max_current_a=32.0,
        )
        self.charging_commands = []
        self.current_commands = []

    async def async_set_charging(self, value: bool) -> None:
        self.charging_commands.append(value)

    async def async_set_current_limit(self, value: float) -> None:
        self.current_commands.append(value)

    async def async_set_work_mode(self, value: str) -> None:
        self.data["work_mode"] = value

    async def async_request_refresh(self) -> None:
        return None


class _Store:
    def __init__(self) -> None:
        self.data = None

    async def async_save(self, data) -> None:
        self.data = data

    async def async_load(self):
        return self.data


class PlannerCommandStatusTests(unittest.TestCase):
    def _planner(self):
        planner = planner_module.AmperePointPlanner.__new__(
            planner_module.AmperePointPlanner
        )
        planner.coordinator = _Coordinator()
        planner.config = {"enabled": True, "windows": []}
        planner.override = None
        planner.pending = None
        planner.command_status = "idle"
        planner.last_confirmation = None
        planner.retry_after = None
        planner.managed_charging = False
        planner._state = "waiting"
        planner._listeners = set()
        planner._lock = asyncio.Lock()
        planner._store = _Store()
        return planner

    def test_failed_status_returns_to_idle_when_desired_state_is_settled(self) -> None:
        now = datetime.now(timezone.utc)
        planner = self._planner()
        planner.config = {"enabled": False, "windows": []}
        planner.override = {
            "mode": "charge",
            "until": (now + timedelta(hours=1)).isoformat(),
            "current_a": 16.0,
        }
        planner.command_status = "failed"
        planner.last_confirmation = {
            "action": "set_current",
            "failed_at": (now - timedelta(minutes=5)).isoformat(),
            "error": "confirmation timeout",
        }
        planner.retry_after = now - timedelta(seconds=1)
        planner.managed_charging = True
        planner._state = "failed"

        asyncio.run(planner.async_evaluate("retry_expired"))

        self.assertEqual(planner.command_status, "idle")
        self.assertIsNone(planner.retry_after)
        self.assertEqual(planner.state, "override_charging")
        self.assertEqual(planner.last_confirmation["error"], "confirmation timeout")

    def test_confirmed_disconnection_settles_failed_stop_without_retry(self) -> None:
        now = datetime.now(timezone.utc)
        planner = self._planner()
        planner.coordinator.data.update(
            {
                "vehicle_connection_known": True,
                "vehicle_connected": False,
            }
        )
        planner.command_status = "failed"
        planner.last_confirmation = {
            "action": "stop",
            "failed_at": now.isoformat(),
            "error": "confirmation timeout",
        }
        planner.retry_after = now + timedelta(minutes=4)
        planner.managed_charging = True

        asyncio.run(planner.async_evaluate("coordinator"))

        self.assertEqual(planner.coordinator.charging_commands, [])
        self.assertEqual(planner.command_status, "idle")
        self.assertIsNone(planner.retry_after)
        self.assertFalse(planner.managed_charging)
        self.assertEqual(planner.state, "waiting")
        self.assertEqual(
            planner.last_confirmation["reason"], "vehicle_disconnected"
        )

    def test_pending_stop_is_settled_as_soon_as_vehicle_disconnects(self) -> None:
        now = datetime.now(timezone.utc)
        planner = self._planner()
        planner.coordinator.data.update(
            {
                "vehicle_connection_known": True,
                "vehicle_connected": False,
            }
        )
        planner.pending = {
            "action": "stop",
            "expected": {"switch_enabled": False},
            "requested_at": now.isoformat(),
        }
        planner.command_status = "pending"

        asyncio.run(planner.async_evaluate("coordinator"))

        self.assertIsNone(planner.pending)
        self.assertEqual(planner.command_status, "idle")
        self.assertEqual(planner.coordinator.charging_commands, [])
        self.assertEqual(
            planner.last_confirmation["reason"], "vehicle_disconnected"
        )

    def test_unknown_connection_state_keeps_safety_stop_behavior(self) -> None:
        planner = self._planner()

        asyncio.run(planner.async_evaluate("minute"))

        self.assertEqual(planner.coordinator.charging_commands, [False])
        self.assertEqual(planner.pending["action"], "stop")
        self.assertEqual(planner.command_status, "pending")

    def test_reconnecting_outside_window_requests_stop(self) -> None:
        planner = self._planner()
        planner.coordinator.data.update(
            {
                "vehicle_connection_known": True,
                "vehicle_connected": False,
            }
        )

        asyncio.run(planner.async_evaluate("coordinator"))
        self.assertEqual(planner.coordinator.charging_commands, [])

        planner.coordinator.data["vehicle_connected"] = True
        asyncio.run(planner.async_evaluate("coordinator"))

        self.assertEqual(planner.coordinator.charging_commands, [False])
        self.assertEqual(planner.pending["action"], "stop")

    def test_restart_drops_stale_stop_and_does_not_reissue_it_unplugged(self) -> None:
        now = datetime.now(timezone.utc)
        planner = self._planner()
        planner.coordinator.data.update(
            {
                "vehicle_connection_known": True,
                "vehicle_connected": False,
            }
        )
        planner._store.data = {
            "config": {"enabled": True, "windows": []},
            "override": None,
            "managed_charging": True,
            "pending": {
                "action": "stop",
                "expected": {"switch_enabled": False},
                "requested_at": now.isoformat(),
            },
            "last_confirmation": None,
        }

        async def restore_and_evaluate() -> None:
            await planner.async_load()
            await planner.async_evaluate("startup")

        asyncio.run(restore_and_evaluate())

        self.assertIsNone(planner.pending)
        self.assertIsNone(planner.retry_after)
        self.assertFalse(planner.managed_charging)
        self.assertEqual(planner.command_status, "idle")
        self.assertEqual(planner.coordinator.charging_commands, [])


class PlannerExternalChangeTests(unittest.TestCase):
    """The planner applies a current once per episode and follows later changes.

    Reproduces a customer's Tuya log: a current set from the app or an
    automation came back about 10 s later because the planner kept sending its
    own value, and a start from the app slipped through after a stop.
    """

    def _planner(self):
        planner = PlannerCommandStatusTests._planner(self)
        planner.coordinator.data.update(
            {"vehicle_connection_known": True, "vehicle_connected": True}
        )
        return planner

    @staticmethod
    def _window_now(current_a: float = 16.0):
        now = datetime.now(timezone.utc)
        return planner_module.normalize_windows(
            [
                {
                    "id": "now",
                    "days": [0, 1, 2, 3, 4, 5, 6],
                    "start": (now - timedelta(minutes=2)).strftime("%H:%M"),
                    "end": (now + timedelta(minutes=30)).strftime("%H:%M"),
                    "current_a": current_a,
                }
            ],
            min_current=6.0,
            max_current=32.0,
        )

    @staticmethod
    def _requested_at(planner) -> datetime:
        return datetime.fromisoformat(planner.pending["requested_at"])

    def test_current_changed_outside_during_override_is_not_reverted(self) -> None:
        planner = self._planner()
        planner.config = {"enabled": True, "windows": []}
        asyncio.run(planner.async_set_override("charge", duration_minutes=60))
        self.assertEqual(planner.coordinator.current_commands, [])

        planner.coordinator.data["current_limit_a"] = 6.0
        asyncio.run(planner.async_evaluate("coordinator"))
        asyncio.run(planner.async_evaluate("minute"))

        self.assertEqual(planner.coordinator.current_commands, [])
        self.assertEqual(planner.override["current_a"], 6.0)
        self.assertEqual(planner.state, "override_charging")

    def test_override_applies_its_own_current_once_then_follows(self) -> None:
        planner = self._planner()
        planner.coordinator.data["current_limit_a"] = 10.0
        asyncio.run(planner.async_set_override("charge", current_a=16.0))
        self.assertEqual(planner.coordinator.current_commands, [16.0])

        planner.coordinator.data["current_limit_a"] = 16.0
        asyncio.run(planner.async_evaluate("coordinator"))
        self.assertIsNone(planner.pending)

        planner.coordinator.data["current_limit_a"] = 12.0
        asyncio.run(planner.async_evaluate("coordinator"))

        self.assertEqual(planner.coordinator.current_commands, [16.0])
        self.assertEqual(planner.override["current_a"], 12.0)

    def test_window_current_is_applied_at_start_and_then_followed(self) -> None:
        planner = self._planner()
        planner.config = {"enabled": True, "windows": self._window_now(16.0)}
        planner.coordinator.data["current_limit_a"] = 10.0

        asyncio.run(planner.async_evaluate("minute"))
        self.assertEqual(planner.coordinator.current_commands, [16.0])
        planner.coordinator.data["current_limit_a"] = 16.0
        asyncio.run(planner.async_evaluate("coordinator"))

        planner.coordinator.data["current_limit_a"] = 13.0
        asyncio.run(planner.async_evaluate("coordinator"))

        self.assertEqual(planner.coordinator.current_commands, [16.0])
        self.assertEqual(planner.state, "scheduled_charging")

    def test_returning_to_plan_applies_the_window_current_again(self) -> None:
        planner = self._planner()
        planner.config = {"enabled": True, "windows": self._window_now(16.0)}
        asyncio.run(planner.async_set_override("charge", current_a=16.0))
        planner.coordinator.data["current_limit_a"] = 8.0
        asyncio.run(planner.async_evaluate("coordinator"))
        self.assertEqual(planner.coordinator.current_commands, [])

        asyncio.run(planner.async_set_override("clear"))

        self.assertEqual(planner.coordinator.current_commands, [16.0])

    def test_followed_current_survives_a_restart(self) -> None:
        planner = self._planner()
        windows = self._window_now(16.0)
        asyncio.run(planner.async_set_config(True, windows))
        self.assertEqual(planner.coordinator.current_commands, [])
        planner.coordinator.data["current_limit_a"] = 9.0
        asyncio.run(planner.async_evaluate("coordinator"))

        restored = self._planner()
        restored._store = planner._store
        restored.coordinator.data["current_limit_a"] = 9.0
        asyncio.run(restored.async_load())
        asyncio.run(restored.async_evaluate("startup"))

        self.assertEqual(restored.coordinator.current_commands, [])
        self.assertEqual(restored.state, "scheduled_charging")

    def test_pending_current_overtaken_from_outside_is_followed(self) -> None:
        planner = self._planner()
        planner.coordinator.data["current_limit_a"] = 10.0
        asyncio.run(planner.async_set_override("charge", current_a=16.0))
        planner.coordinator.data["current_limit_a"] = 12.0
        planner._data_updated_at = self._requested_at(planner) + timedelta(seconds=10)

        asyncio.run(planner.async_evaluate("coordinator"))

        self.assertEqual(planner.coordinator.current_commands, [16.0])
        self.assertIsNone(planner.pending)
        self.assertEqual(planner.override["current_a"], 12.0)

    def test_current_that_did_not_land_is_sent_again(self) -> None:
        planner = self._planner()
        planner.coordinator.data["current_limit_a"] = 10.0
        asyncio.run(planner.async_set_override("charge", current_a=16.0))
        planner._data_updated_at = self._requested_at(planner) + timedelta(seconds=10)

        asyncio.run(planner.async_evaluate("coordinator"))

        self.assertEqual(planner.coordinator.current_commands, [16.0, 16.0])

    def test_charging_started_again_after_a_stop_is_stopped_again(self) -> None:
        planner = self._planner()
        planner.config = {"enabled": True, "windows": []}
        asyncio.run(planner.async_evaluate("coordinator"))
        self.assertEqual(planner.coordinator.charging_commands, [False])

        # The stop landed for a moment, then charging was switched on again
        # from the app before the next refresh, which shows it on.
        planner._data_updated_at = self._requested_at(planner) + timedelta(seconds=10)
        asyncio.run(planner.async_evaluate("coordinator"))

        self.assertEqual(planner.coordinator.charging_commands, [False, False])
        self.assertEqual(planner.pending["action"], "stop")

    def test_disabled_planner_does_not_repeat_its_cleanup_stop(self) -> None:
        planner = self._planner()
        planner.config = {"enabled": False, "windows": []}
        planner.managed_charging = True
        asyncio.run(planner.async_evaluate("config"))
        self.assertEqual(planner.coordinator.charging_commands, [False])

        planner._data_updated_at = self._requested_at(planner) + timedelta(seconds=10)
        asyncio.run(planner.async_evaluate("coordinator"))

        self.assertEqual(planner.coordinator.charging_commands, [False])

    def test_refresh_right_after_a_command_does_not_resend_it(self) -> None:
        planner = self._planner()
        planner.config = {"enabled": True, "windows": []}
        asyncio.run(planner.async_evaluate("coordinator"))

        planner._data_updated_at = self._requested_at(planner) + timedelta(seconds=1)
        asyncio.run(planner.async_evaluate("coordinator"))

        self.assertEqual(planner.coordinator.charging_commands, [False])
        self.assertEqual(planner.command_status, "pending")

    def test_resends_are_limited_and_then_fall_back_to_the_timeout(self) -> None:
        planner = self._planner()
        planner.config = {"enabled": True, "windows": []}
        asyncio.run(planner.async_evaluate("coordinator"))
        for _ in range(planner_module.MAX_COMMAND_RESENDS + 2):
            planner._data_updated_at = self._requested_at(planner) + timedelta(seconds=10)
            asyncio.run(planner.async_evaluate("coordinator"))

        self.assertEqual(
            len(planner.coordinator.charging_commands),
            1 + planner_module.MAX_COMMAND_RESENDS,
        )
        self.assertEqual(planner.command_status, "pending")


if __name__ == "__main__":
    unittest.main()
