# DP19 charging window

AmperePoint Q11/Q22 product definitions describe DP19 `local_timer` as a
writable raw value used by `work_mode=charge_schedule`.

## Confirmed format

The current test charger reports a two-byte, whole-hour charging window:

| Raw Base64 | Decoded bytes | Meaning |
| --- | --- | --- |
| `AAA=` | `00 00` | `00:00` to `00:00`; exact operational meaning not confirmed |
| `Egc=` | `12 07` | today from `18:00` until `07:00` the following day |

The first byte is the start hour and the second byte is the end hour. A window
whose end hour is earlier than its start hour crosses midnight. Minutes are not
encoded by this payload.

The integration exposes separate Home Assistant `time` entities for the start
and end only when the current DP19 payload:

- decodes to exactly two bytes,
- contains two hours in `0..23`,
- and DP19 is writable in the Tuya function definition.

Both entities accept whole hours only. Updating one boundary preserves the
other byte reported by the charger. When the payload does not match this
validated shape, the card does not attempt to write it and directs the user to
Tuya Smart / Smart Life instead.

## UI behavior

- `charge_now`: no target-energy or schedule field.
- `charge_energy`: show DP17 target energy.
- `charge_schedule`: show the DP19 start and end hours and mark overnight
  windows.

DP33 `mode_set` remains diagnostic-only until its raw format is independently
confirmed. The meaning of equal start and end hours must also be confirmed
before the UI assigns it a special label such as disabled or all-day.
