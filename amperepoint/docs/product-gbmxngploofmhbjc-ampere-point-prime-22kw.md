# Product map: Wallbox Prime 22kW / gbmxngploofmhbjc

## Scope

This document records physical LAN observations made on 2026-07-16. They are
not derived from the Tuya cloud product schema.

- Product name: `Wallbox Prime 22kW`
- Product ID: `gbmxngploofmhbjc`
- Protocol: Tuya LAN `3.5`
- Transport: Wi-Fi

The initial cloud integration exposed only light-like capabilities, so it is
not a useful source of the charger DP map. Direct authenticated LAN status
queries were used instead.

> **Data availability:** the DP values documented here are available only
> when this product is connected through `tuya-local`. The standard Home
> Assistant Tuya cloud integration does not expose this local charger telemetry.

## Confirmed local DP set

Direct LAN discovery and forced status reads returned these DPS:

```text
101, 102, 103, 106, 107, 108, 109, 150, 151, 152, 153, 154, 155, 157
```

`188` was also observed once as `false` before later status reads stopped
returning it. Treat it as an intermittent/conditional DP until it is observed
again and its purpose is known.

| DP | Observed value / payload | Interpretation | Confidence |
| --- | --- | --- | --- |
| `101` | `101` while idle; `300` after a vehicle was connected | State-related numeric field; exact meaning not yet decoded. | Observed, undecoded |
| `102` | `{"L1":[2180,66,14],"L2":[0,0,0],"L3":[0,0,0],"t":360,"p":14,"d":1340,"e":1,"cp":60}` | Packed live telemetry. `L1` is voltage, current and power scaled by 10 (`218.0 V`, `6.6 A`, `1.4 kW`). `t` is temperature scaled by 10 (`36.0 C`); `p` is total power in tenths of kW; `d` is session duration in seconds; `e` is session energy in tenths of kWh (`0.1 kWh`); `cp` is control-pilot voltage scaled by 10 (`6.0 V`). | Confirmed during charging |
| `103` | `{"t":"2026-07-16 17:46:39", "r":[1,1]}` | Event/session-related structured value; exact meaning unknown. | Observed, undecoded |
| `106` | `{"r":"Type B, AC 30mA + DC 6mA","fv":"(V9.1.0)F1.4.1"}` | RCD specification and firmware version. | Confirmed |
| `107` | `[6,8,10,13,16,20,25,32]` | Permitted current-limit settings, in amperes. | Confirmed |
| `108` | `0` | Unknown numeric setting/status. | Observed, undecoded |
| `109` | `SLEEP`, `IDLE`, `WORKING` | Charger operating state. `WORKING` was observed immediately after a vehicle was connected. | Confirmed |
| `150` | `17` | Configured charging-current limit, in amperes. | Confirmed |
| `151` | `{"m":0,"dt":0,"ss":"00:00","se":"08:00"}` | Schedule configuration. The fields `m` and `dt` changed from `1` to `0` when the schedule configuration was changed. | Partially decoded |
| `152` | `32` | Unknown numeric setting/status; may be related to the allowed current range, but this has not been proven. | Observed, undecoded |
| `153` | `en` | Device language. | Confirmed |
| `154` | `0` | Unknown numeric setting/status. | Observed, undecoded |
| `155` | `true`, then `false` | User-configurable boolean. It is a candidate for RFID-related configuration, but this must be verified with a controlled RFID setting change. | Candidate |
| `157` | `6` | Unknown numeric setting/status. It equals the lowest permitted current value in the current observation, but its meaning is not yet proven. | Observed, undecoded |

## Charging transition observation

The direct LAN status changed after plugging in a vehicle:

| Field | Before vehicle connection | During charging |
| --- | --- | --- |
| DP `101` | `101` | `300` |
| DP `109` | `IDLE` | `WORKING` |
| DP `102.cp` | `121` | `60` |
| DP `102.L1` | `226.0 V`, `0 A`, `0 kW` | `218.0 V`, `6.6 A`, `1.4 kW` |

This confirms that the charger entered its working state and delivered energy
on L1. The charging sample confirmed `1.4 kW` power and `0.1 kWh` session
energy.

## tuya-local profile status

The initial `tuya-local` setup selected
`avidsen_soriami400_solarinverter`, which created 30 mostly unavailable
entities. That inverter profile is not compatible with this charger and must
not be used as its production mapping.

A conservative read-only profile is available at:

```text
profiles/tuya_local/amperepoint_prime_22kw_evcharger.yaml
```

It exposes DP102 as decoded JSON attributes on the charging-status entity. It
does not expose writable controls until local writes have been tested. Capture
samples at multiple current limits and with RFID and schedule settings toggled
one at a time before promoting the remaining candidate fields to named
entities.
