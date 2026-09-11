"""Readable PRIME measurements and a separate lossless technical table."""
from __future__ import annotations
import json
from .local_source import PRIVATE_DPS


def pair(pl, en):
    return {"pl": pl, "en": en}


UNKNOWN = pair("Wartość techniczna", "Technical value")
INFERRED = pair("Dane urządzenia", "Device data")
LOAD_SCALE = pair("DP102 · skala /10", "DP102 · scale /10")
LABELS = {
    "101": ("session", "Stan ładowarki", "Charger state"),
    "109": ("session", "Stan protokołu", "Protocol state"),
    "140": ("settings", "Ładowanie włączone", "Charging enabled"),
    "150": ("settings", "Zadany prąd ładowania", "Requested charging current"),
    "152": ("settings", "Limit prądu instalacji", "Installation current limit"),
    "107": ("settings", "Skróty wyboru prądu w aplikacji", "App current presets"),
    "153": ("settings", "Język urządzenia", "Device language"),
    "154": ("settings", "Opcja podłączenia", "Plug-in option"),
    "155": ("settings", "Autoryzacja NFC", "NFC authorization"),
    "157": ("device", "Wariant produktu", "Product variant"),
    "188": ("other", "DP odświeżania — ostatnia wartość", "Refresh DP — last value"),
}
STATES = {
    100: pair("Offline", "Offline"),
    101: pair("Oczekiwanie na podłączenie auta", "Waiting for vehicle"),
    200: pair("Gotowość / koniec ładowania", "Ready / charging complete"),
    201: pair("Ładowanie zakończone", "Charging complete"),
    202: pair("Oczekiwanie na harmonogram", "Waiting for schedule"),
    203: pair("Oczekiwanie na opóźniony start", "Waiting for delayed start"),
    204: pair("Wstrzymane", "Paused"),
    300: pair("Ładowanie aktywowane", "Charging activated"),
    400: pair("Zabezpieczenie nadprądowe", "Overcurrent protection"),
    401: pair("Zabezpieczenie nadnapięciowe", "Overvoltage protection"),
    402: pair("Zbyt niskie napięcie", "Undervoltage protection"),
    403: pair("Przegrzanie sterownika", "Controller overheating"),
    404: pair("Przegrzanie gniazda", "Socket overheating"),
    500: pair("Błąd autotestu", "Self-test failure"),
    501: pair("Zadziałanie ochrony różnicowoprądowej", "Leakage protection triggered"),
    502: pair("Błąd: sklejony przekaźnik", "Fault: stuck relay"),
    503: pair("Błąd ochrony różnicowoprądowej", "Leakage protection fault"),
    504: pair("Błąd sygnału CP", "CP signal fault"),
    505: pair("Inny błąd systemu", "Other system fault"),
    506: pair("Nie wykryto diody EV", "EV diode not detected"),
    507: pair("Brak uziemienia", "No protective earth"),
}


def unpack(value):
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, (dict, list)):
                return parsed
        except (TypeError, ValueError):
            pass
    return value


def leaves(value, path=""):
    if isinstance(value, dict) and value:
        for key, item in value.items():
            yield from leaves(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list) and value:
        for index, item in enumerate(value):
            yield from leaves(item, f"{path}[{index}]")
    else:
        yield path, value


