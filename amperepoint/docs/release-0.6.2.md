# 0.6.2 — PRIME LAN controls across firmware versions

## Polski

- Usunięto listę dozwolonych wersji firmware ze sterowania PRIME przez LAN. Przy zgodnym zestawie danych DP140/150/152 sam numer firmware, jego brak lub dodatkowe DP nie powodują trybu tylko do odczytu. Poprawka dotyczy m.in. zgłoszenia PRIME 11 kW z firmware `(V10.22.20)F2.0.5`, który w 0.6.1 był blokowany po numerze wersji.
- Zachowano rozpoznawanie rodzin split i packed, limity prądu oraz niezależny odczyt potwierdzający wykonanie każdej komendy. Dla split DP140 jest raportowanym zezwoleniem na ładowanie; packed może mieć DP140 tylko do zapisu i potwierdza je przez DP101/109. Dodatkowe funkcje firmware nie stają się automatycznie zapisywalne.
- Istniejące wpisy sterowania V11 działają ze wspólnym adapterem split. Wpisy z wyłączonym sterowaniem pozostają tylko do odczytu do zmiany opcji przez użytkownika. Zaktualizowano instrukcje oraz polskie i angielskie opisy konfiguracji.

### Aktualizacja z 0.6.1

1. W HACS otwórz **TuyaExtend AmperePoint** i zainstaluj **v0.6.2**. Jeśli HACS nadal pokazuje starsze wydanie, odśwież informacje o repozytorium i sprawdź aktualizację ponownie.
2. Zrestartuj **Home Assistant** i odśwież stronę panelu. Wersja integracji i dashboardu powinna wynosić **0.6.2**.
3. Dla istniejącego wpisu PRIME tylko do odczytu otwórz **Ustawienia → Urządzenia i usługi → AmperePoint → Konfiguruj** przy właściwej ładowarce. Włącz **Sterowanie LAN i planer HA (wyłącz, aby używać tylko odczytu)** i zatwierdź. Połączenie oraz dostępne DP zostaną ponownie sprawdzone; nie trzeba usuwać urządzenia, ponownie go parować ani wpisywać istniejącego klucza lokalnego.
4. W aplikacji ładowarki pozostaw tryb natychmiastowy; planer działa w HA. Sprawdź odczyty, start/stop i zmianę limitu prądu. Sterowanie nadal jest ograniczone do 16 A i nie przekracza limitu urządzenia.

Jeżeli wpis nadal nie udostępnia sterowania, sprawdź dostępność wymaganych DP, a nie sam numer firmware. Raport z nieudanej próby włączenia sterowania można pobrać z tego samego formularza opcji.

## English

- Removed the firmware allowlist from PRIME LAN controls. With a compatible DP140/150/152 contract, a different or missing firmware version and additional DPs no longer force read-only operation. This addresses the PRIME 11 kW report on `(V10.22.20)F2.0.5`, whose version string was rejected in 0.6.1.
- Split/packed detection, current limits and independent command readback remain enforced. Split reports DP140 charging permission; packed may expose DP140 as write-only and confirms it through DP101/109. Additional firmware features are not automatically made writable.
- Existing V11 control entries remain compatible with the shared split adapter. Entries with controls disabled remain read-only until the user enables them in options. Updated the manuals and Polish/English configuration text.

### Update from 0.6.1

1. Open **TuyaExtend AmperePoint** in HACS and install **v0.6.2**. If HACS still lists the old release, refresh the repository information and check again.
2. Restart **Home Assistant** and refresh the dashboard. Both the integration and dashboard should report **0.6.2**.
3. For an existing read-only PRIME entry, open **Settings → Devices & services → AmperePoint → Configure** for that charger. Enable **LAN controls and HA planner (disable for read-only operation)** and submit. The connection and control DPs are checked again. There is no need to remove or pair the device again, or re-enter the stored local key.
4. Keep the charger app in immediate mode; the planner runs in HA. Check readings, start/stop and current control. Controls remain capped at 16 A and the device's installation limit.

If controls remain unavailable, check the required DPs rather than the firmware version alone. A failed options check offers a downloadable diagnostic report in the same form.

## Validation

374 Python and 24 frontend tests pass, including simulated onboarding and DP140/150 command readback for the reported V10 version, future/missing firmware metadata, additional DPs, packed write-only DP140, V11 profile compatibility, existing read-only entry configuration, current limits and unconfirmed commands. Firmware compatibility simulations use existing sanitized hardware captures with changed version metadata; this release does not claim a new physical test on the customer's V10 charger.
