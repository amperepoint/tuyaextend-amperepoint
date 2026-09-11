# PRIME LAN dashboard and HA charging modes

Local beta 0.5.38b4 extends the verified `prime_split_v1` control adapter with
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
