# 0.5.40 — Home Assistant compatibility and setup recovery

## Polski

- Naprawione uruchamianie integracji na Home Assistant 2025.2–2026.2: panel nie przekazuje już argumentu `show_in_sidebar`, którego te wersje HA nie obsługują.
- Błąd po uruchomieniu platform powoduje ich wyładowanie oraz zatrzymanie planera, dzięki czemu ponowna próba nie pozostawia zdublowanych platform i planerów.
- Nieudana rejestracja panelu nie pozostawia częściowego dashboardu w pamięci. Kolejna próba ponawia rejestrację i przywraca panel w menu.
- Minimalna deklarowana wersja Home Assistant to teraz **2025.2.0**, zgodnie z używanym API Lovelace.

Aktualizacja: pobierz **v0.5.40** w HACS, zrestartuj Home Assistant i odśwież dashboard. Restart usuwa też pozostałości po nieudanym uruchomieniu wcześniejszej wersji.

## English

- Restore integration setup on Home Assistant 2025.2–2026.2 by omitting the unsupported `show_in_sidebar` panel argument.
- Unload platforms and stop the planner when setup fails after platform forwarding, allowing a clean retry.
- Publish the runtime dashboard only after panel registration succeeds, so a failed registration cannot make the next attempt skip a missing panel.
- Declare **Home Assistant 2025.2.0** as the minimum supported version, matching the Lovelace API used by the integration.

Update to **v0.5.40** through HACS, restart Home Assistant and refresh the dashboard. Restarting also clears partial runtime state left by an earlier failed setup.

Validation covers unit and frontend tests plus real-HA setup, reload and panel-registration failure recovery on HA **2025.2.0 and 2026.7.2**. These checks use synthetic configuration and do not exercise a live charger.

Thanks to @dawidcekala-oss for the compatibility fix and full-entry smoke tests in [PR #42](https://github.com/amperepoint/tuyaextend-amperepoint/pull/42).
