# Wallbox Prime: profile installation and Q Series control parity

## Included in this change

AmperePoint ships the reviewed read-only Prime profile inside its HACS component
and offers an installer from both the initial configuration and options menus.
It installs only into an existing Tuya Local installation, preserves different
existing profiles, and can restore a file removed by an update. Restart and
pairing remain explicit steps. Credentials stay in Tuya Local.

Supported hardware: Wallbox Prime 22 kW, PID `gbmxngploofmhbjc`, LAN 3.5.
The existing DP102 decoder and discovery feed the standard dashboard sensors.
This does not claim that other Prime firmware or product IDs are compatible.

## Remaining work for control parity

The UI uses the family name Wallbox PRIME. PRIME 11 kW recognition is included
with a 16 A model ceiling; a family-only name also uses a conservative 16 A
fallback. The shared decoder is data-driven, but the 11 kW firmware/DP match
still needs a real-device check. Do not add an invented PID or assume writable
capabilities from the product name.

For a smoother local onboarding experience, native LAN transport, device/IP
discovery and credentials belong to the existing [native local source plan
(#15)](https://github.com/amperepoint/tuyaextend-amperepoint/issues/15).
The profile installer is a transitional option, not a bundled Tuya Local runtime.

1. Capture a baseline with the existing read-only profile and record firmware.
2. Change current in the Tuya app at several allowed settings; correlate DP150,
   DP107, DP152 and DP157, including allowed steps and hard device bounds.
3. Capture explicit start and stop operations and their acknowledgements. Do not
   infer a writable command from DP109 operating status or unknown boolean DPs.
4. Capture schedule enable/disable and charge-now transitions, including DP151.
   Preserve fields not changed by an operation; establish device timezone and
   overnight-window behavior before offering a writer.
5. Replay each verified command on the test charger and confirm actual reported
   state, including unplugged, connected, charging and rejected-command cases.
6. Expose only confirmed controls in the Tuya Local profile, preserving the
   identity of existing sensor entities so upgrades do not break automations.
7. Gate the AmperePoint planner on writable start/stop, current and mode support;
   add Prime adapters where its semantics differ from Q Series charge_now.
8. Verify timeout/retry, reconnect, restart and energy-target behavior, with
   hardware checks and sanitized regression fixtures. Document limitations.

No automatic HA restart, credential migration, replacement of existing Tuya
Local entries, or unverified writes to chargers are part of profile installation.
