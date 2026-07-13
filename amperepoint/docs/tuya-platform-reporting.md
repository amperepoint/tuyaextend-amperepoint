# Tuya platform reporting notes

## Why this matters

The Q Series EVSE products define more DPS than Home Assistant receives through
the standard Tuya / Device Sharing API path. Tuya Developer Platform tools can
help determine whether a missing DP is:

- not reported by firmware at all,
- reported to Tuya Cloud but not exposed through Device Sharing API,
- exposed only through local LAN/raw protocol,
- throttled or filtered by reporting limits.

## Official Tuya docs checked

- Device Health Check / message reporting test:
  `https://developer.tuya.com/en/docs/iot/message-reporting-test?id=Kbuemcpfebg27`
- Report frequency limits:
  `https://developer.tuya.com/en/docs/iot/report-limit?id=Ke9cnruoat3ct`
- DP model and control protocol:
  `https://developer.tuya.com/en/docs/iot-device-dev/TuyaOS-iot_abi_dp_ctrl?id=Kcoglhn5r7ajr`
- Product functions:
  `https://developer.tuya.com/en/docs/iot/define-product-features?id=K97vug7wgxpoq`
- Message service:
  `https://developer.tuya.com/en/docs/iot/manage-messages?id=Ka49p7loog3ze`

## Recommended Tuya-side checks

### 1. Run Device Health Check during live charging

Use Product > Device Health Check for the active product/PID and add the test
device by Device ID. Run the test while the charger is:

1. idle,
2. plugged in but not charging,
3. actively charging,
4. paused,
5. unplugged after a session.

Tuya says this report includes DP reporting metrics, including the range of DPS
and logs reported to the cloud, total reported messages and message overages.

For us this is the cleanest split:

- If DP6/DP7/DP8 appear in Device Health Check but not in Home Assistant /
  Device Sharing API, the DPS are reported to Tuya Cloud but not exposed through
  the API path used by HA.
- If DP6/DP7/DP8 do not appear in Device Health Check during charging, firmware
  probably does not report phase DPS to cloud in that mode/product generation.

### 2. Export Complex Protocol Parsing for raw DPS

For each EVSE product, save the Tuya Complex Protocol Parsing JSON for:

- DP6 `phase_a`
- DP7 `phase_b`
- DP8 `phase_c`
- DP19 `local_timer`
- DP33 `mode_set`

The Q11/Q Series screen and Tuya event logs confirm the phase raw payload
structure:

| DP | Bytes | Field | Scale | Unit |
| --- | --- | --- | --- | --- |
| `6/7/8` | `0..1` | voltage | `/10` | `V` |
| `6/7/8` | `2..4` | current | `/1000` | `A` |
| `6/7/8` | `5..6` | phase power | `/1000` | `kW` |

This matches the current `tuya-local` candidate masks:

```text
FFFF0000000000 -> voltage / 10
0000FFFFFF0000 -> current / 1000
0000000000FFFF -> phase power / 1000
```

Keep DP6/DP7/DP8 optional until real live payloads are captured per generation.

Observed Tuya event-log samples from 2026-06-29:

| Event detail | Hex payload | Decoded value |
| --- | --- | --- |
| `AAAAAAAAAA==` | `00000000000000` | `0.0 V`, `0.000 A`, `0.000 kW` |
| `Ch0AAAAAAA==` | `0A1D0000000000` | `258.9 V`, `0.000 A`, `0.000 kW` |
| `CD4AFXwEiA==` | `083E00157C0488` | `211.0 V`, `5.500 A`, `1.160 kW` |

The `CD4AFXwEiA==` sample matches the Tuya event log's `Total power 1.16 kW`.
This proves the device reports phase DPS to Tuya Cloud, even though the same DPS
are absent from Home Assistant's Device Sharing API dump.

### 3. Do not use report frequency limits to expose missing DPS

Report frequency limits only restrict reporting volume. They do not make hidden
or unexposed DPS visible in Device Sharing API.

Tuya docs say empty frequency rules mean the DP is not limited by that rule, and
that a global limit plus a DP-specific limit can both restrict reporting. TuyaOS
also has default DP throttling.

Recommended EVSE setting:

- Leave frequency limits empty while debugging missing DPS.
- After Device Health Check confirms real message volume, set limits only for
  noisy measurement DPS if needed.
- Never set low limits on active charging telemetry before dashboard testing.

Possible post-validation limits:

| DP | Suggested handling |
| --- | --- |
| DP3 status | no explicit limit; event-like |
| DP4 current limit | no explicit limit; user command/report |
| DP6/7/8 phase raw | only limit after live payload is confirmed; start no lower than 30/min |
| DP9 total power | keep frequent enough for charts; start no lower than 30/min |
| DP10 fault | no explicit limit; event-like |
| DP24 temperature | can be slower, for example 6-12/min |
| DP1/DP25 energy | avoid aggressive limits until session-energy behavior is validated |

### 4. Remember raw DPS are different

TuyaOS docs state raw-type DPS support synchronous reporting and are not cached
by the framework. Therefore DP6/DP7/DP8 can be present in live traffic but still
not behave like ordinary cached value DPS in status/specification reads.

For HA/Tuya work this means:

- do not rely only on cached status API results for raw phase DPS,
- capture live message reporting and/or local LAN packets,
- keep phase sensors optional in `tuya-local` profiles.

### 5. Message Service is useful for product debugging

Tuya Message Service can push device status/data reporting events to our cloud
project. It is useful for development and monitoring, but it is not the same as
Home Assistant's Device Sharing API and does not guarantee that HA will receive
the same DPS.

Use it to prove whether Tuya Cloud receives DP reports. Then compare with the HA
Device Sharing API dump.

## Product configuration checklist

For each AmperePoint Q Series PID:

- [ ] Confirm Product Functions include the expected EVSE DPS.
- [ ] Confirm data transfer type:
  - Report only for measured telemetry and status,
  - Send and report for controls and settings.
- [ ] Export Complex Protocol Parsing JSON for raw/string DPS.
- [ ] Run Device Health Check while charging.
- [ ] Compare Health Check DP range with Device Sharing API dump.
- [ ] Keep report frequency limits empty until message volume is measured.
- [ ] Ask Tuya to expose missing DPS in Device Sharing API/local strategy if
      Health Check proves they are already reported to cloud.
