# 0.5.44 — PRIME firmware V11.22: LAN setup and control

## Polski

- Wallbox PRIME z oprogramowaniem V11.22 (nowy panel w aplikacji, „Wersja SmartApp 2.0.0”) dodaje się przez „AmperePoint Local (LAN)” bez komunikatu „Połączenie odpowiada, ale tego układu DP jeszcze nie obsługujemy.” i dostaje sterowanie z Home Assistant: start/stop ładowania i limit prądu od 6 do 16 A, a z nimi planer ładowania. Każde polecenie dodatek potwierdza odczytem z wallboxa.
- Dodawanie i odczyty po LAN nie przerywają się już, gdy wallbox zamiast pełnego stanu odpowie bieżącą aktualizacją kilku punktów danych. Dodatek pyta wtedy ponownie, najwyżej trzy razy, i łączy odpowiedzi.

Aktualizacja: pobierz **v0.5.44** w HACS i zrestartuj Home Assistant. Wallbox, którego nie udało się dodać, dodaj ponownie przez „AmperePoint Local (LAN)”. Jeśli został dodany tylko do odczytu, włącz sterowanie w opcjach wpisu.

## English

- A PRIME wallbox on firmware V11.22 (new app panel, “SmartApp version 2.0.0”) can be added through “AmperePoint Local (LAN)” without the message “The device responds but its DP layout is not supported yet.” and gets control from Home Assistant: charging start/stop and a 6–16 A current limit, and with them the charging planner. Every command is confirmed by reading the wallbox back.
- LAN setup and reads no longer fail when the wallbox answers with an unsolicited update of a few datapoints instead of its full status. The integration asks again, at most three times, and merges the answers.

Update to **v0.5.44** through HACS and restart Home Assistant. Add a wallbox that could not be added again through “AmperePoint Local (LAN)”. If it was added read-only, enable control in the entry options.

Validation covers unit and frontend tests, including new V11.22 detection, partial-read and control tests built from a real status read, plus a hardware check of this code on firmware **(V11.22.20)F2.0.6**: current 10 A and 16 A, pause and resume, each confirmed by readback in about 2 s, and 20 A refused before sending. Real-HA setup and failed-setup download checks run on HA **2025.2.0 and 2026.7.2**, energy checks on HA **2024.6.0 and 2026.7.2**.

Changes in [PR #48](https://github.com/amperepoint/tuyaextend-amperepoint/pull/48).
