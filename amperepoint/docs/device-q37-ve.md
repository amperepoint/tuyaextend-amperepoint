# Device map: <device_id_q37_ve>

## Device

- Device ID: `<device_id_q37_ve>`
- HA device name: `Q37 VG`
- Manufacturer in HA: `Tuya`
- Model: `EV Charger VE`
- Product/model ID: `fdfjiphjxtc9qyhd`
- Category: `qccdz`
- Local IP discovered by TinyTuya broadcast: `<local_ip_q37_ve>`
- Local protocol version: `3.4`
- Phase type: 1/3 phases. The currently connected unit behaves as 1-phase, but this product line must be mapped as phase-dynamic and should support 3 phases by default.

The value in parentheses from the HA device page, `fdfjiphjxtc9qyhd`, is the Tuya product/model ID. The Tuya device ID is `<device_id_q37_ve>`.

## Current HA state

Official Tuya created:

```text
switch.q37_vg_switch
```

After Home Assistant restart, Xtend Tuya created readable entities for the cloud-exposed DPS:

| Entity | Last observed state |
| --- | --- |
| `number.q37_vg_charging_current` | `16 A` |
| `sensor.q37_vg_work_state` | `charger_charging` |
| `sensor.q37_vg_connection_state` | `controlpi_6v` |
| `sensor.q37_vg_total_power` | `0.672 kW` |
| `sensor.q37_vg_total_energy` | `0.26..0.28 kWh` |
| `sensor.q37_vg_daily_total_energy` | `0.02..0.04 kWh` |
| `sensor.q37_vg_monthly_total_energy` | `0.02 kWh` |
| `sensor.q37_vg_yearly_total_energy` | `0.02 kWh` |
| `sensor.q37_vg_charge_energy_single` | `3.38 kWh` |
| `sensor.q37_vg_temperatura` | `29 C` |
| `event.q37_vg_device_notifications` | `unknown` |

No voltage/current phase entity is exposed by cloud/Xtend yet. That still needs local DP6/DP7/DP8 verification through `tuya-local`.

After adding to `Tuya Local`, the local profile matched correctly:

```text
type: amperepoint_ve_evcharger
host: <local_ip_q37_ve>
protocol_version: 3.4
manufacturer: AmperePoint
model: VE 1P/3P
```

Local entities observed:

| Entity | State |
| --- | --- |
| `sensor.q37_vg_status` | `charging` |
| `sensor.q37_vg_connection` | `ready_to_charge` |
| `sensor.q37_vg_moc` | `0.888 kW` |
| `sensor.q37_vg_energia` | `0.71 -> 0.74 kWh` |
| `binary_sensor.q37_vg_problem` | `off` |
| `sensor.q37_vg_temperatura_2` | `31 C` |
| `number.q37_vg_charging_current_2` | `16 A` |
| `switch.q37_vg` | `on` |
| `sensor.q37_vg_napiecie_a/b/c` | `unknown` |
| `sensor.q37_vg_prad_a/b/c` | `unknown` |
| `sensor.q37_vg_moc_a/b/c` | `unknown` |

Direct local `status()` confirmed DPS:

```text
1, 3, 4, 9, 10, 13, 14, 18, 24
```

Forced `updatedps()` for `6/7/8` did not return phase payloads on this unit.

Later, while DP6/7/8 were still present in the profile, HA briefly showed invalid decoded phase values:

```text
sensor.q37_vg_napiecie_a: 0.8 V
sensor.q37_vg_prad_a: 12582.931 A
sensor.q37_vg_moc_a: 2360.192 kW
```

Those are not physically plausible. The phase mappings were removed from the tested `EV Charger VE` profile and from the TuyaExtend Q37 test entry. Keep phase support for this product/generation disabled until the raw payload is captured and decoded correctly.

## Raw Tuya DP from cloud

Dump command:

```powershell
.\scripts\dump-tuya-device-dp.ps1 -DeviceId <device_id_q37_ve>
```

Observed values:

