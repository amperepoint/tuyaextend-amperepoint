from __future__ import annotations

import asyncio
import copy
import types
import unittest
from unittest.mock import AsyncMock, patch

from support import load_integration_module

usage = load_integration_module("usage_reporting")


class Store:
    def __init__(self, state=None):
        self.state = state

    async def async_load(self):
        return copy.deepcopy(self.state)

    async def async_save(self, state):
        self.state = copy.deepcopy(state)


class UsageTests(unittest.IsolatedAsyncioTestCase):
    async def test_offline_does_not_raise_and_attempts_are_bounded(self):
        store, send, sleep = Store(), AsyncMock(side_effect=OSError("offline")), AsyncMock()
        await usage.UsageReporter(store, send, sleep=sleep).run()
        self.assertEqual(send.await_count, 3)
        self.assertEqual(store.state["reported_versions"], [])
        self.assertGreater(store.state["retry_after"], 0)
        self.assertEqual([c.args[0] for c in sleep.await_args_list], [60, 3600, 21600])

    async def test_hung_server_times_out_without_acknowledging(self):
        async def hung(*_args):
            await asyncio.Event().wait()
        store = Store()
        with patch.object(usage, "REQUEST_TIMEOUT", 0.01):
            await asyncio.wait_for(usage.UsageReporter(store, hung, sleep=AsyncMock()).run(), 0.5)
        self.assertEqual(store.state["reported_versions"], [])

    async def test_same_version_once_across_restarts_and_identity_survives_update(self):
        store, send = Store(), AsyncMock(return_value=True)
        for version in ("1.0", "1.0", "1.1", "1.0"):
            await usage.UsageReporter(store, send, version=version, sleep=AsyncMock()).run()
        self.assertEqual(send.await_count, 2)
        self.assertEqual(send.await_args_list[0].args[0], send.await_args_list[1].args[0])
        self.assertEqual(store.state["reported_versions"], ["1.0", "1.1"])

    async def test_recovery_after_offline_marks_only_success(self):
        store, send = Store(), AsyncMock(side_effect=[False, True])
        await usage.UsageReporter(store, send, sleep=AsyncMock()).run()
        self.assertEqual(send.await_count, 2)
        self.assertEqual(store.state["reported_versions"], [usage.VERSION])

    async def test_storage_failure_cannot_escape_or_send_ephemeral_identity(self):
        for method in ("async_load", "async_save"):
            store, send = Store(), AsyncMock()
            setattr(store, method, AsyncMock(side_effect=OSError("disk unavailable")))
            await usage.UsageReporter(store, send, sleep=AsyncMock()).run()
            send.assert_not_awaited()

    async def test_corrupt_storage_is_not_replaced_with_new_identity(self):
        store, send = Store({"installation_id": "broken"}), AsyncMock()
        await usage.UsageReporter(store, send, sleep=AsyncMock()).run()
        send.assert_not_awaited()

    async def test_shutdown_cancels_pending_request(self):
        entered = asyncio.Event()
        async def waiting(*_args):
            entered.set()
            await asyncio.Event().wait()
        task = asyncio.create_task(usage.UsageReporter(Store(), waiting, sleep=AsyncMock()).run())
        await entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

    async def test_multiple_chargers_share_one_background_task_and_last_unload_cancels(self):
        tasks, unloads = [], []
        def background(coro, _name):
            task = asyncio.create_task(coro)
            tasks.append(task)
            return task
        hass = types.SimpleNamespace(data={}, state="running", async_create_background_task=background)
        for entry_id in ("a", "b"):
            entry = types.SimpleNamespace(entry_id=entry_id, async_on_unload=unloads.append)
            usage.register_entry(hass, entry)
        self.assertEqual(len(tasks), 1)
        # Setup returned synchronously, before the report or its initial delay ran.
        self.assertFalse(tasks[0].done())
        unloads[0]()
        self.assertEqual(tasks[0].cancelling(), 0)
        unloads[1]()
        with self.assertRaises(asyncio.CancelledError):
            await tasks[0]
        self.assertNotIn(usage.DATA_KEY, hass.data)

    async def test_disabled_reports_do_not_create_a_task_or_store(self):
        hass = types.SimpleNamespace(data={usage.ENABLED_KEY: False})
        usage.register_entry(hass, types.SimpleNamespace(entry_id="a"))
        self.assertNotIn(usage.DATA_KEY, hass.data)

    async def test_startup_waits_for_ha_started_and_unload_removes_listener(self):
        unsubscribe = unittest.mock.Mock()
        listen = unittest.mock.Mock(return_value=unsubscribe)
        background = unittest.mock.Mock()
        unloads = []
        hass = types.SimpleNamespace(data={}, state="starting",
            bus=types.SimpleNamespace(async_listen_once=listen), async_create_background_task=background)
        entry = types.SimpleNamespace(entry_id="a", async_on_unload=unloads.append)
        usage.register_entry(hass, entry)
        background.assert_not_called()
        self.assertEqual(listen.call_args.args[0], "homeassistant_started")
        unloads[0]()
        unsubscribe.assert_called_once()

    async def test_persisted_cooldown_prevents_restart_retry_storm(self):
        store = Store({"installation_id": "a" * 32, "reported_versions": [], "retry_after": 2000})
        sleep, send = AsyncMock(), AsyncMock(return_value=True)
        with patch.object(usage.time, "time", return_value=1000):
            await usage.UsageReporter(store, send, sleep=sleep).run()
        self.assertEqual([call.args[0] for call in sleep.await_args_list], [60, 1000])
