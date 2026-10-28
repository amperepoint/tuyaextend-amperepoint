# 0.5.41 — Dashboard status and fault labels

## Polski

- Dashboard tłumaczy teraz wszystkie stany ładowarki i komunikaty błędów publikowane przez integrację, we wszystkich siedmiu językach dashboardu. Wcześniej na przykład angielski dashboard pokazywał „Gotowy” i „Brak bledu”.
- Wiersz diagnostyki nie jest już oznaczany na czerwono, gdy ładowarka nie zgłasza błędu. Dashboard nie rozpoznawał komunikatu „Brak bledu” jako braku błędu.
- Stany sensorów w Home Assistant pozostają bez zmian, więc istniejące automatyzacje działają jak dotąd.

Aktualizacja: pobierz **v0.5.41** w HACS, zrestartuj Home Assistant i odśwież dashboard.

## English

- The dashboard now translates every charger status and fault label published by the integration, in all seven dashboard languages. Previously an English dashboard showed, for example, "Gotowy" and "Brak bledu".
- The Diagnostics row is no longer drawn as a fault when the charger reports none. The dashboard did not recognise "Brak bledu" as the no-fault state.
- Sensor states in Home Assistant are unchanged, so existing automations keep working.

Update to **v0.5.41** through HACS, restart Home Assistant and refresh the dashboard.

Validation covers unit and frontend tests, including new tests that fail if a label published by the integration has no translation, plus real-HA setup and energy checks on HA **2024.6.0, 2025.2.0 and 2026.7.2**. These checks use synthetic configuration and do not exercise a live charger.

Changes in [PR #43](https://github.com/amperepoint/tuyaextend-amperepoint/pull/43).
