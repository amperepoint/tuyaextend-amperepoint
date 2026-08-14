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

    async def async_set_charging(self, value: bool) -> None:
        self.charging_commands.append(value)

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


if __name__ == "__main__":
    unittest.main()
