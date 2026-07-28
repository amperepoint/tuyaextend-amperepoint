from __future__ import annotations

import base64
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import load_integration_module  # noqa: E402

coordinator = load_integration_module("coordinator")

HIDDEN = {"voltage": None, "current": None, "power": None}


def _phase(voltage, current, power):
    return {"voltage": voltage, "current": current, "power": power}


class ModelPhaseLimitTests(unittest.TestCase):
    """Phases the hardware does not have are dropped whatever they report."""

    def test_single_phase_charger_drops_l2_and_l3(self) -> None:
        # The Q37 is 3.7 kW single-phase but answers on DP7/DP8 like the
        # rest of the series, sometimes with a residual reading.
        phases = [
            _phase(220.0, 7.3, 1.54),
            _phase(0.0, 0.0, 0.0),
            _phase(228.0, 3.0, 0.68),
        ]
        self.assertEqual(
            coordinator._filter_loaded_phases(phases, 1),
            [_phase(220.0, 7.3, 1.54), HIDDEN, HIDDEN],
        )

    def test_three_phase_charger_keeps_loaded_phases(self) -> None:
        phases = [
            _phase(230.0, 16.0, 3.68),
            _phase(229.0, 15.8, 3.62),
            _phase(228.0, 15.9, 3.63),
        ]
        self.assertEqual(coordinator._filter_loaded_phases(phases, 3), phases)


class FilterLoadedPhasesTests(unittest.TestCase):
    def test_idle_charger_hides_all_phases(self) -> None:
        phases = [
            _phase(225.0, 0.0, 0.0),
            _phase(219.0, 0.0, 0.0),
            _phase(218.0, 0.0, 0.0),
        ]
        self.assertEqual(
            coordinator._filter_loaded_phases(phases), [HIDDEN, HIDDEN, HIDDEN]
        )

    def test_single_phase_charging_with_phantom_readings(self) -> None:
        phases = [
            _phase(230.0, 16.0, 3.68),
            _phase(228.0, 0.4, 0.09),
            _phase(229.0, 0.2, 0.05),
        ]
        self.assertEqual(
            coordinator._filter_loaded_phases(phases),
            [_phase(230.0, 16.0, 3.68), HIDDEN, HIDDEN],
        )

    def test_balanced_three_phase_load_is_fully_visible(self) -> None:
        phases = [
            _phase(230.0, 16.0, 3.68),
            _phase(229.0, 15.8, 3.62),
            _phase(231.0, 15.9, 3.67),
        ]
        self.assertEqual(coordinator._filter_loaded_phases(phases), phases)

    def test_real_unbalanced_load_is_not_hidden(self) -> None:
        # 4 A is meaningful load and must stay visible next to a 16 A phase.
        phases = [
            _phase(230.0, 16.0, 3.68),
            _phase(229.0, 4.0, 0.92),
            _phase(231.0, 4.0, 0.92),
        ]
        self.assertEqual(coordinator._filter_loaded_phases(phases), phases)

    def test_power_only_source(self) -> None:
        phases = [
            _phase(None, None, 1.5),
            _phase(None, None, 0.05),
            _phase(None, None, None),
        ]
        self.assertEqual(
            coordinator._filter_loaded_phases(phases),
            [_phase(None, None, 1.5), HIDDEN, HIDDEN],
        )

    def test_zero_current_with_valid_power_is_visible(self) -> None:
        # A source reporting current 0 must not suppress a valid power reading.
        phases = [
            _phase(230.0, 0.0, 0.92),
            _phase(None, 0.0, 0.0),
            _phase(None, None, None),
        ]
        self.assertEqual(
            coordinator._filter_loaded_phases(phases),
            [_phase(230.0, 0.0, 0.92), HIDDEN, HIDDEN],
        )

    def test_no_data_stays_hidden(self) -> None:
        self.assertEqual(
            coordinator._filter_loaded_phases([HIDDEN, HIDDEN, HIDDEN]),
            [HIDDEN, HIDDEN, HIDDEN],
        )


class DecodePhasePayloadTests(unittest.TestCase):
    def test_valid_payload_is_decoded(self) -> None:
        raw = bytes(
            [
                *(2312).to_bytes(2, "big"),  # 231.2 V
                *(15700).to_bytes(3, "big"),  # 15.7 A
                *(3610).to_bytes(2, "big"),  # 3.61 kW
            ]
        )
        decoded = coordinator._decode_phase_payload(base64.b64encode(raw).decode())
        self.assertEqual(
            decoded, {"voltage": 231.2, "current": 15.7, "power": 3.61}
        )

    def test_wrong_length_returns_none(self) -> None:
        payload = base64.b64encode(bytes(5)).decode()
        self.assertIsNone(coordinator._decode_phase_payload(payload))

    def test_invalid_base64_returns_none(self) -> None:
        self.assertIsNone(coordinator._decode_phase_payload("not base64!"))


if __name__ == "__main__":
    unittest.main()
