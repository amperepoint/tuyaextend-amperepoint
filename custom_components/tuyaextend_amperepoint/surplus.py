"""Decide how much charging power the photovoltaic surplus supports.

The engine is deliberately free of Home Assistant imports: it takes normalized
measurements and returns a decision, so cloud cover, house-load spikes, stale
data, sign errors and single- versus three-phase installations can all be
exercised in tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

MODE_OFF = "off"
MODE_PV_ONLY = "pv_only"
MODE_PV_GRID = "pv_grid"
MODE_TARGET = "target"

SURPLUS_MODES = {
    MODE_OFF: "Off",
    MODE_PV_ONLY: "PV surplus only",
    MODE_PV_GRID: "PV + grid",
    MODE_TARGET: "Reach target",
}

# Decision states surfaced on the dashboard.
STATE_DISABLED = "disabled"
STATE_NO_DATA = "no_data"
STATE_WAITING = "waiting_for_surplus"
STATE_CHARGING_PV = "charging_from_pv"
STATE_CHARGING_MIXED = "charging_pv_grid"
STATE_TARGET_NEEDS_GRID = "target_needs_grid"

NOMINAL_VOLTAGE_V = 230.0


@dataclass(slots=True)
class SurplusMeasurements:
    """Normalized power readings, all in watts, all producer-positive.

    ``grid_w`` is positive while importing and negative while exporting, which
    is the convention the coordinator normalizes every source into.
    """

    pv_w: float | None = None
    grid_w: float | None = None
    house_w: float | None = None
    battery_w: float | None = None
    battery_soc: float | None = None
    charger_w: float | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class SurplusSettings:
    mode: str = MODE_OFF
    phases: int = 1
    min_current_a: float = 6.0
    max_current_a: float = 16.0
    voltage_v: float = NOMINAL_VOLTAGE_V
    # Power left for the rest of the house before charging may use surplus.
    reserve_w: float = 0.0
    # Grid import the installation may draw in PV + grid / target mode.
    max_import_w: float = 0.0
    # Battery is only used as a source above this state of charge.
    battery_min_soc: float = 100.0
    # Cloud filtering and switching behaviour.
    smoothing_samples: int = 5
    start_delay: timedelta = timedelta(minutes=2)
    stop_delay: timedelta = timedelta(minutes=3)
    min_run_time: timedelta = timedelta(minutes=5)
    max_data_age: timedelta = timedelta(minutes=5)
    current_step_a: float = 1.0


@dataclass(slots=True)
class SurplusDecision:
    charging: bool
    current_a: float | None
    state: str
    available_w: float
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "charging": self.charging,
            "current_a": self.current_a,
            "state": self.state,
            "available_w": round(self.available_w),
            "reason": self.reason,
        }


@dataclass(slots=True)
class SurplusEngine:
    """Translate measurements into a charging current, with hysteresis."""

    settings: SurplusSettings = field(default_factory=SurplusSettings)
    _samples: list[float] = field(default_factory=list, init=False)
    _above_since: datetime | None = field(default=None, init=False)
    _below_since: datetime | None = field(default=None, init=False)
    _charging_since: datetime | None = field(default=None, init=False)
    _current_a: float | None = field(default=None, init=False)

    # -- helpers ---------------------------------------------------------
    def _phase_power_w(self, current_a: float) -> float:
        return current_a * self.settings.phases * self.settings.voltage_v

    def _current_for(self, power_w: float) -> float:
        divisor = max(1.0, self.settings.phases * self.settings.voltage_v)
        return power_w / divisor

    def _min_power_w(self) -> float:
        return self._phase_power_w(self.settings.min_current_a)

    def reset(self) -> None:
        """Forget history so control restarts from fresh measurements."""
        self._samples.clear()
        self._above_since = None
        self._below_since = None
        self._charging_since = None
        self._current_a = None

    def _smooth(self, value: float) -> float:
        """Average recent samples so passing clouds do not toggle charging."""
        samples = max(1, int(self.settings.smoothing_samples))
        self._samples.append(value)
        if len(self._samples) > samples:
            del self._samples[: len(self._samples) - samples]
        return sum(self._samples) / len(self._samples)

    def _stale(self, now: datetime, measurements: SurplusMeasurements) -> bool:
        updated = measurements.updated_at
        if updated is None:
            return False
        return now - updated > self.settings.max_data_age

    def available_surplus_w(self, measurements: SurplusMeasurements) -> float | None:
        """Power that charging may use on top of what it already draws.

        Grid-based accounting is preferred because it stays correct whatever
        else the house is doing: exporting means unused production, importing
        means the surplus is already gone. The charger's own draw counts as
        available, otherwise raising the current would look like a deficit.
        """
        charger_w = measurements.charger_w or 0.0
        if measurements.grid_w is not None:
            available = -measurements.grid_w + charger_w
        elif measurements.pv_w is not None:
            available = measurements.pv_w - (measurements.house_w or 0.0) + charger_w
        else:
            return None

        if measurements.pv_w is not None:
            # Surplus can never exceed production. Without this bound a grid
            # meter that does not measure the charger turns the accounting into
            # a feedback loop: every ampere added shows up as more "surplus",
            # so the charger ramps to maximum and keeps charging from the grid
            # after dark. Found by driving the engine from the SUN2000
            # simulator, where the surplus climbed to 23 kW at midnight.
            available = min(available, measurements.pv_w)

        battery_w = measurements.battery_w
        if battery_w is not None:
            soc = measurements.battery_soc
            if battery_w > 0 and (soc is None or soc < self.settings.battery_min_soc):
                # The battery is charging and has priority over the car.
                available -= battery_w
        return available - self.settings.reserve_w

    # -- main entry point -------------------------------------------------
    def evaluate(
        self,
        now: datetime,
        measurements: SurplusMeasurements,
        *,
        target_active: bool = False,
    ) -> SurplusDecision:
        settings = self.settings
        if settings.mode == MODE_OFF:
            self.reset()
            return SurplusDecision(False, None, STATE_DISABLED, 0.0, "mode_off")

        if self._stale(now, measurements):
            self.reset()
            return SurplusDecision(False, None, STATE_NO_DATA, 0.0, "stale_measurements")

        raw = self.available_surplus_w(measurements)
        if raw is None:
            self.reset()
            return SurplusDecision(False, None, STATE_NO_DATA, 0.0, "no_measurements")

        available = self._smooth(raw)
        budget = available
        if settings.mode in {MODE_PV_GRID, MODE_TARGET}:
            budget += max(0.0, settings.max_import_w)

        min_power = self._min_power_w()
        # "Reach target" keeps charging even without surplus: the deadline wins
        # and the grid covers whatever the sun does not.
        if settings.mode == MODE_TARGET and target_active and budget < min_power:
            self._charging_since = self._charging_since or now
            self._current_a = settings.min_current_a
            return SurplusDecision(
                True,
                settings.min_current_a,
                STATE_TARGET_NEEDS_GRID,
                available,
                "target_overrides_surplus",
            )

        if budget >= min_power:
            self._below_since = None
            self._above_since = self._above_since or now
            if self._current_a is None and now - self._above_since < settings.start_delay:
                return SurplusDecision(
                    False,
                    None,
                    STATE_WAITING,
                    available,
                    "waiting_for_start_delay",
                )
            return self._start_or_adjust(now, budget, available)

        self._above_since = None
        self._below_since = self._below_since or now
        if self._current_a is not None:
            keep_running = (
                now - self._below_since < settings.stop_delay
                or (
                    self._charging_since is not None
                    and now - self._charging_since < settings.min_run_time
                )
            )
            if keep_running:
                return self._decision_for_current(
                    self._current_a, available, "holding_minimum_run_time"
                )
        self.reset()
        return SurplusDecision(False, None, STATE_WAITING, available, "surplus_too_low")

    def _start_or_adjust(
        self, now: datetime, budget_w: float, available_w: float
    ) -> SurplusDecision:
        settings = self.settings
        wanted = self._current_for(budget_w)
        wanted = max(settings.min_current_a, min(settings.max_current_a, wanted))

        if self._current_a is None:
            self._charging_since = now
            self._current_a = wanted
        else:
            # Ramp instead of jumping, so the charger and the car see a smooth
            # change rather than a burst of set-current commands.
            step = max(0.1, settings.current_step_a)
            delta = wanted - self._current_a
            if abs(delta) >= step:
                self._current_a += step if delta > 0 else -step
                self._current_a = max(
                    settings.min_current_a, min(settings.max_current_a, self._current_a)
                )

        return self._decision_for_current(self._current_a, available_w, "surplus")

    def _decision_for_current(
        self, current_a: float, available_w: float, reason: str
    ) -> SurplusDecision:
        used_w = self._phase_power_w(current_a)
        from_grid = used_w > available_w + 1.0
        state = STATE_CHARGING_MIXED if from_grid else STATE_CHARGING_PV
        return SurplusDecision(True, round(current_a, 1), state, available_w, reason)
