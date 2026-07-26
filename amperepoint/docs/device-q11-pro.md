# Device map: Ampere Point Q11 PRO (11 kW Q Series)

## Scope

LAN observations captured on 2026-07-25 through `tuya-local`, protocol `3.5`.
The Q11 PRO speaks the classic Q Series datapoint set, unlike the Wallbox
Prime 22kW, which packs its telemetry into a single JSON datapoint.

## Confirmed local DP set

A `LOCAL DPS` capture taken with the charger free and idle:

```json
{"3": "charger_free", "4": 8, "9": 0, "10": 0,
 "13": "controlpi_12v", "14": "charge_now", "18": true, "24": 25}
```

| DP | Type | Value seen | Meaning |
| --- | --- | --- | --- |
| `3` | string | `charger_free` | Work state, same vocabulary as Q22 OTA. |
| `4` | integer | `8` | Configured charging current, in amperes. |
| `9` | integer | `0` | Total power, tenths of kW. |
| `10` | bitfield | `0` | Fault flags; `0` means no fault. |
| `13` | string | `controlpi_12v` | Control-pilot / vehicle connection state. |
| `14` | string | `charge_now` | Charging mode. |
| `18` | boolean | `true` | Charging switch. |
| `24` | integer | `25` | Charger temperature in degrees Celsius. |

The unit did **not** report a lifetime meter (`1`), target energy (`17`), a
last-session counter (`25`) or phase payloads (`6`, `7`, `8`). Session energy
is therefore integrated from power by the AmperePoint layer unless a cumulative
source is mapped.

## tuya-local profile

```text
amperepoint/profiles/tuya_local/amperepoint_q11_pro_evcharger.yaml
```

tuya-local auto-selects the unrelated third-party `aimiler_11kW_evcharger`
config for this charger: it declares the same eight datapoints, so it also
scores a 100% match, but it names and scales them differently and produces
entities that do not correspond to this device. The shipped profile must be
picked explicitly in the device-type step; it appears as
`Ampere Point Q11 PRO (amperepoint_q11_pro_evcharger)`.

Replaying tuya-local's matcher over the capture above scores the profile at
`matches=True, quality=100%`.

## Cloud versus local

The official Tuya cloud integration exposes this charger's DP 3, 10, 13 and 18
through the AmperePoint normalization layer, which is enough for status,
vehicle state, fault and start/stop. Power, current limit, charging mode and
temperature are more reliable over LAN, so pairing the charger in `tuya-local`
with this profile in addition to the cloud entry is recommended. AmperePoint
recognizes both registry devices as the same physical charger and keeps a
single entry.
