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


class ChargingEnergy:
    """Accumulate observed consumption; unknown intervals never become zeros."""

    FORMAT = 1
    MAX_POWER_GAP = 60.0  # seconds; no integration over outages/restarts

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
        self.total = total
        self.source = saved.get("source") if isinstance(saved.get("source"), str) else None
        self.method = saved.get("method")
        self.baseline = non_negative(saved.get("baseline"))
        self.timestamp = non_negative(saved.get("timestamp"))
        self._last_seen = non_negative(saved.get("last_seen", self.timestamp))
        self.started_at = non_negative(saved.get("started_at"))
        self.incomplete = bool(saved.get("incomplete", False))
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
                "incomplete": self.incomplete}

    def missing(self) -> None:
        self._interrupted = True
        self._power_previous = None
        self.quality = "unavailable"

    def update(self, sample: EnergySample, now: float, max_power_kw: float) -> float | None:
        if self._invalid_storage is not None:
            self.quality = "storage_error"
            return None
        if not math.isfinite(now) or (self._last_seen is not None and now <= self._last_seen):
            self.quality = "out_of_order"
            return self.total if self.started_at is not None else None
        self._last_seen = now
        value = non_negative(sample.value)
        if value is None:
            self.missing()
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
            return self.total
        if delta > max_power_kw * elapsed / 3600 + 2 * sample.resolution:
            # A stale pre-reset reading or unit change must not become kWh.
            self.incomplete = True
            self.quality = "implausible_sample"
            return None
        self.total += delta
        # Do not move the timestamp on identical polls: low-resolution counters
        # may report the same value repeatedly before their next increment.
        if delta > 0:
            self.baseline, self.timestamp = value, now
        self.quality = "gap_recovered" if self._interrupted and delta > 0 else "measured"
        self._interrupted = False
        return self.total
