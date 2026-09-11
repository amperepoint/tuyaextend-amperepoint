"""Regression tests for the hardware-verified write-only DP140 PRIME firmware."""
import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
from support import load_integration_module, _EntityDescription
from test_local_flow import Flow, CREDENTIALS, flow_module

local = load_integration_module("local_source")
DPS = json.loads((Path(__file__).resolve().parents[1] /
    "amperepoint/observations/prime-packed-tester-20260911.json").read_text(encoding="utf-8"))["dps"]
CONFIG = {**CREDENTIALS, "local_control_profile": local.PACKED_CONTROL_PROFILE}


class PackedControlsTests(unittest.TestCase):
    def snapshot(self, **changes):
        return dict(host=CONFIG["local_host"], dps={**DPS, **changes}, family="prime_packed")

    def test_profile_requires_verified_contract_not_pid_or_name(self):
        self.assertEqual(local.detected_control_profile(DPS, "prime_packed"), local.PACKED_CONTROL_PROFILE)
        self.assertFalse(local.control_supported({}, DPS, "prime_packed"))
        for changes in ({"106": "{}"}, {"152": 32}, {"152": True}, {"150": 6.0}, {"101": True}):
            self.assertIsNone(local.detected_control_profile({**DPS, **changes}, "prime_packed"))
        self.assertIsNone(local.detected_control_profile(DPS, "prime_split"))

    def test_missing_cp_does_not_mean_disconnected(self):
        stub = SimpleNamespace(BinarySensorDeviceClass=SimpleNamespace(PLUG="plug"),
                               BinarySensorEntity=type("BinarySensorEntity", (), {}),
                               BinarySensorEntityDescription=_EntityDescription)
        with patch.dict(sys.modules, {"homeassistant.components.binary_sensor": stub}):
            module = load_integration_module("binary_sensor")
        entity = object.__new__(module.AmperePointBinarySensor)
        entity.entity_description = module.BINARY_SENSORS[0]
        for source, known, connected, expected in (
                ("amperepoint_local", False, False, None),
                ("amperepoint_local", True, False, False),
                ("amperepoint_local", True, True, True),
                ("amperepoint_local", False, True, True),
                ("tuya", False, False, False)):
            entity.coordinator = SimpleNamespace(data={"source_type":source,
                "vehicle_connection_known":known, "vehicle_connected":connected})
            self.assertIs(entity.is_on, expected)

    def test_switch_reports_observation_without_inventing_raw_dp(self):
        source = local.NativeLocalSource(None, SimpleNamespace(data=CONFIG, options={}))
        source.dps, source.family = dict(DPS), "prime_packed"
        self.assertTrue(source.raw("switch"))
        self.assertTrue(source.writable("switch"))
        self.assertNotIn("dp_140", source.values())
        for state, status, expected in ((204, "PAUSE", False), (300, "PAUSE", None),
                                       (204, "WORKING", None), (500, "FAULT", None)):
            source.dps.update({"101": state, "109": status})
            self.assertIs(source.raw("switch"), expected)

    def test_write_only_switch_is_confirmed_by_independent_status_pair(self):
        for enabled, state, status in ((False, 204, "PAUSE"), (True, 300, "WORKING")):
            sent = []
            before = self.snapshot(**{"101": 204 if enabled else 300, "109": "PAUSE" if enabled else "WORKING"})
            after = self.snapshot(**{"101": state, "109": status})
            device = SimpleNamespace(set_value=lambda dp, value: sent.append((dp, value)), close=lambda: None)
            with patch.dict(sys.modules, {"tinytuya": SimpleNamespace(Device=lambda *a, **kw: device)}), \
                 patch.object(local.time, "sleep"), patch.object(local, "read_local", side_effect=[before, before, after]):
                result = local.write_local(CONFIG, "switch", enabled)
            self.assertEqual(sent, [(140, enabled)])
            self.assertNotIn("140", result["dps"])
            self.assertEqual(result["dps"]["151"], DPS["151"])
            self.assertEqual(result["dps"]["152"], 16)

    def test_ack_mismatched_pair_and_stale_state_are_not_confirmation(self):
        for changes in ({}, {"101": 204}, {"109": "PAUSE"}, {"101": 500, "109": "FAULT"}):
            driver = SimpleNamespace(set_value=lambda *a: {}, close=lambda: None)
            with patch.dict(sys.modules, {"tinytuya": SimpleNamespace(Device=lambda *a, **kw: driver)}), \
                 patch.object(local.time, "sleep"), patch.object(local, "read_local", return_value=self.snapshot(**changes)):
                with self.assertRaisesRegex(local.LocalConnectionError, "local_command_unconfirmed"):
                    local.write_local(CONFIG, "switch", False)

    def test_safe_current_and_native_mode_preflight(self):
        with patch.object(local, "read_local", return_value=self.snapshot()):
            for current in (5, 17, 32, 6.5, True, float("nan")):
                with self.assertRaises(local.LocalConnectionError):
                    local.write_local(CONFIG, "charge_cur_set", current)
        with patch.object(local, "read_local", return_value=self.snapshot(**{"151": '{"m":1}'})):
            with self.assertRaisesRegex(local.LocalConnectionError, "local_immediate_mode_required"):
                local.write_local(CONFIG, "switch", True)

    def test_first_run_automatically_offers_full_panel(self):
        flow = Flow()
        with patch.object(flow_module, "read_local", return_value=self.snapshot()):
            result = asyncio.run(flow.async_step_local_manual(CREDENTIALS))
        self.assertEqual(result["step_id"], "local_confirm")
        self.assertEqual(flow._local_pending["local_control_profile"], local.PACKED_CONTROL_PROFILE)

    def test_options_keep_packed_profile_instead_of_forcing_split(self):
        schema = flow_module.local_schema(CONFIG, options=True)
        self.assertTrue(schema({"local_protocol": "3.5"})["enable_test_controls"])
        updated = []
        flow = flow_module.NativeLocalOptionsMixin()
        flow._config_entry = SimpleNamespace(data=CONFIG, options={}, entry_id="test-entry")
        async def execute(fn, *args): return fn(*args)
        async def reload(_): pass
        flow.hass = SimpleNamespace(async_add_executor_job=execute, config_entries=SimpleNamespace(
            async_update_entry=lambda entry, **kw: updated.append(kw), async_reload=reload))
        flow.async_abort = lambda **kw: kw
        with patch.object(flow_module, "read_local", return_value=self.snapshot()):
            result = asyncio.run(flow.async_step_local_connection({"enable_test_controls": True}))
        self.assertEqual(result["reason"], "local_updated")
        self.assertEqual(updated[0]["data"]["local_control_profile"], local.PACKED_CONTROL_PROFILE)