| DP ID | Code | Current raw value | Scale/unit | Meaning |
| --- | --- | --- | --- | --- |
| `1` | `forward_energy_total` | `24..28` | scale 2, `kWh` | Total forward energy, observed increasing from `0.16` to `0.28 kWh`. |
| `3` | `work_state` | `charger_charging` | enum | Work state. |
| `4` | `charge_cur_set` | `16` | `6..48 A` | Current limit. |
| `9` | `power_total` | `672` | scale 3, `kW` | Total power, `0.672 kW`. |
| `13` | `connection_state` | `controlpi_6v` | enum | CP/vehicle connection state. |
| `14` | `work_mode` | `charge_now` | enum | Charging mode. |
| `17` | `energy_charge` | `1` | `1..200 kWh` | Target energy for fixed-energy charge mode. |
| `18` | `switch` | `true` | boolean | Start/stop. |
| `24` | `temp_current` | `28..29` | `C` | Current charger temperature. |
| `25` | `charge_energy_once` | `338` | scale 2, `kWh` | Last/current session energy, `3.38 kWh`. |

Function/writeable DP:

| Code | Range |
| --- | --- |
| `charge_cur_set` | `6..48 A` |
| `work_mode` | `charge_now`, `charge_energy`, `charge_schedule` |
| `energy_charge` | `1..200 kWh` |
| `switch` | `true/false` |

## Local strategy from cloud

| Local DP | Code |
| --- | --- |
| `1` | `forward_energy_total` |
| `3` | `work_state` |
| `4` | `charge_cur_set` |
| `9` | `power_total` |
| `13` | `connection_state` |
| `14` | `work_mode` |
| `17` | `energy_charge` |
| `18` | `switch` |
| `24` | `temp_current` |
| `25` | `charge_energy_once` |

Potential local-only DP to verify after adding to `tuya-local`:

| DP | Candidate meaning |
| --- | --- |
| `6` | Phase A payload: voltage/current/power, likely base64 on EVSE profiles. |
| `7` | Phase B payload: voltage/current/power, optional for 3-phase variants. |
| `8` | Phase C payload: voltage/current/power, optional for 3-phase variants. |
| `10` | Fault bitfield, common on EVSE profiles but not exposed by current cloud dump. |
| `23` | System version, optional. |

## Tuya Local profile

Candidate profile:

```text
profiles/tuya_local/amperepoint_ve_evcharger.yaml
```

The same profile was also copied into the local HA `tuya_local` device profile folder so it can be selected/tested when the device is added to `Tuya Local`.

The tested VE profile intentionally does not expose phase payloads for DP `6`, `7` and `8` anymore. This Q37 unit produced invalid decoded phase values when those DPS were included, so phase entities must stay unmapped until a valid raw payload is captured. Q22 OTA has a separate candidate profile for phase testing:

```text
profiles/tuya_local/amperepoint_q22_ota_evcharger.yaml
```

## TuyaExtend model

Added model:

```text
q_series -> AmperePoint Q Series (auto), up to 3 phases, 6..48 A
q37 -> AmperePoint Q Series VE, up to 3 phases, 6..48 A
```

Recommended first TuyaExtend mapping once source entities exist:

| TuyaExtend field | Source |
| --- | --- |
| `model` | `q_series` or `q37` |
| `source_status` | `sensor.q37_vg_work_state` |
| `source_connected` | `sensor.q37_vg_connection_state` |
| `source_power` | `sensor.q37_vg_total_power` |
| `source_session_energy` | do not use `sensor.q37_vg_charge_energy_single` as live active-session energy; it latched after unplug in the test |
| `source_total_energy` | do not use as lifetime total for Q37; the observed counter resets on unplug/replug |
| `session_energy_mode` | use local mapping below after `tuya-local` is available |
| `source_current_limit` | `number.q37_vg_charging_current` |
| `source_charge_switch` | `switch.q37_vg_switch` |
| `source_voltage_l1` | local phase A voltage sensor, if DP6 confirms |
| `source_current_l1` | local phase A current sensor, if DP6 confirms |
| `source_voltage_l2/l3` | local phase B/C voltage sensors, if DP7/DP8 confirm |
| `source_current_l2/l3` | local phase B/C current sensors, if DP7/DP8 confirm |

