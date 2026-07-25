from __future__ import annotations

import re
from typing import Any

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY
from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_SOURCE_DEVICE_ID, CONF_SOURCE_NAME, DOMAIN
from .discovery import discover_sources

_AUTO_ADOPTION_STARTED = "auto_adoption_started"

_ENTITY_ID_PATTERN = re.compile(r"^[a-z_]+\.[a-z0-9_]+$")


def _physical_ids(hass: HomeAssistant, device_id: str) -> set[str]:
    """Return the underlying vendor ids of a registry device.

    The cloud Tuya and tuya-local integrations register separate registry
    devices for the same physical charger, but both carry the vendor device
    id in their identifier tuples.
    """
    registry = dr.async_get(hass)
    device = registry.async_get(device_id) if registry else None
    if device is None:
        return set()
    return {str(identifier[-1]) for identifier in device.identifiers}


def _normalized_title(value: object) -> str:
    return str(value or "").strip().casefold()


def _entry_infos(hass: HomeAssistant) -> list[dict[str, Any]]:
    infos: list[dict[str, Any]] = []
    for config_entry in hass.config_entries.async_entries(DOMAIN):
        merged = {**config_entry.data, **config_entry.options}
        source_device_id = str(merged.get(CONF_SOURCE_DEVICE_ID, ""))
        titles = {
            title
            for title in (
                _normalized_title(getattr(config_entry, "title", None)),
                _normalized_title(merged.get(CONF_NAME)),
                _normalized_title(merged.get(CONF_SOURCE_NAME)),
            )
            if title
        }
        entities = {
            value
            for value in merged.values()
            if isinstance(value, str) and _ENTITY_ID_PATTERN.match(value)
        }
        infos.append(
            {
                "entry": config_entry,
                "device_id": source_device_id,
                "physical": (
                    _physical_ids(hass, source_device_id) if source_device_id else set()
                ),
                "titles": titles,
                "entities": entities,
            }
        )
    return infos


def _async_backfill_mapping(hass: HomeAssistant, info: dict[str, Any], candidate) -> None:
    """Copy mapping keys a twin source provides into the existing entry.

    When the same physical charger becomes visible through a richer source
    (for example tuya-local exposing the Prime telemetry attribute next to a
    cloud entry), the existing entry gains the missing source mappings
    instead of a duplicate entry being created.
    """
    entry = info["entry"]
    if entry is None:
        return
    merged = {**entry.data, **entry.options}
    missing = {
        key: value
        for key, value in candidate.mapping.items()
        if not merged.get(key)
    }
    if not missing:
        return
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, **missing}
    )


def start_auto_adoption(hass: HomeAssistant) -> int:
    """Schedule one discovery pass for unconfigured AmperePoint chargers.

    Config-entry setup runs again for every entry created by discovery.  The
    domain guard prevents those nested setups from scheduling duplicate flows
    while the first pass is still in flight.
    """
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(_AUTO_ADOPTION_STARTED):
        return 0

    if not hass.is_running:
        # Source entities are still restoring while Home Assistant starts;
        # scanning now can freeze incomplete mappings (for example a Prime
        # whose telemetry attribute is not populated yet) into new entries.
        domain_data[_AUTO_ADOPTION_STARTED] = True

        async def _scan_after_start(_event) -> None:
            domain_data[_AUTO_ADOPTION_STARTED] = False
            start_auto_adoption(hass)

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _scan_after_start)
        return 0

    candidates = discover_sources(hass)
    if not candidates:
        return 0

    domain_data[_AUTO_ADOPTION_STARTED] = True
    infos = _entry_infos(hass)

    scheduled = 0
    # Richer mappings first, so when the same physical charger is visible
    # through several sources (cloud Tuya and tuya-local) the candidate with
    # the most telemetry represents it and the others only contribute the
    # source entities it is missing.
    for candidate in _merge_twin_candidates(hass, candidates):
        candidate_physical = _physical_ids(hass, candidate.device_id)
        candidate_title = _normalized_title(getattr(candidate, "title", ""))
        match = next(
            (
                info
                for info in infos
                if candidate.device_id == info["device_id"]
                or (candidate_physical and candidate_physical & info["physical"])
                or any(
                    entity_id in info["entities"]
                    for entity_id in candidate.mapping.values()
                )
                or (candidate_title and candidate_title in info["titles"])
            ),
            None,
        )
        if match is not None:
            _async_backfill_mapping(hass, match, candidate)
            continue

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_INTEGRATION_DISCOVERY},
                data=candidate.as_config_data(),
            )
        )
        scheduled += 1
        infos.append(
            {
                "entry": None,
                "device_id": candidate.device_id,
                "physical": candidate_physical,
                "titles": {candidate_title} if candidate_title else set(),
                "entities": set(candidate.mapping.values()),
            }
        )
    return scheduled


def _merge_twin_candidates(hass: HomeAssistant, candidates: list) -> list:
    """Collapse candidates describing one physical charger into one candidate.

    The cloud Tuya and tuya-local integrations register separate devices for
    the same charger, and both carry the vendor device id in their registry
    identifiers.  Adopting both would create two entries, two devices and two
    rows in the panel's charger selector for one wallbox, so they are merged
    into the candidate with the richest mapping, which then also inherits the
    source entities only its twin provides.
    """
    ordered = sorted(candidates, key=lambda item: len(item.mapping), reverse=True)
    merged: list = []
    seen_physical: list[set[str]] = []

    for candidate in ordered:
        physical = _physical_ids(hass, candidate.device_id)
        twin_index = next(
            (
                index
                for index, known in enumerate(seen_physical)
                if physical and known & physical
            ),
            None,
        )
        if twin_index is None:
            merged.append(candidate)
            seen_physical.append(set(physical))
            continue

        primary = merged[twin_index]
        for key, value in candidate.mapping.items():
            primary.mapping.setdefault(key, value)
        seen_physical[twin_index] |= physical
    return merged
