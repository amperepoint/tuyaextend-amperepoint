# AmperePoint Q22 OTA DP map

## Scope

This map covers the AmperePoint Q22 OTA product currently tracked in the
`amperepoint/tuya-ap` project.

| Field | Value |
| --- | --- |
| Product name | `Q22 OTA` |
| Product ID / PID | `cu111poj2mtikvls` |
| Observed device ID | `<device_id_q22_ota_legacy>` |
| Category | `qccdz` / EV charger |
| Local protocol | `3.5` on the observed device |
| Local profile | `profiles/tuya_local/amperepoint_q22_ota_evcharger.yaml` |
| HACS model | `q22_ota` |

No local keys or account credentials are stored in this map.

## Confidence levels

| Level | Meaning |
| --- | --- |
| Confirmed product DP | Present in the Tuya Developer function definition for PID `cu111poj2mtikvls`. |
| Confirmed observed DP | Read from the physical Q22 OTA device through Tuya Cloud, Xtend/native Tuya, or `tuya-local`. |
| Candidate DP | Present in the product definition/profile, but not yet confirmed with useful live payload on the physical device. |

## DP overview

| DP | Identifier | Direction | Type | Unit/scale | Status | Meaning |
| --- | --- | --- | --- | --- | --- | --- |
| `1` | `forward_energy_total` | Report | Value | `kWh`, scale `2` | Confirmed observed DP | Main energy counter. Preferred Q22 session source when used as `total_delta`. |
| `3` | `work_state` | Report | Enum | n/a | Confirmed observed DP | Charger state. Normalized to user-readable status in HACS. |
| `4` | `charge_cur_set` | Send/report | Value | `A`, scale `0`, range `6..32` | Confirmed observed DP | Charging current limit. Exposed as a number/slider. |
| `6` | `phase_a` | Report | Raw | 7-byte phase payload | Confirmed observed DP | Phase A voltage/current/power. Full live parsing confirmed on Q22_13072026. |
| `7` | `phase_b` | Report | Raw | 7-byte phase payload | Confirmed observed DP | Phase B voltage/current/power. Full live parsing confirmed on Q22_13072026. |
| `8` | `phase_c` | Report | Raw | 7-byte phase payload | Confirmed observed DP | Phase C voltage/current/power. Full live parsing confirmed on Q22_13072026. |
| `9` | `power_total` | Report | Value | `kW`, scale `3` | Confirmed observed DP | Instant total charging power. |
| `10` | `fault` | Report | Fault bitfield | n/a | Confirmed observed DP | Fault/alarm flags. |
| `13` | `connection_state` | Report | Enum | n/a | Confirmed observed DP | Vehicle/control-pilot connection state. |
| `14` | `work_mode` | Send/report | Enum | n/a | Confirmed observed DP | Charging mode. |
| `17` | `energy_charge` | Send/report | Value | `kWh`, scale `0`, range `1..200` | Confirmed product DP; observed in cloud dump | Target energy for fixed-energy mode. |
| `18` | `switch` | Send/report | Bool | n/a | Confirmed observed DP | Start/stop charging. |
| `19` | `local_timer` | Send/report | Raw | raw schedule payload | Candidate DP | Schedule charging payload. Not decoded yet. |
| `23` | `system_version` | Report | String | n/a | Candidate DP | Firmware/system version. Not returned while waiting. |
| `24` | `temp_current` | Report | Value | `C`, scale `0` | Confirmed observed DP | Charger temperature. |
| `25` | `charge_energy_once` | Report | Value | `kWh`, scale `2` | Confirmed observed DP | Last completed charging session energy. Do not use as live active-session energy. |
| `33` | `mode_set` | Send/report | Raw | raw mode payload | Candidate DP | Extra charge mode/config payload. Not decoded yet. |

## Confirmed paused values

Observed on the physical Q22 OTA while vehicle was detected and charging was paused:

| DP | Identifier | Raw value | Normalized value |
| --- | --- | --- | --- |
| `1` | `forward_energy_total` | `90` | `0.90 kWh` |
| `3` | `work_state` | `charger_wait` | waiting / ready |
| `4` | `charge_cur_set` | `16` | `16 A` |
| `9` | `power_total` | `0` | `0.000 kW` |
| `13` | `connection_state` | `controlpi_9v` | vehicle detected |
| `14` | `work_mode` | `charge_now` | immediate charging |
| `17` | `energy_charge` | `1` | `1 kWh` target |
| `18` | `switch` | `false` | stopped |
| `24` | `temp_current` | `44..49` | `44..49 C` |
| `25` | `charge_energy_once` | `2` | `0.02 kWh` |

Local DPS confirmed by `tuya-local` / TinyTuya direct status:

```text
1, 3, 4, 9, 10, 13, 14, 18, 24, 25
```

Forced local reads for these DPS returned no useful payload while waiting/paused:

```text
6, 7, 8, 19, 23, 33
```