After adding to `tuya-local`, preferred mapping is:

| TuyaExtend field | Local source |
| --- | --- |
| `source_status` | `sensor.q37_vg_status` |
| `source_connected` | `sensor.q37_vg_connection` |
| `source_power` | `sensor.q37_vg_moc` |
| `source_session_energy` | `sensor.q37_vg_energia` |
| `source_total_energy` | leave unmapped because Q37 DP1 is a resetting session counter |
| `session_energy_mode` | `session_entity` |
| `source_current_limit` | `number.q37_vg_charging_current_2` |
| `source_charge_switch` | `switch.q37_vg` |
| `source_error` | `binary_sensor.q37_vg_problem` |
| `source_voltage_l1/l2/l3` | leave unmapped for this tested Q37 unit |
| `source_current_l1/l2/l3` | leave unmapped for this tested Q37 unit |

## CP state mapping

| Raw value | Meaning |
| --- | --- |
| `controlpi_12v` | standby |
| `controlpi_12v_pwm` | communication initialising |
| `controlpi_9v` | vehicle detected |
| `controlpi_9v_pwm` | vehicle connected |
| `controlpi_6v` | ready to charge |
| `controlpi_6v_pwm` | charging |
| `controlpi_error` | error |

TuyaExtend now treats `controlpi_9v`, `controlpi_9v_pwm`, `controlpi_6v` and `controlpi_6v_pwm` as connected.

## Next test actions

1. Observe `AmperePoint Q37` dashboard in HA: compare HACS values with `tuya-local` raw values.
2. Confirm DP1 `sensor.q37_vg_energia` rises during charging and HACS session energy follows it directly.
3. Keep Q37 phase sensors unmapped; DP6/7/8 are not trusted on this tested unit.
4. Observe whether DP25 becomes live session energy later or remains `unknown`/last-session only.
5. Optionally test a small current-limit change from HA, only when it is safe for the active charging session.

## Live HACS test

A TuyaExtend test entry was added for this charger:

```text
name: AmperePoint Q Series Q37 VG
model: q_series
source_status: sensor.q37_vg_work_state
source_connected: sensor.q37_vg_connection_state
source_power: sensor.q37_vg_total_power
source_session_energy: sensor.q37_vg_charge_energy_single
source_total_energy: sensor.q37_vg_total_energy
session_energy_mode: total_delta
source_current_limit: number.q37_vg_charging_current
source_charge_switch: switch.q37_vg_switch
```

This first mapping was replaced after the session behavior test. Current Q37 mapping:

```text
source_status: sensor.q37_vg_status
source_connected: sensor.q37_vg_connection
source_power: sensor.q37_vg_moc
source_session_energy: sensor.q37_vg_energia
source_total_energy: unmapped
session_energy_mode: session_entity
source_current_limit: number.q37_vg_charging_current_2
source_charge_switch: switch.q37_vg
source_error: binary_sensor.q37_vg_problem
```

Backup before the storage change:

```text
<ha_storage_backup_path>
```

Backup before switching the test entry to local sources:

```text
<ha_storage_backup_path>
```

Observed normalized entities:

| Entity | Observed state |
| --- | --- |
| `sensor.amperepoint_q_series_auto_status` | `Ladowanie` |
| `sensor.amperepoint_q_series_auto_moc` | `0.888 kW` |
| `sensor.amperepoint_q_series_auto_energia_calkowita` | `0.47 -> 0.52 kWh` |
| `sensor.amperepoint_q_series_auto_energia_sesji` | `0.00 -> 0.05 kWh` |
| `sensor.amperepoint_q_series_auto_koszt_sesji` | `0.00 -> 0.06 PLN` |
| `sensor.amperepoint_q_series_auto_liczba_faz` | `1`, estimated from power until phase current sensors exist |
| `number.amperepoint_q_series_auto_limit_pradu` | `16 A` |
| `switch.amperepoint_q_series_auto_ladowanie` | `on` |

After switching to local sources:

