# PRIME LAN dashboard and HA charging modes

Local beta 0.5.38b6 extends the verified `prime_split_v1` control adapter with
the existing Q dashboard controls and an HA-managed planner. Other firmware
layouts retain their existing capabilities; this is not blanket write support
for every PRIME product.

## User interface

- Charge now: direct charging permission and current control.
- Charge to energy target: select a target, then press Start. The budget counts
  energy added after Start, not the absolute session counter. Selecting the mode
  prepares it and pauses charging. Editing a running target retains progress.
- Scheduled charging: saved weekdays, minute-accurate intervals and per-window
  current limits; overlapping windows use the existing planner resolution.
- Manual timed charging, energy override, pause and return-to-plan are available.
- Plan, target, overrides and energy progress are restored after HA restart.
- Main diagnostic tables contain named readings. Other device fields are kept
  verbatim in “Additional technical values”, identified by DP and JSON path.
  Card/authentication values remain masked.

## Control boundary

Modes and schedules run in Home Assistant, **not in the charger's firmware**.
HA must stay running and connected over LAN to enforce scheduled stops and energy
targets. If HA or the network fails while permission is on, the charger can keep
charging; it has no HA watchdog or offline energy-budget enforcement.

Keep the device app in immediate mode (`DP151.m = 0`). The integration does not
write DP151 or infer its other fields. Start requests are rejected if the fresh
device preflight reports another/missing mode. Only DP140 (permission) and DP150
(requested current) are written. Current is capped at 16 A and DP152; installation
limits, protection settings, NFC and reset/reboot controls are never changed.
Commands require independent LAN readback, not only protocol acknowledgement.

The energy budget uses the reported session-energy counter with persisted delta
segments, including counter resets. Missing/invalid energy stops a running budget.
The DP102 /10 energy/power scaling comes from the PRIME family mapping. The
connected tester provides no power draw, so delivered-kWh accuracy and stop
overshoot still require a real-load test. Software energy-stop scenarios are tested
with synthetic meter readings, never by inserting fake data into live HA.

This beta remains local until the LAN and load checks are complete. No extra
Tuya Local integration is required for the native AmperePoint transport.

## Verification — 11 September 2026

- 170 Python tests and 10 Node frontend tests passed; JavaScript syntax checked.
- HA-native imports passed with the official Tuya/cloud SDK and Tuya Local imports
  blocked. The live target uses the integration-owned LAN transport.
- Verified in the HA dashboard: all three modes, conditional target-energy input,
  weekly planner, LAN command status, friendly charger/connection labels and
  separate technical values. No repeated unverified-meaning warnings are rendered.
- Live schedule: Friday 14:21–14:23 Europe/Warsaw, 8 A. At 14:21 HA set the
  current and then enabled DP140; independent LAN readings confirmed DP150=8,
  DP140=true, DP101=300. Start confirmation was recorded at 14:21:13.
- Docker/HA was restarted during the active interval. The persisted plan resumed
  without a new schedule configuration. At 14:23 HA disabled DP140; DP101=204
  and permission=false were confirmed at 14:23:02.
- The 3.5 kWh mode was prepared through the HA select and number entities, then
  started with the HA switch. The planner reported target=3.5, delivered=0,
  mode=charge_energy; LAN confirmed permission=true and DP101=300. Device
  DP151.m remained 0 throughout (no native-mode writes).
- The target had been changed by the user to DP152=13 A / DP150=12 A during
  earlier UI checks. The test respected that installation limit. Final readback:
  12 A request, 13 A installation limit, permission=false, DP101=204, CP=6.1 V,
  power=0 kW, 22 physical DPs. Mode restored to Charge now, target=10 kWh,
  planner disabled, test interval removed.

Energy target completion, missing-meter handling, counter resets, target changes
and energy-budget restart recovery were checked with synthetic unit-test readings.
No fake energy was injected into the live HA instance. A real-load energy test is
still required before production approval of kWh accuracy/stop overshoot.
