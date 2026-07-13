# AmperePoint Tuya AP Pack

This folder contains the AmperePoint-specific material collected while testing
Q Series EV chargers with Home Assistant, Tuya, Xtend Tuya and `tuya-local`.

## Contents

```text
profiles/tuya_local/        tuya-local profile candidates
dashboards/                 Lovelace dashboard snippets
docs/                       DP maps, device notes and implementation notes
observations/               sanitized API dumps and short test observations
scripts/                    local HA/Tuya diagnostic scripts
../custom_components/       TuyaExtend AmperePoint HACS integration
```

## Recommended Test Flow

1. Add the charger to Tuya.
2. Let Home Assistant discover it through the standard Tuya integration and/or
   Xtend Tuya.
3. Dump the cloud-visible DPS with:

```powershell
.\scripts\dump-tuya-device-dp.ps1 -DeviceId <device_id>
```

4. Discover local LAN metadata with:

```powershell
.\scripts\find-tuya-local-ip.ps1 -DeviceId <device_id>
```

5. Add the charger to `tuya-local` using the matching profile from
   `profiles/tuya_local/`.
6. Watch live charging with:

```powershell
.\scripts\observe-q22-ota-session.ps1
```

or:

```powershell
.\scripts\observe-q37-session.ps1
```

Decode a raw DP6/DP7/DP8 phase payload with:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\decode-tuya-phase-payload.ps1 -Payload CNQAAAAAAA==
```

## Profiles

### `amperepoint_q22_ota_evcharger.yaml`

Product ID:

```text
cu111poj2mtikvls
```

Current confirmed cloud/HA DPS:

```text
1, 3, 4, 9, 13, 14, 17, 18, 24, 25
```

Candidate/local-only or product-defined DPS still requiring validation:

```text
6, 7, 8, 10, 19, 23, 33
```

DP4 current limit range observed through HA/Tuya Sharing API:

```text
6..32 A
```

### `amperepoint_ve_evcharger.yaml`

Product ID:

```text
fdfjiphjxtc9qyhd
```

Used for the tested Q37/VE charger. Phase DPS are intentionally not exposed as
production sensors for this generation because the tested unit produced invalid
decoded values.

### `amperepoint_q_series_evcharger.yaml`

Older Q Series profile for the first test charger. This generation exposed local
phase payloads on DP6/DP7/DP8.

## Key Documents

```text
docs/amperepoint-q22-ha-reference-map.md
docs/q22-ota-dp-map.md
docs/device-<device_id_q22_ota_current>.md
docs/device-<device_id_q22_ota_legacy>.md
docs/device-<device_id_q37_ve>.md
docs/q-series-generations.md
docs/charging-data-model.md
docs/local-mode-research.md
docs/tuya-platform-reporting.md
```

## Raw API Dumps

The most useful sanitized dumps are:

```text
observations/q22-ota-standard-ha-tuya-api-raw-20260611.json
observations/q22-ota-standard-ha-tuya-datapoints-20260611.json
```

They show that the standard Home Assistant Tuya integration receives only:

```text
forward_energy_total
work_state
charge_cur_set
power_total
connection_state
work_mode
energy_charge
switch
temp_current
charge_energy_once
```

and does not receive:

```text
phase_a
phase_b
phase_c
fault
local_timer
system_version
mode_set
```

## Dashboards

```text
dashboards/q22-ota-ha-test.yaml
dashboards/q37-ha-test.yaml
dashboards/amperepoint.yaml
```

The Q22 OTA dashboard has three views:

- HACS/AmperePoint normalized entities,
- Tuya Cloud/Xtend entities,
- `tuya-local` entities and phase diagnostics.

## Energy Model

The AmperePoint extension supports three session-energy strategies:

```text
session_entity
total_delta
power_integration
```

Use `session_entity` when a DP is already a resetting session counter, as with
the tested Q37 DP1 behavior. Use `total_delta` when a non-resettable/lifetime
meter is available, as expected for newer Q22 OTA firmware.

Session cost is calculated as:

```text
session_energy_kwh * tariff
```

The tariff can be a fixed value or a Home Assistant entity.
