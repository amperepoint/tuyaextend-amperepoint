from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import load_integration_module

local = load_integration_module("local_source")
coordinator = load_integration_module("coordinator")
FIXTURE = json.loads((Path(__file__).resolve().parents[1] /
    "amperepoint/observations/prime-split-tester-20260911.json").read_text(encoding="utf-8"))
CONFIG = {"local_device_id": "test-device", "local_key": "0123456789abcdef",
          "local_host": "192.168.0.154", "local_protocol": "3.5"}


class LocalSourceTests(unittest.TestCase):
    def test_supported_snapshot_filters_unreviewed_and_card_data(self):
        dps, family = local.validate_snapshot({"dps": {**FIXTURE["dps"], "112": "private-card-data", "999": "unknown"}})
        self.assertEqual(family, "prime_split")
        self.assertNotIn("112", dps)
        self.assertNotIn("999", dps)

    def test_unknown_devices_and_authentication_errors_are_rejected(self):
        for value in ({"dps": {"1": True}}, {"Error": "secret response", "Err": "914"}, None):
            with self.subTest(value=value), self.assertRaises(local.LocalConnectionError) as error:
                local.validate_snapshot(value)
            self.assertNotIn("secret", str(error.exception))

    def test_connection_always_closes_and_only_status_is_called(self):
        calls = []
        class Device:
            def __init__(self, *args, **kwargs):
                calls.append("connect")
                self.kwargs = kwargs
            def status(self):
                calls.append("status")
                return {"dps": FIXTURE["dps"]}
            def close(self):
                calls.append("close")
        with patch.dict(sys.modules, {"tinytuya": SimpleNamespace(Device=Device)}):
            result = local.read_local(CONFIG)
        self.assertEqual(calls, ["connect", "status", "close"])
        self.assertEqual(result["family"], "prime_split")

    def test_socket_error_is_sanitized_and_closed(self):
        closed = []
        class Device:
            def __init__(self, *args, **kwargs): pass
            def status(self): raise RuntimeError("key=secret")
            def close(self): closed.append(True)
        with patch.dict(sys.modules, {"tinytuya": SimpleNamespace(Device=Device)}):
            with self.assertRaisesRegex(local.LocalConnectionError, "^local_cannot_connect$"):
                local.read_local(CONFIG)
        self.assertEqual(closed, [True])

    def test_missing_ip_discovers_before_reading(self):
        device = SimpleNamespace(status=lambda: {"dps": FIXTURE["dps"]}, close=lambda: None)
        with patch.dict(sys.modules, {"tinytuya": SimpleNamespace(Device=lambda *a, **k: device)}), \
             patch.object(local, "discover_host", return_value="192.168.0.154") as discover:
            result = local.read_local({**CONFIG, "local_host": ""})
        self.assertEqual(result["host"], "192.168.0.154")
        discover.assert_called_once_with(CONFIG["local_device_id"])

    def test_invalid_hosts_and_keys_do_not_connect(self):
        for host in ("8.8.8.8", "localhost", "127.0.0.1", "0.0.0.0", "224.0.0.1"):
            with self.subTest(host=host), self.assertRaises(local.LocalConnectionError):
                local.validate_credentials({**CONFIG, "local_host": host})
        with self.assertRaises(local.LocalConnectionError):
            local.validate_credentials({**CONFIG, "local_key": "short"})

    def test_disconnect_sets_unavailable_and_recovery_persists_ip(self):
        updates = []
        async def execute(fn, *args): return fn(*args)
        hass = SimpleNamespace(async_add_executor_job=execute,
                               config_entries=SimpleNamespace(async_update_entry=lambda *a, **kw: updates.append(kw)))
        entry = SimpleNamespace(data=dict(CONFIG), options={})
        source = local.NativeLocalSource(hass, entry)
        with patch.object(local, "read_local", return_value={"host": CONFIG["local_host"], "dps": FIXTURE["dps"], "family": "prime_split"}):
            asyncio.run(source.async_refresh())
        self.assertTrue(source.available)
        with patch.object(local, "read_local", side_effect=local.LocalConnectionError("local_cannot_connect")):
            with self.assertRaises(local.LocalConnectionError): asyncio.run(source.async_refresh())
        self.assertFalse(source.available)
        source._next_discovery = 0
        with patch.object(local, "read_local", side_effect=[local.LocalConnectionError("local_cannot_connect"),
             {"host": "192.168.0.155", "dps": FIXTURE["dps"], "family": "prime_split"}]):
            asyncio.run(source.async_refresh())
        self.assertTrue(source.available)
        self.assertEqual(updates[-1]["data"]["local_host"], "192.168.0.155")

    def test_all_coordinator_writes_are_blocked_even_with_old_mappings(self):
        instance = object.__new__(coordinator.AmperePointCoordinator)
        instance.native_source = local.NativeLocalSource(None, SimpleNamespace(data=CONFIG, options={}))
        for method, value in (("async_set_charging", True), ("async_set_current_limit", 16),
                              ("async_set_work_mode", "charge_now"), ("async_set_target_energy", 5)):
            with self.subTest(method=method), self.assertRaises(Exception) as err:
                asyncio.run(getattr(instance, method)(value))
            self.assertIn("read-only", str(err.exception))
        self.assertFalse(instance.native_source.writable("switch"))

