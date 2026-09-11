# Wallbox PRIME: split-telemetry firmware

Profile: `amperepoint_prime_split_evcharger.yaml`.
Display name: **Ampere Point Wallbox PRIME (local)**.
Observed product ID: `3tajnmwugclfmotb`; Tuya LAN 3.5.
Firmware observed: `(V7.0.0)F2.0.0`.

This is a separate firmware profile, not a separate marketing/power model.
Select profiles by matching live DPS, not by a nominal 11/22 kW label.
The existing `amperepoint_prime_22kw_evcharger.yaml` is preserved for the
different DP layout already tested with the earlier PRIME.

## Verified with a tester on 2026-09-11

- Authenticated local status read succeeded.
- Schema and actual Tuya Local `matches`/`match_quality` validation passed
  against the sanitized captured DPS (quality 101 with the matching PID).
- DP102 contains aggregate `L`, temperature and session fields; it does not
  contain the earlier per-phase three-item arrays or control pilot.
- DP117 contains two-item phase arrays and `cp`; the observed `cp=61` matches
  a connected EVSE tester. The dashboard reads CP from this source.
- DP154 is boolean here, unlike the integer in the earlier profile.
- `STATE_C` remains a raw status, not a claim that power is flowing.

## Limits

Read-only profile: no switch, number or select entities and no write commands.
Current setting, bounds and schedule values remain diagnostics. DP150=32 and
DP152=16 must not be treated as confirmed writable limits.

The test had no load. Non-zero power/energy scaling and DP117 phase-current
scaling still need a loaded session. DP117 is available in raw diagnostics;
the dashboard does not invent per-phase power/current from those short arrays.
RFID/card datapoints and credentials are not included in the fixture/profile.

## Installation

The family installer bundles both profiles. Existing different files are kept;
a conflict in one profile does not stop installation of the other generation.
Alternatively, copy this YAML to `config/custom_components/tuya_local/devices/`,
restart HA, add the charger in Tuya Local and select the matching Wallbox PRIME
profile. Existing devices do not have their profile silently replaced.

For split CP support in the AmperePoint panel, the accompanying decoder changes
are required; released version 0.5.37 does not yet decode DP117 control pilot.
