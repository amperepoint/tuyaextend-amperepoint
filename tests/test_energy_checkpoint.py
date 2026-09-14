"""Regression coverage for publish-before-checkpoint and HA constructor APIs."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import load_integration_module, _Store
import test_energy as energy_tests

state = energy_tests.state

coordinator = load_integration_module("coordinator")
storage = load_integration_module("energy_store")
const = load_integration_module("const")


class CheckpointTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.states = {"sensor.energy": state(100, unit_of_measurement="kWh")}
        self.config = {const.CONF_SOURCE_TOTAL_ENERGY: "sensor.energy"}
        self.obj = energy_tests.CoordinatorPipelineTests().make(self.config, self.states)
        await self.update(100, 100)
        await self.update(100.1, 130)

    async def update(self, value, timestamp):
        self.states["sensor.energy"] = state(value, unit_of_measurement="kWh")
        with patch.object(coordinator.dt_util, "utcnow", return_value=datetime.fromtimestamp(timestamp, UTC)):
            result = await self.obj._async_update_data()
        self.obj.data = result
        return result

    async def test_blocked_write_never_publishes_ahead_of_disk(self):
        entered, release = asyncio.Event(), asyncio.Event()
        store = self.obj._store

        async def save(data):
            entered.set()
            await release.wait()
            store._data = data

        with patch.object(store, "async_save", side_effect=save):
            refresh = asyncio.create_task(self.update(100.2, 160))
            await entered.wait()
            self.assertEqual(self.obj.data["charging_energy_kwh"], 0.1)
            self.assertAlmostEqual(store._data["charging_energy"]["total"], 0.1)
            # A process crash here can only restore the last published .1,
            # never the former .2 -> .1 rollback that corrupts HA's sum.
            restored = energy_tests.CoordinatorPipelineTests().make(self.config, self.states)
            restored._store._data = json.loads(json.dumps(store._data))
            await restored.async_load_state()
            self.assertAlmostEqual(restored._charging_energy.total, 0.1)
            release.set()
            self.assertEqual((await refresh)["charging_energy_kwh"], 0.2)
        self.assertAlmostEqual(store._data["charging_energy"]["total"], 0.2)
        self.assertEqual(store._data["charging_energy"]["baseline"], 100.2)

    async def test_failed_write_is_unavailable_not_a_new_meter_state(self):
        with patch.object(self.obj._store, "async_save", side_effect=storage.EnergySaveError("disk full")):
            with self.assertRaises(coordinator.UpdateFailed):
                await self.update(100.2, 160)
        self.assertEqual(self.obj.data["charging_energy_kwh"], 0.1)
        self.assertAlmostEqual(self.obj._store._data["charging_energy"]["total"], 0.1)
        # Keep the uncommitted observed delta for retry, even across a reset.
        self.assertEqual((await self.update(0, 190))["charging_energy_kwh"], 0.2)
        self.assertAlmostEqual(self.obj._store._data["charging_energy"]["total"], 0.2)
        self.assertEqual((await self.update(0.1, 220))["charging_energy_kwh"], 0.3)

    async def test_cancelled_write_drains_before_reload_can_load(self):
        entered, release = asyncio.Event(), asyncio.Event()
        disk = self.obj._store
        verified = storage.EnergyStore(None, 1, "synthetic")

        async def write_and_verify(data):
            entered.set()
            await release.wait()
            await disk.async_save(data)

        self.obj._store = verified
        with patch.object(verified, "_async_save_and_verify", side_effect=write_and_verify):
            refresh = asyncio.create_task(self.update(100.2, 160))
            await entered.wait()
            refresh.cancel()
            await asyncio.sleep(0)
            refresh.cancel()  # even repeated cancellation must drain the writer
            unload = asyncio.create_task(self.obj.async_prepare_unload())
            await asyncio.sleep(0)
            self.assertFalse(refresh.done())
            self.assertFalse(unload.done())
            self.assertEqual(self.obj.data["charging_energy_kwh"], 0.1)
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await refresh
            await unload
        restored = energy_tests.CoordinatorPipelineTests().make(self.config, self.states)
        restored._store = disk
        await restored.async_load_state()
        self.states["sensor.energy"] = state(0)
        with patch.object(coordinator.dt_util, "utcnow", return_value=datetime.fromtimestamp(190, UTC)):
            result = await restored._async_update_data()
        self.assertEqual(result["charging_energy_kwh"], 0.2)
        with self.assertRaises(coordinator.UpdateFailed):
            await self.obj._async_update_data()

    async def test_queued_refresh_cannot_overtake_checkpoint(self):
        entered, release = asyncio.Event(), asyncio.Event()
        store = self.obj._store
        saved = []

        async def save(data):
            if not saved:
                entered.set()
                await release.wait()
            saved.append(data["charging_energy"]["total"])
            store._data = data

        self.states["sensor.energy"] = state(100.2)
        with patch.object(store, "async_save", side_effect=save), patch.object(
            coordinator.dt_util, "utcnow", side_effect=[datetime.fromtimestamp(t, UTC) for t in (160, 190)]
        ):
            first = asyncio.create_task(self.obj._async_update_data())
            await entered.wait()
            self.states["sensor.energy"] = state(100.3)
            second = asyncio.create_task(self.obj._async_update_data())
            await asyncio.sleep(0)
            self.assertFalse(second.done())
            release.set()
            self.assertEqual((await first)["charging_energy_kwh"], 0.2)
            self.assertEqual((await second)["charging_energy_kwh"], 0.3)
        self.assertEqual([round(n, 2) for n in saved], [0.2, 0.3])


class VerifiedStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "checkpoint"

        async def executor(fn, *args):
            return fn(*args)

        self.store = storage.EnergyStore(None, 1, "synthetic")
        self.store.path = str(self.path)
        self.store.hass = types.SimpleNamespace(state=storage.CoreState.running, async_add_executor_job=executor)

    async def test_logged_write_failure_detected_from_actual_file_not_pending_cache(self):
        self.path.write_text(json.dumps({"data": {"total": 0.1}}), encoding="utf-8")
        # The normal HA Store swallows write errors; our stub likewise returns
        # normally and exposes .2 via async_load, but the disk still holds .1.
        with self.assertRaises(storage.EnergySaveError):
            await self.store.async_save({"total": 0.2})
        self.assertEqual(await self.store.async_load(), {"total": 0.2})

    async def test_success_requires_matching_readback(self):
        self.path.write_text(json.dumps({"data": {"total": 0.2}}), encoding="utf-8")
        await self.store.async_save({"total": 0.2})

    async def test_missing_or_corrupt_file_fails_closed(self):
        for content in (None, "{"):
            if content is not None:
                self.path.write_text(content, encoding="utf-8")
            with self.assertRaises(storage.EnergySaveError):
                await self.store.async_save({"total": 0.2})

    async def test_shutdown_cannot_defer_a_checkpoint_and_call_it_success(self):
        self.store.hass.state = storage.CoreState.stopping
        with patch.object(_Store, "async_save", new_callable=AsyncMock) as save:
            with self.assertRaises(storage.EnergySaveError):
                await self.store.async_save({"total": 0.2})
            save.assert_not_awaited()


class CoordinatorCompatibilityTests(unittest.TestCase):
    def test_minimum_ha_signature_does_not_receive_config_entry(self):
        def old_init(instance, hass, logger, *, name, update_interval=None, always_update=True):
            instance.hass = hass

        with patch.object(coordinator.DataUpdateCoordinator, "__init__", old_init):
            obj = energy_tests.CoordinatorPipelineTests().make({}, {})
        self.assertEqual(obj.config_entry.entry_id, "test-entry")

    def test_current_ha_receives_the_explicit_config_entry(self):
        received = []

        def new_init(instance, hass, logger, *, config_entry, name, update_interval=None):
            instance.hass = hass
            received.append(config_entry)

        with patch.object(coordinator.DataUpdateCoordinator, "__init__", new_init):
            obj = energy_tests.CoordinatorPipelineTests().make({}, {})
        self.assertEqual(received, [obj.config_entry])

    def test_unrelated_constructor_typeerror_is_not_hidden_by_retry(self):
        def broken_init(instance, hass, logger, *, config_entry, name, update_interval=None):
            raise TypeError("unrelated constructor failure")

        with patch.object(coordinator.DataUpdateCoordinator, "__init__", broken_init):
            with self.assertRaisesRegex(TypeError, "unrelated"):
                energy_tests.CoordinatorPipelineTests().make({}, {})
