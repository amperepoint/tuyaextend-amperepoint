from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any


WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


class PlannerConfigError(ValueError):
    """Raised when a planner configuration cannot be normalized."""


def parse_clock(value: Any) -> time:
    try:
        hour, minute = str(value).split(":", 1)
        return time(hour=int(hour), minute=int(minute))
    except (TypeError, ValueError) as err:
        raise PlannerConfigError(f"Invalid time: {value}") from err


def normalize_windows(
    value: Any, *, min_current: float = 6, max_current: float = 32
) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise PlannerConfigError("Planner windows must be a list")

    windows: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise PlannerConfigError(f"Window {index + 1} must be an object")
        start = parse_clock(raw.get("start"))
        end = parse_clock(raw.get("end"))
        if start == end:
            raise PlannerConfigError(
                f"Window {index + 1} cannot start and end together"
            )

        raw_days = raw.get("days")
        if not isinstance(raw_days, list) or not raw_days:
            raise PlannerConfigError(f"Window {index + 1} needs at least one weekday")
        try:
            days = sorted({int(day) for day in raw_days})
        except (TypeError, ValueError) as err:
            raise PlannerConfigError(
                f"Window {index + 1} has invalid weekdays"
            ) from err
        if any(day < 0 or day > 6 for day in days):
            raise PlannerConfigError(f"Window {index + 1} has invalid weekdays")

        try:
            current_a = float(raw.get("current_a", max_current))
        except (TypeError, ValueError) as err:
            raise PlannerConfigError(f"Window {index + 1} has invalid current") from err
        if current_a < min_current or current_a > max_current:
            raise PlannerConfigError(
                f"Window {index + 1} current must be {min_current:g}..{max_current:g} A"
            )

        windows.append(
            {
                "id": str(raw.get("id") or f"window-{index + 1}"),
                "days": days,
                "start": start.strftime("%H:%M"),
                "end": end.strftime("%H:%M"),
                "current_a": current_a,
                "priority": int(raw.get("priority", 0)),
            }
        )
    return windows


def _occurrence(
    window: dict[str, Any], start_day: datetime
) -> tuple[datetime, datetime]:
    start_clock = parse_clock(window["start"])
    end_clock = parse_clock(window["end"])
    start = start_day.replace(
        hour=start_clock.hour, minute=start_clock.minute, second=0, microsecond=0
    )
    end = start_day.replace(
        hour=end_clock.hour, minute=end_clock.minute, second=0, microsecond=0
    )
    if end <= start:
        end += timedelta(days=1)
    return start, end


def active_window(
    windows: list[dict[str, Any]], now: datetime
) -> dict[str, Any] | None:
    active: list[dict[str, Any]] = []
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    for day_offset in (-1, 0):
        start_day = midnight + timedelta(days=day_offset)
        for window in windows:
            if start_day.weekday() not in window["days"]:
                continue
            start, end = _occurrence(window, start_day)
            if start <= now < end:
                active.append({**window, "active_start": start, "active_end": end})
    if not active:
        return None
    # Among overlapping windows the highest priority wins, then the one that
    # started last (the more specific window), then the highest current so the
    # winner stays deterministic for windows saved in any order.
    return max(
        active,
        key=lambda item: (
            item.get("priority", 0),
            item["active_start"],
            item.get("current_a", 0),
        ),
    )


def _occurrences(
    windows: list[dict[str, Any]], now: datetime, *, days_ahead: int = 8
) -> list[tuple[datetime, datetime, dict[str, Any]]]:
    occurrences: list[tuple[datetime, datetime, dict[str, Any]]] = []
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    for day_offset in range(-1, days_ahead + 1):
        start_day = midnight + timedelta(days=day_offset)
        for window in windows:
            if start_day.weekday() not in window["days"]:
                continue
            start, end = _occurrence(window, start_day)
            occurrences.append((start, end, window))
    occurrences.sort(key=lambda item: (item[0], item[1]))
    return occurrences


def merged_blocks(
    windows: list[dict[str, Any]], now: datetime, *, days_ahead: int = 8
) -> list[dict[str, Any]]:
    """Merge overlapping and touching occurrences into continuous blocks.

    Overlapping intervals (for example 10:00-12:00 and 10:00-11:00) and
    touching intervals (10:00-11:00 and 11:00-12:00) must charge without
    interruption, so start/stop events are derived from these merged blocks
    instead of from the individual windows.
    """
    blocks: list[dict[str, Any]] = []
    for start, end, window in _occurrences(windows, now, days_ahead=days_ahead):
        if blocks and start <= blocks[-1]["end"]:
            if end > blocks[-1]["end"]:
                blocks[-1]["end"] = end
        else:
            blocks.append({"start": start, "end": end, "window_id": window["id"]})
    return blocks


def planner_events(
    windows: list[dict[str, Any]], now: datetime, *, days_ahead: int = 8
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for block in merged_blocks(windows, now, days_ahead=days_ahead):
        if block["start"] > now:
            events.append(
                {
                    "action": "start",
                    "at": block["start"],
                    "window_id": block["window_id"],
                }
            )
        if block["end"] > now:
            events.append(
                {
                    "action": "stop",
                    "at": block["end"],
                    "window_id": block["window_id"],
                }
            )
    return sorted(events, key=lambda event: event["at"])


def planner_transitions(
    windows: list[dict[str, Any]], now: datetime, *, days_ahead: int = 8
) -> list[dict[str, Any]]:
    """Derive the effective plan actions from all interval boundaries.

    Merged blocks describe start/stop continuity, but inside a block the
    winning interval can change the current limit (for example an outer
    10:00-12:00 at 10 A with a higher-priority 10:30-11:00 at 16 A). The
    transitions therefore include ``set_current`` actions whenever the
    winning interval changes the current, in addition to block ``start``
    and ``stop``.
    """
    boundaries = sorted(
        {
            boundary
            for start, end, _window in _occurrences(
                windows, now, days_ahead=days_ahead
            )
            for boundary in (start, end)
        }
    )
    transitions: list[dict[str, Any]] = []
    previous_current: float | None = None
    for boundary in boundaries:
        winner = active_window(windows, boundary)
        current = float(winner["current_a"]) if winner else None
        if current == previous_current:
            continue
        if previous_current is None:
            transitions.append(
                {"action": "start", "at": boundary, "current_a": current}
            )
        elif current is None:
            transitions.append({"action": "stop", "at": boundary})
        else:
            transitions.append(
                {"action": "set_current", "at": boundary, "current_a": current}
            )
        previous_current = current
    return [transition for transition in transitions if transition["at"] > now]


def next_transition(
    windows: list[dict[str, Any]], now: datetime
) -> dict[str, Any] | None:
    transitions = planner_transitions(windows, now)
    return transitions[0] if transitions else None


def next_event(windows: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    events = planner_events(windows, now)
    return events[0] if events else None


def next_window_start(windows: list[dict[str, Any]], now: datetime) -> datetime | None:
    return next(
        (
            event["at"]
            for event in planner_events(windows, now)
            if event["action"] == "start"
        ),
        None,
    )


def matches_expected(data: dict[str, Any], expected: dict[str, Any]) -> bool:
    for key, expected_value in expected.items():
        actual = data.get(key)
        if isinstance(expected_value, float | int) and not isinstance(
            expected_value, bool
        ):
            try:
                if abs(float(actual) - float(expected_value)) > 0.11:
                    return False
            except (TypeError, ValueError):
                return False
        elif actual != expected_value:
            return False
    return True
