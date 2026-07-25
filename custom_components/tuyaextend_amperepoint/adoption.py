from __future__ import annotations

import re
from typing import Any

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY
from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.storage import Store

from .const import CONF_SOURCE_DEVICE_ID, CONF_SOURCE_NAME, DOMAIN
from .discovery import discover_sources

_AUTO_ADOPTION_STARTED = "auto_adoption_started"
_ADOPTION_STORE = "adoption_store"
_ADOPTION_STORAGE_VERSION = 1

_ENTITY_ID_PATTERN = re.compile(r"^[a-z_]+\.[a-z0-9_]+$")


def _adoption_store(hass: HomeAssistant) -> Store:
    """Return the store that remembers which chargers were already adopted."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    store = domain_data.get(_ADOPTION_STORE)
    if store is None:
        store = Store(hass, _ADOPTION_STORAGE_VERSION, f"{DOMAIN}.adoption")
        domain_data[_ADOPTION_STORE] = store
    return store


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


def _live_entity(hass: HomeAssistant, value: object) -> bool:
    """Whether a mapped source still exists.

    Deleting a charger's tuya-local pairing removes its entities but leaves
    the mapping behind, and a mapping pointing at a deleted entity would
    otherwise look configured and block the replacement from being written
    when the charger is paired again.
    """
    if not isinstance(value, str) or not _ENTITY_ID_PATTERN.match(value):
        return bool(value)
    registry = er.async_get(hass)
    if registry is None:
        return True
    return registry.async_get(value) is not None


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


def _async_backfill_mapping(
    hass: HomeAssistant, info: dict[str, Any], candidate
) -> None:
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
        if not _live_entity(hass, merged.get(key))
    }
    if not missing:
        return
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, **missing}
    )


async def async_start_auto_adoption(hass: HomeAssistant) -> int:
    """Schedule one discovery pass for chargers that were never adopted.

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
            await async_start_auto_adoption(hass)

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _scan_after_start)
        return 0

    candidates = discover_sources(hass)
    if not candidates:
        return 0

    domain_data[_AUTO_ADOPTION_STARTED] = True

    store = _adoption_store(hass)
    stored = await store.async_load() or {}
    # A charger is adopted at most once. Without this an entry the user
    # deleted on purpose would come back on the next restart.
    known: set[str] = set(stored.get("adopted", []))
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
            known.add(candidate.device_id)
            known |= candidate_physical
            continue

        if candidate.device_id in known or (candidate_physical & known):
            # Adopted before and no longer configured: the user removed it.
            continue

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_INTEGRATION_DISCOVERY},
                data=candidate.as_config_data(),
            )
        )
        scheduled += 1
        known.add(candidate.device_id)
        known |= candidate_physical
        infos.append(
            {
                "entry": None,
                "device_id": candidate.device_id,
                "physical": candidate_physical,
                "titles": {candidate_title} if candidate_title else set(),
                "entities": set(candidate.mapping.values()),
            }
        )

    await store.async_save({"adopted": sorted(known)})
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
