# Wallbox PRIME firmware V11.22: LAN controls

Firmware `(V11.22.20)F2.0.6`, product ID `skkg3zksmiibll2r`, Tuya LAN 3.5. The
app shows it with the new panel ("SmartApp version 2.0.0"); after the update
the wallbox is paired again and registers under this product ID. A customer
unit reports `(V11.22.0)F2.0.3-1.6.83` in the app, so builds of the family
differ.

## Layout

The split layout of `(V7.0.0)F2.0.0`, extended: DP102 keeps `L`, `t`, `p`, `d`,
`e` and adds `c`, `s`, `p3`, `duty`, `tduty`; DP117 keeps two-item phase arrays
and `cp`, and adds `gd`, `duty`, `dpn`; DP154 is boolean. New DPs: 114, 115,
116, 118, 121, 160, 161. DP109 reports state letters (`STATE_C` observed)
and `PAUSE`.
Fixture: `amperepoint/observations/prime-split-v11-22-20-charging-20261102.json`.

## Verified on hardware on 2026-11-03

Vehicle connected (`STATE_C`), immediate mode (`DP151.m = 0`), DP152 = 16.

| Command | Device response | Readback |
| --- | --- | --- |
| DP150 = 10, 12, 16 | `{"150": value}` | DP150 = value; DP151 `c` unchanged |
| DP140 = false | `{"101": 204}` | DP140 false, DP101 204, DP109 `PAUSE` |
| DP140 = true | `{"101": 300}` | DP140 true, DP101 300, DP109 `STATE_C` |

DP101 read 370 while the vehicle drew 3.1 A on 2026-11-02, so start is
confirmed by DP140 together with DP101 not being a pause code (201/204),
not by a fixed DP101 value. A non-preset current (12 A) is accepted.

The same checks passed with the integration code itself (`read_local` and
`write_local` against the wallbox): current 10 A and 16 A, pause and resume,
each confirmed in about 2 s, and 20 A refused before anything was sent.

## Detection

`prime_split_v11` requires a V11.22 firmware string in DP106
(`(V11.22.x)F2.0.y`, any suffix), reported DP140 (bool), integer DP150 and
DP152 in 6..80. A read missing DP102/DP109 is still accepted as the split
layout when DP106 or the product ID identifies V11.22. Reads are repeated, at
most three times, until DP102, DP106 and DP109 are present, because TinyTuya
returns the first message with data, which can be an unsolicited update.

## Limits

The current ceiling stays at 16 A, further limited by DP152; the meaning of
DP152 is not proven. `STATE_A` (no vehicle) was not observed on this firmware.
`(V11.22.0)F2.0.3` was not tested directly; every command is still confirmed
by readback, so a build that behaves differently fails as unconfirmed rather
than silently.
