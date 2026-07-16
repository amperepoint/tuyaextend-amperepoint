from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import AmperePointCoordinator
from .planner_model import (
    PlannerConfigError,
    active_window,
    matches_expected,
    next_transition,
    next_window_start,
    normalize_windows,
)


PLANNER_STORAGE_VERSION = 1
COMMAND_TIMEOUT = timedelta(seconds=45)
COMMAND_RETRY_DELAY = timedelta(minutes=5)


class AmperePointPlanner:
    """Persistent minute-accurate planner above the charger command adapter."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: AmperePointCoordinator,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self.config: dict[str, Any] = {"enabled": False, "windows": []}
        self.override: dict[str, Any] | None = None
        self.pending: dict[str, Any] | None = None
        self.command_status = "idle"
        self.last_confirmation: dict[str, Any] | None = None
        self.retry_after: datetime | None = None
        self.managed_charging = False
        self._state = "disabled"
        self._listeners: set[Callable[[], None]] = set()
        self._unsub_minute: Callable[[], None] | None = None
        self._unsub_coordinator: Callable[[], None] | None = None
        self._lock = asyncio.Lock()
        self._store = Store[dict[str, Any]](
            hass,
            PLANNER_STORAGE_VERSION,
            f"{DOMAIN}.{entry.entry_id}.planner",
        )

    async def async_load(self) -> None:
        stored = await self._store.async_load()
        if not isinstance(stored, dict):
            return
        try:
            windows = normalize_windows(
                stored.get("config", {}).get("windows", []),
                min_current=self.coordinator.model_limits.min_current_a,
                max_current=self.coordinator.model_limits.max_current_a,
            )
        except PlannerConfigError:
            windows = []
        self.config = {
            "enabled": bool(stored.get("config", {}).get("enabled", False)),
            "windows": windows,
        }
        self.override = stored.get("override")
        self.managed_charging = bool(stored.get("managed_charging", False))
        stored_pending = stored.get("pending")
        self.last_confirmation = stored.get("last_confirmation")
        if isinstance(stored_pending, dict) and matches_expected(
            self.coordinator.data, stored_pending.get("expected", {})
        ):
            self.last_confirmation = {
                "action": stored_pending.get("action"),
                "confirmed_at": dt_util.now().isoformat(),
                "restored_after_restart": True,
            }
            self.command_status = "confirmed"
        else:
            # A command interrupted by restart is evaluated again from the restored
            # desired plan instead of blocking execution on an expired request.
            self.command_status = "idle"
        self.pending = None
        self.retry_after = None

    async def async_start(self) -> None:
        self._unsub_minute = async_track_time_change(
            self.hass,
            self._handle_minute,
            second=0,
        )
        self._unsub_coordinator = self.coordinator.async_add_listener(
            self._handle_coordinator_update
        )
        await self.async_evaluate("startup")

    async def async_stop(self) -> None:
        if self._unsub_minute:
            self._unsub_minute()
            self._unsub_minute = None
        if self._unsub_coordinator:
            self._unsub_coordinator()
            self._unsub_coordinator = None
        await self._async_save()

    @callback
    def _handle_minute(self, _now: datetime) -> None:
        self.hass.async_create_task(self.async_evaluate("minute"))

    @callback
    def _handle_coordinator_update(self) -> None:
        self.hass.async_create_task(self.async_evaluate("coordinator"))

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.add(listener)

        @callback
        def remove_listener() -> None:
            self._listeners.discard(listener)

        return remove_listener

    @callback
    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()

    async def async_set_config(self, enabled: bool, windows: Any) -> None:
        normalized = normalize_windows(
            windows,
            min_current=self.coordinator.model_limits.min_current_a,
            max_current=self.coordinator.model_limits.max_current_a,
        )
        self.config = {"enabled": bool(enabled), "windows": normalized}
        self.pending = None
        if self.command_status == "pending":
            self.command_status = "idle"
        self.retry_after = None
        await self._async_save()
        self._notify()
        await self.async_evaluate("config")

    async def async_set_override(
        self,
        mode: str,
        *,
        duration_minutes: int | None = None,
        energy_kwh: float | None = None,
        current_a: float | None = None,
    ) -> None:
        now = dt_util.now()
        if mode == "clear":
            self.override = None
        elif mode == "charge":
            duration = max(1, min(int(duration_minutes or 60), 24 * 60))
            self.override = {
                "mode": "charge",
                "until": (now + timedelta(minutes=duration)).isoformat(),
                "duration_minutes": duration,
                "current_a": self._validated_override_current(current_a),
            }
        elif mode == "energy":
            target = float(energy_kwh or 0)
            if target <= 0 or target > 200:
                raise PlannerConfigError("Override energy must be 0..200 kWh")
            meter_key, baseline = self._energy_meter()
            if baseline is None:
                raise PlannerConfigError("No reliable energy meter is available")
            self.override = {
                "mode": "energy",
                "target_kwh": target,
                "meter_key": meter_key,
                "baseline_kwh": baseline,
                "current_a": self._validated_override_current(current_a),
            }
        elif mode == "pause":
            next_start = next_window_start(self.config["windows"], now)
            self.override = {
                "mode": "pause",
                "until": next_start.isoformat() if next_start else None,
            }
        else:
            raise PlannerConfigError(f"Unsupported override: {mode}")

        self.pending = None
        if self.command_status == "pending":
            self.command_status = "idle"
        self.retry_after = None
        await self._async_save()
        self._notify()
        await self.async_evaluate("override")

    def _validated_override_current(self, value: float | None) -> float:
        current = float(value or self.coordinator.data.get("current_limit_a") or 16)
        return max(
            float(self.coordinator.model_limits.min_current_a),
            min(float(self.coordinator.model_limits.max_current_a), current),
        )

    def _energy_meter(self) -> tuple[str, float | None]:
        for key in ("total_energy_kwh", "session_energy_kwh"):
            value = self.coordinator.data.get(key)
            if value is not None:
                return key, float(value)
        return "", None

    async def async_evaluate(self, reason: str) -> None:
        async with self._lock:
            now = dt_util.now()
            if await self._async_confirm_pending(now):
                return

            desired = await self._async_desired(now)
            if desired is None:
                self._state = "disabled"
                self._notify()
                return

            if not self.coordinator.data.get("source_online", True):
                self._state = "source_unavailable"
                self.command_status = "failed"
                self._notify()
                return

            if self.retry_after and now < self.retry_after:
                self._state = "failed"
                self._notify()
                return
            self.retry_after = None

            self._state = desired["state"]
            if desired["charging"]:
                if self.coordinator.data.get("work_mode") != "charge_now":
                    await self._async_send(
                        "set_mode",
                        {"work_mode": "charge_now"},
                        self.coordinator.async_set_work_mode,
                        "charge_now",
                    )
                    return
                current_a = float(desired["current_a"])
                actual_current = self.coordinator.data.get("current_limit_a")
                if (
                    actual_current is None
                    or abs(float(actual_current) - current_a) > 0.11
                ):
                    await self._async_send(
                        "set_current",
                        {"current_limit_a": current_a},
                        self.coordinator.async_set_current_limit,
                        current_a,
                    )
                    return
                if self.coordinator.data.get("switch_enabled") is not True:
                    await self._async_send(
                        "start",
                        {"switch_enabled": True},
                        self.coordinator.async_set_charging,
                        True,
                    )
                    return
            elif self.coordinator.data.get("switch_enabled") is True:
                await self._async_send(
                    "stop",
                    {"switch_enabled": False},
                    self.coordinator.async_set_charging,
                    False,
                )
                return

            if not desired["charging"] and self.managed_charging:
                self.managed_charging = False
                await self._async_save()

            # The desired state is satisfied and nothing is in flight; the
            # command channel returns to idle instead of showing the last
            # confirmation forever. last_confirmation keeps the history for
            # the detail line.
            if self.command_status != "failed":
                self.command_status = "idle"
            self._notify()

    async def _async_confirm_pending(self, now: datetime) -> bool:
        if not self.pending:
            return False
        if matches_expected(self.coordinator.data, self.pending.get("expected", {})):
            self.last_confirmation = {
                "action": self.pending.get("action"),
                "confirmed_at": now.isoformat(),
            }
            self.pending = None
            self.command_status = "confirmed"
            await self._async_save()
            self._notify()
            return False

        requested_at = _as_datetime(self.pending.get("requested_at")) or now
        if now - requested_at >= COMMAND_TIMEOUT:
            self.command_status = "failed"
            self.pending = None
            self.retry_after = now + COMMAND_RETRY_DELAY
            self._state = "failed"
            await self._async_save()
            self._notify()
        return True

    async def _async_desired(self, now: datetime) -> dict[str, Any] | None:
        if self.override:
            mode = self.override.get("mode")
            until = _as_datetime(self.override.get("until"))
            if mode == "charge" and until and now >= until:
                self.override = None
            elif mode == "pause" and until and now >= until:
                self.override = None
            elif mode == "energy":
                meter_key = str(self.override.get("meter_key", ""))
                current = self.coordinator.data.get(meter_key)
                baseline = float(self.override.get("baseline_kwh", 0))
                delivered = max(0.0, float(current or baseline) - baseline)
                self.override["delivered_kwh"] = round(delivered, 3)
                if delivered >= float(self.override.get("target_kwh", 0)):
                    next_start = next_window_start(self.config["windows"], now)
                    self.override = {
                        "mode": "pause",
                        "until": next_start.isoformat() if next_start else None,
                        "reason": "energy_target_reached",
                    }
            if self.override:
                mode = self.override.get("mode")
                if mode in {"charge", "energy"}:
                    return {
                        "charging": True,
                        "current_a": self.override.get("current_a", 16),
                        "state": "override_charging",
                    }
                if mode == "pause":
                    return {"charging": False, "state": "override_paused"}

        if not self.config.get("enabled"):
            if self.managed_charging:
                return {"charging": False, "state": "override_paused"}
            return None
        active = active_window(self.config["windows"], now)
        if active:
            return {
                "charging": True,
                "current_a": active["current_a"],
                "state": "scheduled_charging",
            }
        return {"charging": False, "state": "waiting"}

    async def _async_send(
        self,
        action: str,
        expected: dict[str, Any],
        command: Callable[..., Any],
        value: Any,
    ) -> None:
        now = dt_util.now()
        self.pending = {
            "action": action,
            "expected": expected,
            "requested_at": now.isoformat(),
        }
        if action == "start":
            self.managed_charging = True
        self.command_status = "pending"
        self._state = "pending"
        await self._async_save()
        self._notify()
        try:
            await command(value)
            await self.coordinator.async_request_refresh()
        except Exception as err:  # Home Assistant surfaces the original command error.
            self.pending = None
            self.command_status = "failed"
            self.retry_after = now + COMMAND_RETRY_DELAY
            self._state = "failed"
            self.last_confirmation = {
                "action": action,
                "failed_at": now.isoformat(),
                "error": str(err),
            }
            await self._async_save()
            self._notify()

    @property
    def state(self) -> str:
        return self._state

    def snapshot(self) -> dict[str, Any]:
        now = dt_util.now()
        active = active_window(self.config["windows"], now)
        upcoming = next_transition(self.config["windows"], now)
        return {
            "config_entry_id": self.entry.entry_id,
            "enabled": self.config.get("enabled", False),
            "windows": self.config.get("windows", []),
            "active_window": _serialize_window(active),
            "next_action": _serialize_event(upcoming),
            "effective_next_action": self._effective_next_action(upcoming),
            "override": self.override,
            "command_status": self.command_status,
            "pending": self.pending,
            "last_confirmation": self.last_confirmation,
            "retry_after": self.retry_after.isoformat() if self.retry_after else None,
            "managed_charging": self.managed_charging,
        }

    def _effective_next_action(
        self, upcoming: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        if self.override:
            mode = self.override.get("mode")
            if mode == "charge":
                return {
                    "source": "override",
                    "action": "stop",
                    "at": self.override.get("until"),
                }
            if mode == "energy":
                return {
                    "source": "override",
                    "action": "energy_target",
                    "target_kwh": self.override.get("target_kwh"),
                    "delivered_kwh": self.override.get("delivered_kwh", 0),
                }
            if mode == "pause":
                return {
                    "source": "override",
                    "action": "resume_plan",
                    "at": self.override.get("until"),
                }
        if not upcoming:
            return None
        return {
            **_serialize_event(upcoming),
            "source": "weekly_plan",
        }

    async def _async_save(self) -> None:
        await self._store.async_save(
            {
                "config": self.config,
                "override": self.override,
                "pending": self.pending,
                "command_status": self.command_status,
                "last_confirmation": self.last_confirmation,
                "retry_after": self.retry_after.isoformat()
                if self.retry_after
                else None,
                "managed_charging": self.managed_charging,
            }
        )


def _serialize_window(window: dict[str, Any] | None) -> dict[str, Any] | None:
    if not window:
        return None
    return {
        key: value.isoformat() if isinstance(value, datetime) else value
        for key, value in window.items()
    }


def _serialize_event(event: dict[str, Any] | None) -> dict[str, Any] | None:
    if not event:
        return None
    return {
        **event,
        "at": event["at"].isoformat(),
    }


def _as_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
