# One profile for the Q Series: what it covers and what decides the rest

`amperepoint_q_series_local` is one profile for the whole Q Series. This
file records which models it covers, what was measured, and why the two
per-model differences are resolved outside the profile.

The file was renamed from amperepoint_q11_pro_evcharger once all four
generations were measured. tuya-local stores the file name as the entry's
`config_type`, so entries created under the old name have to be repointed
or re-created - the rename is not backwards compatible.

## Models

Currents and phase counts are from amperepoint.pl. The series names are
kilowatts, not amperes - reading "Q37" as 37 A is what put a 48 A three-phase
figure into the model table originally.

| Model | Power | Current | Phases | Product id | Captured |
| --- | --- | --- | --- | --- | --- |
| Q11 PRO | 11 kW | 6-16 A | 3 | `jhlyzpk5nfk28nrh` | yes |
| Q37 | 3.7 kW | 6-16 A | 1 | `fdfjiphjxtc9qyhd` | yes |
| Q22 | 22 kW | 6-32 A | 3 | `fdfjiphjxtc9qyhd` | yes |
| Q74 | 7.4 kW | 6-32 A | 1 | `bktb3jskdic1ar2t` | yes |

## Every generation answers with the same datapoints

Three units, the same datapoints in the same types:

```
Q11  {"3":"charger_free","4":8, "9":0,"10":0,"13":"controlpi_12v","14":"charge_now","18":true,"24":25}
Q37  {"3":"charger_free","4":16,"9":0,"10":0,"13":"controlpi_12v","14":"charge_now","18":true,"24":28}
Q22  {"3":"charger_free","4":6, "9":0,"10":0,"13":"controlpi_12v","14":"charge_now","18":true,"24":23}
```

Charging adds DP1, DP6, DP7 and DP8 on all of them. DP9 is watts on every
generation. This is what makes one profile possible at all.

How many of them answer at once does vary. A later Q11 capture returned
eleven: the eight above plus DP1 (42.10 kWh), DP23 (`V1`) and DP25, all
while idle. Every datapoint except DP3 and DP4 is therefore optional.

DP1 also differs in meaning: a session counter on the Q37, a lifetime meter
on the Q11. `total_increasing` covers both, so the profile maps it the same
way; the entity name "Total energy" only fits the Q11 reading.

## The Q74 runs on a different OEM base

`bktb3jskdic1ar2t` is not an AmperePoint id at all: the Wada Power, Noeifevo
and Nine profiles declare it too, so it is a base sold under several brands.
Declaring it here means this profile is also offered for those chargers.

It was captured charging, which is what the declaration rests on:

```
12:03:29  work_state waiting     vehicle plugged in, no current
12:03:44  work_state charging    L1 218.0 V x 7.3 A, DP9 1.526 kW
12:04:20  work_state waiting     switch off, still plugged in
12:04:32  work_state available   unplugged
```

218.0 V x 7.3 A is 1.591 kW against 1.526 kW reported, a 4% gap that is
power factor and the 0.1 A rounding of the current. So the watt scale and
the phase masks hold on this base as well.

Three datapoints are missing here and on no other unit: DP13 (Control
Pilot), DP24 (temperature) and DP1, which never appeared even mid-session.
Seven datapoints where the rest of the series reports eight or more.

That makes this the third distinct behaviour for DP1 across the series: a
session counter on the Q37, a lifetime meter on the Q11, absent on the Q74.
DP25 does arrive, carrying the ended session's energy, as it does on the
Q37.

Without DP13 the work state is the only source for whether a vehicle is
plugged in, and the capture above settles its vocabulary: `available` is an
empty socket, `waiting` is a vehicle present but not drawing. The switch
turned on at 12:02:56 and current only started at 12:03:44, when the vehicle
presented - the switch is a permission, not a command.

## The product id does not identify a model

Both the Q37 and the Q22 report `fdfjiphjxtc9qyhd`. The Home Assistant device
registry shows two cloud devices under it, "Q37" and "EV Charger VE 2". So
the id identifies a Tuya product line, not a charger.

Two consequences:

- A second profile cannot be routed automatically by product id. Splitting
  the series into a 16 A and a 32 A profile would mean picking by hand at
  every pairing.
- The `products:` model string must not name a single model. tuya-local
  writes it into the device's model field, and the integration reads that
  field; "Q37 / EV Charger VE" made a Q22 detect as a Q37, costing it two
  phases and half its current. It now reads "EV Charger VE (local)", leaving
  the name the user gave the charger to decide.
- The profile's own `name:` must not name one either. When a charger matches
  on datapoints instead of the product id, tuya-local titles the entry from
  that field, and a Q22 paired this way arrived as "Ampere Point Q11 PRO
  (local)". It now reads "Ampere Point Q Series (local)".

Neither string can identify the charger, so the name the user gives it is
the only reliable signal. A charger left with a generic name falls back to
the Q Series defaults.

For the same reason `models.py` no longer lists `ev charger ve` or that
product id as aliases of the Q37. Only the model number identifies it.

## Current range: union in the profile, narrowed by the model

tuya-local can vary a number's bounds at runtime - `number.py` prefers a
`maximum` dps over the static range, and `device_config.py` lets a mapping or
a condition carry its own range, with `constraint` pointing at another
datapoint. The mechanism is there.

What is missing is a key. Nothing in the LAN response distinguishes a 16 A
unit from a 32 A one: same datapoints, same types, same product id. DP23
reads `V1` on the Q11 and is not reported at all by the Q37 or by the Q22
while idle.

So the profile declares `6..32`, the union, and
`AmperePointCurrentLimitNumber` narrows it to the detected model. The
narrowing takes the minimum of the source bound and the model bound, so it
can only ever reduce: a failed detection offers the series maximum, never an
out-of-range value.

If a future generation does report something distinguishing, the
`maximum`-dps route is the better answer and should replace this.

## Phase count

DP6, DP7 and DP8 exist on every unit because the whole series shares one
datapoint layout, including on the single-phase Q37 and Q74. The load filter
alone is not enough - it hides an unloaded phase, but a residual reading
brings the row back, and the phase does not exist on the hardware at all.

The model's phase count therefore caps both the phase readings and the
raw-datapoint table, which is why a Q37 lists only `l1_*` while a Q22 lists
all three.

## Still open

- Whether a distinguishing datapoint appears while charging on a 32 A unit.
  The Q74 capture did not provide one: it reports fewer datapoints than the
  16 A units, not more.
- The Q22 OTA (`cu111poj2mtikvls`) is a separate product this profile has
  not been measured against.
- `bktb3jskdic1ar2t` is now declared here on the strength of one Q74. The
  other brands on that base were not tested, and the base repo's
  `amperepoint_q_series_evcharger` claims it as well.
