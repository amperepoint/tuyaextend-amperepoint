"""First-run LAN setup must expose tested controls without sending commands."""
import asyncio
import ast
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
from support import load_integration_module, install_homeassistant_stubs

install_homeassistant_stubs()
sys.modules["homeassistant.helpers"].selector = SimpleNamespace(
    TextSelector=lambda config: str, TextSelectorConfig=lambda **kw: kw,
    TextSelectorType=SimpleNamespace(PASSWORD="password"))
flow_module = load_integration_module("local_flow")
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "amperepoint/observations/prime-split-tester-20260911.json").read_text(encoding="utf-8"))
DPS = {**FIXTURE["dps"], "140": True}
CREDENTIALS = dict(name="Test PRIME", local_device_id="test-device",
                   local_key="0123456789abcdef", local_host="192.168.0.154",
                   local_protocol="3.5", local_product_id="test-product")


class Flow(flow_module.NativeLocalFlowMixin):
    def __init__(self):
        async def execute(fn, *args):
            return fn(*args)
        self.hass = SimpleNamespace(async_add_executor_job=execute,
                                   config_entries=SimpleNamespace(async_entries=lambda _: []))
    def async_show_form(self, **kw): return {"type": "form", **kw}
    def async_create_entry(self, **kw): return {"type": "create_entry", **kw}
    def _abort_if_unique_id_configured(self): pass
    async def async_set_unique_id(self, value): self.unique_id = value


class NativeFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_verified_prime_gets_full_controls_and_preserves_pid(self):
        flow = Flow()
        snapshot = dict(host=CREDENTIALS["local_host"], dps=DPS, family="prime_split")
        with patch.object(flow_module, "read_local", return_value=snapshot), \
             patch.object(flow_module, "discover_device") as scan:
            form = await flow.async_step_local_manual(CREDENTIALS)
        scan.assert_not_called()
        self.assertEqual(form["step_id"], "local_confirm")
        self.assertEqual(flow._local_pending["local_control_profile"], "prime_split_v1")
        result = await flow.async_step_local_confirm({})
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"]["local_product_id"], "test-product")
        self.assertEqual(result["data"]["local_control_profile"], "prime_split_v1")
        self.assertNotIn("local_pause_planner", result["data"])

    async def test_unverified_firmware_stays_read_only_even_if_input_claims_controls(self):
        flow = Flow()
        snapshot = dict(host=CREDENTIALS["local_host"], dps={**DPS, "106": '{}'}, family="prime_split")
        with patch.object(flow_module, "read_local", return_value=snapshot):
            form = await flow.async_step_local_manual({**CREDENTIALS, "local_control_profile": "prime_split_v1"})
        self.assertEqual(form["step_id"], "local_confirm_read_only")
        result = await flow.async_step_local_confirm_read_only({})
        self.assertIsNone(result["data"]["local_control_profile"])

    async def test_lan_discovery_can_supply_missing_pid_but_failure_does_not_block_setup(self):
        snapshot = dict(host=CREDENTIALS["local_host"], dps=DPS, family="prime_split")
        credentials = {**CREDENTIALS, "local_product_id": None}
        for discovered, expected in (({"product_id": "lan-product"}, "lan-product"),
                                     (flow_module.LocalConnectionError("local_not_found"), None)):
            flow = Flow()
            with patch.object(flow_module, "read_local", return_value=snapshot), \
                 patch.object(flow_module, "discover_device", side_effect=[discovered]):
                await flow.async_step_local_manual(credentials)
            self.assertEqual(flow._local_pending["local_product_id"], expected)
            self.assertEqual(flow._local_pending["local_control_profile"], "prime_split_v1")

    async def test_cloud_import_reads_product_identity_without_network_calls(self):
        device = SimpleNamespace(id="example", name="EV Charger", category="qccdz",
                                 local_key="0123456789abcdef", product_id="product-from-tuya")
        entry = SimpleNamespace(runtime_data=SimpleNamespace(manager=SimpleNamespace(device_map={"example": device})))
        hass = SimpleNamespace(config_entries=SimpleNamespace(async_entries=lambda _: [entry]))
        candidates = flow_module.cloud_candidates(hass)
        self.assertEqual(candidates["example"]["local_product_id"], "product-from-tuya")

    async def test_migration_preserves_entity_entry_and_pauses_previous_automation(self):
        flow = Flow()
        flow._local_pending = {**CREDENTIALS, "local_control_profile": "prime_split_v1"}
        existing = SimpleNamespace(data={"source_integration": "tuya", "source_power": "sensor.old"},
                                   options={}, entry_id="existing-entry")
        changes = []
        async def reload(entry_id): changes.append(entry_id)
        flow.hass.config_entries.async_update_entry = lambda entry, **kw: changes.append(kw)
        flow.hass.config_entries.async_reload = reload
        flow.async_abort = lambda **kw: kw
        with patch.object(flow_module, "existing_physical_entry", return_value=existing):
            result = await flow.async_step_local_confirm({})
        self.assertEqual(result["reason"], "local_migrated")
        self.assertTrue(changes[0]["data"]["local_pause_planner"])
        self.assertNotIn("source_power", changes[0]["data"])
        self.assertEqual(changes[1], "existing-entry")

    async def test_primary_menus_do_not_offer_separate_tuya_local_installer(self):
        tree = ast.parse((ROOT / "custom_components/tuyaextend_amperepoint/config_flow.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name in ("async_step_user", "async_step_init"):
                self.assertNotIn("prime_profile", ast.unparse(node))

    async def test_new_confirmation_text_is_valid_utf8_and_distinguishes_capabilities(self):
        component = ROOT / "custom_components/tuyaextend_amperepoint"
        for path in [component / "strings.json", component / "translations/en.json", component / "translations/pl.json"]:
            raw = path.read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
            data = json.loads(raw.decode("utf-8"))
            steps = data["config"]["step"]
            self.assertNotIn("prime_profile", steps["user"]["menu_options"])
            for step in ("local_confirm", "local_confirm_read_only"):
                self.assertIn("{name}", steps[step]["description"])
                self.assertIn("{host}", steps[step]["description"])
            self.assertNotEqual(steps["local_confirm"]["description"], steps["local_confirm_read_only"]["description"])
