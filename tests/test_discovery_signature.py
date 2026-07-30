"""A charger has to be found even when nothing names it.

Recognition used to be a list of known model names. A Q74 paired through
tuya-local carries none of them: it arrives as "Q74" with the manufacturer
"Tuya" and an empty model, because the profile it matched declares no
product id for that hardware, so nothing writes a brand into the device.
"""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import load_integration_module  # noqa: E402

discovery = load_integration_module("discovery")
const = load_integration_module("const")


def _entry(entity_id: str, name: str):
    return types.SimpleNamespace(
        entity_id=entity_id,
        name=None,
        original_name=name,
        translation_key=None,
        unique_id=entity_id,
        platform="tuya_local",
        device_id="dev-1",
    )


# What tuya-local actually created for the Q74, minus the datapoints that
# generation does not report (no DP13 connection state, no DP24 temperature).
Q74_ENTITIES = [
    _entry("number.q74_charging_current", "Charging current"),
    _entry("select.q74_charging_mode", "Charging mode"),
    _entry("sensor.q74_charging_status", "Charging status"),
    _entry("switch.q74_charging", "Charging"),
    _entry("sensor.q74_power", "Power"),
    _entry("sensor.q74_current_l1", "Current L1"),
    _entry("sensor.q74_voltage_l1", "Voltage L1"),
    _entry("sensor.q74_fault", "Fault"),
]

SMART_PLUG_ENTITIES = [
    _entry("switch.plug_switch", "Switch"),
    _entry("sensor.plug_power", "Power"),
    _entry("sensor.plug_voltage", "Voltage"),
    _entry("sensor.plug_current", "Current"),
]


class ChargerSignatureTests(unittest.TestCase):
    def test_q74_is_recognised_without_a_known_name(self) -> None:
        text = " ".join(("Q74", "", "Tuya", "tuya_local"))
        self.assertFalse(
            discovery._looks_like_amperepoint(text),
            "precondition: nothing in this device names a known model",
        )
        mapping = discovery.map_source_entities(Q74_ENTITIES)
        self.assertTrue(discovery._has_charger_signature(mapping))

    def test_a_smart_plug_is_not_a_charger(self) -> None:
        mapping = discovery.map_source_entities(SMART_PLUG_ENTITIES)
        self.assertNotIn(const.CONF_SOURCE_CURRENT_LIMIT, mapping)
        self.assertFalse(discovery._has_charger_signature(mapping))

    def test_a_current_limit_alone_is_not_enough(self) -> None:
        # One stray match may not carry the recognition on its own.
        self.assertFalse(
            discovery._has_charger_signature(
                {const.CONF_SOURCE_CURRENT_LIMIT: "number.something"}
            )
        )

    def test_known_names_still_work_without_the_signature(self) -> None:
        # A cloud entry may expose almost nothing; the name carries it there.
        self.assertTrue(
            discovery._looks_like_amperepoint("Ampere Point Q11 PRO Tuya")
        )


if __name__ == "__main__":
    unittest.main()
