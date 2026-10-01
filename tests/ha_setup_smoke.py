"""Optional real-HA smoke test of the whole config-entry setup.

Home Assistant loads the integration from custom_components, with the frontend
and Lovelace, starting from a stored config entry - the same path as a real
installation. The entry has no source entities yet, the state in which HA 2025.3
failed on a panel argument it did not know. No charger connection.
Example: mount the repo at /work read-only and run python /work/tests/ha_setup_smoke.py.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch

from homeassistant import bootstrap, loader
from homeassistant.components import frontend
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import __version__
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

DOMAIN = "tuyaextend_amperepoint"
ENTRY_ID = "01SETUPSMOKE0000000000000"
PANEL = "amperepoint-panel"
SETTINGS = {
    "name": "AmperePoint",
    "session_energy_mode": "auto",
    "tariff_value": 1.2,
    "currency": "PLN",
    "complete_power_threshold_kw": 0.25,
    "complete_idle_minutes": 3,
}


class ErrorLog(logging.Handler):
    """Collect error records; HA logs failed platform setups without failing the entry."""

    def __init__(self) -> None:
        super().__init__(logging.ERROR)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        error = record.exc_info[1] if record.exc_info else None
        self.messages.append(f"{record.getMessage()} {error or ''}")


def store_entry(config: Path) -> None:
    # Oldest storage layout; every supported HA version migrates it on load.
    entry = {
        "entry_id": ENTRY_ID, "version": 1, "minor_version": 1, "domain": DOMAIN,
        "title": "AmperePoint", "data": {**SETTINGS, "model": "q11"},
        "options": {**SETTINGS, "model": "q_series"},
        "pref_disable_new_entities": False, "pref_disable_polling": False,
        "source": "user", "unique_id": None, "disabled_by": None,
    }
    storage = config / ".storage"
    storage.mkdir()
    (storage / "core.config_entries").write_text(json.dumps({
        "version": 1, "minor_version": 1, "key": "core.config_entries",
        "data": {"entries": [entry]},
    }))


async def main():
    logging.basicConfig(level=logging.ERROR)
    errors = ErrorLog()
    logging.getLogger().addHandler(errors)
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="amperepoint-setup-") as directory:
        config = Path(directory)
        shutil.copytree(root / "custom_components" / DOMAIN,
                        config / "custom_components" / DOMAIN)
        store_entry(config)
        hass = HomeAssistant(directory)
        loader.async_setup(hass)
        hass.config.skip_pip = True
        assert await bootstrap.async_from_config_dict({
            "homeassistant": {"name": "Setup smoke", "time_zone": "UTC"},
            "frontend": {},
            "lovelace": {},
        }, hass)
        await hass.async_start()
        await hass.async_block_till_done()
        print(f"HA {__version__} started", flush=True)
        try:
            entry = hass.config_entries.async_get_entry(ENTRY_ID)
            assert entry.state is ConfigEntryState.LOADED, entry.state
            panel = hass.data["frontend_panels"][PANEL]
            assert panel.sidebar_title, panel
            entities = er.async_entries_for_config_entry(er.async_get(hass), ENTRY_ID)
            assert entities, "no entities registered"
            print(f"Loaded: panel in sidebar, {len(entities)} entities", flush=True)

            assert await hass.config_entries.async_reload(ENTRY_ID)
            assert entry.state is ConfigEntryState.LOADED, entry.state
            print("Reload OK", flush=True)

            # Fail inside dashboard creation, after its storage object has
            # been constructed. Retrying must recover both platforms and the
            # frontend panel, not mistake partial setup for an existing panel.
            assert await hass.config_entries.async_unload(ENTRY_ID)
            frontend.async_remove_panel(hass, PANEL)
            hass.data[LOVELACE_DATA].dashboards.pop(PANEL)
            with patch.object(frontend, "async_register_built_in_panel",
                              side_effect=RuntimeError("simulated panel failure")):
                await hass.config_entries.async_setup(ENTRY_ID)
            assert entry.state is ConfigEntryState.SETUP_ERROR, entry.state
            assert ENTRY_ID not in hass.data[DOMAIN], "coordinator was not cleaned up"
            assert PANEL not in hass.data["frontend_panels"]
            assert PANEL not in hass.data[LOVELACE_DATA].dashboards, "partial dashboard remains"
            errors.messages.clear()
            assert await hass.config_entries.async_reload(ENTRY_ID)
            assert entry.state is ConfigEntryState.LOADED, entry.state
            assert hass.data["frontend_panels"][PANEL].sidebar_title
            assert PANEL in hass.data[LOVELACE_DATA].dashboards
            assert not errors.messages, errors.messages
            print("Recovery after a failed setup OK", flush=True)
            print(f"Setup smoke passed on HA {__version__}", flush=True)
        finally:
            await hass.async_stop()


asyncio.run(main())
