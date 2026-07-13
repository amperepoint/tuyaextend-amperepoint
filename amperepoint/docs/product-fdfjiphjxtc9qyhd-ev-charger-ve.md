# Product map: EV Charger_VE / fdfjiphjxtc9qyhd

Source screenshot:

```text
<source_file_path>
```

This product is currently tested in HA as `Q37 VG`.

## Product

- Product name: `EV Charger_VE`
- Product ID: `fdfjiphjxtc9qyhd`
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
| `4` | Charge Current Set | `charge_cur_set` | Send and report | Value | `6..48 A`, scale `0` |
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

## Observed behavior on Q37 VG

The product definition lists DP6/DP7/DP8 phase raw values, but the currently tested unit did not provide a trustworthy local phase decode:

- Direct local status confirmed DPS `1`, `3`, `4`, `9`, `10`, `13`, `14`, `18`, `24`.
- Forced reads for DP6/DP7/DP8 did not produce a clean payload.
- When phase sensors were temporarily enabled in the `tuya-local` profile, HA showed physically impossible values such as `0.8 V`, `12582.931 A` and `2360.192 kW`.

For this tested VE/Q37 unit, keep DP6/DP7/DP8 unmapped until a valid raw payload is captured and decoded.

## HACS mapping used in the live test

Preferred local-source mapping:

```text
source_status: sensor.q37_vg_status
source_connected: sensor.q37_vg_connection
source_power: sensor.q37_vg_moc
source_session_energy: sensor.q37_vg_energia
session_energy_mode: session_entity
source_total_energy: unmapped
source_current_limit: number.q37_vg_charging_current_2
source_charge_switch: switch.q37_vg
source_error: binary_sensor.q37_vg_problem
source_voltage_l1/l2/l3: unmapped
source_current_l1/l2/l3: unmapped
```

Reason: the live Q37 test showed DP1 resets after unplug/replug. It is therefore a current-session counter on this tested generation, not a reliable lifetime meter.

## Comparison with Q22 OTA

The visible function map is effectively the same as the Q22 OTA screenshot. The difference is not the declared Tuya model, but the physical/local behavior observed in HA. Q22 OTA must therefore be tested independently:

- Does DP1 `forward_energy_total` rise live?
- Does DP25 `charge_energy_once` rise live or report only the last/current completed session?
- Do DP6/DP7/DP8 return valid raw phase payloads?
- Does the charger report one active phase or three active phases under load?
