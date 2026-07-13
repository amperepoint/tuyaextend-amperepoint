# Local Tuya mode research

## Decision

For EVSE discovery, use `tuya-local` first, not `localtuya`.

Reason: `tuya-local` already contains EV charger device profiles matching our product ID `bktb3jskdic1ar2t`. Those profiles include optional local DPS for phase data that are not visible in the current Tuya Sharing cloud dump.

Installed in HA:

```text
/config/custom_components/tuya_local
```

Installed version:

```text
2026.5.4
```

`tinytuya==1.18.0` was also installed inside the current HA container so the config flow imports cleanly.

## Why not localtuya first

`localtuya` is useful for manual DP-by-DP mapping and can work without Cloud API, but for easy local key retrieval it strongly prefers a Tuya IoT Cloud API account. That is a heavier path for regular users.

`tuya-local` offers a cloud-assisted path using the Tuya/SmartLife app account to retrieve local connection data, without requiring a Tuya IoT developer account. It also has typed device profiles, which matters for EVSE.

## Matching EVSE profiles found

`tuya-local` has at least two EV charger profiles for product ID:

```text
bktb3jskdic1ar2t
```

Relevant profile files in `tuya-local`:

```text
custom_components/tuya_local/devices/nine_ev_charger.yaml
custom_components/tuya_local/devices/noeifevo_q21w_evcharger.yaml
```

Both profiles include:

| DP | Meaning |
| --- | --- |
| `3` | work state |
| `4` | charging current limit |
| `9` | total power |
| `10` | fault bitfield |
| `14` | charging mode |
| `18` | switch |
| `25` | last/session energy |

The important local-only candidates are:

| DP | Meaning |
| --- | --- |
| `6` | phase A base64 payload: voltage/current/power |
| `7` | phase B base64 payload: voltage/current/power |
| `8` | phase C base64 payload: voltage/current/power |
| `10` | fault bitfield |
| `19` | charge time or schedule payload |
| `23` | system version |

These were not exposed by Tuya Sharing API for `<device_id_q_series_legacy>`, but may appear through the local protocol.

## Current local setup state

- `tuya_local` is installed.
- `tuya_local` has one config entry for `WE1CK46_EV`.
- The entry was first created with `zencar_ev_charger`, then switched to the custom `amperepoint_q_series_evcharger` profile.
- Home Assistant starts cleanly with only the standard custom integration warning.
- Local IP discovered by TinyTuya host scan:

```text
<local_ip_q_series_legacy>
```

Current local discovery result:

```text
Device ID: <device_id_q_series_legacy>
IP: <local_ip_q_series_legacy>
Product ID: bktb3jskdic1ar2t
Local protocol version: 3.4
Tuya TCP port: 6668
```

Custom profile installed in HA:

```text
custom_components/tuya_local/devices/amperepoint_q_series_evcharger.yaml
```

Second candidate profile for the phase-dynamic `EV Charger VE` / product ID `fdfjiphjxtc9qyhd`:

```text
custom_components/tuya_local/devices/amperepoint_ve_evcharger.yaml
```

This profile was confirmed by `tuya-local` for `Q37 VG` with product ID `fdfjiphjxtc9qyhd` and quality `101%`.

The `Q22 OTA` product ID has a separate candidate profile:

```text
profiles/tuya_local/amperepoint_q22_ota_evcharger.yaml
```

This candidate was added from a Tuya Developer function-definition screenshot. It should be verified on hardware before upstreaming.

Observed local DPS:

```text
1, 3, 4, 9, 10, 13, 14, 18, 24
```

Local phase DPS `6`, `7`, `8` are not used in the tested `EV Charger VE` profile because the current Q37 unit produced invalid decoded values when those DPS were included. They remain in the Q22 OTA candidate profile where the Tuya Developer definition explicitly lists phase raw DPS.

The profile is also documented in:

```text
docs/tuya-local-amperepoint-q-series.yaml
```

The full profile copy for reuse is stored in:

```text
profiles/tuya_local/amperepoint_q_series_evcharger.yaml
```

## Local discovery result

Direct TinyTuya local reads confirmed DPS `6`, `7`, `8`:

| DP | Raw base64 | Decoded |
| --- | --- | --- |
| `6` | `CMoAE4gEZQ==` | A: `225.0 V`, `5.0 A`, `1.125 kW` |
| `7` | `CMoAEyQDhA==` | B: `225.0 V`, `4.9 A`, `0.9 kW` |
| `8` | `CMoAEyQDhA==` | C: `225.0 V`, `4.9 A`, `0.9 kW` |

After switching to the custom profile, HA exposed:

```text
sensor.we1ck46_ev_napiecie_a
sensor.we1ck46_ev_napiecie_b
sensor.we1ck46_ev_napiecie_c
sensor.we1ck46_ev_prad_a
sensor.we1ck46_ev_prad_b
sensor.we1ck46_ev_prad_c
sensor.we1ck46_ev_moc_a
sensor.we1ck46_ev_moc_b
sensor.we1ck46_ev_moc_c
binary_sensor.we1ck46_ev_problem
```

TuyaExtend AmperePoint now uses the local phase sensors for:

```text
source_voltage_l1/l2/l3
source_current_l1/l2/l3
```

Confirmed TuyaExtend output:

```text
Liczba faz: 3
Napiecie L1/L2/L3: 225.0 / 224.0 / 225.0 V
Prad L1/L2/L3: 5.0 / 4.9 / 4.9 A
Blad: Brak bledu
```

## Test procedure after reconnecting EVSE

1. Connect the EVSE back to the same LAN as Home Assistant.
2. Close the Tuya/SmartLife app on phones that are on the same local network.
3. In HA, go to `Settings -> Devices & services -> Add integration`.
4. Choose `Tuya Local`.
5. Prefer the cloud-assisted setup path.
6. Select device `WE1CK46_EV` / `<device_id_q_series_legacy>`.
7. If the cloud does not provide the local IP, enter:

```text
<local_ip_q_series_legacy>
```

If DHCP changes the address, run:

```powershell
.\scripts\find-tuya-local-ip.ps1 -DeviceId <device_id_q_series_legacy>
```

8. If asked for device type, pick the matching EV charger profile:

```text
Nine 32A / bktb3jskdic1ar2t
```

or:

```text
Noeifevo Q21W / bktb3jskdic1ar2t
```

9. After setup, inspect whether these entities appear:

```text
Voltage A/B/C
Current A/B/C
Power A/B/C
Fault
System version
Charge time / schedule
```

10. If `tuya-local` reports local DPS in logs but does not create expected entities, copy the local DPS dump into `docs/device-<device_id_q_series_legacy>.md`.

## Caution

Many Tuya devices allow only one local connection. Do not configure both `tuya-local` and `localtuya` against the same EVSE at the same time. Also avoid leaving the Tuya/SmartLife mobile app open during local setup.

## Expected result

Best case: local DPS `6`, `7`, `8` are available and decode into voltage/current/power per phase.

Fallback: local mode only exposes the same DPS we already have from cloud:

```text
3, 4, 9, 14, 18, 25
```

If fallback happens, keep the main integration on `xtend_tuya`/Tuya Sharing and do not make local mode a requirement.

For this device, fallback did not happen: local DPS `6`, `7`, `8` are available.
