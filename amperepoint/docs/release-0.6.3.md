# 0.6.3 — Charging energy after a power cut

## Polski

- „Energia ładowania” nie dolicza już całego licznika ładowarki po zaniku zasilania. Ładowarki serii Q po włączeniu zasilania podają licznik 0, a zapisaną wartość dopiero przy następnym ładowaniu, czasem niższą. Integracja brała ten powrót za zużycie i dopisywała do panelu Energia naraz kilkadziesiąt albo ponad sto kWh. Teraz liczy tylko przyrost ponad wartość, do której licznik wrócił.
- Skok licznika odrzucony jako niemożliwy nie jest już doliczany później, gdy minie dość czasu, żeby wyglądał na możliwy.
- „Energia sesji” nie zaczyna sesji od zera zgłoszonego po włączeniu zasilania, więc nie pokazuje całego licznika ładowarki.
- Skoki zapisane przed aktualizacją zostają w statystykach Home Assistant; można je skorygować ręcznie w narzędziach deweloperskich HA, w statystykach.

Aktualizacja: pobierz **v0.6.3** w HACS i zrestartuj Home Assistant. Wersja zawiera też zmiany z 0.6.2.

## English

- “Charging energy” no longer adds the charger’s whole counter after a power cut. Q Series chargers report their lifetime counter as 0 right after a power-on and send the stored value only with the next charge, sometimes at an older level. The integration took that return for consumption and added tens or over a hundred kWh to HA Energy in one step. It now counts only the growth above the level the counter came back to.
- A counter jump rejected as implausible is no longer added later, once enough time has passed for it to look possible.
- “Session energy” no longer starts a session from a power-on zero, so it does not show the charger’s whole counter.
- Steps recorded before the update stay in the Home Assistant statistics; they can be adjusted by hand under Developer tools → Statistics.

Update to **v0.6.3** through HACS and restart Home Assistant. It includes the 0.6.2 changes.

## Validation

382 Python and 24 frontend tests pass. One replays seven days of a Q11 log with two power-ons, one of which brought the counter back 23.3 kWh lower: the meter read 270.8 kWh before the fix and 113.4 kWh after it, which is what the car took. Real-HA energy checks passed on HA **2024.6.0 and 2026.9.4**, setup checks on HA **2025.2.0 and 2026.9.4**.

Changes in [PR #51](https://github.com/amperepoint/tuyaextend-amperepoint/pull/51).
