from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import (
    CONF_AUTO_DISCOVERED,
    CONF_MODEL,
    CONF_SESSION_ENERGY_MODE,
    CONF_SOURCE_CHARGE_SWITCH,
    CONF_SOURCE_CONNECTED,
    CONF_SOURCE_CURRENT_L1,
    CONF_SOURCE_CURRENT_L2,
    CONF_SOURCE_CURRENT_L3,
    CONF_SOURCE_CURRENT_LIMIT,
    CONF_SOURCE_DEVICE_ID,
    CONF_SOURCE_ERROR,
    CONF_SOURCE_INTEGRATION,
    CONF_SOURCE_LAST_SESSION_ENERGY,
    CONF_SOURCE_NAME,
    CONF_SOURCE_PHASE_A,
    CONF_SOURCE_PHASE_B,
    CONF_SOURCE_PHASE_C,
    CONF_SOURCE_POWER,
    CONF_SOURCE_POWER_L1,
    CONF_SOURCE_POWER_L2,
    CONF_SOURCE_POWER_L3,
    CONF_SOURCE_RAW_DP,
    CONF_SOURCE_SESSION_ENERGY,
    CONF_SOURCE_STATUS,
    CONF_SOURCE_TEMPERATURE,
    CONF_SOURCE_TOTAL_ENERGY,
    CONF_SOURCE_VOLTAGE_L1,
    CONF_SOURCE_VOLTAGE_L2,
    CONF_SOURCE_VOLTAGE_L3,
    SESSION_ENERGY_MODE_TOTAL_DELTA,
)
from .models import DEFAULT_MODEL, MODELS, detect_model_key

SOURCE_PLATFORMS = {"tuya", "tuya_local", "localtuya", "xtend_tuya"}


@dataclass(slots=True)
class SourceCandidate:
    device_id: str
    title: str
    model_key: str
    source_integration: str | None = None
    mapping: dict[str, str] = field(default_factory=dict)

    @property
    def option_label(self) -> str:
        model = MODELS.get(self.model_key, MODELS[DEFAULT_MODEL])
        source = f" / {self.source_integration}" if self.source_integration else ""
        return f"{self.title} ({model.name}{source})"

    def as_config_data(self) -> dict[str, Any]:
        return {
            CONF_AUTO_DISCOVERED: True,
            CONF_MODEL: self.model_key,
            CONF_SOURCE_DEVICE_ID: self.device_id,
            CONF_SOURCE_NAME: self.title,
            CONF_SOURCE_INTEGRATION: self.source_integration,
            CONF_SESSION_ENERGY_MODE: SESSION_ENERGY_MODE_TOTAL_DELTA,
            **self.mapping,
        }


def discover_sources(hass: HomeAssistant) -> list[SourceCandidate]:
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    grouped: dict[str, list[er.RegistryEntry]] = {}

    for entry in entity_registry.entities.values():
        if not entry.device_id:
            continue
        if entry.platform not in SOURCE_PLATFORMS and not _looks_like_amperepoint(
            _entity_text(entry)
        ):
            continue
        grouped.setdefault(entry.device_id, []).append(entry)

    candidates: list[SourceCandidate] = []
    for device_id, entries in grouped.items():
        device = device_registry.async_get(device_id)
        if device is None:
            continue

        device_text = _device_text(device, entries)
        if not _looks_like_amperepoint(device_text):
            continue

        title = (
            device.name_by_user
            or device.name
            or _first_state_name(hass, entries)
            or "AmperePoint charger"
        )
        source_platform = _first_source_platform(entries)
        candidates.append(
            SourceCandidate(
                device_id=device_id,
                title=title,
                model_key=detect_model_key(device_text),
                source_integration=source_platform,
                mapping=map_source_entities(entries),
            )
        )

    return sorted(candidates, key=lambda item: item.option_label.lower())


