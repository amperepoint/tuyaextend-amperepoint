"""Structural checks for the shipped tuya-local device profiles.

tuya-local constructs each entity from a map of named dps and raises
``AttributeError: ... is missing a <name> dps`` when the platform's required
dps is absent, which silently drops the entity (or the whole device) at setup
time.  The rules below mirror tuya-local's own platform code so a broken
profile fails here instead of on a user's charger.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml

PROFILE_DIR = (
    Path(__file__).resolve().parents[1] / "amperepoint" / "profiles" / "tuya_local"
)

# custom_components/tuya_local/<platform>.py: dps_map.pop("<name>")
REQUIRED_DPS_NAME = {
    "sensor": "sensor",
    "binary_sensor": "sensor",
    "number": "value",
    "select": "option",
    "switch": "switch",
}

# helpers/device_config.py: DPSConfig.type mapping table.
ALLOWED_DPS_TYPES = {
    "boolean",
    "integer",
    "string",
    "float",
    "bitfield",
    "json",
    "base64",
    "utf16b64",
    "hex",
    "unixtime",
}


def _profiles() -> list[tuple[str, dict]]:
    loaded = []
    for path in sorted(PROFILE_DIR.glob("*.yaml")):
        with path.open(encoding="utf-8") as handle:
            loaded.append((path.name, yaml.safe_load(handle)))
    return loaded


class TuyaLocalProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profiles = _profiles()
        self.assertTrue(self.profiles, "no tuya-local profiles found")

    def test_profiles_declare_name_and_entities(self) -> None:
        for filename, config in self.profiles:
            with self.subTest(filename):
                self.assertIsInstance(config, dict)
                self.assertTrue(config.get("name"), "missing top-level name")
                self.assertIsInstance(config.get("entities"), list)
                self.assertTrue(config["entities"], "no entities declared")

    def test_every_entity_has_the_dps_its_platform_requires(self) -> None:
        for filename, config in self.profiles:
            for index, entity in enumerate(config["entities"]):
                platform = entity.get("entity")
                label = f"{filename}#{index} ({platform})"
                with self.subTest(label):
                    self.assertIn(
                        platform,
                        REQUIRED_DPS_NAME,
                        f"{label}: unsupported platform",
                    )
                    names = [dps.get("name") for dps in entity.get("dps", [])]
                    self.assertIn(
                        REQUIRED_DPS_NAME[platform],
                        names,
                        f"{label}: tuya-local needs a dps named "
                        f"'{REQUIRED_DPS_NAME[platform]}', got {names}",
                    )

    def test_dps_entries_are_well_formed(self) -> None:
        for filename, config in self.profiles:
            for index, entity in enumerate(config["entities"]):
                dps_list = entity.get("dps", [])
                label = f"{filename}#{index}"
                with self.subTest(label):
                    self.assertTrue(dps_list, f"{label}: entity has no dps")
                    names = [dps.get("name") for dps in dps_list]
                    self.assertEqual(
                        len(names), len(set(names)), f"{label}: duplicate dps names"
                    )
                    for dps in dps_list:
                        self.assertIsNotNone(dps.get("id"), f"{label}: dps without id")
                        self.assertIn(
                            dps.get("type"),
                            ALLOWED_DPS_TYPES,
                            f"{label}: unsupported dps type {dps.get('type')!r}",
                        )
                        self.assertTrue(dps.get("name"), f"{label}: dps without name")

    def test_prime_profile_exposes_the_telemetry_datapoint(self) -> None:
        """The AmperePoint coordinator decodes DP102 from this attribute."""
        config = dict(_profiles())["amperepoint_prime_22kw_evcharger.yaml"]
        telemetry = [
            dps
            for entity in config["entities"]
            for dps in entity.get("dps", [])
            if dps.get("name") == "telemetry"
        ]
        self.assertEqual(len(telemetry), 1)
        self.assertEqual(str(telemetry[0]["id"]), "102")
        # tuya-local delivers json dps as a string; the coordinator's decoder
        # accepts both a JSON string and a mapping.
        self.assertEqual(telemetry[0]["type"], "json")


if __name__ == "__main__":
    unittest.main()
