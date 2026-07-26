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


# Profiles this repository authors. The remaining ones were inherited from
# earlier releases for chargers that cannot be measured here, so they are
# only checked against the structural rules, not against these conventions.
MAINTAINED_FILENAMES = (
    "amperepoint_prime_22kw_evcharger.yaml",
    "amperepoint_q11_pro_evcharger.yaml",
)


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
        self.maintained = {
            filename: config
            for filename, config in self.profiles
            if filename in MAINTAINED_FILENAMES
        }
        self.assertEqual(len(self.maintained), len(MAINTAINED_FILENAMES))

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

    def test_maintained_profiles_are_named_and_marked_local(self) -> None:
        """tuya-local labels a profile from its product, falling back to name.

        Only the profiles this repository maintains carry the marker; the
        ones inherited from earlier releases are left as they were.
        """
        for filename, config in self.maintained.items():
            with self.subTest(filename):
                self.assertNotEqual(config["name"], "EV charger")
                self.assertIn("(local)", config["name"])
                for product in config.get("products", []):
                    self.assertIn("(local)", product["model"])

    def test_profiles_without_product_ids_have_a_required_signature(self) -> None:
        """A profile without a PID must not match every unrelated Tuya device."""
        for filename, config in self.profiles:
            product_ids = [
                product.get("id")
                for product in config.get("products", [])
                if product.get("id")
            ]
            if product_ids:
                continue
            required = {
                dps["id"]
                for entity in config["entities"]
                for dps in entity["dps"]
                if not dps.get("optional")
            }
            with self.subTest(filename):
                self.assertTrue(
                    required,
                    "profile has neither a product id nor a required DP signature",
                )

    def test_q11_uses_stable_dps_as_its_signature(self) -> None:
        """DP3 and DP4 were present in the measured idle status response."""
        config = self.maintained["amperepoint_q11_pro_evcharger.yaml"]
        required = {
            dps["id"]
            for entity in config["entities"]
            for dps in entity["dps"]
            if not dps.get("optional")
        }
        self.assertEqual(required, {3, 4})

    def test_intermittent_datapoints_remain_optional(self) -> None:
        """Datapoints absent from hardware captures must not hide a profile."""
        intermittent = {
            "amperepoint_prime_22kw_evcharger.yaml": {108},
            "amperepoint_q11_pro_evcharger.yaml": {1, 6, 7, 8, 17, 19, 23, 25, 33},
        }
        for filename, ids in intermittent.items():
            config = self.maintained[filename]
            for entity in config["entities"]:
                for dps in entity["dps"]:
                    if dps["id"] not in ids:
                        continue
                    with self.subTest(f"{filename}/{dps['id']}"):
                        self.assertTrue(dps.get("optional"))

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

    def test_datapoints_missing_from_a_status_reply_are_forced(self) -> None:
        """tuya-local asks for a datapoint explicitly only when force is set.

        The Q11 answers a plain status query with eight datapoints; the phase
        payloads arrive once a session starts, and the meters were never seen
        at all. helpers/device_config.py collects dps marked force into the
        updatedps request that device.py alternates with status, so they must
        carry the flag to be polled. Only the Q11 was measured, so the flag is
        claimed for it alone.
        """
        answered_by_status = {3, 4, 9, 10, 13, 14, 18, 24}
        config = self.maintained["amperepoint_q11_pro_evcharger.yaml"]
        for entity in config["entities"]:
            for dps in entity["dps"]:
                if dps["id"] in answered_by_status:
                    continue
                with self.subTest(str(dps["id"])):
                    self.assertTrue(
                        dps.get("force"),
                        f"dp {dps['id']} is not returned by a status query",
                    )


if __name__ == "__main__":
    unittest.main()