Additional Q22_13072026 cloud status samples from 2026-07-13.

First sample while phase A was reported as 226 V in Tuya:

| DP | Identifier | Raw value | Decoded value |
| --- | --- | --- | --- |
| `6` | `phase_a` | `CNQAAAAAAA==` / `08 d4 00 00 00 00 00` | `226.0 V`, `0.000 A`, `0.000 kW` |

Second sample during active 3-phase charging:

| DP | Identifier | Raw value | Decoded value |
| --- | --- | --- | --- |
| `6` | `phase_a` | `CJgAKvgJdA==` / `08 98 00 2a f8 09 74` | `220.0 V`, `11.000 A`, `2.420 kW` |
| `7` | `phase_b` | `CKwAKvgJig==` / `08 ac 00 2a f8 09 8a` | `222.0 V`, `11.000 A`, `2.442 kW` |
| `8` | `phase_c` | `CJgAKvgJdA==` / `08 98 00 2a f8 09 74` | `220.0 V`, `11.000 A`, `2.420 kW` |

The phase sum is `2.420 + 2.442 + 2.420 = 7.282 kW`, matching DP9
`power_total = 7282` with scale `3`.

## Enum mapping

### DP3 `work_state`

| Raw value | HACS meaning | Polish display |
| --- | --- | --- |
| `charger_free` | available | `Gotowy` |
| `charger_insert` | plugged in | `Auto podlaczone` |
| `charger_free_fault` | fault while unplugged/free | `Blad` |
| `charger_wait` | waiting | `Gotowy` |
| `charger_charging` | charging | `Ladowanie` |
| `charger_pause` | paused | `Wstrzymane` |
| `charger_end` | charged/complete | `Zakonczone` |
| `charger_fault` | fault | `Blad` |

### DP13 `connection_state`

| Raw value | HACS meaning | Polish display |
| --- | --- | --- |
| `controlpi_12v` | standby | `Gotowy` |
| `controlpi_12v_pwm` | communication initialising | `Gotowy` |
| `controlpi_9v` | vehicle detected | `Auto wykryte` |
| `controlpi_9v_pwm` | vehicle connected | `Auto podlaczone` |
| `controlpi_6v` | ready to charge | `Gotowy do ladowania` |
| `controlpi_6v_pwm` | charging | `Ladowanie` |
| `controlpi_error` | control-pilot error | `Blad` |

### DP14 `work_mode`

| Raw value | Meaning |
| --- | --- |
| `charge_now` | Charge immediately |
| `charge_energy` | Charge to configured energy target |
| `charge_schedule` | Scheduled charge |

## Fault map

DP10 is a fault bitfield. The profile currently uses this candidate numeric
mapping, derived from the Tuya fault labels and bit order:

| Bit value | Fault label |
| --- | --- |
| `1` | `ov_cr` |
| `2` | `ov2_cr_fault` |
| `4` | `ov_vol` / overvoltage alarm |
| `8` | `undervoltage_alarm` |
| `16` | `contactor_adhesion` |
| `32` | `contactor_fault` |
| `64` | `earth_fault` |
| `128` | `meter_hardware_alarm` |
| `256` | `scram_fault` |
| `512` | `cp_fault` |
| `1024` | `meter_commu_fault` |
| `2048` | `card_reader_fault` |
| `4096` | `cir_short_fault` |
| `8192` | `adhesion_fault` |
| `16384` | `self_test_alarm` |
| `32768` | `leakagecurr_alarm` |
| `65536` | `over_temp_fault` |

`0` means no active fault.

## Phase payload parsing

The Tuya Developer definition lists DP6/DP7/DP8 as raw phase values. Tuya event
logs and the Complex Protocol Parsing screen for a related Q Series product show
each phase as a 7-byte payload:

| Bytes | Field | Scale | Unit |
| --- | --- | --- | --- |
| `0..1` | voltage, unsigned big-endian | `/10` | `V` |
| `2..4` | current, unsigned big-endian | `/1000` | `A` |
| `5..6` | phase power, unsigned big-endian | `/1000` | `kW` |

This matches the current `tuya-local` profile masks. For Q22_13072026, DP6,
DP7 and DP8 were also observed in the raw Tuya cloud status payload after
switching the Tuya project/product access to DP Instruction mode. The native
Home Assistant/Xtend entity layer still does not create phase entities from
that raw payload.

Observed Tuya event-log examples from 2026-06-29:

| Event detail | Hex payload | Decoded value |
| --- | --- | --- |
| `AAAAAAAAAA==` | `00000000000000` | `0.0 V`, `0.000 A`, `0.000 kW` |
| `Ch0AAAAAAA==` | `0A1D0000000000` | `258.9 V`, `0.000 A`, `0.000 kW` |
| `CD4AFXwEiA==` | `083E00157C0488` | `211.0 V`, `5.500 A`, `1.160 kW` |
| `CNQAAAAAAA==` | `08D40000000000` | `226.0 V`, `0.000 A`, `0.000 kW` |
| `CJgAKvgJdA==` | `0898002AF80974` | `220.0 V`, `11.000 A`, `2.420 kW` |
| `CKwAKvgJig==` | `08AC002AF8098A` | `222.0 V`, `11.000 A`, `2.442 kW` |

