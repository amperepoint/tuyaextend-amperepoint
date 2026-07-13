# Device map: <device_id_q22_ota_legacy>

## Device

- Device ID: `<device_id_q22_ota_legacy>`
- HA device name: `Q22 OTA`
- Manufacturer in HA: `Tuya`
- Model/product name: `Q22 OTA`
- Product/model ID: `cu111poj2mtikvls`
- Category: `qccdz`
- Local IP discovered by TinyTuya broadcast: `<local_ip_q22_ota_legacy>`
- Local protocol version: `3.5`
- Test state at discovery: vehicle detected / paused, not charging.

## Cloud DP dump

Dump command:

```powershell
.\scripts\dump-tuya-device-dp.ps1 -DeviceId <device_id_q22_ota_legacy>
```

Observed while paused:

| DP ID | Code | Raw value | Scale/unit | Meaning |
| --- | --- | --- | --- | --- |
| `1` | `forward_energy_total` | `90` | scale `2`, `kWh` | `0.90 kWh`; expected to be non-resettable on Q22, needs physical confirmation. |
| `3` | `work_state` | `charger_wait` | enum | Waiting/paused. |
| `4` | `charge_cur_set` | `16` | `A` | Current limit. |
| `9` | `power_total` | `0` | scale `3`, `kW` | Not charging. |
| `13` | `connection_state` | `controlpi_9v` | enum | Vehicle detected. |
| `14` | `work_mode` | `charge_now` | enum | Immediate charging mode. |
| `17` | `energy_charge` | `1` | `kWh` | Fixed-energy target value. |
| `18` | `switch` | `false` | bool | Start/stop off. |
| `24` | `temp_current` | `44..47` | `C` | Charger temperature. |
| `25` | `charge_energy_once` | `2` | scale `2`, `kWh` | `0.02 kWh`; needs observation to determine whether live or previous-session value. |

Local strategy from cloud:

```text
1  -> forward_energy_total
3  -> work_state
4  -> charge_cur_set
9  -> power_total
13 -> connection_state
14 -> work_mode
17 -> energy_charge
18 -> switch
24 -> temp_current
25 -> charge_energy_once
```

## HA entities

Xtend/native Tuya entities observed:

| Entity | Paused state |
| --- | --- |
| `sensor.q22_ota_work_state` | `charger_wait` |
| `sensor.q22_ota_connection_state` | `controlpi_9v` |
| `sensor.q22_ota_total_power` | `0.0 kW` |
| `sensor.q22_ota_total_energy` | `0.9 kWh` |
| `sensor.q22_ota_charge_energy_single` | `0.02 kWh` |
| `number.q22_ota_charging_current` | `16 A` |
| `switch.q22_ota_switch_2` | `off` |
| `sensor.q22_ota_temperatura` | `44..47 C` |

`switch.q22_ota_switch` from Xtend was `unavailable` after restart. The working start/stop source is the native Tuya entity:

```text
switch.q22_ota_switch_2
```

## Tuya Local

The device was added to `tuya-local` with:

```text
type: amperepoint_q22_ota_evcharger
host: <local_ip_q22_ota_legacy>
protocol_version: 3.5
manufacturer: AmperePoint
model: Q22 OTA
```

`tuya-local` matched the profile with quality `101%`.

Local DPS confirmed by `tuya-local` and direct TinyTuya status:

```text
1, 3, 4, 9, 10, 13, 14, 18, 24, 25
```

Direct forced local reads for:

```text
6, 7, 8, 19, 23, 33
```

returned no additional payload while the charger was waiting/paused.

Local entities observed:

| Entity | State |
| --- | --- |
| `sensor.q22_ota_status` | `waiting` |
| `sensor.q22_ota_connection` | `vehicle_detected` |
| `sensor.q22_ota_moc` | `0.0 kW` |
| `sensor.q22_ota_energia` | `0.9 kWh` |
| `sensor.q22_ota_last_session_energy` | `0.02 kWh` |
| `binary_sensor.q22_ota_problem` | `off` |
| `sensor.q22_ota_temperatura_2` | `45..49 C` |
| `number.q22_ota_charging_current_2` | `16 A` |
| `switch.q22_ota` | `off` |
| `sensor.q22_ota_napiecie_a/b/c` | `unknown` |
| `sensor.q22_ota_prad_a/b/c` | `unknown` |
| `sensor.q22_ota_moc_a/b/c` | `unknown` |

Profile correction:

- DP10 fault description mapping was added to `profiles/tuya_local/amperepoint_q22_ota_evcharger.yaml`.
- Optional DP6/DP7/DP8 phase entities remain in the profile for validation during live charging, but are not mapped into HACS until a valid payload appears.

## TuyaExtend mapping

A dedicated HACS model was added:

```text
q22_ota -> AmperePoint Q22 OTA, up to 3 phases, 6..32 A
```

Current test mapping:

```text
source_status: sensor.q22_ota_status
source_connected: sensor.q22_ota_connection
source_power: sensor.q22_ota_moc
source_total_energy: sensor.q22_ota_energia
source_session_energy: sensor.q22_ota_last_session_energy
session_energy_mode: total_delta
source_current_limit: number.q22_ota_charging_current_2
source_charge_switch: switch.q22_ota
source_error: binary_sensor.q22_ota_problem
tariff_value: 1.20
currency: PLN
```

Observed HACS baseline after restart:

| Entity | State |
| --- | --- |
| `sensor.amperepoint_q22_ota_status` | `Gotowy` |
| `binary_sensor.amperepoint_q22_ota_auto_podlaczone` | `on` |
| `sensor.amperepoint_q22_ota_moc` | `0.0 kW` |
| `sensor.amperepoint_q22_ota_energia_calkowita` | `0.9 kWh` |
| `sensor.amperepoint_q22_ota_energia_sesji` | `0.0 kWh` |
| `sensor.amperepoint_q22_ota_koszt_sesji` | `0.0 PLN` |
| `sensor.amperepoint_q22_ota_blad` | `Brak bledu` |
| `sensor.amperepoint_q22_ota_taryfa` | `1.2 PLN/kWh` |
| `number.amperepoint_q22_ota_limit_pradu` | `16 A` |
| `switch.amperepoint_q22_ota_ladowanie` | `off` |

Persisted baseline:

```text
total_energy_baseline_kwh: 0.9
last_total_energy_kwh: 0.9
was_connected: true
```

## Test dashboard and logger

Dashboard:

```text
dashboards/q22-ota-ha-test.yaml
```

Logger:

```powershell
.\scripts\observe-q22-ota-session.ps1
```

Current background observation:

```text
observations/q22-ota-local-session-test-20260528-101923.csv
```

## Next test actions

1. Resume charging and observe whether DP1 `sensor.q22_ota_total_energy` continues from `0.90 kWh`.
2. Confirm HACS session energy grows as `DP1 - 0.90 kWh`.
3. Observe whether DP25 `sensor.q22_ota_charge_energy_single` grows live or remains a previous/small session value.
4. Pause/resume without unplugging and confirm baseline does not reset.
5. Unplug/replug and confirm whether DP1 remains non-resettable. If DP1 resets, change Q22 mapping to `session_entity`; if it does not reset, keep `total_delta`.
6. Add to `tuya-local` with profile `amperepoint_q22_ota_evcharger` and test DP6/DP7/DP8 phase payloads.
