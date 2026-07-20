from __future__ import annotations

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY
from homeassistant.core import HomeAssistant

from .const import CONF_SOURCE_DEVICE_ID, DOMAIN
from .discovery import discover_sources

_AUTO_ADOPTION_STARTED = "auto_adoption_started"


def start_auto_adoption(hass: HomeAssistant) -> int:
    """Schedule one discovery pass for unconfigured AmperePoint chargers.

    Config-entry setup runs again for every entry created by discovery.  The
    domain guard prevents those nested setups from scheduling duplicate flows
    while the first pass is still in flight.
    """
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(_AUTO_ADOPTION_STARTED):
        return 0

    candidates = discover_sources(hass)
    if not candidates:
        return 0

    domain_data[_AUTO_ADOPTION_STARTED] = True
    configured_device_ids = {
        str(config_entry.data.get(CONF_SOURCE_DEVICE_ID, ""))
        for config_entry in hass.config_entries.async_entries(DOMAIN)
    }

    scheduled = 0
    for candidate in candidates:
        if candidate.device_id in configured_device_ids:
            continue
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_INTEGRATION_DISCOVERY},
                data=candidate.as_config_data(),
            )
        )
        scheduled += 1
    return scheduled
