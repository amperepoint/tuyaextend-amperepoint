from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.storage import Store

from .const import CONF_SOURCE_DEVICE_ID, CONF_SOURCE_PHYSICAL_IDS, DOMAIN
from .discovery import discover_sources

_LOGGER = logging.getLogger(__name__)

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


def _entry_infos(hass: HomeAssistant) -> list[dict[str, Any]]:
    infos: list[dict[str, Any]] = []
    for config_entry in hass.config_entries.async_entries(DOMAIN):
        merged = {**config_entry.data, **config_entry.options}
        source_device_id = str(merged.get(CONF_SOURCE_DEVICE_ID, ""))
        entities = {
            value
            for value in merged.values()
            if isinstance(value, str) and _ENTITY_ID_PATTERN.match(value)
        }
        # Pairing a charger again gives it a new device registry id and new
        # entities, and deletes the old device the live lookup reads from.
        # The remembered vendor ids are then the only thing still tying this
        # entry to the charger it was adopted from.
        live = _physical_ids(hass, source_device_id) if source_device_id else set()
        remembered = {
            str(value) for value in merged.get(CONF_SOURCE_PHYSICAL_IDS, []) or []
        }
        infos.append(
            {
                "entry": config_entry,
                "device_id": source_device_id,
                "physical": live | remembered,
                "live_physical": live,
                "remembered_physical": remembered,
                "entities": entities,
            }
        )
    return infos


def _async_remember_physical_ids(hass: HomeAssistant, info: dict[str, Any]) -> None:
    """Persist the vendor ids of an entry's source while it still exists."""
    entry = info.get("entry")
    live = info.get("live_physical") or set()
    if entry is None or not live:
        return
    remembered = info.get("remembered_physical") or set()
    if live <= remembered:
        return
    merged = sorted(remembered | live)
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_SOURCE_PHYSICAL_IDS: merged}
    )
    info["remembered_physical"] = set(merged)


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
    # The charger was paired again: its old device is gone from the registry
    # and the entry has to follow the replacement, or every later pass would
    # keep matching on remembered vendor ids alone.
    previous_device_id = info.get("device_id")
    if (
        previous_device_id
        and not info.get("live_physical")
        and candidate.device_id != previous_device_id
    ):
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_SOURCE_DEVICE_ID: candidate.device_id}
        )
        info["device_id"] = candidate.device_id
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
    # Record the vendor ids now, while the source devices are still in the
    # registry. Once a charger is paired again the old device is gone, and
    # this is what lets the entry be recognised as the same charger.
    for info in infos:
        _async_remember_physical_ids(hass, info)

    scheduled = 0
    # Richer mappings first, so when the same physical charger is visible
    # through several sources (cloud Tuya and tuya-local) the candidate with
    # the most telemetry represents it and the others only contribute the
    # source entities it is missing.
    for candidate in _merge_twin_candidates(hass, candidates):
        candidate_physical = _physical_ids(hass, candidate.device_id)
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
            ),
            None,
        )
        if match is not None:
            _async_backfill_mapping(hass, match, candidate)
            # Remember the ids of the charger that actually matched. The pass
            # above only covers entries whose source device still exists, so
            # without this an entry that was matched through its entities -
            # after its device had already been deleted - would never record
            # anything and would be orphaned by the next re-pairing.
            if candidate_physical:
                match["live_physical"] = candidate_physical
                _async_remember_physical_ids(hass, match)
            known.add(candidate.device_id)
            known |= candidate_physical
            continue

        if candidate.device_id in known or (candidate_physical & known):
            # Adopted before and no longer configured: the user removed it.
            continue

        try:
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_INTEGRATION_DISCOVERY},
                data=candidate.as_config_data(),
            )
        except Exception:  # pragma: no cover - Home Assistant flow boundary
            _LOGGER.exception(
                "Automatic adoption failed for %s", candidate.device_id
            )
            continue
        result_type = result.get("type") if isinstance(result, dict) else None
        if getattr(result_type, "value", result_type) != "create_entry":
            _LOGGER.warning(
                "Automatic adoption did not create an entry for %s: %s",
                candidate.device_id,
                result,
            )
            continue

        scheduled += 1
        known.add(candidate.device_id)
        known |= candidate_physical
        infos.append(
            {
                "entry": None,
                "device_id": candidate.device_id,
                "physical": candidate_physical,
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
