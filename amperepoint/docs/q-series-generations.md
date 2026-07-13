# AmperePoint Q Series generations

## Principle

Treat tested chargers as AmperePoint Q Series generations, not as unrelated products. The HACS integration should expose one consistent AmperePoint data model, while `tuya-local` profiles document how each Tuya product ID reports DPS.

Default assumptions for Q Series:

- Support up to 3 phases.
- Detect active phase count dynamically from L1/L2/L3 current sensors.
- Do not assume one universal energy DP.
- Prefer cloud/Xtend entities for the first HACS version.
- Use `tuya-local` profiles to discover and decode local-only phase payloads.

## Known generations

| Product ID | HA model/name | Device ID observed | Current source | Energy behavior |
| --- | --- | --- | --- | --- |
| `bktb3jskdic1ar2t` | `EV Charging Station` / `WE1CK46_EV` | `<device_id_q_series_legacy>` | Cloud + local | DP25 `charge_energy_once` exposed by cloud; local DP6/7/8 expose phases. |
| `fdfjiphjxtc9qyhd` | `EV Charger VE` / `Q37 VG` | `<device_id_q37_ve>` | Cloud/Xtend + local | Local DP1 `forward_energy_total` rises live but resets on unplug/replug, so treat it as current-session energy. DP25 latches the completed previous session. DP10 fault works; DP6/7/8 did not decode correctly on the currently tested unit. |
| `cu111poj2mtikvls` | `Q22 OTA` | `<device_id_q22_ota_legacy>` | Cloud/Xtend + local | Earlier pairing. Product definition includes DP1, DP6/7/8, DP10, DP13, DP17, DP19, DP23, DP24, DP25 and DP33. Local status confirmed DP1, DP3, DP4, DP9, DP10, DP13, DP14, DP18, DP24, DP25. DP6/7/8/19/23/33 did not return payload while waiting. Paused baseline was DP1 `0.90 kWh`, DP25 `0.02 kWh`. |
| `cu111poj2mtikvls` | `Q22 OTA` | `<device_id_q22_ota_current>` | Cloud/Xtend | Current pairing after re-adding to Tuya on 2026-06-11. Online. Cloud status confirms DP1, DP3, DP4, DP9, DP13, DP14, DP17, DP18, DP24 and DP25. Current DP4 range is `6..32 A`. LAN broadcast found IP `<local_ip_q22_ota_current>`, protocol `3.5`; local key must be refreshed before `tuya-local` can be used. |

## Tuya Developer export

Developer export captured additional Q Series projects:

| Product name | Product ID | Notes |
| --- | --- | --- |
| `Q21_11kW_with_OTA` | `kvldga0omutrnify` | Newer OTA generation candidate. |
| `Q20_7KW_with_OTA` | `1qu8ca6etdubbigj` | Seen earlier in HA registry as `Q20_7-vdevo`. |
| `Q20_3.5KW_with_OTA` | `c2sgesr3zo1met7q` | Candidate generation. |
| `Q11_11KW_with_OTA` | `3axf0fkgiop0ukhb` | Seen earlier in HA registry as `Q11 OTA`. |
| `Q22 OTA` | `cu111poj2mtikvls` | Function definition screenshot captured. |
| `EV Charger_NO_OTA_3.5KW_7KW_11KW_22KW` | `jhlyzpk5nfk28nrh` | Candidate non-OTA generation. |
| `EV Charger_VE` | `fdfjiphjxtc9qyhd` | Tested as Q37 VG. |

Full export summary:

```text
docs/tuya-developer-products.md
```

EV Charger VE function map:

```text
docs/product-fdfjiphjxtc9qyhd-ev-charger-ve.md
```

Q22 OTA function map:

```text
docs/product-cu111poj2mtikvls-q22-ota.md
```

Q22 OTA physical device map:

```text
docs/device-<device_id_q22_ota_legacy>.md
```

Q22 OTA current pairing:

```text
docs/device-<device_id_q22_ota_current>.md
```

Q22 OTA practical DP-to-HA map:

```text
docs/q22-ota-dp-map.md
```

Q22 producer reference map:

```text
docs/amperepoint-q22-ha-reference-map.md
```

## Current Q37 observation

After adding a TuyaExtend test entry with:

```text
source_total_energy: sensor.q37_vg_total_energy
session_energy_mode: total_delta
```

the normalized HACS entity behaved correctly during live charging:

| Time | Source total | Normalized session | Cost |
| --- | --- | --- | --- |
| 17:02:22 | `0.47 kWh` | `0.00 kWh` | `0.00 PLN` |
| 17:02:37 | `0.52 kWh` | `0.05 kWh` | `0.06 PLN` |

