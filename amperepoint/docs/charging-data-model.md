# Charging data model

## Direction

Project sequence:

1. Keep `TuyaExtend AmperePoint` as a simple HACS integration that normalizes existing HA entities.
2. Maintain an AmperePoint profile for `tuya-local` so local EVSE DPS are decoded cleanly.
3. Later add a direct local mode to `TuyaExtend AmperePoint`: device ID, local key, host, protocol version and DPS polling.

Model variants that may be sold as either 1-phase or 3-phase should be configured as up-to-3-phase models. The live phase count should come from active L1/L2/L3 current sensors, not from a fixed model label.

Treat AmperePoint Q devices as one hardware family with multiple generations. Product IDs may expose different energy DPS, so the HACS integration must normalize the data model while `tuya-local` profiles capture per-generation DP details.

This keeps the first HACS version easy to install and avoids making local keys mandatory for every user.

## Current observation

Short live observation on 2026-05-27, local time:

| Field | Observed value |
| --- | --- |
| Status | `Ladowanie` |
| Vehicle connected | `on` |
| Phase count | `3` |
| Total power | `2.93..3.16 kW` |
| Voltage L1/L2/L3 | about `226 / 225 / 225 V` |
| Current L1/L2/L3 | about `5.0 / 4.9 / 4.8..4.9 A` |
| Current limit | `14 A` |
| Session energy source | `26.33 kWh`, currently from Xtend/cloud source |
| Session cost | `31.60 PLN`, derived from session energy and tariff |

Recorder history for the last hour showed about 94 power samples for `sensor.amperepoint_q22_moc`, so the power graph is already usable. Phase sensors are also entering short-term statistics through TuyaExtend.

Important note: the current `session_energy` value did not increase during the short observation window. It is still sourced from Xtend/cloud, while local DP25 is optional and was not yet confirmed as a live local value. Treat session energy as supported but still needing a real charging-session verification.

## Data we can collect now

### Control and state

| Data | HA form | Purpose |
| --- | --- | --- |
| Model | `select` | Pick AmperePoint profile and ranges. |
| Charging status | `sensor` enum/text | Human-readable state: ready, plugged, charging, paused, finished, fault. |
| CP connection state | `sensor` enum/text | Lower-level vehicle/control-pilot state such as `controlpi_6v`. |
| Vehicle connected | `binary_sensor` | Dashboard state and end-of-charge detection. |
| Charging switch | `switch` | Start/stop from HA. |
| Current limit | `number`, unit `A` | Slider with model-specific min/max. |
| Charging mode | `select`, optional | Immediate/scheduled/fixed energy modes if exposed. |
| Target energy | `number`, unit `kWh`, optional | Fixed-energy charge mode target. |

### Live electrical telemetry

| Data | HA form | State class | Use |
| --- | --- | --- | --- |
| Total power | `sensor`, `kW`, device class `power` | `measurement` | Live tile, 6h graph, session analytics. |
| Voltage L1/L2/L3 | `sensor`, `V`, device class `voltage` | `measurement` | Diagnostics and phase quality. |
| Current L1/L2/L3 | `sensor`, `A`, device class `current` | `measurement` | Phase detection and imbalance. |
| Power L1/L2/L3 | optional `sensor`, `kW` | `measurement` | Debug and phase balancing; currently exposed by `tuya-local`. |
| Phase count | `sensor` integer | none or diagnostic | Derived from phase currents above threshold. |

### Energy and cost

| Data | HA form | State class | Use |
| --- | --- | --- | --- |
| Session energy | `sensor`, `kWh`, device class `energy` | `total_increasing` | Current session tile and session cost. |
| Total forward energy | `sensor`, `kWh`, device class `energy` | `total_increasing` | Lifetime or meter total, useful for daily/monthly deltas. |
| Tariff | `sensor`, `PLN/kWh` | `measurement` | Fixed tariff or external price entity. |
| Session cost | `sensor`, currency | `total` | Current session cost. |
| Daily energy | `utility_meter` or derived sensor | `total_increasing` | Daily chart. |
| Monthly cost | `utility_meter`/derived aggregation | `total` | Monthly chart. |

