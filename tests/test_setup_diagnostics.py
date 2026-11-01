"""Setup reports must explain failed detection without exporting credentials."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
from support import load_integration_module, install_homeassistant_stubs, _module

install_homeassistant_stubs()
local = load_integration_module("local_source")
diagnostics = load_integration_module("setup_diagnostics")
ROOT = Path(__file__).resolve().parents[1]
CONFIG = {"local_device_id": "private-device-identifier", "local_key": "private-key-1234",
          "local_host": "192.168.1.20", "local_protocol": "3.5",
          "local_product_id": "gbmxngploofmhbjc"}


class SnapshotTests(unittest.TestCase):
    def test_real_fixtures_keep_firmware_telemetry_and_types(self):
        for family in ("split", "packed"):
            fixture = json.loads((ROOT / f"amperepoint/observations/prime-{family}-tester-20260911.json").read_text())
            report = diagnostics.describe_response({"dps": fixture["dps"]}, CONFIG)
            self.assertTrue(report["checks"]["dp109_is_string"])
            self.assertEqual(report["checks"]["dp102_missing_required_fields"], [])
            self.assertIn("fv", report["dps"]["106"]["value"])
            self.assertEqual(report["dps"]["150"]["type"], "integer")
            self.assertEqual(report["dps"]["102"]["encoding"], "json_string")

    def test_private_unknown_malformed_and_nested_data_are_not_exported(self):
        private = "do-not-export-card-or-token"
        response = {"Error": private, "Err": "914", "payload": private, "dps": {
            "112": private, "113": [private], "999": {"token": private},
            "102": json.dumps({"p": 1, "e": 2, "t": 3, "L": [2300, 0, 0],
                               "serial": private, "c": {"password": private}}),
            "106": json.dumps({"fv": CONFIG["local_key"], "serial": private}),
            "109": CONFIG["local_device_id"], "151": {"ss": private},
            private: private, "107": [private], "150": float("nan"),
            "152": 10 ** 500,
        }}
        snapshot = diagnostics.describe_response(response, CONFIG)
        error = local.LocalConnectionError("local_unsupported")
        error.diagnostics = snapshot
        report = diagnostics.build_report(error, CONFIG, "local_import", "test-ha")
        encoded = json.dumps(report, allow_nan=False)
        for secret in (private, CONFIG["local_key"], CONFIG["local_host"], CONFIG["local_device_id"]):
            self.assertNotIn(secret, encoded)
        self.assertEqual(report["product_id"], CONFIG["local_product_id"])
        self.assertEqual(snapshot["protocol_error_code"], "914")
        self.assertEqual(snapshot["dps"]["112"]["value"], diagnostics.REDACTED)
        self.assertEqual(snapshot["dps"]["999"]["type"], "object")

    def test_missing_required_dp_is_reported_without_changing_validation(self):
        device = SimpleNamespace(status=lambda: {"dps": {"102": '{"p":0,"e":0,"t":30,"L":[]}' }}, close=lambda: None)
        with patch.dict(sys.modules, {"tinytuya": SimpleNamespace(Device=lambda *a, **kw: device)}):
            with self.assertRaisesRegex(local.LocalConnectionError, "local_unsupported") as caught:
                local.read_local(CONFIG)
        self.assertFalse(caught.exception.diagnostics["checks"]["dp109_present"])
        self.assertTrue(caught.exception.diagnostics["checks"]["dp102_L_is_array"])

    def test_protocol_error_body_never_reaches_snapshot(self):
        device = SimpleNamespace(status=lambda: {"Error": CONFIG["local_key"], "Err": "914"}, close=lambda: None)
        with patch.dict(sys.modules, {"tinytuya": SimpleNamespace(Device=lambda *a, **kw: device)}):
            with self.assertRaises(local.LocalConnectionError) as caught:
                local.read_local(CONFIG)
        self.assertNotIn(CONFIG["local_key"], json.dumps(caught.exception.diagnostics))

    def test_untrusted_error_text_and_large_payloads_are_bounded(self):
        report = diagnostics.build_report(RuntimeError(CONFIG["local_key"]), CONFIG, "untrusted", "test-ha")
        self.assertEqual(report["error"], "local_cannot_connect")
        response = {"dps": {str(n): "x" * 5000 for n in range(300)}}
        snapshot = diagnostics.describe_response(response, CONFIG)
        self.assertTrue(snapshot["dps_truncated"])
        self.assertLess(len(json.dumps(snapshot)), 15000)


class DownloadTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Only stub HA imports; exercise the real aiohttp response and real store.
        _module("homeassistant.components.http", HomeAssistantView=object)
        _module("homeassistant.components.http.auth", async_sign_path=lambda hass, path, expiration: path + "?authSig=test")
        _module("homeassistant.const", __version__="test-ha")
        self.download = load_integration_module("setup_diagnostics_download")
        self.views = []
        self.hass = SimpleNamespace(data={}, loop=asyncio.get_running_loop(),
                                    http=SimpleNamespace(register_view=self.views.append))

    async def test_download_is_separate_for_each_attempt_and_has_attachment_headers(self):
        error = local.LocalConnectionError("local_unsupported")
        path = self.download.create_download(self.hass, error, CONFIG, "local_manual")
        path2 = self.download.create_download(self.hass, error, CONFIG, "local_import")
        self.assertNotEqual(path, path2)
        self.assertEqual(len(self.views), 1)
        self.assertTrue(self.views[0].requires_auth)
        token = path.split("?")[0].rsplit("/", 1)[1]
        response = await self.views[0].get(None, token)
        self.assertEqual(response.content_type, "application/json")
        self.assertIn("attachment;", response.headers["Content-Disposition"])
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(json.loads(response.text)["operation"], "local_manual")

    async def test_expired_unknown_and_evicted_reports_cannot_be_downloaded(self):
        from aiohttp import web
        store = self.download.ReportStore()
        with patch.object(self.download.time, "monotonic", return_value=10):
            first = store.put({"test": True})
            for _ in range(self.download.MAX_REPORTS):
                last = store.put({"test": True})
            self.assertIsNone(store.get(first))
            self.assertIsNotNone(store.get(last))
        with patch.object(self.download.time, "monotonic", return_value=10 + self.download.TTL):
            with self.assertRaises(web.HTTPNotFound):
                await self.download.SetupDiagnosticView(store).get(None, last)
        self.assertEqual(len(store.reports), 0)
        with self.assertRaises(web.HTTPNotFound):
            await self.download.SetupDiagnosticView(store).get(None, "unknown")


class ErrorFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        sys.modules["homeassistant.helpers"].selector = SimpleNamespace(
            TextSelector=lambda config: str, TextSelectorConfig=lambda **kw: kw,
            TextSelectorType=SimpleNamespace(PASSWORD="password"))
        self.flow_module = load_integration_module("local_flow")
        class Flow(self.flow_module.NativeLocalFlowMixin):
            def async_show_form(self, **kwargs): return kwargs
            async def async_step_local_confirm(self, user_input=None): return {"step_id": "local_confirm"}
        self.flow = Flow()
        async def execute(fn, *args): return fn(*args)
        self.flow.hass = SimpleNamespace(async_add_executor_job=execute)

    async def test_failed_manual_setup_offers_download_and_retry_uses_current_input(self):
        error = local.LocalConnectionError("local_unsupported")
        with patch.object(self.flow_module, "diagnostic_form", side_effect=lambda flow, step, schema, err, config: {
            "step_id": step + "_error", "error": str(err), "schema": schema}) as report:
            with patch.object(self.flow_module, "read_local", side_effect=error):
                result = await self.flow.async_step_local_manual(CONFIG)
            self.assertEqual(result["step_id"], "local_manual_error")
            self.assertEqual(report.call_args.args[-1], CONFIG)
            with patch.object(self.flow_module, "read_local", return_value={"host": CONFIG["local_host"], "family": "prime_split", "dps": {}}):
                result = await self.flow.async_step_local_manual_error(CONFIG)
            self.assertEqual(result["step_id"], "local_confirm")

    async def test_cloud_import_failure_preserves_selected_device(self):
        candidates = {CONFIG["local_device_id"]: {**CONFIG, "name": "PRIME"}}
        with patch.object(self.flow_module, "cloud_candidates", return_value=candidates), \
             patch.object(self.flow_module, "read_local", side_effect=local.LocalConnectionError("local_unsupported")), \
             patch.object(self.flow_module, "diagnostic_form", return_value={"step_id": "local_import_error"}) as report:
            result = await self.flow.async_step_local_import({"local_device_id": CONFIG["local_device_id"]})
        self.assertEqual(result["step_id"], "local_import_error")
        schema = report.call_args.args[2]
        self.assertEqual(schema({})["local_device_id"], CONFIG["local_device_id"])

    async def test_all_error_steps_have_translated_download_links_and_retry_fields(self):
        base = ROOT / "custom_components/tuyaextend_amperepoint"
        for name in ("strings.json", "translations/pl.json", "translations/en.json"):
            data = json.loads((base / name).read_text(encoding="utf-8"))
            for section, step in (("config", "local_import"), ("config", "local_manual"), ("options", "local_connection")):
                original = data[section]["step"][step]
                failed = data[section]["step"][step + "_error"]
                self.assertIn("]({diagnostic_url})", failed["description"])
                self.assertEqual(original["data"], failed["data"])

    async def test_options_failure_has_report_and_does_not_save_unverified_controls(self):
        class Options(self.flow_module.NativeLocalOptionsMixin):
            def async_show_form(self, **kwargs): return kwargs
        options = Options()
        options.hass = self.flow.hass
        options._config_entry = SimpleNamespace(data=CONFIG, options={})
        snapshot = {"host": CONFIG["local_host"], "family": "prime_split", "dps": {
            "102": '{"p":0,"e":0,"t":30,"L":[]}', "109": "STATE_C"}}
        with patch.object(self.flow_module, "read_local", return_value=snapshot), \
             patch.object(self.flow_module, "diagnostic_form", return_value={"step_id": "local_connection_error"}) as report:
            result = await options.async_step_local_connection({"enable_test_controls": True})
        self.assertEqual(result["step_id"], "local_connection_error")
        self.assertFalse(report.call_args.args[3].diagnostics["controls_verified"])
        self.assertEqual(options._config_entry.data, CONFIG)


if __name__ == "__main__":
    unittest.main()