def map_source_entities(entries: Iterable[er.RegistryEntry]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    scored: dict[str, tuple[int, str]] = {}

    for entry in entries:
        text = _normalize(_entity_text(entry))
        domain = entry.entity_id.split(".", 1)[0]
        for key, score in _match_mapping_keys(text, domain):
            current = scored.get(key)
            if current is None or score > current[0]:
                scored[key] = (score, entry.entity_id)

    for key, (_score, entity_id) in scored.items():
        mapping[key] = entity_id
    return mapping


def _match_mapping_keys(text: str, domain: str) -> Iterable[tuple[str, int]]:
    if "raw dp" in text or "datapoint" in text:
        yield CONF_SOURCE_RAW_DP, 90

    if _has_any(text, "work state", "work_state", "status", "charger state"):
        if "connection" not in text:
            yield CONF_SOURCE_STATUS, 80

    if _has_any(text, "connection state", "connection_state", "controlpi", "control pilot", "cp"):
        yield CONF_SOURCE_CONNECTED, 85

    if _has_any(text, "power total", "power_total", "total power", "moc calkowita", "moc chwilowa"):
        yield CONF_SOURCE_POWER, 90
    elif domain == "sensor" and _has_any(text, "power", "moc") and not _has_any(text, "phase", "l1", "l2", "l3"):
        yield CONF_SOURCE_POWER, 60

    if _has_any(text, "forward energy total", "forward_energy_total", "total forward energy", "total energy", "energia calkowita"):
        yield CONF_SOURCE_TOTAL_ENERGY, 90
    elif _has_any(text, "energy total", "licznik"):
        yield CONF_SOURCE_TOTAL_ENERGY, 70

    if _has_any(text, "session energy", "current session", "energia sesji"):
        yield CONF_SOURCE_SESSION_ENERGY, 75

    if _has_any(text, "charge energy once", "charge_energy_once", "last session", "ostatnia sesja"):
        yield CONF_SOURCE_LAST_SESSION_ENERGY, 90

    if _has_any(text, "charge cur set", "charge_cur_set", "charging current", "current limit", "limit pradu", "limit current"):
        yield CONF_SOURCE_CURRENT_LIMIT, 90

    if domain in {"switch", "input_boolean"} and _has_any(text, "switch", "start", "stop", "charging", "ladowanie"):
        yield CONF_SOURCE_CHARGE_SWITCH, 90

    if _has_any(text, "fault", "error", "alarm", "problem", "blad"):
        yield CONF_SOURCE_ERROR, 85

    if _has_any(text, "temp current", "temp_current", "temperature", "temperatura"):
        yield CONF_SOURCE_TEMPERATURE, 85

    for marker, voltage_key, current_key, power_key, raw_key in (
        ("a", CONF_SOURCE_VOLTAGE_L1, CONF_SOURCE_CURRENT_L1, CONF_SOURCE_POWER_L1, CONF_SOURCE_PHASE_A),
        ("b", CONF_SOURCE_VOLTAGE_L2, CONF_SOURCE_CURRENT_L2, CONF_SOURCE_POWER_L2, CONF_SOURCE_PHASE_B),
        ("c", CONF_SOURCE_VOLTAGE_L3, CONF_SOURCE_CURRENT_L3, CONF_SOURCE_POWER_L3, CONF_SOURCE_PHASE_C),
        ("l1", CONF_SOURCE_VOLTAGE_L1, CONF_SOURCE_CURRENT_L1, CONF_SOURCE_POWER_L1, CONF_SOURCE_PHASE_A),
        ("l2", CONF_SOURCE_VOLTAGE_L2, CONF_SOURCE_CURRENT_L2, CONF_SOURCE_POWER_L2, CONF_SOURCE_PHASE_B),
        ("l3", CONF_SOURCE_VOLTAGE_L3, CONF_SOURCE_CURRENT_L3, CONF_SOURCE_POWER_L3, CONF_SOURCE_PHASE_C),
    ):
        if not _phase_marker_matches(text, marker):
            continue
        if _has_any(text, "phase", "raw"):
            yield raw_key, 75
        if _has_any(text, "voltage", "napiecie"):
            yield voltage_key, 90
        if _has_any(text, "current", "prad"):
            yield current_key, 90
        if _has_any(text, "power", "moc"):
            yield power_key, 90


def _phase_marker_matches(text: str, marker: str) -> bool:
    aliases = {
        "a": ("phase a", "phase_a", "faza a", "napiecie a", "prad a", "moc a"),
        "b": ("phase b", "phase_b", "faza b", "napiecie b", "prad b", "moc b"),
        "c": ("phase c", "phase_c", "faza c", "napiecie c", "prad c", "moc c"),
        "l1": (" l1", "_l1", "phase l1"),
        "l2": (" l2", "_l2", "phase l2"),
        "l3": (" l3", "_l3", "phase l3"),
    }
    return any(alias in text for alias in aliases[marker])


def _first_source_platform(entries: Iterable[er.RegistryEntry]) -> str | None:
    for entry in entries:
        if entry.platform in SOURCE_PLATFORMS:
            return entry.platform
    return None


def _first_state_name(hass: HomeAssistant, entries: Iterable[er.RegistryEntry]) -> str | None:
    for entry in entries:
        state = hass.states.get(entry.entity_id)
        if state and (name := state.attributes.get("friendly_name")):
            return str(name)
    return None


def _device_text(device: dr.DeviceEntry, entries: Iterable[er.RegistryEntry]) -> str:
    parts: list[str] = [
        str(device.name_by_user or ""),
        str(device.name or ""),
        str(device.model or ""),
        str(device.manufacturer or ""),
    ]
    for identifier in device.identifiers:
        parts.extend(str(part) for part in identifier)
    for entry in entries:
        parts.append(_entity_text(entry))
    return _normalize(" ".join(parts))


def _entity_text(entry: er.RegistryEntry) -> str:
    return " ".join(
        str(value or "")
        for value in (
            entry.entity_id,
            entry.name,
            entry.original_name,
            entry.translation_key,
            entry.unique_id,
        )
    )


def _looks_like_amperepoint(text: str) -> bool:
    normalized = _normalize(text)
    return _has_any(
        normalized,
        "amperepoint",
        "ampere point",
        "ampery point",
        "q11",
        "q22",
        "q37",
        "q series",
        "ev charger",
        "evse",
        "mode 3 type 2",
    )


def _has_any(text: str, *needles: str) -> bool:
    return any(_normalize(needle) in text for needle in needles)


def _normalize(value: str) -> str:
    translation = str.maketrans(
        {
            "_": " ",
            "-": " ",
            ".": " ",
            "ą": "a",
            "ć": "c",
            "ę": "e",
            "ł": "l",
            "ń": "n",
            "ó": "o",
            "ś": "s",
            "ż": "z",
            "ź": "z",
        }
    )
    return " ".join(value.lower().translate(translation).split())
