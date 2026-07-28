# One profile for the Q Series: what it covers and what decides the rest

`amperepoint_q11_pro_evcharger` is being grown into a single profile for the
whole Q Series. This file records which models it covers, what was measured,
and why the two per-model differences are resolved outside the profile.

The file name still says q11_pro; renaming it would orphan existing
tuya-local entries, so that waits for a deliberate migration.

## Models

Currents and phase counts are from amperepoint.pl. The series names are
kilowatts, not amperes - reading "Q37" as 37 A is what put a 48 A three-phase
figure into the model table originally.

| Model | Power | Current | Phases | Product id | Captured |
| --- | --- | --- | --- | --- | --- |
| Q11 PRO | 11 kW | 6-16 A | 3 | none confirmed | yes |
| Q37 | 3.7 kW | 6-16 A | 1 | `fdfjiphjxtc9qyhd` | yes |
| Q22 | 22 kW | 6-32 A | 3 | `fdfjiphjxtc9qyhd` | yes |
| Q74 | 7.4 kW | 6-32 A | 1 | unknown | no |

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

- Capture a Q74 to confirm its product id and that it answers like the rest.
- Whether a distinguishing datapoint appears while charging on a 32 A unit.
- The Q22 OTA (`cu111poj2mtikvls`) and the unit behind
  `amperepoint_q_series_evcharger` (`bktb3jskdic1ar2t`) are separate products
  that this profile has not been measured against.
