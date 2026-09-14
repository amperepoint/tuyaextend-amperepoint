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

from homeassistant import bootstrap, loader
from homeassistant.core import HomeAssistant
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder import statistics
from homeassistant.components.recorder.tasks import StatisticsTask
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.storage import Store
from homeassistant.const import __version__


async def main():
    # Load production modules without running the integration's setup and
    # optional charger dependencies. All HA classes below are real, not stubs.
    root = Path(__file__).resolve().parents[1]
    package_name = "amperepoint_energy_smoke"
    package = types.ModuleType(package_name)
    package.__path__ = [str(root / "custom_components" / "tuyaextend_amperepoint")]
    sys.modules[package_name] = package
    energy = importlib.import_module(f"{package_name}.energy")
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
            coordinator = DataUpdateCoordinator(hass, config_entry=None, logger=logging.getLogger(__name__), name="energy-smoke")
            coordinator.config_entry = types.SimpleNamespace(entry_id="energy-smoke", title="Energy smoke")
            coordinator.model = types.SimpleNamespace(name="Synthetic Q/PRIME")
            coordinator.data = {}
            desc = next(item for item in sensor.SENSORS if item.key == "charging_energy")
            entity = sensor.AmperePointSensor(coordinator, desc)
            entity.entity_id = "sensor.amperepoint_energy_smoke"
            meter = energy.ChargingEnergy()
            timestamp = datetime.now(UTC).timestamp()

            def update(value, offset):
                total = meter.update(energy.EnergySample("synthetic:dp1", "device_counter", value), timestamp + offset, 25)
                coordinator.async_set_updated_data({
                    "charging_energy_kwh": total,
                    "charging_energy_method": meter.method,
                    "charging_energy_quality": meter.quality,
                    "charging_energy_incomplete": meter.incomplete,
                })

            update(100, 0)
            await hass.data["sensor"].async_add_entities([entity])
            print("Sensor added", flush=True)
            await hass.async_block_till_done()
            state = hass.states.get(entity.entity_id)
            assert state.state == "0.0", state
            assert state.attributes["unit_of_measurement"] == "kWh", state
            assert state.attributes["device_class"] == "energy", state
            assert state.attributes["state_class"] == "total_increasing", state

            update(101, 3600)
            await hass.async_block_till_done()
            update(None, 3615)
            await hass.async_block_till_done()
            assert hass.states.get(entity.entity_id).state == "unavailable"
            update(102, 7200)
            await hass.async_block_till_done()
            assert float(hass.states.get(entity.entity_id).state) == 2

            store = Store(hass, 1, "amperepoint_energy_smoke")
            await store.async_save(meter.dump())
            meter = energy.ChargingEnergy(await store.async_load())
            update(102, 7215)
            await hass.async_block_till_done()
            assert float(hass.states.get(entity.entity_id).state) == 2
            update(0, 7300)
            await hass.async_block_till_done()
            update(103, 7315)  # implausible stale pre-reset packet
            await hass.async_block_till_done()
            assert hass.states.get(entity.entity_id).state == "unavailable"
            update(1, 10900)
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
                  "unavailable handling; Store round-trip; reset/stale packet; Recorder sum=3 kWh")
        except Exception:
            logging.exception("Real HA energy smoke failed")
            raise
        finally:
            await hass.async_stop(force=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
