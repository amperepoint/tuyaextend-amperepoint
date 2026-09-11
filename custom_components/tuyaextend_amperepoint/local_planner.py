"""HA-owned charging modes for verified PRIME LAN controls.

No device schedule (DP151) is written. HA persists the plan and sends only
verified permission/current commands; the device must remain in immediate mode.
"""
from __future__ import annotations

import math
from typing import Any

from .planner import AmperePointPlanner
from .planner_model import PlannerConfigError, next_window_start, normalize_windows

MODES = ["charge_now", "charge_energy", "charge_schedule"]


class AmperePointLocalPlanner(AmperePointPlanner):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._local_mode = "charge_now"
        self.target_energy_kwh = 10.0

    async def async_load(self):
        await super().async_load()
        stored = await self._store.async_load() or {}
        local = stored.get("local_control", {})
        mode = local.get("mode")
        self._local_mode = mode if mode in MODES else "charge_now"
        try:
            self.target_energy_kwh = self._energy_target(local.get("target_kwh", 10))
        except (TypeError, ValueError, PlannerConfigError):
            self.target_energy_kwh = 10.0

    def _storage_extra(self):
        return {"local_control": {"mode": self._local_mode, "target_kwh": self.target_energy_kwh}}

    @property
    def charging_mode(self):
        if self.override and self.override.get("mode") == "energy":
            return "charge_energy"
        if self.config.get("enabled"):
            return "charge_schedule"
        return self._local_mode

    def snapshot(self):
        return {**super().snapshot(), "control_source": "home_assistant_lan",
                "charging_mode": self.charging_mode, "target_energy_kwh": self.target_energy_kwh}

    async def async_set_mode(self, mode):
        async with self._lock:
            pass  # Finish any in-flight evaluation before replacing its intent.
        if mode not in MODES:
            raise PlannerConfigError("Unsupported local charging mode")
        self._local_mode = mode
        self.config["enabled"] = mode == "charge_schedule"
        # Selecting energy mode prepares the target; Start begins a new budget.
        self.override = {"mode": "pause", "until": None, "reason": "energy_ready"} if mode == "charge_energy" else None
        self.managed_charging = False
        self.pending = None
        self.retry_after = None
        self.command_status = "idle"
        await self._async_save()
        self._notify()
        await self.async_evaluate("local_mode")

    @staticmethod
    def _energy_target(value):
        target = float(value)
        if not math.isfinite(target) or not 0.1 <= target <= 200:
            raise PlannerConfigError("Energy target must be 0.1..200 kWh")
        return target

    async def async_set_target(self, value):
        async with self._lock:
            pass
        self.target_energy_kwh = self._energy_target(value)
        if self.override and self.override.get("mode") == "energy":
            # Editing the target must not reset energy already delivered.
            self.override["target_kwh"] = self.target_energy_kwh
        await self._async_save()
        self._notify()
        await self.async_evaluate("local_target")

    async def async_user_charging(self, enabled):
        async with self._lock:
            pass
        if not enabled:
            await self.async_set_override("pause")
        elif self.charging_mode == "charge_energy":
            await self.async_set_override("energy", energy_kwh=self.target_energy_kwh)
        elif self.config.get("enabled"):
            await self.async_set_override("charge", duration_minutes=60)
        else:
            self.override = None
            self.managed_charging = False
            self.pending = None
            self.retry_after = None
            await self._async_save()
            await self.coordinator.async_set_charging(True)
            self._notify()

    def _validated_override_current(self, value):
        if value is not None and (not math.isfinite(float(value)) or float(value) != int(float(value))):
            raise PlannerConfigError("Local current must be a whole number of amperes")
        current = super()._validated_override_current(value)
        maximum = self.coordinator.dp_definition("charge_cur_set").get("max", 16)
        if not math.isfinite(current) or current != int(current):
            raise PlannerConfigError("Local current must be a whole number of amperes")
        return min(current, float(maximum))

    async def async_set_config(self, enabled, windows):
        async with self._lock:
            pass
        windows = normalize_windows(windows, min_current=6,
                                    max_current=self.coordinator.dp_definition("charge_cur_set").get("max", 16))
        self._local_mode = "charge_schedule" if enabled else "charge_now"
        await super().async_set_config(enabled, windows)

    async def async_set_override(self, mode, **kwargs):
        async with self._lock:
            pass
        if mode == "energy":
            kwargs["energy_kwh"] = self._energy_target(kwargs.get("energy_kwh"))
            key, baseline = self._energy_meter()
            if baseline is None or not math.isfinite(baseline) or baseline < 0:
                raise PlannerConfigError("No energy meter is available")
            self.target_energy_kwh = kwargs["energy_kwh"]
            self._local_mode = "charge_energy"
        await super().async_set_override(mode, **kwargs)

    def _vehicle_is_confirmed_disconnected(self):
        # Native DP140 is permission: leaving it on outside a window would allow
        # a newly connected vehicle to start before HA's next evaluation.
        return False

    async def _async_desired(self, now):
        if self.override and self.override.get("mode") == "energy":
            budget = self.override
            reading = self.coordinator.data.get(budget.get("meter_key"))
            valid = type(reading) in (int, float) and math.isfinite(reading) and reading >= 0
            if not valid:
                self.override = {"mode": "pause", "until": None, "reason": "energy_meter_unavailable"}
                await self._async_save()
            else:
                last = float(budget.get("last_meter_kwh", budget["baseline_kwh"]))
                delivered = float(budget.get("delivered_kwh", 0))
                # A resetting session counter starts a new segment, not a new
                # budget. Both values are persisted for restart recovery.
                delivered += max(0.0, reading - last) if reading >= last else reading
                changed = last != reading or "last_meter_kwh" not in budget
                budget.update(last_meter_kwh=reading, delivered_kwh=round(delivered, 6))
                if delivered >= budget["target_kwh"]:
                    next_start = next_window_start(self.config["windows"], now) if self.config.get("enabled") else None
                    self.override = {"mode": "pause", "until": next_start.isoformat() if next_start else None,
                                     "reason": "energy_target_reached", "delivered_kwh": round(delivered, 3)}
                    changed = True
                else:
                    if changed:
                        await self._async_save()
                    return {"charging": True, "current_a": budget["current_a"], "state": "override_charging"}
                if changed:
                    await self._async_save()
        # A disabled weekly plan must not silently end a user's manual pause.
        if self.override and self.override.get("mode") == "pause" and not self.config.get("enabled") and self.override.get("until"):
            self.override["until"] = None
            await self._async_save()
        return await super()._async_desired(now)
