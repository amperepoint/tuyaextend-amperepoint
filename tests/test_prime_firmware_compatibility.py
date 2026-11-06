"""PRIME firmware updates must not disable an unchanged LAN control contract.

These are protocol simulations derived from existing hardware captures, not a
claim that the customer's V10 firmware has been exercised on physical hardware.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
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
ROOT = Path(__file__).resolve().parents[1]
SPLIT = json.loads((ROOT / "amperepoint/observations/prime-split-tester-20260911.json").read_text(encoding="utf-8"))["dps"]
PACKED = json.loads((ROOT / "amperepoint/observations/prime-packed-tester-20260911.json").read_text(encoding="utf-8"))["dps"]


@contextmanager
def charger(dps, *, acknowledge_only=False):
    """Exercise real transport/preflight/readback with an in-memory device."""
    state, commands = deepcopy(dps), []

    class Device:
        def __init__(self, *args, **kwargs):
            pass

        def status(self):
            return {"dps": deepcopy(state)}

        def set_value(self, dp, value):
            commands.append((dp, value))
            if not acknowledge_only:
                if dp == 140:
                    if "140" in state:
                        state["140"] = value
                        state["101"] = 370 if value else 204
                        state["109"] = "STATE_C" if value else "PAUSE"
                    else:
                        state["101"] = 300 if value else 204
                        state["109"] = "WORKING" if value else "PAUSE"
                else:
                    state[str(dp)] = value
            return {}  # An ACK is deliberately distinct from the next status.

        def close(self):
            pass

    with patch.dict(sys.modules, {"tinytuya": SimpleNamespace(Device=Device)}), \
            patch.object(local.time, "sleep"):
        yield state, commands


class FirmwareCompatibilityTests(unittest.IsolatedAsyncioTestCase):
    def split(self, firmware="(V10.22.20)F2.0.5"):
        return {**deepcopy(SPLIT), "140": True, "150": 16,
                "106": json.dumps({"fv": firmware})}

    async def test_customer_firmware_can_onboard_and_control_with_unchanged_dps(self):
        dps = {**self.split(), "160": {"new_feature": 1}}
        with charger(dps) as (state, commands):
            flow = Flow()
            form = await flow.async_step_local_manual(CREDENTIALS)
            self.assertEqual(form["step_id"], "local_confirm")
            entry = await flow.async_step_local_confirm({})
            self.assertEqual(commands, [])  # Onboarding never sends a command.
            for code, value in (("charge_cur_set", 12), ("switch", False), ("switch", True)):
                result = local.write_local(entry["data"], code, value)
            self.assertEqual(commands, [(150, 12), (140, False), (140, True)])
            self.assertEqual(result["dps"]["101"], 370)
            for dp in ("151", "152", "160"):
                self.assertEqual(state[dp], dps[dp])

    async def test_future_firmware_and_missing_version_do_not_block_same_contract(self):
        for version in ("(V12.99.1)F3.2.1", "", None):
            with self.subTest(version=version), charger(self.split(version)):
                flow = Flow()
                form = await flow.async_step_local_manual(CREDENTIALS)
                self.assertEqual(form["step_id"], "local_confirm")
        dps = self.split()
        dps.pop("106")
        with charger(dps):
            form = await Flow().async_step_local_manual(CREDENTIALS)
            self.assertEqual(form["step_id"], "local_confirm")

    async def test_packed_firmware_update_retains_write_only_switch_support(self):
        dps = {**PACKED, "106": json.dumps({"fv": "(V9.9.9)F2.1.0"}), "180": "new"}
        with charger(dps) as (state, commands):
            flow = Flow()
            form = await flow.async_step_local_manual(CREDENTIALS)
            self.assertEqual(form["step_id"], "local_confirm")
            entry = await flow.async_step_local_confirm({})
            for code, value in (("charge_cur_set", 8), ("switch", False), ("switch", True)):
                local.write_local(entry["data"], code, value)
            self.assertEqual(commands, [(150, 8), (140, False), (140, True)])
            self.assertNotIn("140", state)
            self.assertEqual(state["180"], "new")

    async def test_known_v11_partial_telemetry_keeps_existing_control_support(self):
        dps = self.split("(V11.22.20)F2.0.6")
        dps.pop("102")
        with charger(dps) as (_, commands):
            flow = Flow()
            form = await flow.async_step_local_manual(CREDENTIALS)
            self.assertEqual(form["step_id"], "local_confirm")
            entry = await flow.async_step_local_confirm({})
            local.write_local(entry["data"], "charge_cur_set", 8)
            self.assertEqual(commands, [(150, 8)])

    async def test_existing_read_only_entry_can_enable_controls_in_options(self):
        updated = []
        options = flow_module.NativeLocalOptionsMixin()
        options._config_entry = SimpleNamespace(
            data={**CREDENTIALS, "local_control_profile": None}, options={}, entry_id="test-entry")

        async def execute(fn, *args):
            return fn(*args)

        async def reload(entry_id):
            pass

        options.hass = SimpleNamespace(async_add_executor_job=execute,
            config_entries=SimpleNamespace(async_update_entry=lambda entry, **kw: updated.append(kw),
                                            async_reload=reload))
        options.async_abort = lambda **kw: kw
        with charger(self.split()) as (_, commands):
            result = await options.async_step_local_connection({"enable_test_controls": True})
        self.assertEqual(result["reason"], "local_updated")
        self.assertEqual(updated[0]["data"]["local_control_profile"], local.CONTROL_PROFILE)
        self.assertEqual(commands, [])

    def test_existing_v11_profile_survives_firmware_changes_without_reconfiguration(self):
        config = {**CREDENTIALS, "local_control_profile": local.V11_CONTROL_PROFILE}
        with charger(self.split()) as (_, commands):
            local.write_local(config, "charge_cur_set", 8)
        self.assertEqual(commands, [(150, 8)])

    def test_explicit_read_only_and_incomplete_contract_never_send_commands(self):
        enabled = {**CREDENTIALS, "local_control_profile": local.CONTROL_PROFILE}
        for config, changes in ((CREDENTIALS, {}), (enabled, {"140": "true"}),
                                (enabled, {"150": None}), (enabled, {"152": True})):
            with self.subTest(changes=changes), charger({**self.split(), **changes}) as (_, commands):
                with self.assertRaisesRegex(local.LocalConnectionError, "local_control_not_verified"):
                    local.write_local(config, "charge_cur_set", 8)
                self.assertEqual(commands, [])

    def test_unconfirmed_command_and_invalid_current_still_fail_on_customer_firmware(self):
        config = {**CREDENTIALS, "local_control_profile": local.CONTROL_PROFILE}
        with charger(self.split(), acknowledge_only=True) as (_, commands):
            with self.assertRaisesRegex(local.LocalConnectionError, "local_command_unconfirmed"):
                local.write_local(config, "charge_cur_set", 8)
            self.assertEqual(commands, [(150, 8)])
        with charger(self.split()) as (_, commands):
            for current in (5, 17, 12.5, True, float("nan"), float("inf")):
                with self.subTest(current=current), self.assertRaises(local.LocalConnectionError):
                    local.write_local(config, "charge_cur_set", current)
            self.assertEqual(commands, [])

    def test_conflicting_state_is_not_confirmed_as_a_start(self):
        config = {**CREDENTIALS, "local_control_profile": local.CONTROL_PROFILE}
        for changes in ({"101": 204}, {"109": "PAUSE"}, {"109": "FAULT"}, {"101": None}):
            before = {"host": CREDENTIALS["local_host"], "dps": self.split(), "family": "prime_split"}
            after = {**before, "dps": {**before["dps"], "101": 370, **changes}}
            device = SimpleNamespace(set_value=lambda *args: {}, close=lambda: None)
            with self.subTest(changes=changes), \
                    patch.dict(sys.modules, {"tinytuya": SimpleNamespace(Device=lambda *args, **kw: device)}), \
                    patch.object(local.time, "sleep"), \
                    patch.object(local, "read_local", side_effect=[before, after, after, after]):
                with self.assertRaisesRegex(local.LocalConnectionError, "local_command_unconfirmed"):
                    local.write_local(config, "switch", True)
