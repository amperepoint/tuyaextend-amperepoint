from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "tuyaextend_amperepoint"
    ),
)

from planner_model import (  # noqa: E402
    PlannerConfigError,
    active_window,
    matches_expected,
    merged_blocks,
    next_event,
    next_window_start,
    normalize_windows,
    planner_transitions,
)


WARSAW = timezone(timedelta(hours=2))


class PlannerModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.windows = normalize_windows(
            [
                {
                    "id": "night",
                    "days": [0, 1, 2, 3, 4],
                    "start": "22:15",
                    "end": "06:45",
                    "current_a": 16,
                },
                {
                    "id": "weekend",
                    "days": [5, 6],
                    "start": "10:05",
                    "end": "12:35",
                    "current_a": 10,
                },
            ]
        )

    def test_cross_midnight_window_uses_previous_weekday(self) -> None:
        tuesday_morning = datetime(2026, 7, 14, 6, 30, tzinfo=WARSAW)
        active = active_window(self.windows, tuesday_morning)
        self.assertEqual(active["id"], "night")
        self.assertEqual(active["active_end"].strftime("%H:%M"), "06:45")

    def test_minute_precision_and_next_event(self) -> None:
        monday = datetime(2026, 7, 13, 22, 14, tzinfo=WARSAW)
        event = next_event(self.windows, monday)
        self.assertEqual(event["action"], "start")
        self.assertEqual(event["at"].strftime("%H:%M"), "22:15")

    def test_rejects_equal_boundaries_and_invalid_current(self) -> None:
        with self.assertRaises(PlannerConfigError):
            normalize_windows(
                [{"days": [0], "start": "10:00", "end": "10:00", "current_a": 16}]
            )
        with self.assertRaises(PlannerConfigError):
            normalize_windows(
                [{"days": [0], "start": "10:00", "end": "11:00", "current_a": 2}]
            )

    def test_command_confirmation_uses_numeric_tolerance(self) -> None:
        data = {"switch_enabled": True, "current_limit_a": 15.95}
        self.assertTrue(
            matches_expected(data, {"switch_enabled": True, "current_limit_a": 16})
        )
        self.assertFalse(matches_expected(data, {"switch_enabled": False}))


def _window(id_, days, start, end, current=16, priority=0):
    return {
        "id": id_,
        "days": days,
        "start": start,
        "end": end,
        "current_a": current,
        "priority": priority,
    }


def _at(day, clock):
    hour, minute = map(int, clock.split(":"))
    # 2026-07-16 is a Thursday (weekday 3).
    return datetime(2026, 7, 16 + day, hour, minute, tzinfo=WARSAW)


THURSDAY = [3]
FRIDAY = [4]
EVERY_DAY = list(range(7))


