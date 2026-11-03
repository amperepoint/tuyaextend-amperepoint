# 0.5.42 — Planner follows current changes

## Polski

- Planer ładowania nie cofa już prądu zmienionego poza nim. Prąd z przedziału harmonogramu albo z trybu „Ładuj” ustawia raz, na początku, a zmianę z aplikacji Tuya, Tuya Local albo automatyzacji przyjmuje. Wcześniej w przedziale planu i przez godzinę po starcie przyciskiem na karcie prąd wracał do wartości planera po kilku sekundach.
- Ładowanie włączone ponownie zaraz po tym, jak planer je wyłączył (poza przedziałem albo podczas wstrzymania), planer wyłącza znowu. Wcześniej taka druga próba przechodziła i planer przez 5 minut nie pilnował ładowarki.
- Wyłączony planer, tak jak dotąd, wyłącza tylko sesję, którą sam uruchomił, jeden raz.

Aktualizacja: pobierz **v0.5.42** w HACS, zrestartuj Home Assistant i odśwież dashboard.

## English

- The charging planner no longer reverts a current changed outside it. It applies the current of a plan window or a Charge override once, when it starts, and then follows changes made in the Tuya app, Tuya Local or an automation. Previously, during a plan window and for an hour after Start on the card, the current returned to the planner's value within seconds.
- Charging switched on again right after the planner switched it off (outside a window or while paused) is switched off again. Previously that second attempt went through and the planner left the charger unsupervised for 5 minutes.
- A disabled planner still switches off only a session it started itself, once.

Update to **v0.5.42** through HACS, restart Home Assistant and refresh the dashboard.

Validation covers unit and frontend tests, including new planner tests built from a customer's Tuya event log that fail on 0.5.41, plus real-HA setup and energy checks on HA **2024.6.0, 2025.2.0 and 2026.7.2**. These checks use synthetic configuration and do not exercise a live charger.

Changes in [PR #46](https://github.com/amperepoint/tuyaextend-amperepoint/pull/46).
