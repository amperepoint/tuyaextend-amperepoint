# 0.6.1 — PV surplus charging

## Polski

- Ładowanie z nadwyżki fotowoltaiki: integracja dobiera prąd ładowania do nadwyżki PV z encji, które już są w Home Assistant (produkcja PV, licznik sieci ze znakiem albo osobny import i eksport, opcjonalnie zużycie domu i magazyn energii). Tryby `PV surplus only` (tylko nadwyżka), `PV + grid` (nadwyżka i sieć do ustawionego limitu importu) i `Reach target` (cel energii z doborem z sieci). Ręczne nadpisanie ma pierwszeństwo, a włączony plan tygodniowy działa jak okno pozwolenia. Prąd zmienia się stopniowo, w pełnych amperach. Tryb jest domyślnie wyłączony i bez jego włączenia ładowarka pracuje tak jak w 0.5.44.
- Tryb PV działa dla ładowarek dodanych przez integrację Tuya albo przez przypisanie encji. Wpis „AmperePoint Local (LAN)” nie ma jeszcze ustawień PV i nie dostaje encji PV.
- Nowe encje: Tryb PV, Nadwyżka PV, Energia słoneczna sesji, Udział słoneczny sesji i Dzienna energia słoneczna, a na panelu sekcja PV. Energie słoneczne nie tworzą statystyk, więc nie dublują „Energii ładowania” w panelu Energia.
- Ładowarka bez punktu Control Pilot (Q74) pokazuje podłączone auto także w stanach oczekiwania, pauzy i zakończenia, a puste gniazdo rozpoznaje po stanie wolnym.
- Profil Tuya Local serii Q (`amperepoint_q11_pro_evcharger`) obejmuje Q11 PRO, Q37, Q22 i Q74 i nazywa się „Ampere Point Q Series (local)”. Plik zachował nazwę, więc istniejące wpisy Tuya Local działają dalej.

Aktualizacja: pobierz **v0.6.1** w HACS, zrestartuj Home Assistant i odśwież przeglądarkę. Tryb PV włącza się w opcjach integracji po wskazaniu encji energii.

## English

- PV surplus charging: the integration sets the charging current from the PV surplus measured by entities already in Home Assistant (PV production, a signed grid sensor or separate import and export sensors, optionally house consumption and a home battery). Modes `PV surplus only`, `PV + grid` within an import allowance and `Reach target`. A manual override wins and an enabled weekly plan is a permission window. The current ramps in whole amperes. The mode is off by default; without it the charger behaves as in 0.5.44.
- PV works for chargers added through the Tuya integration or by entity mapping. An “AmperePoint Local (LAN)” entry has no PV settings yet and gets no PV entities.
- New entities: PV mode, PV surplus, Session solar energy, Session solar share and Daily solar energy, plus a PV section on the panel. The solar energies record no statistics, so they do not double “Charging energy” in HA Energy.
- A charger without a Control Pilot datapoint (Q74) reports a plugged-in vehicle also while waiting, paused or finished, and an empty socket from its free state.
- The Q Series Tuya Local profile (`amperepoint_q11_pro_evcharger`) covers the Q11 PRO, Q37, Q22 and Q74 and is named “Ampere Point Q Series (local)”. The file keeps its name, so existing Tuya Local entries keep working.

Update to **v0.6.1** through HACS, restart Home Assistant and refresh the browser. Turn PV on in the integration options after selecting the energy entities.

Validation covers 365 Python and 24 frontend tests, including the surplus engine, source normalization, planner ownership and end-to-end coordinator refreshes with synthetic meter data, plus real-HA setup and failed-setup download checks on HA **2025.2.0, 2026.6.4 and 2026.9.4**, energy checks on HA **2024.6.0, 2026.6.4 and 2026.9.4**, and the PV options form with Polish entity names on HA **2025.2.0 and 2026.9.4**. PV charging has not been tested on a charger.

Changes in [PR #49](https://github.com/amperepoint/tuyaextend-amperepoint/pull/49).
