# Q37 / EV Charger VE - LAN capture through tuya-local (2026-07-26)

Companion to `device-q37-ve.md`, which describes the same charger as seen
through the Tuya cloud. This file records what the unit reports over the LAN
while paired with `amperepoint_q11_pro_evcharger`, because that profile is
being grown into a single profile for the whole Q Series.

Two of the open questions in the cloud document are answered here, and the
answers go the other way than the cloud observations suggested. Both are
called out below.

- Product/model id: `fdfjiphjxtc9qyhd`
- Profile used while capturing: `amperepoint_q11_pro_evcharger`
- Method: `LOCAL DPS` line logged by tuya-local at the device-type step, plus
  the recorder history of the resulting entities across two charge sessions.

## Datapoints while idle

```json
{"3": "charger_free", "4": 16, "9": 0, "10": 0, "13": "controlpi_12v",
 "14": "charge_now", "18": true, "24": 28}
```

Eight datapoints, the same set, the same types and the same value vocabulary
as the Q11 PRO reported on 2026-07-25 - only the values differ (16 A instead
of 8 A, 28 C instead of 25 C). This is what makes one profile possible: no
datapoint has to be typed differently per generation.

Not reported in the states captured first:

| DP | Meaning | Note |
| --- | --- | --- |
| `17` | Target energy | never seen, also absent on the Q11 |
| `25` | Last session energy | appears once a session has ended, see below |

DP25 was initially recorded as never seen, which was only true because no
session had finished yet at that point. It arrives at the moment a session
ends, carrying that session's energy.

Both stay `optional: true` in the profile, so their absence cannot hide the
profile from the device-type list.

## Two charge sessions

Recorder history, both sessions single-phase on L1:

| Time | DP1 total energy | Power | L1 | L2 / L3 |
| --- | --- | --- | --- | --- |
| 13:12:46 | `unknown` | 0 kW | 0.0 A | 0.0 A |
| 13:14:48 | 0.00 kWh | - | 229.0 V | - |
| 13:15:00 | - | 1.533 kW | 219.0 V, 7.2 A, 1.533 kW | 0.0 |
| 13:16:18 | 0.03 kWh | - | - | - |
| 13:16:31 | - | 0 kW | 0.0 A | 0.0 |
| 13:17:56 | 0.04 kWh | session 1 ended | - | - |
| 13:19:33 | - | 1.519 kW | 7.3 A | 0.0 |
| 13:20:45 | 0.07 kWh | - | - | - |
| 13:21:25 | - | 0 kW | 0.0 A | 0.0 |
| 13:22:15 | 0.08 kWh | session 2 ended | - | - |

### DP1 is the current session, DP25 is the previous one

An earlier revision of this file claimed DP1 was a lifetime meter and that
`device-q37-ve.md` was wrong to call it a resetting session counter. That
claim was mistaken and is withdrawn. `device-q37-ve.md` was right.

The mistake came from the shape of the test, not from the readings. The two
sessions were a stop and a restart of the charge with the load left
connected the whole time, so the run never crossed a disconnect - the one
boundary the same revision explicitly named as untested.

Later runs crossed it three times:

| Time | Event | DP1 | DP25 |
| --- | --- | --- | --- |
| 13:46 | charging, still connected | 0.10 | - |
| 14:16 | disconnected | - | 0.11 |
| 14:49 | new session started | 0.00 | 0.11 |
| 15:03 | session ended | - | 0.02 |
| 15:04 | after the session | 0.00 | 0.02 |
| 15:07 | new session charging | 0.02 | 0.02 |

DP1 restarts from zero for each session and DP25 takes the value the ended
session finished with. Home Assistant restarted four times during those runs
and DP1 held its value across every one of them (0.08, 0.08, 0.10, 0.10), so
the zeros are the charger's own state and not a restart artefact.

`total_increasing` stays the correct class: it is the class meant for a
counter that resets, and Home Assistant accumulates the long-term statistic
across resets.

### This is the Q37's behaviour, not the series'

A Q11 PRO captured on the same day answered `{"1": 4210, "3":
"charger_free", ...}` - 42.10 kWh with the charger idle and no session
running. That is a lifetime meter, not a session counter.

So DP1 means different things on different generations, and neither reading
generalises. The profile maps it the same way on both because
`total_increasing` covers a resetting counter and a lifetime meter alike;
only the entity name, "Total energy", fits one of them and not the other.

The same Q11 capture reported DP23 (`V1`) and DP25 while idle, which the Q37
and the Q22 never did. Eleven datapoints against their eight.

### Correction 2: the phase payloads decode correctly

