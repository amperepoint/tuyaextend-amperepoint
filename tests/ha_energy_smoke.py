"""Optional real-HA smoke test; run in an isolated Home Assistant container.

This script uses temporary configuration/database storage, synthetic energy
readings and no charger connection. It is separate from the stub unit tests.
Example: mount the repo at /work read-only and run python /work/tests/ha_energy_smoke.py.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import importlib
import logging
from pathlib import Path
import sys
import tempfile
import types
from unittest.mock import patch

from homeassistant import bootstrap, loader
from homeassistant.core import HomeAssistant
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder import statistics
from homeassistant.components.recorder.tasks import StatisticsTask
from homeassistant.const import __version__
from homeassistant.util.file import WriteError


async def main():
    # Load production modules without running the integration's setup and
    # optional charger dependencies. All HA classes below are real, not stubs.
    root = Path(__file__).resolve().parents[1]
    package_name = "amperepoint_energy_smoke"
    package = types.ModuleType(package_name)
    package.__path__ = [str(root / "custom_components" / "tuyaextend_amperepoint")]
    sys.modules[package_name] = package
    coordinator_module = importlib.import_module(f"{package_name}.coordinator")
    sensor = importlib.import_module(f"{package_name}.sensor")

    with tempfile.TemporaryDirectory(prefix="amperepoint-energy-") as directory:
        hass = HomeAssistant(directory)
        loader.async_setup(hass)
        hass.config.skip_pip = True
        assert await bootstrap.async_from_config_dict({
            "homeassistant": {"name": "Energy smoke", "time_zone": "UTC"},
            "recorder": {"db_url": f"sqlite:///{directory}/smoke.db", "commit_interval": 1, "auto_purge": False},
            "sensor": [],
        }, hass)
        await hass.async_start()
        print("HA started", flush=True)
        try:
            entry = types.SimpleNamespace(entry_id="energy-smoke", title="Energy smoke",
                data={"source_total_energy": "sensor.synthetic_source"}, options={},
                pref_disable_polling=True, async_on_unload=lambda fn: None)
            coordinator = coordinator_module.AmperePointCoordinator(hass, entry)
            coordinator.data = {}
            desc = next(item for item in sensor.SENSORS if item.key == "charging_energy")
            entity = sensor.AmperePointSensor(coordinator, desc)
            entity.entity_id = "sensor.amperepoint_energy_smoke"
            timestamp = datetime.now(UTC).timestamp()

            async def update(value, offset):
                hass.states.async_set("sensor.synthetic_source", value if value is not None else "unavailable",
                                      {"unit_of_measurement": "kWh"})
                # Only advance the integration's sample clock. Patching HA's
                # shared dt module would also move Recorder's event timestamps.
                with patch.object(coordinator_module, "dt_util", types.SimpleNamespace(
                    utcnow=lambda: datetime.fromtimestamp(timestamp + offset, UTC)
                )):
                    data = await coordinator._async_update_data()
                # Read the actual file before publishing, not a Store cache.
                assert coordinator._store._read_checkpoint()["data"]["charging_energy"] == coordinator._charging_energy.dump()
                coordinator.async_set_updated_data(data)

            await update(100, 0)
            await hass.data["sensor"].async_add_entities([entity])
            print("Sensor added", flush=True)
            await hass.async_block_till_done()
            state = hass.states.get(entity.entity_id)
            assert state.state == "0.0", state
            assert state.attributes["unit_of_measurement"] == "kWh", state
            assert state.attributes["device_class"] == "energy", state
            assert state.attributes["state_class"] == "total_increasing", state

            await update(101, 3600)
            await hass.async_block_till_done()
            # Exercise HA Store's real error-swallowing behavior. The wrapper
            # must detect the failed write before the sensor can publish 1.1.
            async def failed_write(*_args):
                raise WriteError("synthetic disk failure (expected by smoke test)")

            with patch.object(coordinator._store, "_async_write_data", side_effect=failed_write):
                try:
                    await update(101.1, 3615)
                except coordinator_module.UpdateFailed:
                    pass
                else:
                    raise AssertionError("Uncommitted energy was published")
            assert float(hass.states.get(entity.entity_id).state) == 1
            assert coordinator._store._read_checkpoint()["data"]["charging_energy"]["total"] == 1
            await update(None, 3630)
            await hass.async_block_till_done()
            assert hass.states.get(entity.entity_id).state == "unavailable"
            await update(102, 7200)
            await hass.async_block_till_done()
            assert float(hass.states.get(entity.entity_id).state) == 2

            # Reload the production coordinator immediately, without a sleep or
            # explicit test-only save (the old test hid the delayed-write bug).
            await coordinator.async_prepare_unload()
            restored = coordinator_module.AmperePointCoordinator(hass, entry)
            await restored.async_load_state()
            coordinator._charging_energy = restored._charging_energy
            coordinator._store = restored._store
            coordinator._unloading = False
            await update(102, 7215)
            await hass.async_block_till_done()
            assert float(hass.states.get(entity.entity_id).state) == 2
            await update(0, 7300)
            await hass.async_block_till_done()
            await update(103, 7315)  # implausible stale pre-reset packet
            await hass.async_block_till_done()
            assert hass.states.get(entity.entity_id).state == "unavailable"
            await update(1, 10900)
            await hass.async_block_till_done()
            assert float(hass.states.get(entity.entity_id).state) == 3

            recorder = get_instance(hass)
            await recorder.async_block_till_done()
            start = datetime.fromtimestamp(timestamp, UTC).replace(second=0, microsecond=0)
            start -= timedelta(minutes=start.minute % 5)
            recorder.queue_task(StatisticsTask(start, False))
            await recorder.async_block_till_done()
            await hass.async_add_executor_job(recorder.block_till_done)
            rows = await recorder.async_add_executor_job(
                statistics.statistics_during_period, hass, start, start + timedelta(minutes=5),
                {entity.entity_id}, "5minute", None, {"state", "sum"},
            )
            assert rows.get(entity.entity_id), rows
            row = rows[entity.entity_id][-1]
            assert row["sum"] == 3, row
            assert row["state"] == 3, row
            print(f"PASS: HA {__version__}: real SensorEntity kWh/energy/total_increasing; "
                  "production coordinator/checkpoints/reload; reset/stale packet; Recorder sum=3 kWh")
        except Exception:
            logging.exception("Real HA energy smoke failed")
            raise
        finally:
            await hass.async_stop(force=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
