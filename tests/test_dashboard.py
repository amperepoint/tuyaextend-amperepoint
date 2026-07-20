from __future__ import annotations

import copy
import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import load_integration_module  # noqa: E402

dashboard = load_integration_module("dashboard")


def _legacy_config(entry, entities: dict[str, str]) -> dict:
    return {
        "title": f"AmperePoint – {entry.title}",
        "views": [
            {
                "title": entry.title,
                "path": "charger",
                "icon": dashboard.DASHBOARD_ICON,
                "panel": True,
                "cards": [
                    {
                        "type": "custom:amperepoint-q22-card",
                        "entities": entities,
                    }
                ],
            }
        ],
    }


class LegacyDashboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.entry = types.SimpleNamespace(entry_id="entry-1", title="Garage")
        self.entities = {
            "switch": "switch.garage_charging",
            "power": "sensor.garage_power",
        }

    def test_unchanged_generated_dashboard_can_be_removed(self) -> None:
        config = _legacy_config(self.entry, self.entities)
        self.assertTrue(
            dashboard._is_generated_legacy_dashboard(config, self.entry, self.entities)
        )

    def test_custom_card_is_preserved(self) -> None:
        config = _legacy_config(self.entry, self.entities)
        config["views"][0]["cards"].append({"type": "markdown", "content": "Hi"})
        self.assertFalse(
            dashboard._is_generated_legacy_dashboard(config, self.entry, self.entities)
        )

    def test_user_entity_override_is_preserved(self) -> None:
        config = _legacy_config(self.entry, copy.deepcopy(self.entities))
        config["views"][0]["cards"][0]["entities"]["power"] = "sensor.custom_power"
        self.assertFalse(
            dashboard._is_generated_legacy_dashboard(config, self.entry, self.entities)
        )

    def test_extra_card_setting_is_preserved(self) -> None:
        config = copy.deepcopy(_legacy_config(self.entry, self.entities))
        config["views"][0]["cards"][0]["name"] = "My charger"
        self.assertFalse(
            dashboard._is_generated_legacy_dashboard(config, self.entry, self.entities)
        )


if __name__ == "__main__":
    unittest.main()
