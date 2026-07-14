from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import (
    CONF_RESOURCE_TYPE_WS,
    LOVELACE_DATA,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN, FRONTEND_MODULE, FRONTEND_URL

_LOGGER = logging.getLogger(__name__)

_STATIC_REGISTERED = f"{DOMAIN}_frontend_static_registered"
_RESOURCE_REGISTERED = f"{DOMAIN}_frontend_resource_registered"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Expose the bundled card and add it to Lovelace resources."""
    if not hass.data.get(_STATIC_REGISTERED):
        frontend_path = Path(__file__).parent / "frontend"
        await hass.http.async_register_static_paths(
            [StaticPathConfig(FRONTEND_URL, str(frontend_path), False)]
        )
        hass.data[_STATIC_REGISTERED] = True

    if not hass.data.get(_RESOURCE_REGISTERED):
        await _async_ensure_lovelace_resource(hass)


async def _async_ensure_lovelace_resource(hass: HomeAssistant) -> None:
    lovelace_data = hass.data.get(LOVELACE_DATA)
    resource_collection = getattr(lovelace_data, "resources", None)
    if resource_collection is None:
        _LOGGER.debug("Lovelace resources are not ready yet")
        return

    if not hasattr(resource_collection, "async_create_item"):
        _LOGGER.debug("Lovelace resources are in YAML mode; skipping card registration")
        return

    await resource_collection.async_get_info()
    for item in resource_collection.async_items():
        if not _same_resource(item):
            continue
        if item.get("url") != FRONTEND_MODULE and hasattr(
            resource_collection, "async_update_item"
        ):
            await resource_collection.async_update_item(
                item["id"],
                {
                    "url": FRONTEND_MODULE,
                    CONF_RESOURCE_TYPE_WS: "module",
                },
            )
        hass.data[_RESOURCE_REGISTERED] = True
        return

    await resource_collection.async_create_item(
        {
            "url": FRONTEND_MODULE,
            CONF_RESOURCE_TYPE_WS: "module",
        }
    )
    hass.data[_RESOURCE_REGISTERED] = True


def _same_resource(item: dict[str, Any]) -> bool:
    url = str(item.get("url", "")).split("?", 1)[0]
    return url == FRONTEND_MODULE.split("?", 1)[0] or url.endswith(
        "/amperepoint-q22-card.js"
    )
