# Product map: Q22 OTA / cu111poj2mtikvls

Source screenshot:

```text
<source_file_path>
```

This charger has not been physically connected/tested yet.

Physical test device was later added:

```text
docs/device-<device_id_q22_ota_legacy>.md
```

Practical DP-to-HA mapping:

```text
docs/q22-ota-dp-map.md
```

Producer reference mapping:

```text
docs/amperepoint-q22-ha-reference-map.md
```

## Product

- Product name: `Q22 OTA`
- Product ID: `cu111poj2mtikvls`
- Category: EV charger
- Protocol: Wi-Fi, Bluetooth LE
- Standard functions: 17
- Custom functions: 0
- Advanced functions: 6/7 enabled in the screenshot

## Standard functions

| DP ID | Name | Identifier | Transfer | Type | Properties |
| --- | --- | --- | --- | --- | --- |
| `1` | Total Forward Energy | `forward_energy_total` | Report only | Value | `0..99999999`, scale `2`, unit `kWh` |
| `3` | Work State | `work_state` | Report only | Enum | `charger_free`, `charger_insert`, `charger_free_fault`, `charger_wait`, `charger_charging`, `charger_pause`, `charger_end`, `charger_fault` |
| `4` | Charge Current Set | `charge_cur_set` | Send and report | Value | `6..32 A`, scale `0` in the current cloud API dump |
| `6` | Phase A | `phase_a` | Report only | Raw | Protocol parsing spec available in Tuya UI |
| `7` | Phase B | `phase_b` | Report only | Raw | Protocol parsing spec available in Tuya UI |
| `8` | Phase C | `phase_c` | Report only | Raw | Protocol parsing spec available in Tuya UI |
| `9` | Total power | `power_total` | Report only | Value | scale `3`, unit `kW` |
| `10` | Fault | `fault` | Report only | Fault | EVSE fault bitfield |
| `13` | Connection State | `connection_state` | Report only | Enum | `controlpi_12v`, `controlpi_12v_pwm`, `controlpi_9v`, `controlpi_9v_pwm`, `controlpi_6v`, `controlpi_6v_pwm`, `controlpi_error` |
| `14` | Work Mode | `work_mode` | Send and report | Enum | `charge_now`, `charge_energy`, `charge_schedule` |
| `17` | Energy Charge | `energy_charge` | Send and report | Value | `1..200 kWh`, scale `0` |
| `18` | Switch | `switch` | Send and report | Bool | Start/stop |
| `19` | Schedule charging | `local_timer` | Send and report | Raw | Protocol parsing spec available in Tuya UI |
| `23` | System version | `system_version` | Report only | String | Firmware/system version |
| `24` | Current temp | `temp_current` | Report only | Value | `-40..200 C`, scale `0` |
| `25` | Once Charge Energy | `charge_energy_once` | Report only | Value | `1..999999 kWh`, scale `2` |
| `33` | Charge mode | `mode_set` | Send and report | Raw | Protocol parsing spec available in Tuya UI |

## Fault values

The screenshot includes these fault labels for DP10:

```text
ov_cr
ov2_cr_fault
ov_vol
undervoltage_alarm
contactor_adhesion
contactor_fault
earth_fault
meter_hardware_alarm
scram_fault
cp_fault
meter_commu_fault
card_reader_fault
cir_short_fault
adhesion_fault
self_test_alarm
leakagecurr_alarm
over_temp_fault
```

## Expected HACS mapping

Use generic Q Series model:

```text
model: q_series
session_energy_mode: auto
```

When connected through `tuya-local`, prefer:

```text
source_status: sensor.<device>_status
source_connected: sensor.<device>_connection
source_power: sensor.<device>_moc
source_total_energy: sensor.<device>_energia
source_current_limit: number.<device>_charging_current
source_charge_switch: switch.<device>
source_error: binary_sensor.<device>_problem
source_voltage_l1/l2/l3: sensor.<device>_napiecie_a/b/c
source_current_l1/l2/l3: sensor.<device>_prad_a/b/c
```

Energy strategy to verify:

- If DP1 `forward_energy_total` is non-resettable and rises during charging, use `total_delta`.
- If DP25 `charge_energy_once` rises live from the current session start, `session_entity` can be used.
- If both are unreliable, use `power_integration`.

User expectation before physical test: this Q22 generation exposes a non-resettable meter counter. Initial paused baseline from the physical device was DP1 `0.90 kWh` and DP25 `0.02 kWh`. If DP1 remains non-resettable during unplug/replug tests, it should be the preferred source for reliable session cost, with TuyaExtend storing the baseline for the active plug-in session.

## Tuya Local profile

Candidate support was added to:

```text
profiles/tuya_local/amperepoint_q22_ota_evcharger.yaml
```

This is intentionally separate from the tested `EV Charger VE` profile. Q37/VE produced invalid phase values when DP6/7/8 were included, while the Q22 OTA Developer definition explicitly lists phase raw DPS. The phase raw layout still must be verified on hardware.
