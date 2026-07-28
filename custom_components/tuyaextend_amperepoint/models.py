from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AmperePointModel:
    key: str
    name: str
    phases: int
    min_current_a: int
    max_current_a: int
    current_step_a: int = 1
    nominal_voltage_v: int = 230


MODELS: dict[str, AmperePointModel] = {
    "q_series": AmperePointModel(
        key="q_series",
        name="AmperePoint Q Series (auto)",
        phases=3,
        min_current_a=6,
        max_current_a=48,
    ),
    # The Q Series names are kilowatts, not amperes: amperepoint.pl lists the
    # Q11 as 11 kW three-phase and the Q37 as 3.7 kW single-phase, and both
    # adjust 6-16 A in 1 A steps.
    "q11": AmperePointModel(
        key="q11",
        name="AmperePoint Q Series Q11",
        phases=3,
        min_current_a=6,
        max_current_a=16,
    ),
    "q37": AmperePointModel(
        key="q37",
        name="AmperePoint Q Series VE",
        phases=1,
        min_current_a=6,
        max_current_a=16,
    ),
    "q74": AmperePointModel(
        key="q74",
        name="AmperePoint Q Series Q74",
        phases=1,
        min_current_a=6,
        max_current_a=32,
    ),
    "q22": AmperePointModel(
        key="q22",
        name="AmperePoint Q Series Q22",
        phases=3,
        min_current_a=6,
        max_current_a=32,
    ),
    "q22_ota": AmperePointModel(
        key="q22_ota",
        name="AmperePoint Q22 OTA",
        phases=3,
        min_current_a=6,
        max_current_a=32,
    ),
    "s22": AmperePointModel(
        key="s22",
        name="AmperePoint S22",
        phases=3,
        min_current_a=6,
        max_current_a=32,
    ),
    "prime_22kw": AmperePointModel(
        key="prime_22kw",
        name="Ampere Point Wallbox Prime 22kW",
        phases=3,
        min_current_a=6,
        max_current_a=32,
    ),
}

DEFAULT_MODEL = "q_series"

MODEL_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "prime_22kw",
        ("wallbox prime", "prime 22kw", "gbmxngploofmhbjc"),
    ),
    ("q22_ota", ("q22 ota", "q22_ota", "cu111poj2mtikvls")),
    # "ev charger ve" and the product id fdfjiphjxtc9qyhd are NOT listed for
    # the Q37: Tuya sells several models under that one product, and a Q22
    # was captured reporting the same id while being named "Q22 - EV Charger
    # VE". Matching on either would label every one of them a Q37, which is
    # 1 phase and 16 A. Only the model number itself identifies a Q37.
    ("q37", ("q37",)),
    ("q74", ("q74", "7.4kw", "7,4kw")),
    ("q22", ("q22",)),
    ("q11", ("q11", "11kw")),
    ("s22", ("s22",)),
)

STATUS_MAP = {
    "charging": "Ladowanie",
    "charger_charging": "Ladowanie",
    "charge": "Ladowanie",
    "running": "Ladowanie",
    "start": "Ladowanie",
    "1": "Gotowy",
    "2": "Ladowanie",
    "3": "Zakonczone",
    "4": "Blad",
    "standby": "Gotowy",
    "ready": "Gotowy",
    "idle": "Gotowy",
    "sleep": "Uspiony",
    "available": "Gotowy",
    "waiting": "Gotowy",
    "charger_free": "Gotowy",
    "charger_wait": "Gotowy",
    "connected": "Auto podlaczone",
    "plugged": "Auto podlaczone",
    "plugged_in": "Auto podlaczone",
    "charger_insert": "Auto podlaczone",
    "complete": "Zakonczone",
    "completed": "Zakonczone",
    "finished": "Zakonczone",
    "charged": "Zakonczone",
    "charger_end": "Zakonczone",
    "paused": "Wstrzymane",
    "charger_pause": "Wstrzymane",
    "controlpi_12v": "Gotowy",
    "controlpi_12v_pwm": "Gotowy",
    "controlpi_9v": "Auto wykryte",
    "controlpi_9v_pwm": "Auto podlaczone",
    "controlpi_6v": "Gotowy do ladowania",
    "controlpi_6v_pwm": "Ladowanie",
    "controlpi_error": "Blad",
    "communication_initialising": "Gotowy",
    "vehicle_detected": "Auto wykryte",
    "vehicle_connected": "Auto podlaczone",
    "ready_to_charge": "Gotowy do ladowania",
    "fault": "Blad",
    "fault_unplugged": "Blad",
    "error": "Blad",
    "charger_fault": "Blad",
    "charger_free_fault": "Blad",
    "offline": "Offline",
    "unavailable": "Niedostepne",
    "unknown": "Nieznany",
}

COMPLETE_STATUSES = {"Zakonczone"}
CHARGING_STATUSES = {"Ladowanie"}

ERROR_MAP = {
    "0": "Brak bledu",
    "false": "Brak bledu",
    "off": "Brak bledu",
    "none": "Brak bledu",
    "ok": "Brak bledu",
    "1": "Blad",
    "true": "Blad",
    "on": "Blad",
    "over_current": "Przekroczony prad",
    "over_voltage": "Zbyt wysokie napiecie",
    "under_voltage": "Zbyt niskie napiecie",
    "leakage": "Wykryto uplyw pradu",
    "over_temperature": "Zbyt wysoka temperatura",
    "ground_fault": "Problem z uziemieniem",
    "relay_fault": "Blad przekaznika",
    "cp_fault": "Blad sygnalu CP",
    "offline": "Urzadzenie offline",
}


def get_model(key: str | None) -> AmperePointModel:
    return MODELS.get(key or DEFAULT_MODEL, MODELS[DEFAULT_MODEL])


def detect_model_key(value: Any) -> str:
    """Identify a charger from text, refusing to guess when it is ambiguous.

    One profile serves the whole series, so its name reaches this text and
    can mention several models at once. Picking the first alias that hits
    would then label every charger the same, which is how a 32 A Q22 once
    became a 16 A single-phase Q37. Text naming more than one model
    identifies none of them.
    """
    raw = _normalize_text(value)
    matched = {
        model_key
        for model_key, aliases in MODEL_ALIASES
        if any(alias in raw for alias in aliases)
    }
    if len(matched) != 1:
        return DEFAULT_MODEL
    return matched.pop()


def normalize_status(value: Any) -> str:
    if value is None:
        return "Nieznany"
    raw = str(value).strip()
    if not raw:
        return "Nieznany"
    return STATUS_MAP.get(raw.lower(), raw)


def normalize_error(value: Any) -> str:
    if value is None:
        return "Brak danych"
    raw = str(value).strip()
    if not raw:
        return "Brak danych"
    return ERROR_MAP.get(raw.lower(), raw)


def normalize_connected(value: Any, fallback: bool = False) -> bool:
    if value is None:
        return fallback
    raw = str(value).strip().lower()
    if raw in {
        "1",
        "true",
        "on",
        "yes",
        "connected",
        "plugged",
        "plugged_in",
        "charging",
        "charger_charging",
        "charger_insert",
        "controlpi_9v",
        "controlpi_9v_pwm",
        "controlpi_6v",
        "controlpi_6v_pwm",
        "vehicle_detected",
        "vehicle_connected",
        "ready_to_charge",
        "podlaczone",
    }:
        return True
    if raw in {"0", "false", "off", "no", "disconnected", "unplugged", "odlaczone"}:
        return False
    return fallback


def _normalize_text(value: Any) -> str:
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
    return " ".join(str(value or "").lower().translate(translation).split())