At the same time `sensor.q37_vg_charge_energy_single` stayed at `3.38 kWh`, so this generation should not use DP25 as live session energy until proven otherwise.

After adding `Q37 VG` to `tuya-local`, the profile `amperepoint_ve_evcharger` matched with quality `101%`. Local DPS confirmed:

```text
1, 3, 4, 9, 10, 13, 14, 18, 24
```

The Tuya Developer definition for `EV Charger_VE` lists raw phase DPS `6`, `7`, `8`, matching the Q22 OTA function map. On the actual Q37 VG test unit, however, local DPS `6`, `7`, `8` were not present in direct `status()` or forced `updatedps()` reads. When included in the profile, the HA sensors later produced invalid decoded values such as `0.8 V`, `12582.931 A` and `2360.192 kW`, so phase DPS were removed from the tested `EV Charger VE` profile and should not be mapped into HACS for this generation until raw payloads are understood.

The HACS test entry was then switched from Xtend/cloud sources to local sources:

```text
source_status: sensor.q37_vg_status
source_connected: sensor.q37_vg_connection
source_power: sensor.q37_vg_moc
source_total_energy: sensor.q37_vg_energia
source_error: binary_sensor.q37_vg_problem
session_energy_mode: total_delta
```

Observed after switching to local sources:

| Time | Local total | HACS session | HACS cost | Fault |
| --- | --- | --- | --- | --- |
| 17:13:36 | `0.71 kWh` | `0.02 kWh` | `0.02 PLN` | `off` |
| 17:15:07 | `0.74 kWh` | `0.05 kWh` | `0.06 PLN` | `off` |

Later pause/resume and unplug/replug testing showed that Q37 DP1 is not a lifetime counter. It reached `1.50 kWh`, DP25 latched `1.53 kWh` when unplugged, and DP1 restarted at `0.01 kWh` on the next plug-in. The Q37 HACS mapping was changed to:

```text
source_session_energy: sensor.q37_vg_energia
session_energy_mode: session_entity
source_total_energy: unmapped
```

This makes HACS session energy match the actual Q37 session counter and avoids showing a false lifetime/total energy value.

## Energy strategies

The HACS integration supports these session energy modes:

| Mode | Use |
| --- | --- |
| `auto` | Prefer configured total energy delta, then session entity, then power integration. |
| `session_entity` | Use a source entity that is already the current session energy. Good when a DP resets on unplug/replug, as Q37 DP1 did in the live test. |
| `total_delta` | Use delta from cumulative total energy. Good when `forward_energy_total` is a true non-resettable meter, as expected for Q22 OTA. |
| `power_integration` | Integrate power over time. Fallback when energy counters are unreliable. |

Recommended mapping for `fdfjiphjxtc9qyhd` after the session test:

```text
source_power: sensor.q37_vg_moc
source_session_energy: sensor.q37_vg_energia
source_total_energy: unmapped
session_energy_mode: session_entity
```

Recommended mapping for Q22 OTA if the non-resettable counter is confirmed:

```text
source_power: sensor.<q22>_moc
source_total_energy: sensor.<q22>_energia
session_energy_mode: total_delta
```

Recommended mapping for `bktb3jskdic1ar2t` depends on live retest:

```text
source_power: sensor.we1ck46_ev_total_power
source_session_energy: sensor.we1ck46_ev_charge_energy_single
session_energy_mode: session_entity
```

If DP25 turns out to be last-session only on a generation, do not use it for active session cost. Prefer a live resetting session counter (`session_entity`) or a non-resettable meter with persisted baseline (`total_delta`).

## Tuya Local profile work

Profiles in this repo:

```text
profiles/tuya_local/amperepoint_q_series_evcharger.yaml
profiles/tuya_local/amperepoint_ve_evcharger.yaml
profiles/tuya_local/amperepoint_q22_ota_evcharger.yaml
```

They should be kept alongside the HACS integration. The profile naming can stay product/generation-specific even when the HACS model is generic Q Series. The VE/Q37 profile currently excludes DP6/7/8 phase sensors because the tested unit produced invalid decoded values. The Q22 OTA profile keeps DP6/7/8 as a candidate for the next physical test.

## Next generation test checklist

1. Add the charger to Tuya and capture Device ID + Product ID.
2. Run cloud DP dump.
3. Check which energy fields rise during a 5-10 minute charge.
4. Add to `tuya-local` and check local DP6/7/8 for phases.
5. Record whether DP25 is live session energy or last-session energy.
6. Decide HACS mapping: `session_entity`, `total_delta`, or `power_integration`.