The `CD4AFXwEiA==` sample aligns with a Tuya event log `Total power` value of
`1.16 kW`. The `CNQAAAAAAA==` sample aligns with the live Q22_13072026 phase A
voltage value of `226 V`. The `CJgAKvgJdA==` and `CKwAKvgJig==` samples confirm
the full voltage/current/power layout for live Q22_13072026 3-phase charging.

## HA entity map

### Tuya Cloud / Xtend/native Tuya

| DP | Entity | Meaning |
| --- | --- | --- |
| `3` | `sensor.q22_ota_work_state` | Raw work state |
| `13` | `sensor.q22_ota_connection_state` | Raw connection state |
| `9` | `sensor.q22_ota_total_power` | Total power |
| `1` | `sensor.q22_ota_total_energy` | Energy counter |
| `25` | `sensor.q22_ota_charge_energy_single` | Last completed charging session energy |
| `24` | `sensor.q22_ota_temperatura` | Temperature |
| `4` | `number.q22_ota_charging_current` | Current limit |
| `18` | `switch.q22_ota_switch_2` | Working start/stop switch |

`switch.q22_ota_switch` was observed as unavailable after restart; the native
Tuya switch `switch.q22_ota_switch_2` was the working control entity.

### Tuya Local

| DP | Entity | Meaning |
| --- | --- | --- |
| `3` | `sensor.q22_ota_status` | Normalized local status |
| `13` | `sensor.q22_ota_connection` | Normalized local connection |
| `9` | `sensor.q22_ota_moc` | Total power |
| `1` | `sensor.q22_ota_energia` | Energy counter |
| `25` | `sensor.q22_ota_last_session_energy` | Last completed charging session energy |
| `10` | `binary_sensor.q22_ota_problem` | Problem/fault |
| `24` | `sensor.q22_ota_temperatura_2` | Temperature |
| `4` | `number.q22_ota_charging_current_2` | Current limit |
| `17` | `number.q22_ota_target_energy` | Target energy |
| `14` | `select.q22_ota_tryb_ladowania` | Charging mode |
| `18` | `switch.q22_ota` | Start/stop |
| `6` | `sensor.q22_ota_napiecie_a`, `sensor.q22_ota_prad_a`, `sensor.q22_ota_moc_a` | Candidate phase A sensors; currently unknown |
| `7` | `sensor.q22_ota_napiecie_b`, `sensor.q22_ota_prad_b`, `sensor.q22_ota_moc_b` | Candidate phase B sensors; currently unknown |
| `8` | `sensor.q22_ota_napiecie_c`, `sensor.q22_ota_prad_c`, `sensor.q22_ota_moc_c` | Candidate phase C sensors; currently unknown |

## Preferred TuyaExtend mapping

Current preferred mapping for Q22 OTA in the HACS integration:

```yaml
model: q22_ota
source_status: sensor.q22_ota_status
source_connected: sensor.q22_ota_connection
source_power: sensor.q22_ota_moc
source_total_energy: sensor.q22_ota_energia
session_energy_mode: total_delta
source_current_limit: number.q22_ota_charging_current_2
source_charge_switch: switch.q22_ota
source_error: binary_sensor.q22_ota_problem
tariff_value: 1.20
currency: PLN
```

Preferred energy strategy:

1. Use DP1 `forward_energy_total` as a non-resettable meter if it stays monotonic
   across pause/resume and unplug/replug.
2. Calculate session energy as `current DP1 - persisted session baseline`.
3. Calculate cost as `session_energy_kwh * tariff`.
4. Treat DP25 `charge_energy_once` as informational last-session energy, not as
   the live active-session counter.

## Dashboard and observation files

| Purpose | File |
| --- | --- |
| Q22 HA test dashboard | `dashboards/q22-ota-ha-test.yaml` |
| Q22 observation script | `scripts/observe-q22-ota-session.ps1` |
| Physical device notes | `docs/device-<device_id_q22_ota_legacy>.md` |
| Product function definition | `docs/product-cu111poj2mtikvls-q22-ota.md` |

## Open validation items

1. Confirm DP1 remains non-resettable during a complete charge, pause/resume,
   unplug, and replug cycle.
2. Observe exactly when DP25 updates after stop/unplug; it represents the last
   completed charging session.
3. Confirm whether DP6/DP7/DP8 phase payloads are also available through local
   LAN polling, not only the raw cloud status payload.
4. Decide whether phase data should come from `tuya-local`, Tuya Cloud/Xtend, or
   HACS-only derived calculations.
5. Decode DP19 schedule payload and DP33 charge-mode payload only after they are
   needed in the user-facing integration.
