# PRIME packed LAN control profile — 0.5.38b9

Tested 2026-09-11 with a Wallbox PRIME 11 kW, PID `gbmxngploofmhbjc`,
firmware `(V8.0.7)F1.3.6`, LAN protocol 3.5. An EVSE tester was connected,
with zero measured load. No private device ID, address or key is published.

## Contract and physical tests

| Function | Write | Independent readback | Result |
| --- | --- | --- | --- |
| Current | DP150 integer 6, 8, 11, 13 | DP150 matches each request | Passed |
| Stop | DP140 false | DP101 204 + DP109 PAUSE | Passed twice |
| Start | DP140 true | DP101 300 + DP109 WORKING | Passed |
| Restore | DP150 16, DP140 true | 16 A + 300/WORKING | Passed |

DP140 is not returned by this firmware, even after successful commands. The
adapter therefore uses the two independently read status fields to confirm
start/stop, not an optimistic command cache. It never inserts a synthetic DP140
into raw diagnostics. Unknown or contradictory status pairs produce an unknown
switch state and cannot confirm a command. A protocol ACK alone is insufficient.

DP107 lists application presets `[6,8,10,13,16]`; the confirmed 11 A request
supports a 1 A control step on this device. DP152 remained 16 throughout.
Native DP151 stayed `{"m":0,"dt":0,"ss":"00:00","se":"08:00"}`.
No native schedule, protection, reset, authentication or installation-limit
write was attempted. HA polling was stopped for the direct protocol experiment
and resumed afterwards. Original enabled state and 16 A were restored.

## Integration behavior

`prime_packed_v1` is separate from `prime_split_v1`. Selection requires the
tested firmware string, packed telemetry, state fields and integer current/limit
DPs. It is not selected merely because the product name says PRIME or 11 kW.
The current ceiling is conservatively 16 A, further limited by DP152.

The same HA-owned planner/UI supports charge-now, charge-energy, schedule,
manual override and next action. The charger stays in native immediate mode;
HA persists and executes the plan over LAN. No separate Tuya Local or cloud
integration is required for runtime control. Reconfiguration uses HA's normal
options flow and preserves the existing entry and its entity IDs.

The sanitized observation is in
[`../observations/prime-packed-tester-20260911.json`](../observations/prime-packed-tester-20260911.json).
Regression tests cover fresh status confirmation, stale/contradictory readback,
firmware gating, current limits, native mode checks, onboarding and options.

## Home Assistant verification

Installed locally and enabled through the existing entry's options flow:

- Standard HA switch: stop and start confirmed by the wallbox.
- Standard HA number: 8 A request read back as 8 A.
- Energy mode: 3.5 kWh budget created, start/stop confirmed, delivered energy
  correctly stayed 0 kWh on the tester.
- Weekly planner: the 16:14–16:15 test window started at 6 A and stopped at
  its end. The next-action field changed from start to stop to next week's start.
- Afterwards: test window removed, planner disabled, override cleared, target
  restored to 10 kWh, current restored to 16 A, initial enabled state restored.
- Chrome dashboard verified with controls, three modes, planner, LAN tables,
  public PID and version `0.5.38b9` visible.
- A subsequent HA restart reconnected automatically with controls, PID and
  restored settings intact. Import checks also passed with cloud SDK and
  external Tuya Local modules deliberately blocked.
- Automated checks: 189 Python tests and 12 Node frontend tests pass.

## Limits

- Zero-load tests verify accepted commands and reported transitions, not actual
  energy delivery, metering accuracy or contactor operation under load.
- Energy-target cutoff and nonzero phase measurements require a real vehicle.
- This snapshot has no CP value. The integration must not claim disconnected
  solely because current and power are zero.
- Other firmware/state pairs require additional captured evidence; no broad
  writable profile is enabled by product ID alone.
- HA must remain online to execute schedules and energy cutoffs. These are not
  autonomous schedules stored in the wallbox.

## Prior mapping evidence

The [Tuya Local dewall profile](https://github.com/make-all/tuya-local/blob/main/custom_components/tuya_local/devices/dewall_evcharger.yaml)
provided DP140 start/stop and DP150 current candidates. Tuya Local reports
[#3120](https://github.com/make-all/tuya-local/issues/3120) and
[#4314](https://github.com/make-all/tuya-local/issues/4314) describe the write-only
DP140 pattern. These were test hypotheses; the profile above is based on the
actual device readbacks, not assumed compatibility with another vendor.