| Entity | Observed state |
| --- | --- |
| `sensor.amperepoint_q_series_auto_energia_calkowita` | `0.71 -> 0.74 kWh` |
| `sensor.amperepoint_q_series_auto_energia_sesji` | `0.02 -> 0.05 kWh` |
| `sensor.amperepoint_q_series_auto_koszt_sesji` | `0.02 -> 0.06 PLN` |
| `sensor.amperepoint_q_series_auto_blad` | `Brak bledu` |

## Session behavior test

Recorder-derived test export:

```text
observations/q37-session-recorder-20260527.csv
```

Observed test sequence on 2026-05-27:

| Time | Action / state | Observed behavior |
| --- | --- | --- |
| `17:55:52` | Tesla pause, cable still connected | Status changed to `waiting`, connection to `vehicle_detected`, power to `0.0 kW`. |
| `17:56:03` | Resume | Status returned to `charging`, connection to `ready_to_charge`; energy counter continued from the same value. |
| `17:56:53` | Second short pause | Same pattern: `waiting`, `vehicle_detected`, power `0.0 kW`. |
| `17:57:02` | Resume | Status returned to `charging`; no session reset from the charger. |
| `17:57:26` | Unplug / stop session | Status changed to `available`, connection to `standby`, switch to `off`; DP25/`charge_energy_once` latched `1.53 kWh`. |
| `17:58:19` | New plug/charge | DP1/`forward_energy_total` reset to `0.01 kWh`; power jumped back above `2 kW`. |

Conclusion for Q37/VE:

- DP1 `forward_energy_total` behaves like a current-session/resetting counter on this generation, not like a lifetime meter.
- DP25 `charge_energy_once` is useful as the completed previous session value after unplug, but is not the live active session counter.
- Pause/resume without unplugging should remain one charging session.
- Unplug/replug is a new session.
- HACS mapping should use `session_entity` with `sensor.q37_vg_energia` for this generation.

After removing invalid Q37 phase mappings and restarting HA:

| Entity | Observed state |
| --- | --- |
| `sensor.q37_vg_status` | `charging` |
| `sensor.q37_vg_moc` | `1.105 kW` |
| `sensor.q37_vg_energia` | `1.17 kWh` |
| `sensor.amperepoint_q_series_auto_status` | `Ladowanie` |
| `sensor.amperepoint_q_series_auto_moc` | `1.105 kW` |
| `sensor.amperepoint_q_series_auto_energia_calkowita` | `1.17 kWh` |
| `sensor.amperepoint_q_series_auto_energia_sesji` | `0.02 kWh` after restart baseline |
| `sensor.amperepoint_q_series_auto_napiecie_l1/l2/l3` | `unknown` |
| `sensor.amperepoint_q_series_auto_prad_l1/l2/l3` | `unknown` |

After remapping Q37 from `total_delta` to `session_entity`:

| Entity | Observed state |
| --- | --- |
| `sensor.q37_vg_energia` | `0.28 kWh` |
| `sensor.q37_vg_last_session_energy` | `1.53 kWh` |
| `sensor.amperepoint_q_series_auto_energia_sesji` | `0.28 kWh` |
| `sensor.amperepoint_q_series_auto_energia_calkowita` | `unknown`, intentionally unmapped for Q37 because DP1 is not a lifetime counter |
| `sensor.amperepoint_q_series_auto_koszt_sesji` | `0.34 PLN` with `1.20 PLN/kWh` |

Tuya mobile app reference during the same Q37 generation test:

| Value in Tuya app | Meaning |
| --- | --- |
| `4.9 A` | Real charging current shown by the app |
| `224 V` | Real line voltage shown by the app |
| `0.89 kW` | Instant power, matching HA `sensor.q37_vg_moc` / `sensor.amperepoint_q_series_auto_moc` |
| `1.3 kWh` | Energy delivered to the car, close to local total counter during the live test |

This confirms the charger/app has real voltage and current data, but the current HA/local profile does not expose those values reliably yet for Q37. Cost in TuyaExtend is therefore based on energy, not on the unavailable phase current/voltage sensors.

Test dashboard:

```text
dashboards/q37-ha-test.yaml
```
