# Device map: <device_id_q_series_legacy>

## Device

- Device ID: `<device_id_q_series_legacy>`
- HA device name: `WE1CK46_EV`
- Manufacturer: `Tuya`
- Model: `EV Charging Station`
- Model ID: `bktb3jskdic1ar2t`

## Integrations installed

- Official Tuya: configured and active.
- Xtend Tuya: installed manually as `custom_components/xtend_tuya`, version `4.4.7`.
- TuyaExtend AmperePoint: installed manually as `custom_components/tuyaextend_amperepoint`.

`xtend_tuya` was configured from the existing official Tuya config entry in `no_openapi=true` mode. A storage backup was created before the change:

```text
<ha_storage_backup_path>
```

TuyaExtend AmperePoint was then configured against the `xtend_tuya` entities. A storage backup was created before the change:

```text
<ha_storage_backup_path>
```

## Source entities

| Source | Entity | DP code from unique_id | Meaning |
| --- | --- | --- | --- |
| Official Tuya | `switch.we1ck46_ev_switch` | `switch` | Start/stop charging |
| Xtend Tuya | `number.we1ck46_ev_charging_current` | `charge_cur_set` | Current limit in A |
| Xtend Tuya | `sensor.we1ck46_ev_charge_energy_single` | `charge_energy_once` | Session energy in kWh |
| Xtend Tuya | `sensor.we1ck46_ev_work_state` | `work_state` | Charger work state |
| Xtend Tuya | `sensor.we1ck46_ev_total_power` | `power_total` | Total charging power in kW |
| Xtend Tuya | `event.we1ck46_ev_device_notifications` | `xt_device_event_notify` | Device notifications |

## Raw Tuya DP

Dump command:

```powershell
.\scripts\dump-tuya-device-dp.ps1 -DeviceId <device_id_q_series_legacy>
```

Current raw DP from Tuya Sharing API:

| DP ID | Code | Current raw value | Type/range | Meaning |
| --- | --- | --- | --- | --- |
| `3` | `work_state` | `charger_charging` | enum: `charger_free`, `charger_insert`, `charger_free_fault`, `charger_wait`, `charger_charging`, `charger_pause`, `charger_end`, `charger_fault` | Work state |
| `4` | `charge_cur_set` | `14` | integer, `6..48 A`, step `1` | Current limit |
| `9` | `power_total` | `4936` | integer, scale `3`, unit `kW` | Total power, displayed as `4.936 kW` |
| `14` | `work_mode` | `charge_now` | enum: `charge_now`, `charge_pct`, `charge_energy`, `charge_schedule` | Charging mode |
| `18` | `switch` | `true` | boolean | Start/stop |
| `25` | `charge_energy_once` | `4` | integer, scale `2`, unit `kW h` | Session energy, displayed as `0.04 kWh` |

No voltage or per-phase current DP was exposed for this Device ID by Tuya Sharing API.

## TuyaExtend AmperePoint mapping

| TuyaExtend field | Entity |
| --- | --- |
| `model` | `q22` or generic `q_series` |
| `source_status` | `sensor.we1ck46_ev_work_state` |
| `source_power` | `sensor.we1ck46_ev_total_power` |
| `source_session_energy` | `sensor.we1ck46_ev_charge_energy_single` |
| `source_current_limit` | `number.we1ck46_ev_charging_current` |
| `source_charge_switch` | `switch.we1ck46_ev_switch` |
| `tariff_value` | `1.2` |
| `currency` | `PLN` |

## TuyaExtend entities created

| Entity | Last observed state |
| --- | --- |
| `sensor.amperepoint_q22_status` | `Ladowanie` |
| `binary_sensor.amperepoint_q22_auto_podlaczone` | `on` |
| `sensor.amperepoint_q22_moc` | `4.936 kW` |
| `sensor.amperepoint_q22_energia_sesji` | `0.04 kWh` |
| `sensor.amperepoint_q22_koszt_sesji` | `0.05 PLN` |
| `number.amperepoint_q22_limit_pradu` | `14 A` |
| `switch.amperepoint_q22_ladowanie` | `on` |

Timestamp for the last state check in HA database: `2026-05-27 10:48:53 UTC`.

## Status mapping learned

`sensor.we1ck46_ev_work_state` reported:

```text
charger_charging
```

This is now mapped by TuyaExtend AmperePoint to:

```text
Ladowanie
```

Known Xtend Tuya EV work states found in translations:

| Raw value | TuyaExtend value |
| --- | --- |
| `charger_free` | `Gotowy` |
| `charger_insert` | `Auto podlaczone` |
| `charger_wait` | `Gotowy` |
| `charger_charging` | `Ladowanie` |
| `charger_pause` | `Wstrzymane` |
| `charger_end` | `Zakonczone` |
| `charger_fault` | `Blad` |
| `charger_free_fault` | `Blad` |

## Current gaps

- Cloud API did not expose voltage L1/L2/L3 or current L1/L2/L3.
- Local Tuya mode exposes voltage/current/power per phase through DPS `6`, `7`, `8`.
- No explicit vehicle-connected source entity yet; TuyaExtend currently infers connection from charging/power.
- Phase detection can now use local phase current sensors.
- `event.we1ck46_ev_device_notifications` is available, but not yet mapped as an error/status source.
- `work_mode` exists in raw DP, but is not exposed as a HA entity by `xtend_tuya` for this device yet.

## Local Tuya phase map

The custom `tuya-local` profile `amperepoint_q_series_evcharger` decodes:

| Local DP | Phase | Payload | Decoded sample |
| --- | --- | --- | --- |
| `6` | A / L1 | base64 voltage/current/power | `225.0 V`, `5.0 A`, `1.125 kW` |
| `7` | B / L2 | base64 voltage/current/power | `225.0 V`, `4.9 A`, `0.9 kW` |
| `8` | C / L3 | base64 voltage/current/power | `225.0 V`, `4.9 A`, `0.9 kW` |

TuyaExtend source additions:

```text
source_connected: sensor.we1ck46_ev_status
source_error: binary_sensor.we1ck46_ev_problem
source_voltage_l1: sensor.we1ck46_ev_napiecie_a
source_voltage_l2: sensor.we1ck46_ev_napiecie_b
source_voltage_l3: sensor.we1ck46_ev_napiecie_c
source_current_l1: sensor.we1ck46_ev_prad_a
source_current_l2: sensor.we1ck46_ev_prad_b
source_current_l3: sensor.we1ck46_ev_prad_c
```

## Next test actions

1. Change the current limit from HA and confirm the charger physically follows it.
2. Stop charging from `switch.amperepoint_q22_ladowanie` and confirm `switch.we1ck46_ev_switch` follows.
3. Observe `sensor.we1ck46_ev_work_state` for idle, plugged, charging, paused, finished and fault states.
4. Check if `xtend_tuya` exposes more entities after a reconnect or after adding Tuya OpenAPI credentials.
5. If voltage/current phase data remains missing, collect diagnostics from official Tuya and Xtend Tuya.
