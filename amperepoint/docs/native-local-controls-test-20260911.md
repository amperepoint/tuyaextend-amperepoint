# PRIME LAN controls and readable diagnostics — 0.5.38b3

Final HA build: `0.5.38b3`. Automated verification: 156 Python tests and 9
frontend tests pass. Native controls were enabled through the normal HA options
flow, then verified through the real dashboard: stop → PAUSE, slider → 11 A,
restore slider → 16 A, start → STATE_C. DP150 readback confirmed the 11 A value
despite 11 A not being an app preset, supporting 1 A slider steps on this device.
The native button now follows DP140 charging permission even when power is zero.
Raw DP count counts physical datapoints, not additional decoded table rows.

## Physical test conditions

PRIME split telemetry firmware `(V7.0.0)F2.0.0`, Tuya LAN 3.5, EVSE tester
connected, no electrical load. Only the explicitly selected test charger was
addressed. HA polling was stopped during direct protocol tests and restarted
afterward. No safety, NFC, factory-reset or installation-limit DP was written.

## Results

| Operation | Command | Independently read state | Result |
| --- | --- | --- | --- |
| Set session current | DP150 = 6, 8, 13 (integer) | DP150 = 6, 8, 13 | Confirmed |
| Restore original request | DP150 = 32 | DP150 = 16; DP152 stays 16 | Device clamps to installation limit |
| Stop | DP140 = false | DP140 false, DP101 204, DP109 PAUSE | Confirmed |
| Start | DP140 = true | DP140 true, DP101 300, DP109 STATE_C | Confirmed |
| Stop again | DP140 = false | Same stopped values | Confirmed |
| Restore initial enabled state | DP140 = true | DP101 300, DP109 STATE_C | Confirmed |

Power stayed zero and CP stayed 6.1 V. These checks establish command acceptance
and reported state transitions, not current delivered to a real vehicle. The
original anomalous 32 A request could not be restored: the firmware itself
returned 16 A. Its installation limit remained 16 A throughout.

## Enabled scope

In AmperePoint local connection options, the user can opt into tested controls.
The backend checks the validated layout, firmware and DP types again before
every write. It permits only DP140 and DP150, requires independent readback,
rejects fractional/nonfinite current, and caps current at the smaller of DP152
and the pilot's 16 A ceiling. It never writes DP152. A protocol acknowledgement
without matching fresh state is not treated as success.

New entries remain read-only unless explicitly opted in. Unknown firmware and
the older packed PRIME layout remain read-only. No native schedule/mode writer,
target-energy writer, or HA planner is enabled yet. Those require separate
mode-transition captures and nonzero energy validation before Q-like parity can
be claimed. DP151 is preserved, including its currently unverified `c` field.

All received DPs now appear in diagnostics rather than being silently dropped.
Readable tables flatten structured telemetry into individual rows, including
unknown fields marked as such. DP112/113 card/authentication contents are
redacted, with their presence still visible. Voltage interpretations and
nonzero power/energy scaling are explicitly distinguished from tested facts.

## Mapping evidence

- [Tuya Local dewall profile](https://github.com/make-all/tuya-local/blob/main/custom_components/tuya_local/devices/dewall_evcharger.yaml)
  supplied the DP140/150/152 test candidates, not automatic compatibility.
- [EV_charger implementation](https://github.com/lachand/EV_charger/tree/main/custom_components/tuya_ev_charger)
  independently uses the same command family.
- The user-provided PRIME application translation export
  `itemInfo_1784727544553.xlsx`, Export rows 50–93, identifies DP101 state labels.
  Labels alone were not used as proof of successful hardware commands.
