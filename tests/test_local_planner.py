"""HA-managed PRIME modes: same UX, no speculative firmware writes."""
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from support import load_integration_module

module = load_integration_module("local_planner")


class Coordinator:
    def __init__(self):
        self.data = dict(source_online=True, work_mode="charge_now", current_limit_a=16,
                         switch_enabled=True, local_session_energy_kwh=0)
        self.model_limits = SimpleNamespace(min_current_a=6, max_current_a=16)
        self.commands = []

    def dp_definition(self, code):
        return {"max": 16}

    async def async_set_charging(self, enabled):
        self.commands.append(("switch", enabled))
        self.data["switch_enabled"] = enabled

    async def async_set_current_limit(self, value):
        self.commands.append(("current", value))
        self.data["current_limit_a"] = value

    async def async_set_work_mode(self, mode):
        raise module.PlannerConfigError("Device immediate mode required")

    async def async_request_refresh(self):
        pass


def make():
    return module.AmperePointLocalPlanner(SimpleNamespace(), SimpleNamespace(entry_id="test"), Coordinator())


class LocalPlannerTests(unittest.IsolatedAsyncioTestCase):
    async def test_migration_pauses_automation_without_charger_commands_and_keeps_windows(self):
        planner = make()
        windows = [{"id": "saved"}]
        planner.config = {"enabled": True, "windows": windows}
        planner.override = {"mode": "charge"}
        planner.managed_charging = True
        planner.pending = {"action": "start"}
        await planner.async_prepare_onboarding()
        await planner.async_evaluate("startup")
        self.assertEqual(planner.coordinator.commands, [])
        self.assertFalse(planner.config["enabled"])
        self.assertEqual(planner.config["windows"], windows)
        self.assertIsNone(planner.override)
        self.assertIsNone(planner.pending)
        self.assertEqual(planner.charging_mode, "charge_now")

    async def test_default_does_not_change_charger(self):
        planner = make()
        await planner.async_evaluate("startup")
        self.assertEqual(planner.charging_mode, "charge_now")
        self.assertEqual(planner.coordinator.commands, [])

    async def test_energy_selection_waits_for_start_and_stops_at_budget(self):
        planner = make()
        await planner.async_set_mode("charge_energy")
        self.assertFalse(planner.coordinator.data["switch_enabled"])
        await planner.async_set_target(2)
        await planner.async_user_charging(True)
        self.assertTrue(planner.coordinator.data["switch_enabled"])
        planner.coordinator.data["local_session_energy_kwh"] = 1.9
        await planner.async_evaluate("reading")
        self.assertTrue(planner.coordinator.data["switch_enabled"])
        planner.coordinator.data["local_session_energy_kwh"] = 2
        await planner.async_evaluate("reading")
        self.assertFalse(planner.coordinator.data["switch_enabled"])
        self.assertEqual(planner.override["reason"], "energy_target_reached")

    async def test_energy_budget_survives_counter_reset_and_ha_restart(self):
        planner = make()
        planner.coordinator.data["local_session_energy_kwh"] = 10
        await planner.async_set_override("energy", energy_kwh=3)
        planner.coordinator.data["local_session_energy_kwh"] = 11
        await planner.async_evaluate("reading")
        planner.coordinator.data["local_session_energy_kwh"] = 0.5
        await planner.async_evaluate("counter_reset")
        self.assertEqual(planner.override["delivered_kwh"], 1.5)
        restored = make()
        restored._store = planner._store
        restored.coordinator.data["local_session_energy_kwh"] = 2
        await restored.async_load()
        await restored.async_evaluate("restart")
        self.assertEqual(restored.target_energy_kwh, 3)
        self.assertFalse(restored.coordinator.data["switch_enabled"])
        self.assertEqual(restored.override["reason"], "energy_target_reached")

    async def test_missing_energy_fails_closed(self):
        planner = make()
        await planner.async_set_override("energy", energy_kwh=2)
        planner.coordinator.data["local_session_energy_kwh"] = None
        planner.coordinator.data["session_energy_kwh"] = 0  # HA's fallback is not a fresh meter.
        await planner.async_evaluate("missing")
        self.assertFalse(planner.coordinator.data["switch_enabled"])
        self.assertEqual(planner.override["reason"], "energy_meter_unavailable")

    async def test_target_edit_preserves_progress(self):
        planner = make()
        await planner.async_set_override("energy", energy_kwh=10)
        planner.coordinator.data["local_session_energy_kwh"] = 3
        await planner.async_evaluate("reading")
        await planner.async_set_target(2)
        self.assertFalse(planner.coordinator.data["switch_enabled"])
        self.assertEqual(planner.override["delivered_kwh"], 3)

    async def test_weekly_plan_uses_only_current_and_switch(self):
        planner = make()
        now = datetime.now(timezone.utc)
        window = dict(id="w1", days=[now.weekday()], start=(now-timedelta(minutes=1)).strftime("%H:%M"),
                      end=(now+timedelta(minutes=5)).strftime("%H:%M"), current_a=8)
        planner.coordinator.data["switch_enabled"] = False
        await planner.async_set_config(True, [window])
        await planner.async_evaluate("readback")
        await planner.async_evaluate("readback")
        self.assertEqual(planner.charging_mode, "charge_schedule")
        self.assertEqual(planner.coordinator.commands, [("current", 8), ("switch", True)])
        restored = make()
        restored._store = planner._store
        restored.coordinator.data.update(current_limit_a=8, switch_enabled=True)
        await restored.async_load()
        await restored.async_evaluate("startup")
        self.assertEqual(restored.charging_mode, "charge_schedule")
        self.assertEqual(restored.coordinator.commands, [])
        self.assertIsNotNone(restored.snapshot()["effective_next_action"])
        await restored.async_set_config(False, [window])
        self.assertFalse(restored.coordinator.data["switch_enabled"])

    async def test_schedule_empty_waits_and_manual_override_can_start(self):
        planner = make()
        await planner.async_set_mode("charge_schedule")
        self.assertFalse(planner.coordinator.data["switch_enabled"])
        await planner.async_user_charging(True)
        self.assertTrue(planner.coordinator.data["switch_enabled"])
        self.assertEqual(planner.override["duration_minutes"], 60)
        await planner.async_user_charging(False)
        self.assertFalse(planner.coordinator.data["switch_enabled"])

    async def test_manual_pause_with_disabled_windows_has_no_expiry(self):
        planner = make()
        planner.override = dict(mode="pause", until=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat())
        await planner.async_evaluate("restart")
        self.assertFalse(planner.coordinator.data["switch_enabled"])
        self.assertIsNone(planner.override["until"])

    async def test_device_schedule_blocks_planner_start_without_writing_mode(self):
        planner = make()
        planner.coordinator.data.update(work_mode=None, switch_enabled=False)
        await planner.async_set_override("charge", duration_minutes=30)
        self.assertEqual(planner.command_status, "failed")
        self.assertEqual(planner.coordinator.commands, [])

    async def test_invalid_energy_and_current_do_not_write(self):
        planner = make()
        for value in (0, -1, 201, float("nan"), float("inf")):
            with self.assertRaises(module.PlannerConfigError):
                await planner.async_set_target(value)
        with self.assertRaises(module.PlannerConfigError):
            await planner.async_set_override("charge", current_a=6.5)
        self.assertEqual(planner.coordinator.commands, [])

    async def test_ha_mode_and_target_entities_use_planner_not_device_dp(self):
        select = load_integration_module("select")
        number = load_integration_module("number")
        planner = make()
        co = planner.coordinator
        co.config_entry = planner.entry
        co.planner = planner
        entity = select.AmperePointChargingModeSelect(co)
        target = number.AmperePointTargetEnergyNumber(co)
        await entity.async_select_option("charge_energy")
        await target.async_set_native_value(4.5)
        self.assertEqual(entity.current_option, "charge_energy")
        self.assertEqual(entity.options, module.MODES)
        self.assertEqual(target.native_value, 4.5)
        self.assertEqual(target.native_step, 0.1)
