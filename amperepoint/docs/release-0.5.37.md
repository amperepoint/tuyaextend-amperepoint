# 0.5.37 — PRIME local telemetry and a shared Tuya dashboard

## English

- Added an opt-in Wallbox Prime profile installer to AmperePoint's initial
  setup and Configure menus. Tuya Local must already be installed.
- Supported profile: **Wallbox Prime 22 kW, PID `gbmxngploofmhbjc`, LAN 3.5**.
  Support is **read-only**: power, session energy, temperature, phase readings,
  vehicle connection, session duration and diagnostics, when reported by the device.
- PRIME start/stop, current changes, schedule/mode writes, kWh targets and
  planner execution are **not supported in this release**. Q Series support
  remains unchanged. Other PRIME PIDs/firmware need separate validation.
- The shared panel and card subtitle are now **Ampere Point - Tuya dashboard**.
  Existing custom dashboard titles and the card's YAML type are preserved.
- Updated English and Polish installation instructions, including local versus
  cloud setup, credential requirements and restoring a profile after HACS updates.

Upgrade through HACS and **restart Home Assistant**. Refresh the browser if it
still shows the previous card. The shared panel is at `/amperepoint-panel/charger`.
PRIME requires a separate Tuya Local pairing step; updating AmperePoint does not
pair the charger, install Tuya Local or send charger commands automatically.
See [English installation](../../INSTALL.en.md) and
[Polish installation](../../INSTALL.pl.md).

Validation: 133 Python tests, 7 frontend tests, syntax/whitespace checks and
module imports on HA 2026.7.2. These checks do not establish hardware command
support or certify every PRIME firmware. End-to-end PRIME pairing remains a
device-specific validation step.

## Polski

- Instalator profilu Wallbox Prime jest dostępny przy dodawaniu integracji
  AmperePoint oraz w jej menu Konfiguruj. Wymaga zainstalowanego Tuya Local.
- **Wallbox Prime 22 kW, PID `gbmxngploofmhbjc`, LAN 3.5:** lokalny odczyt mocy,
  energii sesji, temperatury, pomiarów faz, podłączenia auta, czasu sesji i
  diagnostyki — w zakresie danych raportowanych przez urządzenie.
- **Bez sterowania PRIME:** start/stop, zmiana prądu, zapis harmonogramu i trybu,
  cel kWh oraz wykonywanie planera nie są jeszcze obsługiwane. Funkcje Q Series
  pozostają bez zmian. Inne PID/firmware PRIME wymagają osobnej weryfikacji.
- Nowa wspólna nazwa panelu: **Ampere Point - Tuya dashboard**.
- Uporządkowane instrukcje instalacji PL/EN i informacje o ograniczeniach.

Po aktualizacji przez HACS **zrestartuj HA** i odśwież przeglądarkę.
Panel: `/amperepoint-panel/charger`. PRIME dodaj osobno przez Tuya Local;
aktualizacja nie paruje urządzenia ani nie instaluje Tuya Local za użytkownika.