def readable_rows(dps):
    rows = []
    for dp, raw in sorted(dps.items(), key=lambda x: (int(x[0]) if str(x[0]).isdigit() else 10000, str(x[0]))):
        dp = str(dp)
        parsed = unpack(raw)
        fields = [("", parsed)] if dp in PRIVATE_DPS or dp == "107" else leaves(parsed)
        for path, value in fields:
            original_value = value
            group, pl, en = LABELS.get(dp, ("other", f"Dodatkowe dane DP{dp}", f"Additional data DP{dp}"))
            label, note, unit = pair(pl, en), UNKNOWN, ""
            display = None
            numeric = type(value) in (int, float)
            if dp in PRIVATE_DPS:
                label = pair("Dane kart / autoryzacji", "Card / authentication data")
                display = pair("Ukryte", "Hidden")
                note = pair("Dane odczytane, ale niepublikowane w dashboardzie", "Read, but not published in the dashboard")
            elif dp == "101":
                display = STATES.get(value) if numeric else None
                note = pair("Stan firmware; pobór mocy pokazujemy oddzielnie", "Firmware state; power draw is shown separately")
            elif dp == "109":
                note = pair("Dosłowny stan zgłoszony przez firmware", "Exact state reported by firmware")
            elif dp == "102":
                group = "session"
                known = {
                    "p": ("Moc całkowita", "Total power", "kW", 10),
                    "e": ("Energia sesji", "Session energy", "kWh", 10),
                    "t": ("Temperatura sterownika", "Controller temperature", "°C", 10),
                    "d": ("Czas sesji", "Session duration", "s", 1),
                    "cp": ("Napięcie CP", "CP voltage", "V", 10),
                }
                if path in known and numeric:
                    pl,en,unit,divisor = known[path]
                    label, value = pair(pl,en), value / divisor
                    note = LOAD_SCALE if path in ("p","e") else pair("Odczyt urządzenia", "Device reading")
                elif path.startswith("L"):
                    group = "electrical"
                    label = pair(f"Pomiar elektryczny {path}", f"Electrical reading {path}")
                    if path.endswith("[0]") and numeric:
                        label, unit, value, note = pair(f"Napięcie {path[:-3]}", f"Voltage {path[:-3]}"), "V", value/10, INFERRED
                else:
                    label = pair(f"Telemetria — pole {path}", f"Telemetry — field {path}")
            elif dp == "117":
                group = "electrical"
                label = pair(f"Pomiar elektryczny {path}", f"Electrical reading {path}")
                if path == "cp" and numeric:
                    label, unit, value, note = pair("Napięcie CP", "CP voltage"), "V", value/10, pair("Potwierdzone na testerze", "Verified with the tester")
                elif path.endswith("[0]") and path.startswith("L") and numeric:
                    label, unit, value, note = pair(f"Napięcie {path[:-3]}", f"Voltage {path[:-3]}"), "V", value/10, INFERRED
            elif dp == "106":
                group = "device"
                label = {"fv": pair("Wersja firmware", "Firmware version"),
                         "r": pair("Ochrona RCD — deklaracja urządzenia", "RCD protection — device specification")}.get(path, pair(f"Informacje — {path}", f"Information — {path}"))
                note = pair("Informacja zgłoszona przez urządzenie", "Information reported by the device")
            elif dp == "151":
                group = "settings"
                label = {"m": pair("Tryb ładowania (kod)", "Charging mode (code)"),
                         "c": pair("Parametr c trybu ładowania", "Charging-mode parameter c"),
                         "ss": pair("Początek okna urządzenia", "Device window start"),
                         "se": pair("Koniec okna urządzenia", "Device window end"),
                         "dt": pair("Parametr opóźnienia dt", "Delay parameter dt")}.get(path, pair(f"Tryb — pole {path}", f"Mode — field {path}"))
            elif dp in ("140", "150", "152"):
                unit = "A" if dp != "140" else ""
                note = pair("Potwierdzone w testach lokalnych", "Verified in local tests")
            elif dp == "107":
                unit, note = "A", pair("Nie zastępuje limitu instalacji DP152", "Does not override installation limit DP152")
            elif dp == "153":
                display = {"en":pair("Angielski","English"), "pl":pair("Polski","Polish")}.get(value)
                note = pair("Kod języka urządzenia", "Device language code")
            elif dp in ("154", "155", "157", "188"):
                note = INFERRED
                if dp == "154" and type(value) is bool:
                    note = UNKNOWN  # Do not apply another firmware's integer enum.
            if path and dp not in ("102", "106", "117", "151"):
                label = pair(f"{pl} — {path}", f"{en} — {path}")
            if note == UNKNOWN or note == INFERRED:
                # Keep exact values and paths without assigning a speculative
                # meaning or unit. Main tables contain the normalized readings.
                group = "technical"
                label = pair(f"DP{dp}" + (f" · {path}" if path else ""),
                             f"DP{dp}" + (f" · {path}" if path else ""))
                value, unit, display = original_value, "", None
            if dp in PRIVATE_DPS:
                group = "technical"
            rows.append({"dp": dp, "path": path, "group": group, "label": label,
                         "value": value, "display": display, "unit": unit, "note": note})
    return rows
