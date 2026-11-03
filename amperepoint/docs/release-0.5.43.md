# 0.5.43 — Error report for failed LAN setup

## Polski

- Gdy dodanie wallboxa PRIME przez „AmperePoint Local (LAN)” się nie uda (import z integracji Tuya, ręczne dodanie albo zmiana połączenia w opcjach), w tym samym formularzu pojawia się link **Pobierz raport błędu**. Raport JSON można pobrać, zanim powstanie wpis integracji, i przesłać pomocy technicznej. Formularz zachowuje wpisane dane, więc można je poprawić i od razu spróbować ponownie.
- Raport pokazuje wynik próby połączenia, wersję Home Assistant i dodatku, identyfikator produktu (jeśli jest znany), wersję oprogramowania ładowarki oraz to, czy ładowarka przysłała komplet danych potrzebnych do rozpoznania układu. Nie zawiera local key, Device ID, adresu IP, danych kart ani nieznanych wartości. Link działa 15 minut i wymaga zalogowania w Home Assistant. Samo pobranie niczego nie wysyła do AmperePoint.

Aktualizacja: pobierz **v0.5.43** w HACS, zrestartuj Home Assistant i odśwież dashboard.

## English

- When adding a PRIME wallbox through “AmperePoint Local (LAN)” fails (Tuya import, manual setup or the LAN options check), the same form now shows **Download error report**. The JSON report can be downloaded before any config entry exists and sent to support. The form keeps its values, so you can correct them and retry right away.
- The report shows the connection result, the Home Assistant and integration versions, the product ID when known, the charger firmware version, and whether the charger returned the data needed to recognise its layout. It excludes the local key, device ID, IP address, card data and unknown values. The link lasts 15 minutes and requires a Home Assistant login. Downloading sends nothing to AmperePoint.

Update to **v0.5.43** through HACS, restart Home Assistant and refresh the dashboard.

Validation covers unit and frontend tests, including report and layout tests on a real status read from PRIME firmware **(V11.22.20)F2.0.6** (accepted as the split layout, read-only), plus real-HA setup and failed-setup download checks on HA **2025.2.0 and 2026.7.2** and energy checks on HA **2024.6.0 and 2026.7.2**. These checks use synthetic configuration and a simulated charger.

Changes in [PR #45](https://github.com/amperepoint/tuyaextend-amperepoint/pull/45) and [PR #47](https://github.com/amperepoint/tuyaextend-amperepoint/pull/47).