For stable dashboards, daily and monthly values should be derived from recorder/statistics or `utility_meter`, not from ad-hoc template history.

Supported session energy strategies in the HACS integration:

| Mode | Data source | When to use |
| --- | --- | --- |
| `auto` | Prefer total energy delta when configured, otherwise session entity, otherwise power integration. | Default for Q Series generations. |
| `session_entity` | Source entity is already the current session counter. | Older/resetting generations where a DP resets after unplug/replug, for example Q37 DP1 in the live test. |
| `total_delta` | Delta from a cumulative, non-resettable energy counter. | Newer generations such as Q22 OTA when `forward_energy_total` is a true meter/lifetime counter. |
| `power_integration` | Integrate `power_total` over time. | Fallback when no reliable energy counter exists. |

The cost formula is intentionally simple in the first HACS version:

```text
session_cost = session_energy_kwh * tariff
```

The tariff is user-configurable as a fixed value and can also be mapped to an external HA entity through `tariff_entity`. Time-of-use tariffs, schedules and monthly billing rules should be built on top of this later without changing the basic session energy model.

Session energy must be based on the counter semantics of the charger generation:

| Counter behavior | Example | HACS mode |
| --- | --- | --- |
| Resets on unplug/new session | Q37/VE DP1 observed as `1.50 kWh`, then after unplug/replug `0.01 kWh` | `session_entity` |
| Non-resettable/lifetime meter | Q22 OTA expected behavior | `total_delta` with a persisted baseline |
| No reliable energy counter | Emergency fallback | `power_integration` |

For `total_delta`, TuyaExtend persists the baseline in HA storage. A short pause/resume while the vehicle remains connected should not reset the session; a new plug-in event or a source counter drop should.

### Diagnostics

| Data | HA form | Use |
| --- | --- | --- |
| Fault bitfield | `binary_sensor` + diagnostic attributes | Detect and decode charger errors. |
| Error text | `sensor` | Dashboard-friendly problem state. |
| System version | diagnostic `sensor` | Compare firmware/device revisions. |
| Temperature | diagnostic `sensor`, `C` | Charger thermal diagnostics. |
| Source availability | diagnostic `binary_sensor`/attributes | Distinguish cloud stale data from local live data. |
| Raw DPS snapshot | diagnostics JSON | Bug reports and support for new charger models. |

## Recommended storage forms

1. HA entities for dashboard/live control.
2. Long-term statistics for numeric sensors with `state_class`.
3. `utility_meter` helpers for daily/monthly energy and cost.
4. CSV snapshots for charger comparison during development.
5. Diagnostics JSON from config entries for support tickets.

## Observation script

Use:

```powershell
.\scripts\observe-charging.ps1 -Samples 12 -IntervalSeconds 30
```

For another normalized TuyaExtend instance:

```powershell
.\scripts\observe-charging.ps1 -Prefix amperepoint_q_series_auto -Samples 12 -IntervalSeconds 30
```

If Windows blocks local scripts, run it with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\observe-charging.ps1 -Samples 12 -IntervalSeconds 30
```

Optional CSV export:

```powershell
.\scripts\observe-charging.ps1 -Samples 120 -IntervalSeconds 30 -OutputCsv .tmp_observations\amperepoint-q22.csv
```

The script reads Home Assistant recorder data only. It does not change charger state.

## Next charger test

When the newer charger is connected:

1. Add it to Tuya/cloud and check the official DP list.
2. Add it to `tuya-local` and record product ID, protocol version and matching profile.
3. Run the observation script for 30-60 minutes.
4. Compare DPS and entities against the current Q-series profile.
5. Check whether new DPS expose temperature, energy counters, charge time, schedule, firmware or richer error states.
