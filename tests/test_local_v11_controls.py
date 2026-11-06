"""Regression tests for PRIME firmware V11.22 (app panel 2.0), verified on hardware."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
from support import load_integration_module
from test_local_flow import Flow, CREDENTIALS, flow_module

local = load_integration_module("local_source")
DPS = json.loads((Path(__file__).resolve().parents[1] /
    "amperepoint/observations/prime-split-v11-22-20-charging-20261102.json").read_text(encoding="utf-8"))["dps"]
CONFIG = {**CREDENTIALS, "local_control_profile": local.V11_CONTROL_PROFILE}
V11_PID = "skkg3zksmiibll2r"


class V11DetectionTests(unittest.TestCase):
    def test_firmware_builds_of_the_family_match_including_app_suffix(self):
        for firmware in ("(V11.22.20)F2.0.6", "(V11.22.0)F2.0.3", "(V11.22.0)F2.0.3-1.6.83"):
            self.assertTrue(local.is_v11_firmware({"106": json.dumps({"fv": firmware})}), firmware)
        for firmware in ("(V7.0.0)F2.0.0", "(V9.1.0)F1.4.1", "(V11.23.0)F2.0.3", "", None):
            self.assertFalse(local.is_v11_firmware({"106": json.dumps({"fv": firmware})}), firmware)

    def test_partial_v11_read_is_accepted_by_firmware_or_product_id_only(self):
        no_telemetry = {k: v for k, v in DPS.items() if k not in ("102", "109")}
        self.assertEqual(local.validate_snapshot({"dps": no_telemetry})[1], "prime_split")
        update = {"153": "dlb: iget 0A->13A"}
        self.assertEqual(local.validate_snapshot({"dps": update}, V11_PID)[1], "prime_split")
        for product_id in (None, "gbmxngploofmhbjc"):
            with self.assertRaisesRegex(local.LocalConnectionError, "local_unsupported"):
                local.validate_snapshot({"dps": update}, product_id)

    def test_control_profile_requires_split_layout_and_reported_control_dps(self):
        self.assertEqual(local.detected_control_profile(DPS, "prime_split"), local.CONTROL_PROFILE)
        self.assertTrue(local.control_supported(CONFIG, DPS, "prime_split"))
        for changes in ({"152": None}, {"140": None}, {"150": 6.0}, {"152": True}, {"152": 5}):
            self.assertIsNone(local.detected_control_profile({**DPS, **changes}, "prime_split"))
        self.assertIsNone(local.detected_control_profile(DPS, "prime_packed"))
        old_split = {**DPS, "106": json.dumps({"fv": "(V7.0.0)F2.0.0"})}
        self.assertEqual(local.detected_control_profile(old_split, "prime_split"), local.CONTROL_PROFILE)

    def test_unsolicited_update_is_merged_with_the_next_read(self):
        reads = [{"dps": {"153": "dlb: iget 0A->13A"}}, {"dps": dict(DPS)}]
        calls = []
        class Device:
            def __init__(self, *args, **kwargs): pass
            def status(self):
                calls.append("status")
                return reads.pop(0)
            def close(self): pass
        with patch.dict(sys.modules, {"tinytuya": SimpleNamespace(Device=Device)}):
            result = local.read_local(CREDENTIALS)
        self.assertEqual(calls, ["status", "status"])
        self.assertEqual(result["family"], "prime_split")
        self.assertEqual(result["dps"]["109"], DPS["109"])

    def test_reads_stop_after_three_attempts(self):
        calls = []
        class Device:
            def __init__(self, *args, **kwargs): pass
            def status(self):
                calls.append("status")
                return {"dps": {"153": "dlb"}}
            def close(self): pass
        with patch.dict(sys.modules, {"tinytuya": SimpleNamespace(Device=Device)}):
            with self.assertRaisesRegex(local.LocalConnectionError, "local_unsupported"):
                local.read_local({**CREDENTIALS, "local_product_id": None})
        self.assertEqual(len(calls), local.SNAPSHOT_ATTEMPTS)


class V11ControlTests(unittest.TestCase):
    def snapshot(self, **changes):
        return dict(host=CONFIG["local_host"], dps={**DPS, **changes}, family="prime_split")

    def write(self, code, value, reads):
        sent = []
        device = SimpleNamespace(set_value=lambda dp, val: sent.append((dp, val)) or {}, close=lambda: None)
        with patch.dict(sys.modules, {"tinytuya": SimpleNamespace(Device=lambda *a, **kw: device)}), \
             patch.object(local.time, "sleep"), patch.object(local, "read_local", side_effect=reads):
            result = local.write_local(CONFIG, code, value)
        return sent, result

    def test_pause_and_resume_are_confirmed_by_reported_dp140(self):
        # Observed on (V11.22.20)F2.0.6: pause -> 101=204 PAUSE, resume -> 101=300,
        # and 101=370 while the vehicle draws current.
        running = self.snapshot(**{"101": 300, "109": "STATE_C", "140": True})
        paused = self.snapshot(**{"101": 204, "109": "PAUSE", "140": False})
        sent, result = self.write("switch", False, [running, paused])
        self.assertEqual(sent, [(140, False)])
        self.assertIs(result["dps"]["140"], False)
        for resumed in (running, self.snapshot(**{"101": 370, "109": "STATE_C", "140": True})):
            sent, result = self.write("switch", True, [paused, resumed])
            self.assertEqual(sent, [(140, True)])
            self.assertIs(result["dps"]["140"], True)

    def test_stale_or_paused_state_is_not_confirmation(self):
        running = self.snapshot(**{"101": 300, "140": True})
        for after, value in ((running, False), (self.snapshot(**{"101": 204, "140": True}), True)):
            before = self.snapshot(**{"101": 204, "140": False}) if value else running
            with self.assertRaisesRegex(local.LocalConnectionError, "local_command_unconfirmed"):
                self.write("switch", value, [before, after, after, after])

    def test_current_is_confirmed_by_dp150_and_capped_at_16_amps(self):
        sent, result = self.write("charge_cur_set", 12, [self.snapshot(), self.snapshot(**{"150": 12})])
        self.assertEqual(sent, [(150, 12)])
        self.assertEqual(result["dps"]["150"], 12)
        for value in (5, 17, 12.5):
            with self.assertRaisesRegex(local.LocalConnectionError, "local_current_out_of_range"):
                self.write("charge_cur_set", value, [self.snapshot()])

    def test_resume_requires_immediate_mode(self):
        scheduled = self.snapshot(**{"140": False, "151": json.dumps({"m": 1, "c": 16})})
        with self.assertRaisesRegex(local.LocalConnectionError, "local_immediate_mode_required"):
            self.write("switch", True, [scheduled])


class V11OnboardingTests(unittest.IsolatedAsyncioTestCase):
    async def test_tuya_import_of_v11_offers_full_controls(self):
        flow = Flow()
        snapshot = dict(host=CREDENTIALS["local_host"], dps=DPS, family="prime_split")
        with patch.object(flow_module, "read_local", return_value=snapshot):
            form = await flow.async_step_local_manual({**CREDENTIALS, "local_product_id": V11_PID})
        self.assertEqual(form["step_id"], "local_confirm")
        self.assertEqual(flow._local_pending["local_control_profile"], local.CONTROL_PROFILE)


if __name__ == "__main__":
    unittest.main()
