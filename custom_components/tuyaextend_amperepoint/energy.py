"""One persisted, monotonic consumption meter, independent of charging sessions.

The first source reading is a baseline, not historical consumption. A changing
DP1 is deliberately called a counter, never assumed to be a lifetime meter.
Only one source contributes at a time. No charger commands or Recorder writes.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


def non_negative(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


@dataclass(frozen=True)
class EnergySample:
    source: str
    method: str  # device_counter, session_counter, power_estimate
    value: float | None
    resolution: float = 0.01  # kWh, for counter quantization/jitter


@dataclass(frozen=True)
class PowerSample:
    source: str
    value: float | None
    reported_at: float | None


class ChargingEnergy:
    """Accumulate observed consumption; unknown intervals never become zeros."""

    FORMAT = 1
    MAX_POWER_GAP = 60.0  # seconds; no integration over outages/restarts
    POWER_TOLERANCE = 0.10
    MIN_CORRECTION_KWH = 0.1
    COMPARISON_WINDOW = 3600.0

    def __init__(self, saved: Any = None) -> None:
        self.total = 0.0
        self.source: str | None = None
        self.method: str | None = None
        self.baseline: float | None = None
        self.timestamp: float | None = None
        self._last_seen: float | None = None
        self.started_at: float | None = None
        self.incomplete = False
        self.quality = "waiting_for_source"
        self._power_previous: float | None = None
        self._interrupted = False
        self._invalid_storage: dict[str, Any] | None = None
        self.power_total = 0.0
        self.power_incomplete = False
        self.corrections = 0
        self.excluded_energy = 0.0
        self.validation = "waiting_for_power"
        self._reference_previous: PowerSample | None = None
        self._reference_time: float | None = None
        self._reference_valid = False
        self._reference_energy = 0.0
        self._reference_counted = 0.0
        self._reference_start = 0.0
        self._restore(saved)

    def _restore(self, saved: Any) -> None:
        if saved is None:
            return
        if not isinstance(saved, dict):
            self._invalid_storage = {"unreadable_state": saved}
            self.quality = "storage_error"
            return
        total = non_negative(saved.get("total"))
        if saved.get("format") != self.FORMAT or total is None:
            # A downgrade/corrupt file must not silently reset a meter already
            # recorded by HA. Fail closed and preserve it for recovery.
            self._invalid_storage = saved
            self.quality = "storage_error"
            return
        if "power_total" in saved and non_negative(saved["power_total"]) is None:
            self._invalid_storage = saved
            self.quality = "storage_error"
            return
        self.total = total
        self.source = saved.get("source") if isinstance(saved.get("source"), str) else None
        self.method = saved.get("method")
        self.baseline = non_negative(saved.get("baseline"))
        self.timestamp = non_negative(saved.get("timestamp"))
        self._last_seen = non_negative(saved.get("last_seen", self.timestamp))
        self.started_at = non_negative(saved.get("started_at"))
        self.incomplete = bool(saved.get("incomplete", False))
        self.power_total = non_negative(saved.get("power_total")) or 0.0
        self.power_incomplete = True  # never bridge a restart with held power
        self.corrections = int(non_negative(saved.get("corrections")) or 0)
        self.excluded_energy = non_negative(saved.get("excluded_energy")) or 0.0
        # A restored counter can recover its delta. Power cannot tell what
        # happened while HA was stopped, so never restore the power sample.
        self._interrupted = True
        self.quality = "waiting_for_source"

    def dump(self) -> dict[str, Any]:
        if self._invalid_storage is not None:
            return self._invalid_storage
        return {"format": self.FORMAT, "total": self.total, "source": self.source,
                "method": self.method, "baseline": self.baseline,
                "timestamp": self.timestamp, "last_seen": self._last_seen,
                "started_at": self.started_at,
                "incomplete": self.incomplete, "power_total": self.power_total,
                "power_incomplete": self.power_incomplete,
                "corrections": self.corrections, "excluded_energy": self.excluded_energy}

    def missing(self) -> None:
        self._interrupted = True
        self._power_previous = None
        self._reference_valid = False
        self._reference_previous = None
        self.power_incomplete = True
        self.validation = "incomplete_power"
        self.quality = "unavailable"

    def _observe_power(self, power: PowerSample | None, now: float, maximum: float) -> bool:
        """Integrate only covered sample-and-hold intervals, including real zeros."""
        value = non_negative(power.value) if power else None
        stamp = non_negative(power.reported_at) if power else None
        valid = (value is not None and value <= maximum and stamp is not None
                 and 0 <= now - stamp <= self.MAX_POWER_GAP)
        previous = self._reference_previous
        elapsed = now - self._reference_time if self._reference_time is not None else None
        covered = (valid and previous is not None and elapsed is not None
                   and 0 < elapsed <= self.MAX_POWER_GAP
                   and power.source == previous.source
                   and stamp >= previous.reported_at
                   and now - previous.reported_at <= self.MAX_POWER_GAP)
        if covered:
            amount = previous.value * elapsed / 3600
            self.power_total += amount
            self._reference_energy += amount
        else:
            self._reference_valid = False
            if self._reference_time is not None:
                self.power_incomplete = True
        self._reference_previous = PowerSample(power.source, value, stamp) if valid else None
        self._reference_time = now
        self.validation = "active" if self._reference_valid else "incomplete_power"
        return valid

    def _reset_reference(self, valid: bool, now: float) -> None:
        self._reference_valid = valid
        self._reference_energy = self._reference_counted = 0.0
        self._reference_start = now
        self.validation = "active" if valid else "incomplete_power"

    def update(self, sample: EnergySample, now: float, max_power_kw: float,
               power: PowerSample | None = None) -> float | None:
        if self._invalid_storage is not None:
            self.quality = "storage_error"
            return None
        if not math.isfinite(now) or (self._last_seen is not None and now <= self._last_seen):
            self.quality = "out_of_order"
            return self.total if self.started_at is not None else None
        self._last_seen = now
        power_valid = self._observe_power(power, now, max_power_kw)
        value = non_negative(sample.value)
        if value is None:
            self._interrupted = True
            self._power_previous = None
            self._reference_valid = False
            self.validation = "missing_counter"
            self.quality = "unavailable"
            return None
        if sample.method == "power_estimate" and value > max_power_kw:
            self.missing()
            self.incomplete = True
            self.quality = "implausible_sample"
            return None
        if sample.source != self.source or sample.method != self.method or self.baseline is None or self.timestamp is None:
            if self.source is not None:
                self.incomplete = True  # skip ambiguous overlap at a source switch
            self.source, self.method = sample.source, sample.method
            self.baseline, self.timestamp = value, now
            self.started_at = self.started_at if self.started_at is not None else now
            self._power_previous = value if sample.method == "power_estimate" else None
            self._interrupted = False
            self.quality = "estimated" if sample.method == "power_estimate" else "baseline"
            self._reset_reference(power_valid, now)
            return self.total

        elapsed = now - self.timestamp
        if sample.method == "power_estimate":
            if self._power_previous is not None and elapsed <= self.MAX_POWER_GAP and not self._interrupted:
                # Left sum is appropriate for sample-and-hold EVSE power.
                self.total += self._power_previous * elapsed / 3600
                self.quality = "estimated"
            else:
                self.incomplete = True
                self.quality = "gap_not_integrated"
            self.baseline, self.timestamp = value, now
            self._power_previous = value
            self._interrupted = False
            return self.total

        delta = value - self.baseline
        tolerance = sample.resolution * 1.01
        if delta < 0:
            if value != 0 and abs(delta) <= tolerance:
                # Keep the high-water mark: 10 -> 9.99 -> 10 must not add .01.
                self.quality = "counter_jitter"
                return self.total
            # Reset/correction: a lower reading is NOT energy consumption.
            # Rebase without adding its value (might be a late/corrected sample).
            self.baseline, self.timestamp = value, now
            self.incomplete = self.incomplete or value != 0 or self._interrupted
            self.quality = "counter_reset" if value == 0 else "counter_rebased"
            self._interrupted = False
            self._reset_reference(power_valid, now)
            return self.total
        if delta > 0 and self._reference_valid:
            # Compare cumulative readings over the SAME covered interval, not
            # individual rounded/delayed DP increments. Allow 10%, two counter
            # ticks / 0.1 kWh, and a minute at the physical upper power bound.
            # Use the bound, not observed power: DP1 can arrive before DP9
            # when charging starts, while the cached power is still zero.
            allowance = (max(self.MIN_CORRECTION_KWH, 2 * sample.resolution)
                         + max_power_kw * self.MAX_POWER_GAP / 3600)
            limit = self._reference_energy * (1 + self.POWER_TOLERANCE) + allowance
            if self._reference_counted + delta > limit + 1e-9:
                replacement = min(delta, max(0.0, self._reference_energy - self._reference_counted))
                self.total += replacement
                self.excluded_energy += delta - replacement
                self.corrections += 1
                # Consume the faulty source increment now: it must never be
                # retried or "caught up" by later polls or after a restart.
                self.baseline, self.timestamp = value, now
                self.incomplete = True  # corrected consumption is an estimate
                self.quality = "power_corrected"
                self._interrupted = False
                self._reset_reference(power_valid, now)
                return self.total
        if delta > max_power_kw * elapsed / 3600 + 2 * sample.resolution:
            # A stale pre-reset reading or unit change must not become kWh.
            self.incomplete = True
            self.quality = "implausible_sample"
            return None
        self.total += delta
        self._reference_counted += delta
        # Do not move the timestamp on identical polls: low-resolution counters
        # may report the same value repeatedly before their next increment.
        if delta > 0:
            self.baseline, self.timestamp = value, now
            # Only re-anchor when the counter advances, so a legitimate late
            # report retains all the power accumulated while it was unchanged.
            if not self._reference_valid or now - self._reference_start >= self.COMPARISON_WINDOW:
                self._reset_reference(power_valid, now)
        self.quality = "gap_recovered" if self._interrupted and delta > 0 else "measured"
        self._interrupted = False
        return self.total
