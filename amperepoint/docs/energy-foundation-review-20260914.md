# Energy foundation — review and verification

Scope: issue #36's agreed **energy foundation first**, not the complete session
history/cost epic. Development version: `0.5.39b2`, based on main / `v0.5.38`.

## Automated checks

- 241 Python unit/regression tests passed (11 added after the blocking review).
- 16 named frontend tests plus existing inline assertions passed.
- Python compilation, JavaScript syntax and Git whitespace checks passed.
- Real Home Assistant **2024.6.0 and 2026.7.2** smoke tests passed in separate containers with
  an internal-only network and temporary database/configuration. No real charger
  was connected to that test.
- The production coordinator (not a generic test coordinator) exposed `kWh`,
  `energy`, `total_increasing`; missing data became unavailable. Immediate reload,
  a real Store write failure, source reset and rejected stale packet preserved
  the meter. Recorder compiled an expected sum of **3 kWh** on both HA versions.
- The real-HA CI matrix covers the declared minimum and our installed HA version.

## Blocking review fixes (b2)

- Removed delayed meter writes. Atomic checkpoints include both total and source
  baseline and are read back from the file before publishing. HA Store can log
  write errors without raising; checking its cached async_load would be unsafe.
- Write failure does not publish an uncommitted increase. The in-memory pending
  delta remains available for a later successful retry, including a source reset.
- Refreshes are serialized. Cancelled writes drain before releasing the lock;
  unloading waits for the same lock and blocks stale/queued refreshes.
- Tests cover a blocked write/crash boundary, write failure and retry, repeated
  cancellation with reload, overlapping refreshes, missing/corrupt readback,
  shutdown deferral, and both coordinator constructor signatures.
- Pass config_entry only when the HA constructor supports it. Do not catch/retry
  arbitrary TypeError. The declared HA 2024.6.0 minimum remains unchanged.

## Local HA verification (initial b1 UI check)

- Backed up the previously installed integration and installed this development
  build without changing charger configuration or the home's Energy settings.
- HA restarted successfully; Q and PRIME each created their own Charging energy
  sensor. PRIME was reachable over native LAN and reported zero power/energy.
- The live dashboard displayed the new development version and the exact selected
  charger's energy entity ID. The Energy setup link opened HA's Energy settings.
- Both new sensors appeared in HA's individual-device energy selector. The test
  dialog was cancelled without saving an Energy configuration.
- Checked the new section at desktop width and a 390 px mobile viewport: the
  entity ID wraps, instructions and link remain readable. Viewport override reset.
- No start/stop, current, schedule or planner commands were issued in this review.

### b2 deployment check

- Backed up b1, verified installed files had no unrelated edits, and deployed b2.
- HA restarted and served HTTP 200; the live footer displayed `v0.5.39b2`.
- The charger was already reporting `local_cannot_connect` before deployment.
  Q and PRIME currently expose unavailable energy sensors; this is not a loaded
  hardware measurement test. No charger settings or Energy configuration changed.

## Issues caught before commit

- Added the new key to full frontend detection, not only the registry mapping;
  otherwise the guide had no entity ID despite the sensor existing in HA.
- Kept a separate last-seen timestamp so duplicate counter polls cannot admit a
  later-arriving sample with an older timestamp.
- Unknown/corrupt saved meter formats fail closed rather than reset statistics.
- PRIME's older status-entity fallback is matched to the actual telemetry provider.
- Explicit mapped energy/power units are validated and normalized.
- Pass the config entry explicitly for newer HA APIs, conditionally for older HA.

## Remaining limitations / release notes

- A tester at zero load is not evidence of nonzero PRIME energy calibration or
  accurate energy-target cutoff. A loaded charging session remains necessary.
- Unobserved resets, sessions during outages, cloud delays and source changes
  can leave incomplete history. Recovering a counter delta cannot determine the
  exact missing hour or historical price.
- Legacy source/session sensors keep their IDs/values, but stop declaring
  statistics state classes. Existing Energy users must choose the new sensor;
  old Recorder statistics are preserved, not migrated or merged.
- No real energy samples were replaced with demonstration values. No statistical
  history was deleted, and no prices or session-history features were added.

See [setup and measurement contract](home-assistant-energy.md).
