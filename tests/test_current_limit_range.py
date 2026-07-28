"""The charging-current slider must respect the limits of the real charger.

One tuya-local profile covers the whole Q Series, and the chargers give it
nothing to tell the generations apart: a 32 A Q22 answers with the same eight
datapoints as a 16 A Q37 and reports the same Tuya product id. The profile
therefore declares the union of the series, 6-32 A, and the detected model is
what narrows the slider back down.
"""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import load_integration_module  # noqa: E402

number = load_integration_module("number")
models = load_integration_module("models")

PROFILE_RANGE = {"min": 6, "max": 32}


class _States:
    def __init__(self, entity_id, attributes) -> None:
        self._entity_id = entity_id
        self._attributes = attributes

    def get(self, entity_id):
        if entity_id != self._entity_id or self._attributes is None:
            return None
        return types.SimpleNamespace(attributes=self._attributes)


class _Coordinator:
    """Only the surface the number entity touches."""

    def __init__(self, model_key, *, source_attributes=None, dp=None) -> None:
        self.model_limits = models.get_model(model_key)
        self._source = "number.q_series_charging_current" if source_attributes else None
        self.hass = types.SimpleNamespace(
            states=_States(self._source, source_attributes)
        )
        self._dp = dp or {}

    def _config(self, _key):
        return self._source

    def dp_definition(self, _code):
        return self._dp


def _slider(coordinator):
    entity = number.AmperePointCurrentLimitNumber.__new__(
        number.AmperePointCurrentLimitNumber
    )
    entity.coordinator = coordinator
    return entity


class CurrentLimitRangeTests(unittest.TestCase):
    def test_sixteen_amp_models_are_narrowed(self) -> None:
        for model_key in ("q11", "q37"):
            with self.subTest(model=model_key):
                slider = _slider(
                    _Coordinator(model_key, source_attributes=PROFILE_RANGE)
                )
                self.assertEqual(slider.native_min_value, 6.0)
                self.assertEqual(slider.native_max_value, 16.0)

    def test_thirty_two_amp_models_keep_the_full_range(self) -> None:
        for model_key in ("q22", "q74"):
            with self.subTest(model=model_key):
                slider = _slider(
                    _Coordinator(model_key, source_attributes=PROFILE_RANGE)
                )
                self.assertEqual(slider.native_min_value, 6.0)
                self.assertEqual(slider.native_max_value, 32.0)

    def test_datapoint_definition_is_narrowed_too(self) -> None:
        # Direct LAN control reads the range from the datapoint instead.
        slider = _slider(_Coordinator("q37", dp=PROFILE_RANGE))
        self.assertEqual(slider.native_max_value, 16.0)

    def test_narrowing_never_raises_the_source_bound(self) -> None:
        # A profile that already knows the exact charger stays authoritative,
        # so a wrong detection cannot offer more than the source allows.
        slider = _slider(_Coordinator("q22", source_attributes={"min": 6, "max": 16}))
        self.assertEqual(slider.native_max_value, 16.0)

    def test_unknown_model_is_capped_by_the_profile(self) -> None:
        # An unrecognised charger falls back to the Q Series defaults, which
        # allow more than the profile; the profile bound has to win.
        slider = _slider(
            _Coordinator("q_series", source_attributes=PROFILE_RANGE)
        )
        self.assertEqual(slider.native_max_value, 32.0)

    def test_source_below_the_model_minimum_does_not_win(self) -> None:
        slider = _slider(_Coordinator("q11", source_attributes={"min": 0, "max": 32}))
        self.assertEqual(slider.native_min_value, 6.0)

    def test_without_any_source_the_model_decides(self) -> None:
        slider = _slider(_Coordinator("q74"))
        self.assertEqual(slider.native_min_value, 6.0)
        self.assertEqual(slider.native_max_value, 32.0)


class ModelDetectionTests(unittest.TestCase):
    """Several models share one Tuya product, so only the name identifies."""

    def test_shared_product_name_does_not_become_a_q37(self) -> None:
        # What a Q22 looks like once tuya-local writes the profile's product
        # model into the device: the old "Q37 / EV Charger VE" string used to
        # win here and cost the charger two phases and half its current.
        detected = models.detect_model_key("Q22 Ampere Point EV Charger VE (local)")
        self.assertEqual(detected, "q22")
        limits = models.get_model(detected)
        self.assertEqual((limits.phases, limits.max_current_a), (3, 32))

    def test_q37_still_detected_by_its_model_number(self) -> None:
        limits = models.get_model(models.detect_model_key("Q37 EV Charger VE (local)"))
        self.assertEqual((limits.phases, limits.max_current_a), (1, 16))

    def test_q74_is_single_phase_at_thirty_two_amps(self) -> None:
        limits = models.get_model(models.detect_model_key("Q74 EV Charger VE (local)"))
        self.assertEqual((limits.phases, limits.max_current_a), (1, 32))

    def test_unnamed_charger_falls_back_to_the_series(self) -> None:
        self.assertEqual(
            models.detect_model_key("Ampere Point EV Charger VE (local)"), "q_series"
        )


if __name__ == "__main__":
    unittest.main()


class AmbiguousTextTests(unittest.TestCase):
    """Text naming several models identifies none of them."""

    def test_a_multi_model_profile_name_identifies_nothing(self) -> None:
        # What a picker label listing every covered model would put into the
        # device's model field.
        self.assertEqual(
            models.detect_model_key("Ampere Point Q Series Q37 Q74 Q11 Q22 local"),
            "q_series",
        )

    def test_the_shipped_label_is_safe(self) -> None:
        self.assertEqual(
            models.detect_model_key("Ampere Point Q Series - all models (local)"),
            "q_series",
        )

    def test_the_suggested_entry_name_is_safe(self) -> None:
        self.assertEqual(
            models.detect_model_key("Ampere Point EV Charger (local)"), "q_series"
        )

    def test_a_single_model_still_identifies(self) -> None:
        self.assertEqual(models.detect_model_key("Q22 charger"), "q22")
