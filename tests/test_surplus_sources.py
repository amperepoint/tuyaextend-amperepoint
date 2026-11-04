"""Normalization of the user-selected energy entities into engine inputs."""

from __future__ import annotations

import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import load_integration_module  # noqa: E402

const = load_integration_module("const")
coordinator = load_integration_module("coordinator")

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)


class _States:
    def __init__(self, states):
        self._states = states

    def get(self, entity_id):
        return self._states.get(entity_id)


def _state(value, unit=None, updated=NOW):
    attributes = {"unit_of_measurement": unit} if unit else {}
    return types.SimpleNamespace(
        state=value, attributes=attributes, last_updated=updated
    )


def _coordinator(config, states):
    instance = object.__new__(coordinator.AmperePointCoordinator)
    instance.config_entry = types.SimpleNamespace(data=config, options={})
    instance.hass = types.SimpleNamespace(states=_States(states))
    instance.model = load_integration_module("models").get_model("q22_ota")
    instance._seen_datapoints = {}
    return instance


class GridNormalizationTests(unittest.TestCase):
    def test_watts_pass_through_and_kilowatts_are_scaled(self) -> None:
        instance = _coordinator(
            {
                const.CONF_SOURCE_PV_POWER: "sensor.pv_kw",
                const.CONF_SOURCE_GRID_POWER: "sensor.grid_w",
            },
            {
                "sensor.pv_kw": _state("4.2", "kW"),
                "sensor.grid_w": _state("-1500", "W"),
            },
        )
        measurements = instance.surplus_measurements(None)
        self.assertEqual(measurements.pv_w, 4200.0)
        self.assertEqual(measurements.grid_w, -1500.0)

    def test_export_positive_convention_is_inverted(self) -> None:
        config = {
            const.CONF_SOURCE_GRID_POWER: "sensor.grid",
            const.CONF_GRID_IMPORT_POSITIVE: False,
        }
        instance = _coordinator(config, {"sensor.grid": _state("1500", "W")})
        # 1500 W "export positive" means 1500 W leaving the house.
        self.assertEqual(instance.surplus_measurements(None).grid_w, -1500.0)

    def test_separate_import_and_export_sensors_are_combined(self) -> None:
        instance = _coordinator(
            {
                const.CONF_SOURCE_GRID_IMPORT: "sensor.import",
                const.CONF_SOURCE_GRID_EXPORT: "sensor.export",
            },
            {
                "sensor.import": _state("0", "W"),
                "sensor.export": _state("2.5", "kW"),
            },
        )
        self.assertEqual(instance.surplus_measurements(None).grid_w, -2500.0)

    def test_charger_power_is_converted_to_watts(self) -> None:
        instance = _coordinator(
            {const.CONF_SOURCE_GRID_POWER: "sensor.grid"},
            {"sensor.grid": _state("0", "W")},
        )
        self.assertEqual(instance.surplus_measurements(1.4).charger_w, 1400.0)

    def test_battery_sign_convention_is_applied(self) -> None:
        config = {
            const.CONF_SOURCE_BATTERY_POWER: "sensor.battery",
            const.CONF_SOURCE_BATTERY_SOC: "sensor.soc",
            const.CONF_BATTERY_CHARGE_POSITIVE: False,
        }
        instance = _coordinator(
            config,
            {
                "sensor.battery": _state("-800", "W"),
                "sensor.soc": _state("64"),
            },
        )
        measurements = instance.surplus_measurements(None)
        self.assertEqual(measurements.battery_w, 800.0)
        self.assertEqual(measurements.battery_soc, 64.0)

    def test_unavailable_sources_are_reported_as_missing(self) -> None:
        instance = _coordinator(
            {const.CONF_SOURCE_GRID_POWER: "sensor.grid"},
            {"sensor.grid": _state("unavailable", "W")},
        )
        self.assertIsNone(instance.surplus_measurements(None).grid_w)

    def test_measurement_age_uses_the_oldest_source(self) -> None:
        stale = datetime(2026, 7, 25, 11, 0, tzinfo=timezone.utc)
        instance = _coordinator(
            {
                const.CONF_SOURCE_PV_POWER: "sensor.pv",
                const.CONF_SOURCE_GRID_POWER: "sensor.grid",
            },
            {
                "sensor.pv": _state("1000", "W", updated=stale),
                "sensor.grid": _state("-500", "W", updated=NOW),
            },
        )
        self.assertEqual(instance.surplus_measurements(None).updated_at, stale)


class SettingsTests(unittest.TestCase):
    def test_settings_follow_the_charger_model_and_options(self) -> None:
        instance = _coordinator(
            {
                const.CONF_PV_MODE: "pv_grid",
                const.CONF_PV_RESERVE_W: 500,
                const.CONF_PV_MAX_IMPORT_W: 1500,
                const.CONF_PV_BATTERY_MIN_SOC: 80,
            },
            {},
        )
        settings = instance.surplus_settings()
        self.assertEqual(settings.mode, "pv_grid")
        self.assertEqual(settings.reserve_w, 500.0)
        self.assertEqual(settings.max_import_w, 1500.0)
        self.assertEqual(settings.battery_min_soc, 80.0)
        self.assertEqual(settings.phases, instance.model.phases)
        self.assertEqual(settings.max_current_a, float(instance.model.max_current_a))

    def test_pv_is_off_by_default(self) -> None:
        instance = _coordinator({}, {})
        self.assertEqual(instance.surplus_settings().mode, "off")


if __name__ == "__main__":
    unittest.main()