class PlannerOverlapTests(unittest.TestCase):
    def test_contained_interval_charges_without_interruption(self) -> None:
        windows = normalize_windows(
            [
                _window("outer", THURSDAY, "10:00", "12:00", 16),
                _window("inner", THURSDAY, "10:00", "11:00", 8),
            ]
        )
        for minute in range(0, 120):
            moment = _at(0, "10:00") + timedelta(minutes=minute)
            self.assertIsNotNone(active_window(windows, moment), moment)
        self.assertIsNone(active_window(windows, _at(0, "12:00")))
        events = [
            event
            for event in planner_transitions(windows, _at(0, "10:30"))
            if event["action"] == "stop"
        ]
        self.assertEqual(events[0]["at"], _at(0, "12:00"))

    def test_touching_intervals_merge_into_one_block(self) -> None:
        windows = normalize_windows(
            [
                _window("first", THURSDAY, "10:00", "11:00"),
                _window("second", THURSDAY, "11:00", "12:00"),
            ]
        )
        blocks = [
            block
            for block in merged_blocks(windows, _at(0, "09:00"), days_ahead=0)
            if block["start"].day == 16
        ]
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["start"], _at(0, "10:00"))
        self.assertEqual(blocks[0]["end"], _at(0, "12:00"))

    def test_duplicate_intervals_merge_into_one_block(self) -> None:
        windows = normalize_windows(
            [
                _window("a", THURSDAY, "10:00", "12:00"),
                _window("b", THURSDAY, "10:00", "12:00"),
            ]
        )
        blocks = [
            block
            for block in merged_blocks(windows, _at(0, "09:00"), days_ahead=0)
            if block["start"].day == 16
        ]
        self.assertEqual(len(blocks), 1)

    def test_partial_overlap_chain_merges(self) -> None:
        windows = normalize_windows(
            [
                _window("a", THURSDAY, "10:00", "11:30"),
                _window("b", THURSDAY, "11:00", "13:00"),
                _window("c", THURSDAY, "12:45", "14:00"),
            ]
        )
        blocks = [
            block
            for block in merged_blocks(windows, _at(0, "09:00"), days_ahead=0)
            if block["start"].day == 16
        ]
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["end"], _at(0, "14:00"))

    def test_chain_crossing_midnight_merges(self) -> None:
        windows = normalize_windows(
            [
                _window("night", THURSDAY, "22:00", "06:00"),
                _window("morning", FRIDAY, "05:00", "08:00"),
            ]
        )
        transitions = planner_transitions(windows, _at(0, "23:00"))
        self.assertEqual(transitions[0]["action"], "stop")
        self.assertEqual(transitions[0]["at"], _at(1, "08:00"))
        self.assertIsNotNone(active_window(windows, _at(1, "06:30")))

    def test_winner_is_deterministic_regardless_of_order(self) -> None:
        first = normalize_windows(
            [
                _window("low", THURSDAY, "10:00", "12:00", 8),
                _window("high", THURSDAY, "10:00", "11:00", 16),
            ]
        )
        second = normalize_windows(
            [
                _window("high", THURSDAY, "10:00", "11:00", 16),
                _window("low", THURSDAY, "10:00", "12:00", 8),
            ]
        )
        moment = _at(0, "10:30")
        self.assertEqual(active_window(first, moment)["id"], "high")
        self.assertEqual(active_window(second, moment)["id"], "high")
        self.assertEqual(active_window(first, _at(0, "11:30"))["id"], "low")

    def test_priority_beats_current_and_later_start_wins(self) -> None:
        priority = normalize_windows(
            [
                _window("prio", THURSDAY, "10:00", "12:00", 8, priority=1),
                _window("fast", THURSDAY, "10:00", "12:00", 16),
            ]
        )
        self.assertEqual(active_window(priority, _at(0, "10:30"))["id"], "prio")
        specific = normalize_windows(
            [
                _window("all-day", THURSDAY, "08:00", "20:00", 6),
                _window("peak", THURSDAY, "17:00", "19:00", 16),
            ]
        )
        self.assertEqual(active_window(specific, _at(0, "18:00"))["id"], "peak")

    def test_pause_target_skips_starts_inside_the_current_block(self) -> None:
        windows = normalize_windows(
            [
                _window("outer", EVERY_DAY, "10:00", "12:00"),
                _window("inner", EVERY_DAY, "10:30", "11:00"),
            ]
        )
        self.assertEqual(
            next_window_start(windows, _at(0, "10:15")), _at(1, "10:00")
        )


class PlannerTransitionTests(unittest.TestCase):
    def test_higher_priority_inner_interval_yields_current_transitions(self) -> None:
        windows = normalize_windows(
            [
                _window("outer", THURSDAY, "10:00", "12:00", 10),
                _window("inner", THURSDAY, "10:30", "11:00", 16, priority=1),
            ]
        )
        transitions = planner_transitions(windows, _at(0, "09:00"))
        expected = [
            ("start", _at(0, "10:00"), 10.0),
            ("set_current", _at(0, "10:30"), 16.0),
            ("set_current", _at(0, "11:00"), 10.0),
            ("stop", _at(0, "12:00"), None),
        ]
        actual = [
            (item["action"], item["at"], item.get("current_a"))
            for item in transitions[: len(expected)]
        ]
        self.assertEqual(actual, expected)

    def test_transitions_only_contain_future_actions(self) -> None:
        windows = normalize_windows(
            [
                _window("outer", THURSDAY, "10:00", "12:00", 10),
                _window("inner", THURSDAY, "10:30", "11:00", 16, priority=1),
            ]
        )
        transitions = planner_transitions(windows, _at(0, "10:45"))
        self.assertEqual(transitions[0]["action"], "set_current")
        self.assertEqual(transitions[0]["at"], _at(0, "11:00"))
        self.assertEqual(transitions[0]["current_a"], 10.0)

    def test_same_current_intervals_produce_no_set_current(self) -> None:
        windows = normalize_windows(
            [
                _window("first", THURSDAY, "10:00", "11:00", 16),
                _window("second", THURSDAY, "11:00", "12:00", 16),
            ]
        )
        transitions = planner_transitions(windows, _at(0, "09:00"))
        actions = [item["action"] for item in transitions[:2]]
        self.assertEqual(actions, ["start", "stop"])


if __name__ == "__main__":
    unittest.main()
