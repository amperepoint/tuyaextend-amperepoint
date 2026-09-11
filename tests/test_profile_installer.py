from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import load_integration_module

installer = load_integration_module("profile_installer")
ROOT = Path(__file__).resolve().parents[1]


class ProfileInstallerTests(unittest.TestCase):
    def test_family_installer_includes_split_generation(self):
        self.prepare_tuya_local()
        self.assertEqual(installer.install_prime_profiles(str(self.root)), "prime_profile_installed")
        for name in (installer.PROFILE_NAME, installer.SPLIT_PROFILE_NAME):
            self.assertTrue((self.devices / name).is_file())
            canonical = ROOT / "amperepoint/profiles/tuya_local" / name
            self.assertEqual(canonical.read_text(encoding="utf-8"),
                             (self.devices / name).read_text(encoding="utf-8"))

    def test_old_conflict_does_not_block_new_generation(self):
        target = self.prepare_tuya_local()
        target.write_text("custom profile", encoding="utf-8")
        self.assertEqual(installer.install_prime_profiles(str(self.root)), "prime_profile_conflict")
        self.assertEqual(target.read_text(), "custom profile")
        self.assertTrue((self.devices / installer.SPLIT_PROFILE_NAME).is_file())

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.integration = self.root / "custom_components" / "tuya_local"
        self.devices = self.integration / "devices"

    def prepare_tuya_local(self):
        self.devices.mkdir(parents=True)
        (self.integration / "manifest.json").write_text('{}', encoding="utf-8")
        return self.devices / installer.PROFILE_NAME

    def install(self):
        return installer.install_prime_profile(str(self.root))

    def test_missing_dependency_does_not_create_fake_tuya_local_install(self):
        self.assertEqual(self.install(), "prime_tuya_local_missing")
        self.assertFalse(self.integration.exists())

    def test_installs_bundled_profile_and_repairs_file_removed_by_update(self):
        target = self.prepare_tuya_local()
        self.assertEqual(self.install(), "prime_profile_installed")
        self.assertEqual(target.read_bytes(), installer.BUNDLED_PROFILE.read_bytes())
        self.assertEqual(self.install(), "prime_profile_installed")
        target.unlink()
        self.assertEqual(self.install(), "prime_profile_installed")
        self.assertEqual(target.read_bytes(), installer.BUNDLED_PROFILE.read_bytes())
        self.assertEqual(list(self.devices.glob("*.tmp")), [])

    def test_preserves_existing_different_profile(self):
        target = self.prepare_tuya_local()
        target.write_text("name: user profile\n", encoding="utf-8")
        self.assertEqual(self.install(), "prime_profile_conflict")
        self.assertEqual(target.read_text(), "name: user profile\n")

    def test_line_endings_do_not_create_false_conflict(self):
        target = self.prepare_tuya_local()
        target.write_bytes(installer.BUNDLED_PROFILE.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        self.assertEqual(self.install(), "prime_profile_installed")

    def test_concurrent_installations_publish_one_complete_file(self):
        target = self.prepare_tuya_local()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.install(), range(2)))
        self.assertEqual(results, ["prime_profile_installed"] * 2)
        self.assertEqual(target.read_bytes(), installer.BUNDLED_PROFILE.read_bytes())
        self.assertEqual(list(self.devices.glob("*.tmp")), [])

    def test_publish_failure_leaves_no_partial_profile(self):
        target = self.prepare_tuya_local()
        with patch.object(installer.os, "link", side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                self.install()
        self.assertFalse(target.exists())
        self.assertEqual(list(self.devices.glob("*.tmp")), [])

    def test_package_profile_matches_reviewed_repo_profile(self):
        canonical = ROOT / "amperepoint/profiles/tuya_local" / installer.PROFILE_NAME
        self.assertEqual(
            canonical.read_text(encoding="utf-8"),
            installer.BUNDLED_PROFILE.read_text(encoding="utf-8"),
        )


class _Flow(installer.PrimeProfileFlowMixin):
    def __init__(self):
        self.calls = []

        async def execute(function, path):
            self.calls.append((function, path))
            return self.result

        self.hass = SimpleNamespace(
            config=SimpleNamespace(path=lambda: "/config"),
            async_add_executor_job=execute,
        )

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_abort(self, **kwargs):
        return {"type": "abort", **kwargs}


class ProfileFlowTests(unittest.TestCase):
    def test_prime_notice_is_not_restricted_to_a_rating_or_product_id(self):
        paths = [ROOT / "custom_components/tuyaextend_amperepoint/strings.json"]
        paths += [ROOT / "custom_components/tuyaextend_amperepoint/translations" / f"{language}.json"
                  for language in ("en", "pl")]
        for path in paths:
            data = json.loads(path.read_text(encoding="utf-8"))
            for section in ("config", "options"):
                notice = data[section]["step"]["prime_profile"]["description"]
                self.assertIn("Wallbox PRIME", notice)
                self.assertNotIn("PID", notice)
                self.assertNotIn("kW", notice)
                self.assertNotIn("gbmxngploofmhbjc", notice)

    def test_opening_form_does_not_install(self):
        flow = _Flow()
        result = asyncio.run(flow.async_step_prime_profile())
        self.assertEqual(result["type"], "form")
        self.assertEqual(flow.calls, [])

    def test_success_does_not_create_an_empty_charger_entry(self):
        flow = _Flow()
        flow.result = "prime_profile_installed"
        result = asyncio.run(flow.async_step_prime_profile({}))
        self.assertEqual(result, {"type": "abort", "reason": flow.result})
        self.assertEqual(len(flow.calls), 1)

    def test_conflict_and_missing_dependency_keep_flow_retryable(self):
        for error in ("prime_profile_conflict", "prime_tuya_local_missing"):
            with self.subTest(error=error):
                flow = _Flow()
                flow.result = error
                result = asyncio.run(flow.async_step_prime_profile({}))
                self.assertEqual(result["type"], "form")
                self.assertEqual(result["errors"], {"base": error})

    def test_error_has_translations_in_both_flows_and_languages(self):
        for language in ("en", "pl"):
            path = ROOT / "custom_components/tuyaextend_amperepoint/translations" / f"{language}.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            for section in ("config", "options"):
                self.assertIn("prime_profile", data[section]["step"])
                self.assertIn("prime_profile_installed", data[section]["abort"])
                self.assertIn("prime_profile_write_error", data[section]["error"])
