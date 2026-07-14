# DP19 charging schedule

AmperePoint Q11/Q22 product definitions describe DP19 `local_timer` as a
writable raw value used by `work_mode=charge_schedule`.

## Observed format

The tested Q11 reported two valid values:

| Raw Base64 | Decoded bytes | Meaning |
| --- | --- | --- |
| `AAA=` | `00 00` | `00:00` |
| `Egc=` | `12 07` | `18:07` |

This is consistent with a two-byte `hour, minute` device-local start time. The
integration exposes a Home Assistant `time` entity only when the current DP19
payload:

- decodes to exactly two bytes,
- contains an hour in `0..23`,
- contains a minute in `0..59`,
- and DP19 is writable in the Tuya function definition.

When the payload does not match this validated shape, the card does not attempt
to write it and directs the user to Tuya Smart / Smart Life instead. This avoids
guessing a raw protocol on a different product generation.

## UI behavior

- `charge_now`: no target-energy or schedule field.
- `charge_energy`: show DP17 target energy.
- `charge_schedule`: show the decoded DP19 start time.

DP33 `mode_set` remains diagnostic-only until its raw format is independently
confirmed.
