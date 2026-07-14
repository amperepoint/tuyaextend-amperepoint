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
    next_event,
    normalize_windows,
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


if __name__ == "__main__":
    unittest.main()
