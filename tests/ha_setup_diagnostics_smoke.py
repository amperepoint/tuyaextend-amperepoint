"""Real HA config flow + signed HTTP download; synthetic device, no LAN writes."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from aiohttp import ClientSession
from homeassistant import bootstrap, loader
from homeassistant.core import HomeAssistant
from homeassistant.const import __version__

DOMAIN = "tuyaextend_amperepoint"


async def main():
    logging.basicConfig(level=logging.ERROR)
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="amperepoint-diagnostics-") as directory:
        config = Path(directory)
        shutil.copytree(root / "custom_components" / DOMAIN, config / "custom_components" / DOMAIN)
        hass = HomeAssistant(directory)
        loader.async_setup(hass)
        hass.config.skip_pip = True
        assert await bootstrap.async_from_config_dict({
            "homeassistant": {"name": "Diagnostics smoke", "time_zone": "UTC"},
            "http": {"server_host": "127.0.0.1", "server_port": 8127},
            "frontend": {}, "lovelace": {},
        }, hass)
        await hass.async_start()
        await hass.async_block_till_done()
        print(f"HA {__version__}: isolated HTTP server started", flush=True)
        try:
            response = {"dps": {"102": '{"p":0,"e":0,"t":30,"L":[]}',
                                "112": "PRIVATE_CARD_DATA"}}
            calls = []
            class Device:
                def __init__(self, *args, **kwargs): pass
                def status(self):
                    calls.append("status")
                    return response
                def close(self): calls.append("close")
            with patch.dict(sys.modules, {"tinytuya": SimpleNamespace(Device=Device)}):
                result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
                flow_id = result["flow_id"]
                result = await hass.config_entries.flow.async_configure(flow_id, {"next_step_id": "local"})
                result = await hass.config_entries.flow.async_configure(flow_id, {"next_step_id": "local_manual"})
                assert result["step_id"] == "local_manual", result
                values = {"name": "Synthetic PRIME", "local_device_id": "PRIVATE_DEVICE_ID",
                          "local_key": "PRIVATE_KEY_1234", "local_host": "192.168.0.20", "local_protocol": "3.5"}
                assert len(values["local_key"]) == 16
                result = await hass.config_entries.flow.async_configure(flow_id, values)
                assert result["step_id"] == "local_manual_error", result
                assert result["errors"]["base"] == "local_unsupported", result
                # An incomplete answer is re-read, a bounded number of times, on one device.
                from custom_components.tuyaextend_amperepoint.local_source import SNAPSHOT_ATTEMPTS
                assert calls == ["status"] * SNAPSHOT_ATTEMPTS + ["close"], calls
                assert not hass.config_entries.async_entries(DOMAIN)
                path = result["description_placeholders"]["diagnostic_url"]
                async with ClientSession() as client:
                    async with client.get("http://127.0.0.1:8127" + path.split("?")[0]) as download:
                        assert download.status == 401, download.status
                    async with client.get("http://127.0.0.1:8127" + path) as download:
                        assert download.status == 200, download.status
                        assert "attachment" in download.headers["Content-Disposition"]
                        assert download.headers["Cache-Control"] == "no-store"
                        text = await download.text()
                        report = json.loads(text)
                        assert report["snapshot"]["checks"]["dp109_present"] is False
                        for secret in (*values.values(), "PRIVATE_CARD_DATA"):
                            if secret == "3.5": continue
                            assert secret not in text
                    async with client.get("http://127.0.0.1:8127" + path + "tampered") as download:
                        assert download.status == 401
                    from custom_components.tuyaextend_amperepoint.setup_diagnostics_download import DATA_KEY
                    hass.data[DATA_KEY].reports.clear()
                    async with client.get("http://127.0.0.1:8127" + path) as download:
                        assert download.status == 404
                print("Failed setup: downloadable JSON, secret redaction, auth, signature and expiry OK", flush=True)
                response["dps"]["109"] = "STATE_C"
                # Supply the public PID to avoid a LAN discovery query on success.
                from custom_components.tuyaextend_amperepoint import local_flow
                with patch.object(local_flow, "discover_device", return_value={"product_id": "public-test-product"}):
                    result = await hass.config_entries.flow.async_configure(flow_id, values)
                assert result["step_id"] == "local_confirm_read_only", result
                hass.config_entries.flow.async_abort(flow_id)
                assert not hass.config_entries.async_entries(DOMAIN)
                print("Retry from error form succeeds without creating an entry or sending commands", flush=True)
        finally:
            await hass.async_stop()


asyncio.run(main())