`device-q37-ve.md` reports implausible phase values and disables DP6/7/8 for
this generation. Decoded with the masks this profile already used for the
Q22 - voltage `FFFF0000000000` scale 10, current `0000FFFFFF0000` scale
1000, power `0000000000FFFF` scale 1000 - the same unit produced physically
consistent readings: 219.0 V x 7.2 A = 1.58 kW against a reported 1.533 kW,
and 229.0 V unloaded sagging to 219.0 V under load.

L2 and L3 stayed at exactly 0.0 throughout. Note what this does and does not
prove: the Q37 is a single-phase unit, so empty L2/L3 is the expected result,
not evidence about the three-phase case from issue 18. It does show the
decoder produces clean zeros rather than noise. The three-phase case has to
be confirmed on a Q11.

The load during both sessions was a kettle on a test rig, not a vehicle,
which is why the parameters repeat so exactly between sessions.

The raw base64 payloads were not retained in the log; the values above come
from the decoded entities in the recorder.

Session energy read 0.08 kWh at the end, covering both bursts rather than
restarting at 13:19. That is intended: the vehicle stayed connected the whole
time (`binary_sensor` on from 13:14:48, DP13 `controlpi_6v` throughout), and
a session is bounded by the plug-in, not by a stop/start of the charge.

### DP9 is watts on this generation too

1533 W reported on DP9 next to L1 at 219.0 V and 7.2 A. The `scale: 1000`
that was corrected for the Q11 is right here as well, so the scale does not
have to vary per generation.

## Control Pilot states, measured with a test rig

The rig was stepped through every Control Pilot state while DP13, DP3 and the
L1 current were recorded:

| Step | DP13 | DP3 | L1 |
| --- | --- | --- | --- |
| A, nothing connected | `controlpi_12v` | available | - |
| B, connected, not charging | `controlpi_9v` | waiting | - |
| C, charging | `controlpi_6v` | charging | 7.3 A |
| C, charge stopped | `controlpi_6v` | waiting | **0.0 A** |
| back to B | `controlpi_9v` | waiting | 0.0 A |
| back to A | `controlpi_12v` | available | - |

The fourth row is the one that matters. With the charge stopped and no
current flowing, DP13 still reported `controlpi_6v` - the same value it
reports at full load. So `controlpi_6v` does not mean "charging"; it means
the vehicle signals state C, that it is connected and ready to draw. Whether
energy actually flows is DP3 and DP18, not DP13. Mapping DP13 `controlpi_6v`
to a charging state would therefore be wrong, and the existing
`ready_to_charge` label is accurate for a sensor named "Vehicle connection
state".

`controlpi_12v` was mapped to `ready`, which reads as "ready to charge" while
it actually means nothing is plugged in. Renamed to `standby`, matching the
vocabulary the base VE profile uses for the same value.

No `_pwm` variant appeared in any state, with or without current, so the four
mappings in this profile cover everything this generation emits.

## Charging current range

No conflict between these two generations. Per amperepoint.pl the series
names are kilowatts, not amperes:

| Model | Power | Current | Phases |
| --- | --- | --- | --- |
| Q37 | 3.7 kW | 6-16 A, 1 A steps | 1 |
| Q11 | 11 kW | 6-16 A | 3 |
| Q74 | 7.4 kW | up to 32 A | 1 |
| Q22 | 22 kW | up to 32 A | 3 |

Both captured units are 16 A, so the profile keeps `range: 6..16`.

`models.py` inherited from the base repo read "Q37" as 37 A and declared the
model as 48 A three-phase, the exact opposite of the product. That is
corrected here: Q37 is 1 phase / 16 A, Q11 is 3 phases / 16 A.

Still open for a truly universal profile: the 32 A models (Q22, Q74) do not
fit a 6-16 A range, and the charger publishes no minimum/maximum datapoint to
tell generations apart. Decide that when one of them is actually captured -
not from the model name.

## Matcher result after adding the product id

Replayed against the real tuya-local matcher with the captured datapoints:

| Input | Our profile |
| --- | --- |
| Q11 idle, no product id | `matches=True`, quality 100 |
| Q37 idle, no product id | `matches=True`, quality 100 |
| Q37 idle, product id | `matches=True`, quality 101 |
| Q37 charging, product id | `matches=True`, quality 101 |

101 is the score tuya-local gives a product-id match. `amperepoint_ve_evcharger`
declares the same id and also scores 101, so both appear at the top of the
device-type list; the `(local)` marker in the model name tells them apart.

## Still to capture

- Q22 OTA (`cu111poj2mtikvls`) and the legacy Q Series, to confirm the
  datapoint set holds there too. Both have to report DP3 and DP4, which the
  profile now requires as its signature.
- Any unit that actually reports DP17 over the LAN.
- Whether the "Total energy" entity should be renamed, now that DP1 is known
  to hold the current session rather than a lifetime total.
