"""Native HA lifecycle smoke test, run separately from the lightweight stubs.

Run with Home Assistant installed: python tests/usage_ha_runtime.py
"""

import asyncio
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from homeassistant.core import CoreState, HomeAssistant
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from custom_components.tuyaextend_amperepoint import CONFIG_SCHEMA, usage_reporting as usage


class NativeLifecycleTest(unittest.IsolatedAsyncioTestCase):
    async def test_offline_report_does_not_hold_up_ha_startup(self):
        with tempfile.TemporaryDirectory() as directory:
            hass = HomeAssistant(directory)
            hass.state = CoreState.starting
            unloads = []
            entered = asyncio.Event()

            async def hung_server(*_args):
                entered.set()
                await asyncio.Event().wait()

            with patch.object(usage, "START_DELAY", 0), patch.object(usage, "_send", hung_server):
                entry = SimpleNamespace(entry_id="charger-a", async_on_unload=unloads.append)
                usage.register_entry(hass, entry)
                self.assertIsNone(hass.data[usage.DATA_KEY].task)
                hass.state = CoreState.running
                hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
                await asyncio.wait_for(entered.wait(), 2)
                # This is HA's real readiness wait. The network task is still hung.
                await asyncio.wait_for(hass.async_block_till_done(), 0.5)
                task = hass.data[usage.DATA_KEY].task
                self.assertFalse(task.done())
                unloads[0]()
                with self.assertRaises(asyncio.CancelledError):
                    await task
                await hass.async_block_till_done()

    async def test_reporting_can_be_disabled_in_yaml(self):
        config = CONFIG_SCHEMA({usage.DOMAIN: {"usage_reporting": False}})
        self.assertFalse(config[usage.DOMAIN]["usage_reporting"])


if __name__ == "__main__":
    unittest.main()
